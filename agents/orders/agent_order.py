"""Agent Order Body V1 — fachlicher Auftragskörper (MO-RIS-AGENT-ORDER-BODY-01).

Abgrenzung (drei Ebenen, bewusst getrennt):

A. **Mays-Orders Order** verwahrt den ``agentOrder`` als Bestandteil der Order.
B. **Transport Envelope V1** (``agents/transport/order_transport.py``) ist der
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
from typing import Any, Dict, Iterable, Optional

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

TOP_LEVEL_KEYS = frozenset({
    "orderType", "agentOrder",
})
BODY_KEYS = frozenset({
    "schemaVersion", "target", "input", "metadata", "processing",
    "resultContract",
})
TARGET_KEYS = frozenset({"agentId", "capability", "agentVersion"})
INPUT_KEYS = frozenset({"schemaVersion", "data"})
METADATA_KEYS = frozenset({
    "source", "partnerApplicationRef", "apiProfileRef", "requestId",
    "idempotencyKey",
})
PROCESSING_KEYS = frozenset({
    "trigger", "parentOrderId", "parentWorkId", "executionProfile",
})
RESULT_CONTRACT_KEYS = frozenset({
    "schemaVersion", "format", "expectedCapability", "delivery",
})


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
    from agents.transport.order_transport import TransportError, assert_secret_free

    try:
        assert_secret_free(value, path)
    except TransportError as exc:
        raise AgentOrderError(exc.code, exc.message) from exc


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_agent_order(body: Any, *,
                         expected_capability: Optional[str] = None,
                         expected_agent: Optional[str] = None) -> Dict[str, Any]:
    """Validate one ``agentOrder`` document and return it normalised.

    Optional blocks receive documented defaults so an older V1 document that
    omits ``metadata``/``processing``/``resultContract`` still validates.
    """
    _require(isinstance(body, dict), "invalid_body",
             "agentOrder must be a JSON object")
    _reject_unknown(body, BODY_KEYS, "agentOrder")

    version = body.get("schemaVersion")
    _require(version in ACCEPTED_AGENT_ORDER_VERSIONS,
             "unsupported_agent_order_version",
             f"agentOrder.schemaVersion {version!r} is not supported "
             f"(expected {AGENT_ORDER_SCHEMA_VERSION})")

    target = body.get("target")
    _require(isinstance(target, dict), "invalid_target",
             "'target' must be an object")
    _reject_unknown(target, TARGET_KEYS, "target")
    agent_id = _assert_str(target.get("agentId"), "target.agentId")
    _require(bool(AGENT_ID_RE.match(agent_id)), "invalid_target",
             "'target.agentId' has unsupported characters")
    capability = _assert_str(target.get("capability"), "target.capability")
    _require(bool(CAPABILITY_RE.match(capability)), "invalid_capability",
             "'target.capability' must look like 'domain.action'")
    agent_version = target.get("agentVersion")
    if agent_version is not None:
        _assert_str(agent_version, "target.agentVersion")

    if expected_agent is not None:
        _require(agent_id == expected_agent, "target_mismatch",
                 f"agentOrder targets {agent_id!r}, expected {expected_agent!r}")
    if expected_capability is not None:
        _require(capability == expected_capability, "capability_mismatch",
                 f"agentOrder capability is {capability!r}, "
                 f"expected {expected_capability!r}")

    raw_input = body.get("input")
    _require(isinstance(raw_input, dict), "invalid_input",
             "'input' must be an object")
    _reject_unknown(raw_input, INPUT_KEYS, "input")
    input_version = raw_input.get("schemaVersion", "1.0")
    _require(input_version in ACCEPTED_AGENT_ORDER_VERSIONS,
             "unsupported_input_version",
             f"input.schemaVersion {input_version!r} is not supported")
    data = raw_input.get("data")
    _require(isinstance(data, dict), "invalid_input",
             "'input.data' must be an object")

    metadata = body.get("metadata") or {}
    _require(isinstance(metadata, dict), "invalid_metadata",
             "'metadata' must be an object")
    _reject_unknown(metadata, METADATA_KEYS, "metadata")
    for key, value in metadata.items():
        if value is not None:
            _assert_str(value, f"metadata.{key}")

    processing = body.get("processing") or {}
    _require(isinstance(processing, dict), "invalid_processing",
             "'processing' must be an object")
    _reject_unknown(processing, PROCESSING_KEYS, "processing")

    result_contract = body.get("resultContract") or {
        "schemaVersion": "1.0",
        "format": "json",
        "expectedCapability": capability,
        "delivery": "order-result",
    }
    _require(isinstance(result_contract, dict), "invalid_result_contract",
             "'resultContract' must be an object")
    _reject_unknown(result_contract, RESULT_CONTRACT_KEYS, "resultContract")
    fmt = result_contract.get("format", "json")
    _require(fmt in SUPPORTED_RESULT_FORMATS, "unsupported_result_format",
             f"resultContract.format {fmt!r} is not supported")
    delivery = result_contract.get("delivery", "order-result")
    _require(delivery in SUPPORTED_DELIVERIES, "unsupported_delivery",
             f"resultContract.delivery {delivery!r} is not supported")
    expected = result_contract.get("expectedCapability", capability)
    _require(expected == capability, "result_contract_mismatch",
             "resultContract.expectedCapability must equal target.capability")

    # One rule for credentials, shared with the transport contract.
    _assert_clean(data, "input.data")
    _assert_clean(metadata, "agentOrder.metadata")

    return {
        "schemaVersion": AGENT_ORDER_SCHEMA_VERSION,
        "target": {
            "agentId": agent_id,
            "capability": capability,
            "agentVersion": agent_version,
        },
        "input": {"schemaVersion": "1.0", "data": data},
        "metadata": {
            "source": metadata.get("source", DEFAULT_SOURCE),
            "partnerApplicationRef": metadata.get("partnerApplicationRef"),
            "apiProfileRef": metadata.get("apiProfileRef"),
            "requestId": metadata.get("requestId"),
            "idempotencyKey": metadata.get("idempotencyKey"),
        },
        "processing": {
            "trigger": processing.get("trigger", DEFAULT_TRIGGER),
            "parentOrderId": processing.get("parentOrderId"),
            "parentWorkId": processing.get("parentWorkId"),
            "executionProfile": processing.get(
                "executionProfile", DEFAULT_EXECUTION_PROFILE),
        },
        "resultContract": {
            "schemaVersion": "1.0",
            "format": fmt,
            "expectedCapability": expected,
            "delivery": delivery,
        },
    }


def validate_order_document(raw: Any, **kwargs) -> Dict[str, Any]:
    """Validate a Mays-Orders document that embeds an ``agentOrder``."""
    _require(isinstance(raw, dict), "invalid_order_document",
             "order body must be an object")
    order_type = raw.get("orderType")
    _require(order_type == ORDER_TYPE_AGENT, "unsupported_order_type",
             f"orderType {order_type!r} is not {ORDER_TYPE_AGENT!r}")
    body = raw.get("agentOrder")
    _require(isinstance(body, dict), "missing_agent_order",
             "orderType 'agent.execution' requires an 'agentOrder' object")
    return validate_agent_order(body, **kwargs)


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


def dispatch_payload(agent_order: Dict[str, Any]) -> Dict[str, Any]:
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


__all__ = [
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
    "validate_result",
]
