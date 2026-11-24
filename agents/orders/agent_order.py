"""Agent Order Body V1 — fachlicher Auftragskörper (MO-RIS-AGENT-ORDER-BODY-01).

Verantwortlich für die fachliche Klassifizierung und Validierung von
Bestellungen im RIS-Kontext. Enthält das kanonische Mapping von
Mays-Orders-Order an RIS-interne Strukturen.

Abgrenzung (drei Ebenen, bewusst getrennt):
A. **Mays-Orders Order** verwahrt den ``agentOrder`` als Bestandteil der Order.
B. **Transport Envelope V1** (`agents/transport/order_transport.py`) ist der
   Zustell-/Korrelationsvertrag.
C. **RIS Agent Ecosystem** (WorkItem, ProcessingEnvelope, Registry, Agent Body)
   führt aus.

Dieses Modul definiert ausschließlich Ebene A als validierbares Dokument und
die Abbildung auf Ebene C. Es enthält keine Zustelllogik, keine Persistenz und
keine Berechtigungsentscheidung.

Identität: ``metadata.partnerApplicationRef`` und ``apiProfileRef`` sind
**Referenzen**, keine Nachweise. Autorisierung entsteht ausschließlich aus dem
serverseitig verifizierten Kontext (``VerifiedContext``).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

#: Fachliche Version des Agent Order Body. Unabhängig von der
#: Transport-Envelope-Version und der Mays-Orders-Modulversion.
AGENT_ORDER_SCHEMA_VERSION = "1.0"
ACCEPTED_AGENT_ORDER_VERSIONS = frozenset({"1.0", "1"})

ORDER_TYPE_AGENT = "agent.execution"

AGENT_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
CAPABILITY_RE = re.compile(r"^[a-z0-9]+\.[a-z0-9_.\-]{1,64}$")

SUPPORTED_RESULT_FORMATS = frozenset({"json"})
SUPPORTED_DELIVERIES = frozenset({"order-result"})

DEFAULT_TRIGGER = "ORDER_CREATED"
DEFAULT_EXECUTION_PROFILE = "default"
DEFAULT_SOURCE = "ris-agent-ecosystem"

#: Maximale Länge von orderDescription in Zeichen.
#: Überschreitung führt zu ValidationError, kein stummes Abschneiden.
MAX_ORDER_DESCRIPTION_LENGTH = 1024

#: Erlaubte Felder im body-Objekt eines agentOrder-Dokuments.
#: orderDescription ist erlaubt und wird auf Längenvalidierung geprüft.
BODY_KEYS = frozenset({
    "schemaVersion", "target", "input", "metadata", "processing",
    "resultContract", "orderDescription",
})
TOP_LEVEL_KEYS = frozenset({"orderType", "agentOrder"})


class AgentOrderError(ValueError):
    """Controlled rejection with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AgentOrderError(code, message)


def _reject_unknown(mapping: Dict[str, Any], allowed: Iterable[str],
                    path: str) -> None:
    unknown = [k for k in mapping if k not in allowed]
    if unknown:
        raise AgentOrderError("unknown_field",
                              f"unknown field '{unknown[0]}' at {path}")


def _assert_str(value: Any, path: str) -> str:
    _require(isinstance(value, str) and value.strip() != "", "invalid_field",
             f"'{path}' must be a non-empty string")
    return value


def _assert_clean(value: Any, path: str) -> None:
    """Secret/size check with one error type for this contract."""
    try:
        from agents.transport.order_transport import TransportError, assert_secret_free
    except ImportError:  # repository layout (tests / agent bundle)
        from agents.transport.order_transport import (
            TransportError,
            assert_secret_free,
        )

    try:
        assert_secret_free(value, path)
    except TransportError as exc:
        raise AgentOrderError(exc.code, exc.message) from exc


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------
def validate_agent_order(body: Any, *,
                         expected_capability: Optional[str] = None,
                         expected_agent: Optional[str] = None) -> Dict[str, Any]:
    """Validate one ``agentOrder`` document and return it normalised.

    Optional blocks receive documented defaults so an older V1 document that
    omits ``metadata``/``processing``/``resultContract`` still validates.

    Returns:
        Das normalisierte agentOrder-Dict.
    """
    _require(isinstance(body, dict), "invalid_body",
             "agentOrder muss ein JSON-Objekt sein")
    _reject_unknown(body, BODY_KEYS, "agentOrder")

    version = body.get("schemaVersion")
    _require(
        version in ACCEPTED_AGENT_ORDER_VERSIONS,
        "unsupported_agent_order_version",
        f"agentOrder.schemaVersion {version!r} ist nicht unterstützt "
        f"(erwartet {AGENT_ORDER_SCHEMA_VERSION})",
    )

    target = body.get("target")
    _require(isinstance(target, dict), "invalid_target",
             "'target' muss ein Objekt sein")
    _require(
        bool(AGENT_ID_RE.match(target.get("agentId"))),
        "invalid_target",
        "'target.agentId' hat unsupportete Zeichen",
    )

    capability = _assert_str(target.get("capability"), "target.capability")
    _require(
        bool(CAPABILITY_RE.match(capability)),
        "invalid_capability",
        "'target.capability' muss wie 'domain.action' aussehen",
    )

    agent_version = target.get("agentVersion")
    if agent_version is not None:
        _require(
            bool(AGENT_ID_RE.match(agent_version)),
            "invalid_agent_version",
            "'target.agentVersion' hat unsupportete Zeichen",
        )

    # Neu: Validierung von orderDescription
    order_description = body.get("orderDescription")
    if order_description is not None:
        _require(
            isinstance(order_description, str),
            "invalid_order_description",
            "orderDescription muss ein String sein",
        )
        if len(order_description) > MAX_ORDER_DESCRIPTION_LENGTH:
            raise AgentOrderError(
                "order_description_too_long",
                f"orderDescription überschreitet die maximal erlaubte Länge "
                f"von {MAX_ORDER_DESCRIPTION_LENGTH} Zeichen. "
                "Kürzen Sie den Payload nicht manuell, sondern reduzieren Sie "
                "die Payload-Größe.",
            )

    return body


def validate_order_document(raw: Any, **kwargs) -> Dict[str, Any]:
    """Validiere ein Mays-Orders-Dokument, das ein ``agentOrder`` enthält."""

    _require(isinstance(raw, dict), "invalid_order_document",
             "order body muss ein Objekt sein")
    order_type = raw.get("orderType")
    _require(
        order_type == ORDER_TYPE_AGENT,
        "unsupported_order_type",
        f"orderType {order_type!r} ist nicht {ORDER_TYPE_AGENT!r}",
    )
    body = raw.get("agentOrder")
    _require(isinstance(body, dict), "missing_agent_order",
             "orderType 'agent.execution' erfordert ein 'agentOrder'-Objekt")
    return validate_agent_order(body, **kwargs)


# ---------------------------------------------------------------------------
# Mapping: agentOrder → orderDescription
# ---------------------------------------------------------------------------
def serialize_agent_order(agent_order: Dict[str, Any]) -> str:
    """Serialisiert ein ``agentOrder``-Dict nach kanonischem JSON.

    Das resultierende JSON wird für die Übermittlung als
    ``orderDescription`` an Mays-Orders übergeben.

    Es ist sicherzustellen, dass der serialisierte Payload die
    maximal erlaubte Länge von ``MAX_ORDER_DESCRIPTION_LENGTH`` Zeichen
    nicht überschreitet. Eine nachträgliche Kürzung unterbindet die
    Integrität der Korrelationskette.

    Args:
        agent_order: Das zu serialisierendeagentOrder-Dict.

    Returns:
        Der kanonische JSON-String.

    Raises:
        AgentOrderError: Wenn der serialized Payload die Längengrenze überschreitet.
    """
    json_str = json.dumps(agent_order, sort_keys=True)
    if len(json_str) > MAX_ORDER_DESCRIPTION_LENGTH:
        raise AgentOrderError(
            "order_description_too_long",
            f"serialisiertes agentOrder überschreitet die maximal erlaubte "
            f"Länge von {MAX_ORDER_DESCRIPTION_LENGTH} Zeichen. "
            "Reduzieren Sie die Payload-Größe, schneiden Sie nicht einfach "
            "am Ende ab.",
        )
    return json_str


# ---------------------------------------------------------------------------
# Mapping: Mays-Orders Order → RIS-interne Strukturen
# ---------------------------------------------------------------------------
def map_mo_order_to_ris(
    mo_order: Dict[str, Any],
) -> Dict[str, Any]:
    """Mappt ein Mays-Orders-Order-Dict an die RIS-interne Darstellung.

    Folgende Felder werden übernommen:
    - ``orderType``: Wird auf ``agent.execution`` gesetzt.
    - ``items[0].sku``: Wird als ``service`` in ``agentOrder`` übernommen.
    - ``items[0].quantity`` und ``items[0].unitPrice``: Werden im
      ``agentOrder``-Kontext verarbeitet.
    - ``orderDescription``: Wird kanonischserialisiert aus dem
      ``agentOrder``-Objekt erzeugt.

    V1: Es wird immer genau eine ausführbare Agentenposition pro Bestellung
    berücksichtigt. Weitere Positionen werden stillschweigend ignoriert.

    Returns:
        Ein Dict mit den für RIS relevanten Felder.
    """
    # 1. Basisdaten extrahieren
    order_type = ORDER_TYPE_AGENT
    items = mo_order.get("items", [])
    first_item = items[0] if items else {}

    # 2. SKU zu Service mappen (Standalone-Fallback: bekannte SKUs,
    #  sonst 'generic'. Die Mapping-Tabelle kann im Modul erweitert werden.)
    service = "generic"
    sku = first_item.get("sku", "")
    if sku:
        # Einfaches festes Mapping für gängliche SKUs.
        # Erweitern Sie dieses Dict bei neuen SKUs.
        _SKU_MAP = {
            "ATS": "ats",
            "JobSearch": "jobsearch",
            "Health": "health",
        }
        service = _SKU_MAP.get(sku, "generic")

    # 3. agentOrder zusammenbauen
    agent_order = {
        "service": service,
        "capability": mo_order.get("capability", "default"),
        "inputData": mo_order.get("inputData", {}),
    }

    # 4. Kanonisch nach JSON serialisieren (für orderDescription)
    order_description = serialize_agent_order(agent_order)

    return {
        "orderType": order_type,
        "agentOrder": agent_order,
        "orderDescription": order_description,
    }


# ---------------------------------------------------------------------------
# Dispatch-Payload
# ---------------------------------------------------------------------------
def dispatch_payload(agent_order: Dict[str, Any]) -> Dict[str, Any]:
    """Erstellt den Payload für die Dispatch-Übermittlung.

    Mappt ein validiertes ``agentOrder`` auf den internele
    Dispatch-Format.

    Returns:
        Ein Dict mit den für die Dispatch-Übermittlung relevanten Felder.
    """
    return {
        "orderType": ORDER_TYPE_AGENT,
        "agentOrder": agent_order,
    }


# ---------------------------------------------------------------------------
# Versioning (A02)
# ---------------------------------------------------------------------------
def version_matrix() -> Dict[str, Any]:
    """The three independent versions. They never imply each other."""
    from agents.transport.order_transport import SCHEMA_VERSION as TRANSPORT

    return {
        "ordersModule": {
            "version": None,
            "note": "external (Mays-Orders); not changed by this contract",
        },
        "transportEnvelope": {
            "version": TRANSPORT,
            "accepted": ["1", "1.0"],
        },
        "agentOrder": {
            "version": AGENT_ORDER_SCHEMA_VERSION,
            "accepted": sorted(ACCEPTED_AGENT_ORDER_VERSIONS),
        },
    }


def fingerprint(agent_order: Dict[str, Any]) -> str:
    """Immutability marker for already-accepted execution parameters.

    Covers schema version, target and input only: those are the parameters a
    running order must not silently change. Metadata/correlation stays outside
    so a retry with a new requestId is not a different execution.
    """
    canonical = json.dumps(
        {
            "schemaVersion": agent_order["schemaVersion"],
            "target": agent_order["target"],
            "input": agent_order["input"],
        },
        sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Mapping to the existing RIS ecosystem (A03)
# ---------------------------------------------------------------------------
def to_work_item(agent_order: Dict[str, Any], *,
                 verified_context: Any,
                 order_id: str,
                 correlation_id: str,
                 idempotency_key: Optional[str] = None,
                 work_id: Optional[str] = None,
                 agent_version: Optional[str] = None,
                 now: Optional[datetime] = None) -> Dict[str, Any]:
    """Map ``agentOrder`` onto the canonical RIS work item.

    Identity comes from ``verified_context`` only. The metadata references are
    checked for agreement when present, but never used as authorization.
    """
    from agents.runtime.work_item import build_work_item

    if not order_id or not order_id.startswith("ord_"):
        raise AgentOrderError("invalid_order_id",
                              "'orderId' must match 'ord_<alphanumeric>'")

    metadata = agent_order.get("metadata") or {}
    for ref_key, verified in (
        ("partnerApplicationRef", verified_context.partner_application_id),
        ("apiProfileRef", verified_context.api_profile_id),
    ):
        claimed = metadata.get(ref_key)
        if claimed is not None and str(claimed) != str(verified):
            raise AgentOrderError(
                "identity_mismatch",
                f"metadata.{ref_key} disagrees with the verified context")

    target = agent_order["target"]
    return build_work_item(
        agent_id=target["agentId"],
        capability=target["capability"],
        payload=agent_order["input"]["data"],
        tenant_id=verified_context.tenant_id,
        user_id=verified_context.owner_id,
        requested_by=verified_context.actor(),
        agent_version=agent_version or target.get("agentVersion"),
        idempotency_key=idempotency_key or metadata.get("idempotencyKey"),
        request_id=metadata.get("requestId") or correlation_id,
        work_id=work_id,
        now=now,
        api_profile_id=verified_context.api_profile_id,
        partner_application_id=verified_context.partner_application_id,
        issuer=verified_context.issuer,
        extra={
            "orderId": order_id,
            "correlationId": correlation_id,
            "agentOrderVersion": agent_order["schemaVersion"],
            "agentOrderFingerprint": fingerprint(agent_order),
            "parentWorkId": (agent_order.get("processing") or {}).get(
                "parentWorkId"),
        },
    )


def dispatch_payload_v2(agent_order: Dict[str, Any]) -> Dict[str, Any]:
    """The only part that crosses the transport boundary as payload."""
    return agent_order["input"]["data"]


def validate_result(agent_order: Dict[str, Any],
                    result: Any) -> Dict[str, Any]:
    """Check a work result against the accepted ``resultContract``."""
    contract = agent_order["resultContract"]
    _require(isinstance(result, dict), "invalid_result",
             "agent result must be an object")
    _assert_clean(result, "result")
    if contract["format"] == "json":
        _require("sum" in result or "data" in result, "result_shape",
                 "json result carries neither 'sum' nor 'data'")
    return result


# ---------------------------------------------------------------------------
# Öffentliche_API
# ---------------------------------------------------------------------------
__all__ = [
    "AGENT_ORDER_SCHEMA_VERSION",
    "ACCEPTED_AGENT_ORDER_VERSIONS",
    "ORDER_TYPE_AGENT",
    "AGENT_ID_RE",
    "CAPABILITY_RE",
    "SUPPORTED_RESULT_FORMATS",
    "SUPPORTED_DELIVERIES",
    "DEFAULT_TRIGGER",
    "DEFAULT_EXECUTION_PROFILE",
    "DEFAULT_SOURCE",
    "TOP_LEVEL_KEYS",
    "BODY_KEYS",
    "AGENT_ORDER_SCHEMA_VERSION",
    "ACCEPTED_AGENT_ORDER_VERSIONS",
    "ORDER_TYPE_AGENT",
    "AgentOrderError",
    "validate_agent_order",
    "validate_order_document",
    "version_matrix",
    "fingerprint",
    "to_work_item",
    "dispatch_payload",
    "dispatch_payload_v2",
    "validate_result",
    "map_mo_order_to_ris",
    "serialize_agent_order",
    "MAX_ORDER_DESCRIPTION_LENGTH",
]