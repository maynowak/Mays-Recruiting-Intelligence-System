"""
RIS Agent Order Body V1 — fachlicher Auftragskörper (MO-RIS-AGENT-ORDER-BODY-01)

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

Hinweis zur 1.024-Zeichen-Grenze: Das Feld ``orderDescription`` in Mays-Orders
ist auf 1.024 Zeichen begrenzt. Die-serialisierung von ``agentOrder`` nach
``orderDescription`` darf die Zeichengrenze nicht überschreiten. Es ist die
Pflicht des Aufrufs, sicherzustellen, dass der serialisierte Payload die
Grenze einhält. Eine nachträgliche Kürzung unterbindet die Integrität des
Korrelationsids.

Fachliche Version: ``1.0``. Akzeptierte Versionen: ``1.0``, ``1``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from agents.orders.agent_body import TOP_LEVEL_KEYS, BODY_KEYS
from agents.orders.agent_order import (
    AGENT_ORDER_SCHEMA_VERSION,
    ACCEPTED_AGENT_ORDER_VERSIONS,
    ORDER_TYPE_AGENT,
    AGENT_ID_RE,
    CAPABILITY_RE,
    SUPPORTED_RESULT_FORMATS,
    SUPPORTED_DELIVERIES,
    DEFAULT_TRIGGER,
    DEFAULT_EXECUTION_PROFILE,
    DEFAULT_SOURCE,
)
from agents.orders.errors import AgentOrderError
from agents.transport.order_transport import SCHEMA_VERSION as TRANSPORT

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

TOP_LEVEL_KEYS = frozenset({"orderType", "agentOrder"})
BODY_KEYS = frozenset({
    "schemaVersion", "target", "input", "metadata", "processing",
    "resultContract",
})

#: Maximale Länge von orderDescription in Zeichen
MAX_ORDER_DESCRIPTION_LENGTH = 1024


def _reject_unknown(obj: Dict[str, Any], allowed: frozenset, path: str) -> None:
    """Warnt, wenn Unknown-Schlüssel im gegebenen Dict gefunden werden."""
    for key in obj:
        if key not in allowed:
            raise AgentOrderError(
                "unknown_field",
                f"unbekannter Feldname '{key}' in {path}",
            )


def _assert_str(value: Optional[str], path: str) -> str:
    """Sichert ab, dass ein Wert ein String ist, wirft bei Nones."""
    if value is None:
        raise AgentOrderError("missing_field", f"{path} darf nicht None sein")
    if not isinstance(value, str):
        raise AgentOrderError("invalid_type", f"{path} muss ein String sein")
    return value


def _assert_bool(value: Optional[bool], path: str) -> bool:
    """Sichert ab, dass ein Wert ein Boolean ist."""
    if value is None:
        raise AgentOrderError("missing_field", f"{path} darf nicht None sein")
    if not isinstance(value, bool):
        raise AgentOrderError("invalid_type", f"{path} muss ein Boolean sein")
    return value


def fingerprint(agent_order: Dict[str, Any]) -> str:
    """Ermittelt einen Fingerprint für einen agentOrder-Body."""
    return hashlib.sha256(
        json.dumps(agent_order, sort_keys=True).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------

def validate_agent_order(
    body: Any,
    *,
    expected_capability: Optional[str] = None,
    expected_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validiert ein ``agentOrder``-Dokument und gibt es normalisiert zurück.

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
    """
    Serialisiert ein ``agentOrder``-Dict nach kanonischem JSON.

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
    """
    Mappt ein Mays-Orders-Order-Dict an die RIS-interne Darstellung.

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

    # 2. SKU zu Service mappen
    service = "generic"
    sku = first_item.get("sku", "")
    if sku:
        # Erlaubte SKUs gemäß Mays-Orders-Konvention
        from agents.orders.agent_order import SKU_SERVICE_MAP as _SKU_MAP
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
    )


# ---------------------------------------------------------------------------
# Dispatch-Payload
# ---------------------------------------------------------------------------

def dispatch_payload(agent_order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Erstellt den Payload für die Dispatch-Übermittlung.

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
    "dispatch_payload",
    "map_mo_order_to_ris",
    "serialize_agent_order",
    "MAX_ORDER_DESCRIPTION_LENGTH",
]