"""Generic Order Transport Envelope V1.

RIS-AGENT-GENERIC-ORDER-TRANSPORT-01, T02–T05.

Boundary
--------
This module defines a *transport* contract only. It owns correlation, message
typing and validation. It does NOT own:

- the order lifecycle (Mays-Orders),
- the work item schema (``agents/runtime/work_item.py``),
- the processing envelope (``agents/ecosystem/event_hook.py``),
- agent execution (the existing Agent Body).

Design rules enforced here
--------------------------
1. Versioned: only ``schemaVersion`` 1 (``"1"`` / ``"1.0"``) is accepted.
2. Strict: unknown top-level or nested keys are rejected, so a typo cannot be
   silently ignored.
3. Typed: unsupported message types are rejected; merely *reserved* types are
   rejected with a distinct code so callers can tell the two apart.
4. Secret-free: payloads are scanned for credential-shaped keys and values.
5. Identity is resolved server-side. The envelope carries a *reference*
   (``identity.contextRef``) plus non-authoritative claims; a work item is only
   built from a ``VerifiedContext`` supplied by the server. Claims that
   disagree with the verified context are rejected.
6. Sender/recipient direction is type-bound: ORDER_DISPATCH goes
   orders -> ris, every result type goes ris -> orders.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

SCHEMA_VERSION = "1"
ACCEPTED_SCHEMA_VERSIONS = frozenset({"1", "1.0"})

ORDER_DISPATCH = "ORDER_DISPATCH"
ORDER_RESULT = "ORDER_RESULT"
ORDER_FAILED = "ORDER_FAILED"
ORDER_CANCELLED = "ORDER_CANCELLED"
ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED"

#: Implemented and validated in V1.
SUPPORTED_MESSAGE_TYPES = frozenset({
    ORDER_DISPATCH,
    ORDER_RESULT,
    ORDER_FAILED,
    ORDER_CANCELLED,
    ORDER_STATUS_CHANGED,
})

#: Recognised by the contract, deliberately NOT implemented in V1. They are
#: rejected with ``reserved_message_type`` rather than treated as unknown.
RESERVED_MESSAGE_TYPES = frozenset({"ORDER_PROGRESS", "ORDER_ACK"})

SYSTEM_ORDERS = "mays-orders"
SYSTEM_RIS = "ris"

#: Message type -> (sender system, recipient system).
DIRECTION = {
    ORDER_DISPATCH: (SYSTEM_ORDERS, SYSTEM_RIS),
    ORDER_RESULT: (SYSTEM_RIS, SYSTEM_ORDERS),
    ORDER_FAILED: (SYSTEM_RIS, SYSTEM_ORDERS),
    ORDER_CANCELLED: (SYSTEM_RIS, SYSTEM_ORDERS),
    ORDER_STATUS_CHANGED: (SYSTEM_RIS, SYSTEM_ORDERS),
}

RESULT_TYPES = frozenset({ORDER_RESULT, ORDER_FAILED, ORDER_CANCELLED,
                          ORDER_STATUS_CHANGED})

TOP_LEVEL_KEYS = frozenset({
    "schemaVersion", "messageId", "messageType", "orderId", "correlationId",
    "idempotencyKey", "sender", "recipient", "identity", "parentOrderId",
    "parentWorkId", "payload", "payloadRef", "createdAt", "execution",
})

REQUIRED_KEYS = frozenset({
    "schemaVersion", "messageId", "messageType", "orderId", "correlationId",
    "idempotencyKey", "sender", "recipient", "identity", "createdAt",
})

ORDER_ID_RE = re.compile(r"^ord_[A-Za-z0-9]+$")
MESSAGE_ID_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,128}$")

MAX_PAYLOAD_BYTES = 16 * 1024

#: Keys that must never appear in a transport payload.
FORBIDDEN_KEY_PARTS = (
    "secret", "apikey", "api_key", "password", "passwd", "credential",
    "authorization", "bearer", "token", "jwt", "privatekey", "private_key",
)
#: Value prefixes that indicate a leaked RIS credential or bearer token.
FORBIDDEN_VALUE_PREFIXES = ("ris_", "Bearer ", "bearer ")


class TransportError(ValueError):
    """Controlled transport rejection with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class VerifiedContext:
    """Server-resolved identity. Never built from the SQS message alone."""

    context_ref: str
    tenant_id: str
    owner_id: str
    api_profile_id: str
    partner_application_id: str
    issuer: str
    actor_id: Optional[str] = None

    def actor(self) -> str:
        return self.actor_id or self.owner_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise TransportError(code, message)


def _is_plain_object(value: Any) -> bool:
    return isinstance(value, dict)


def _reject_unknown(mapping: Dict[str, Any], allowed: Iterable[str],
                    path: str, code: str = "unknown_field") -> None:
    unknown = [k for k in mapping if k not in allowed]
    if unknown:
        raise TransportError(code, f"unknown field '{unknown[0]}' at {path}")


def _assert_str(value: Any, path: str, code: str = "invalid_field") -> str:
    _require(isinstance(value, str) and value.strip() != "", code,
             f"'{path}' must be a non-empty string")
    return value


def _assert_iso(value: Any, path: str) -> str:
    _assert_str(value, path)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TransportError("invalid_timestamp",
                             f"'{path}' must be an ISO-8601 timestamp") from exc
    return value


def _scan_for_secrets(value: Any, path: str = "payload") -> None:
    """Reject credential-shaped keys and values anywhere in a payload."""
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                raise TransportError(
                    "secret_in_transport",
                    f"forbidden credential-shaped field at {path}.{key}")
            _scan_for_secrets(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_for_secrets(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if value.startswith(FORBIDDEN_VALUE_PREFIXES):
            raise TransportError(
                "secret_in_transport",
                f"credential-shaped value at {path}")


def _check_payload_size(payload: Any, path: str) -> None:
    try:
        encoded = json.dumps(payload, default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TransportError("invalid_payload",
                             f"'{path}' must be JSON-serializable") from exc
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise TransportError(
            "payload_too_large",
            f"'{path}' exceeds {MAX_PAYLOAD_BYTES} bytes")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_envelope(raw: Any,
                      expected_type: Optional[str] = None) -> Dict[str, Any]:
    """Validate and return a normalised V1 envelope.

    Raises:
        TransportError: with a stable ``code`` for every rejection.
    """
    _require(_is_plain_object(raw), "invalid_envelope",
             "envelope must be a JSON object")
    _reject_unknown(raw, TOP_LEVEL_KEYS, "envelope")

    missing = [key for key in REQUIRED_KEYS if key not in raw]
    _require(not missing, "missing_field",
             f"missing required field '{missing[0]}'" if missing else "")

    version = raw["schemaVersion"]
    _require(version in ACCEPTED_SCHEMA_VERSIONS, "unsupported_schema_version",
             f"schemaVersion {version!r} is not supported (expected {SCHEMA_VERSION})")

    message_type = raw["messageType"]
    if message_type in RESERVED_MESSAGE_TYPES:
        raise TransportError(
            "reserved_message_type",
            f"messageType {message_type!r} is reserved and not implemented in V1")
    _require(message_type in SUPPORTED_MESSAGE_TYPES, "unknown_message_type",
             f"unknown messageType {message_type!r}")
    if expected_type is not None:
        _require(message_type == expected_type, "unexpected_message_type",
                 f"expected {expected_type!r}, got {message_type!r}")

    _assert_str(raw["messageId"], "messageId")
    _require(bool(MESSAGE_ID_RE.match(raw["messageId"])), "invalid_message_id",
             "'messageId' contains unsupported characters")

    _assert_str(raw["orderId"], "orderId")
    _require(bool(ORDER_ID_RE.match(raw["orderId"])), "invalid_order_id",
             "'orderId' must match 'ord_<alphanumeric>'")

    _assert_str(raw["correlationId"], "correlationId")
    _assert_str(raw["idempotencyKey"], "idempotencyKey")
    _assert_iso(raw["createdAt"], "createdAt")

    sender = raw["sender"]
    _require(_is_plain_object(sender), "invalid_sender", "'sender' must be an object")
    _reject_unknown(sender, {"system", "reference"}, "sender")
    _assert_str(sender.get("system"), "sender.system")

    recipient = raw["recipient"]
    _require(_is_plain_object(recipient), "invalid_recipient",
             "'recipient' must be an object")
    _reject_unknown(recipient, {"system", "agentId", "capability"}, "recipient")
    _assert_str(recipient.get("system"), "recipient.system")

    identity = raw["identity"]
    _require(_is_plain_object(identity), "invalid_identity",
             "'identity' must be an object")
    _reject_unknown(identity,
                    {"contextRef", "tenantId", "apiProfileId",
                     "partnerApplicationId", "issuer"}, "identity")
    _assert_str(identity.get("contextRef"), "identity.contextRef",
                code="missing_verified_context")

    # Direction is bound to the message type, so a forged recipient is caught
    # even when the rest of the envelope is well formed.
    expected_sender, expected_recipient = DIRECTION[message_type]
    _require(sender["system"] == expected_sender, "wrong_sender_system",
             f"{message_type} must be sent by {expected_sender}")
    _require(recipient["system"] == expected_recipient, "wrong_recipient_system",
             f"{message_type} must be addressed to {expected_recipient}")

    has_payload = "payload" in raw and raw["payload"] is not None
    has_ref = "payloadRef" in raw and raw["payloadRef"] is not None
    _require(has_payload != has_ref, "invalid_payload_reference",
             "exactly one of 'payload' or 'payloadRef' is required")
    if has_payload:
        _require(_is_plain_object(raw["payload"]), "invalid_payload",
                 "'payload' must be an object")
        _check_payload_size(raw["payload"], "payload")
        _scan_for_secrets(raw["payload"])
    else:
        _assert_str(raw["payloadRef"], "payloadRef", code="invalid_payload")

    if message_type == ORDER_DISPATCH:
        _assert_str(recipient.get("agentId"), "recipient.agentId")
        agent_id = recipient["agentId"]
        _require(re.match(r"^[A-Za-z0-9_.\-]{1,64}$", agent_id) is not None,
                 "invalid_recipient", "'recipient.agentId' has unsupported characters")
        # A05-1: a dispatch MAY carry a pre-bound workId. It is optional and
        # backward compatible: envelopes without it keep their previous
        # behaviour (the receiver generates the id).
        execution = raw.get("execution")
        if execution is not None:
            _require(_is_plain_object(execution), "missing_execution",
                     "'execution' must be an object")
            _reject_unknown(execution, {"workId", "attempt", "executionId"},
                            "execution")
            _assert_str(execution.get("workId"), "execution.workId")

    if message_type in RESULT_TYPES:
        execution = raw.get("execution")
        _require(_is_plain_object(execution), "missing_execution",
                 f"{message_type} requires an 'execution' object")
        _reject_unknown(execution, {"workId", "attempt", "executionId"}, "execution")
        _assert_str(execution.get("workId"), "execution.workId")
        attempt = execution.get("attempt", 1)
        _require(isinstance(attempt, int) and not isinstance(attempt, bool)
                 and attempt >= 1, "invalid_attempt",
                 "'execution.attempt' must be an integer >= 1")

    if "parentOrderId" in raw and raw["parentOrderId"] is not None:
        _assert_str(raw["parentOrderId"], "parentOrderId")
        _require(bool(ORDER_ID_RE.match(raw["parentOrderId"])),
                 "invalid_parent_order", "'parentOrderId' must match 'ord_<alphanumeric>'")
    if "parentWorkId" in raw and raw["parentWorkId"] is not None:
        _assert_str(raw["parentWorkId"], "parentWorkId")

    return {key: raw[key] for key in TOP_LEVEL_KEYS if key in raw}


# ---------------------------------------------------------------------------
# Mapping: envelope <-> work item
# ---------------------------------------------------------------------------
def dispatch_to_work_item(envelope: Dict[str, Any],
                          context: VerifiedContext,
                          *,
                          agent_version: Optional[str] = None,
                          now: Optional[datetime] = None,
                          work_id: Optional[str] = None) -> Dict[str, Any]:
    """Map a validated ORDER_DISPATCH onto the canonical RIS work item.

    Identity comes from ``context`` only. Envelope identity claims are treated
    as assertions that must *agree* with the verified context; they are never
    the source of truth.
    """
    from agents.runtime.work_item import build_work_item

    _require(envelope.get("messageType") == ORDER_DISPATCH,
             "unexpected_message_type", "dispatch_to_work_item needs ORDER_DISPATCH")

    identity = envelope.get("identity") or {}
    _require(identity.get("contextRef") == context.context_ref,
             "missing_verified_context",
             "identity.contextRef does not match the verified context")

    for claim_key, verified_value in (
        ("tenantId", context.tenant_id),
        ("apiProfileId", context.api_profile_id),
        ("partnerApplicationId", context.partner_application_id),
        ("issuer", context.issuer),
    ):
        claimed = identity.get(claim_key)
        if claimed is not None and str(claimed) != str(verified_value):
            raise TransportError(
                "identity_mismatch",
                f"identity.{claim_key} disagrees with the verified context")

    recipient = envelope["recipient"]
    payload = envelope.get("payload")
    _require(payload is not None, "invalid_payload",
             "ORDER_DISPATCH requires an inline payload")

    # A05-1: prefer the workId the sender bound to its order. The idempotency
    # key stays the dedup anchor either way; a missing pre-bound id keeps the
    # old behaviour of generating one here.
    bound_work_id = (envelope.get("execution") or {}).get("workId")
    effective_work_id = work_id or bound_work_id

    return build_work_item(
        agent_id=recipient["agentId"],
        capability=recipient.get("capability"),
        payload=payload,
        tenant_id=context.tenant_id,
        user_id=context.owner_id,
        requested_by=context.actor(),
        agent_version=agent_version,
        idempotency_key=envelope["idempotencyKey"],
        request_id=envelope["correlationId"],
        work_id=effective_work_id,
        now=now,
        api_profile_id=context.api_profile_id,
        partner_application_id=context.partner_application_id,
        issuer=context.issuer,
        extra={
            "orderId": envelope["orderId"],
            "correlationId": envelope["correlationId"],
            "senderRef": (envelope.get("sender") or {}).get("reference", ""),
            "transportMessageId": envelope["messageId"],
            "parentWorkId": envelope.get("parentWorkId"),
        },
    )


def _result_payload(work_result: Any) -> Dict[str, Any]:
    """Keep the result small, JSON-safe and secret-free."""
    _require(_is_plain_object(work_result), "invalid_result",
             "agent result must be an object")
    _check_payload_size(work_result, "result")
    _scan_for_secrets(work_result, "result")
    return work_result


def result_from_work_item(envelope: Dict[str, Any],
                          work_row: Dict[str, Any],
                          *,
                          message_type: str = ORDER_RESULT,
                          now: Optional[datetime] = None) -> Dict[str, Any]:
    """Map a completed work item onto ORDER_RESULT (or a result-family type).

    Guarantees:
    - the order id comes from the dispatch envelope, never from the work row,
    - completion requires ``status == COMPLETED`` and a present result,
    - the idempotency key is stable per (order, work, type), so a duplicate
      delivery produces the same key and cannot double-complete,
    - a stale attempt (``attempt < attempt_no``) is rejected.
    """
    _require(envelope.get("messageType") == ORDER_DISPATCH,
             "unexpected_message_type", "result mapping needs the original dispatch")
    _require(message_type in RESULT_TYPES, "unknown_message_type",
             f"unsupported result type {message_type!r}")
    _require(_is_plain_object(work_row), "invalid_work_row",
             "work row must be an object")

    work_id = work_row.get("workId")
    _assert_str(work_id, "workId", code="missing_work_id")

    status = work_row.get("status")
    attempt_no = int(work_row.get("attempt_no") or work_row.get("attempt") or 1)

    if message_type == ORDER_RESULT:
        _require(status == "COMPLETED", "result_not_completed",
                 f"work item is {status!r}, not COMPLETED")
        payload = _result_payload(work_row.get("result"))
    elif message_type == ORDER_FAILED:
        _require(status == "FAILED", "result_not_failed",
                 f"work item is {status!r}, not FAILED")
        error = work_row.get("error") or {"message": "agent failed"}
        payload = {"error": _result_payload(error)}
    elif message_type == ORDER_CANCELLED:
        payload = {"cancelled": True}
    else:  # ORDER_STATUS_CHANGED
        payload = _result_payload({"status": status})

    stamp = (now or datetime.now(timezone.utc)).isoformat()

    return {
        "schemaVersion": SCHEMA_VERSION,
        "messageId": f"msg_{work_id}_{message_type.lower()}",
        "messageType": message_type,
        "orderId": envelope["orderId"],
        "correlationId": envelope["correlationId"],
        "idempotencyKey": f"{envelope['orderId']}:{work_id}:{message_type}",
        "sender": {"system": SYSTEM_RIS, "reference": "ris-runtime"},
        "recipient": {"system": SYSTEM_ORDERS},
        "identity": {
            "contextRef": (envelope.get("identity") or {}).get("contextRef", ""),
            "tenantId": (envelope.get("identity") or {}).get("tenantId"),
            "apiProfileId": (envelope.get("identity") or {}).get("apiProfileId"),
            "partnerApplicationId": (envelope.get("identity") or {}).get(
                "partnerApplicationId"),
            "issuer": (envelope.get("identity") or {}).get("issuer"),
        },
        "parentOrderId": envelope.get("parentOrderId"),
        "parentWorkId": envelope.get("parentWorkId"),
        "payload": payload,
        "createdAt": stamp,
        "execution": {"workId": work_id, "attempt": attempt_no},
    }


def is_stale_attempt(work_row: Dict[str, Any], attempt: Any) -> bool:
    """True when an inbound attempt reference is older than the stored one."""
    if not isinstance(attempt, int) or isinstance(attempt, bool):
        return True
    stored = int(work_row.get("attempt_no") or work_row.get("attempt") or 1)
    return attempt < stored


def accepted_message_types() -> Tuple[str, ...]:
    """Implemented types only (reserved types are intentionally excluded)."""
    return tuple(sorted(SUPPORTED_MESSAGE_TYPES))


def assert_secret_free(value: Any, path: str = "value") -> None:
    """Public wrapper: reject credential-shaped content before transport.

    Shared with the Agent Order Body so both contracts use one rule instead of
    two slightly different ones.
    """
    _scan_for_secrets(value, path)
    _check_payload_size(value, path)


__all__ = [
    "SCHEMA_VERSION",
    "ACCEPTED_SCHEMA_VERSIONS",
    "ORDER_DISPATCH",
    "ORDER_RESULT",
    "ORDER_FAILED",
    "ORDER_CANCELLED",
    "ORDER_STATUS_CHANGED",
    "SUPPORTED_MESSAGE_TYPES",
    "RESERVED_MESSAGE_TYPES",
    "RESULT_TYPES",
    "SYSTEM_ORDERS",
    "SYSTEM_RIS",
    "TransportError",
    "VerifiedContext",
    "validate_envelope",
    "dispatch_to_work_item",
    "result_from_work_item",
    "is_stale_attempt",
    "accepted_message_types",
    "assert_secret_free",
]
