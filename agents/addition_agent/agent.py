"""Addition Agent — minimal deterministic ``math.add`` domain agent.

Scope (RIS-MO-ADDITION-AGENT-E2E-01, G03):

- performs exactly one mathematical operation: addition of two operands;
- owns no user administration, no credential store and no queue;
- returns a JSON-compatible, deterministic payload;
- is registered in the existing Runtime registry and Agent Body.

The agent deliberately carries no infrastructure knowledge: no DynamoDB, no
SQS, no HTTP. Callers reach it through the existing Agent Run Body only.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from agents.base import AgentBase

logger = logging.getLogger(__name__)

ADDITION_AGENT_ID = "addition_agent"
ADDITION_CAPABILITY = "math.add"
ADDITION_WORK_TYPE = f"agent_{ADDITION_AGENT_ID}"
ADDITION_AGENT_VERSION = "1.0.0"


class AdditionInputError(ValueError):
    """Raised when the addition input does not satisfy the contract."""


def _as_decimal(value: Any, field: str) -> Decimal:
    """Convert one operand to an exact Decimal or raise AdditionInputError.

    Accepted: ``int`` and finite ``float``. Rejected: ``bool`` (a subclass of
    int in Python but not a number here), ``None``, strings, and the
    non-finite floats ``inf``/``nan`` — none of which is a valid mathematical
    operand and all of which would break the JSON result contract.
    """
    if isinstance(value, bool) or value is None:
        raise AdditionInputError(f"Field '{field}' must be a finite number")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AdditionInputError(f"Field '{field}' must be a finite number")
        return Decimal(str(value))
    raise AdditionInputError(f"Field '{field}' must be a finite number")


def _json_number(value: Decimal) -> Any:
    """Render a Decimal as an int or a finite float (never Decimal/NaN/inf)."""
    if value == value.to_integral_value():
        return int(value)
    rendered = float(value)
    if not math.isfinite(rendered):
        raise AdditionInputError("Result is not representable as a finite number")
    return rendered


def add_operands(left: Any, right: Any) -> Dict[str, Any]:
    """Pure, deterministic addition: returns ``{left, right, sum}``."""
    left_dec = _as_decimal(left, "left")
    right_dec = _as_decimal(right, "right")
    try:
        total = left_dec + right_dec
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise AdditionInputError("Operands could not be added") from exc
    return {
        "left": _json_number(left_dec),
        "right": _json_number(right_dec),
        "sum": _json_number(total),
    }


class AdditionAgent(AgentBase):
    """Agent Base implementation of the ``math.add`` capability."""

    CAPABILITY_ADD = ADDITION_CAPABILITY

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = ADDITION_AGENT_ID
        self.version = ADDITION_AGENT_VERSION

    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Process one work item; unknown capabilities fail closed."""
        if not isinstance(work_item, dict):
            return self._error("Work item must be an object", "ValidationError")

        capability = work_item.get("capability") or self.CAPABILITY_ADD
        if capability != self.CAPABILITY_ADD:
            return self._error(
                f"Unknown capability: {capability}", "ValidationError"
            )

        payload = work_item.get("payload")
        if not isinstance(payload, dict):
            return self._error(
                "Field 'payload' must be an object", "ValidationError"
            )
        operands = self._operand_payload(payload)

        work_id = work_item.get("workId")
        logger.info(
            "addition capability processing: workId=%s agentId=%s",
            work_id,
            work_item.get("agentId"),
        )

        try:
            data = add_operands(operands.get("left"), operands.get("right"))
        except AdditionInputError as exc:
            return self._error(str(exc), "ValidationError")

        return {
            "success": True,
            "data": data,
            "metrics": {
                "workId": work_id,
                "agentId": work_item.get("agentId") or ADDITION_AGENT_ID,
                "agentVersion": self.version,
                "capability": self.CAPABILITY_ADD,
            },
        }

    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        """Structural validation mirroring the runtime's work-item contract."""
        if not isinstance(work_item, dict):
            return False
        for field in ("workId", "type", "tenantId", "idempotencyKey"):
            if field not in work_item:
                logger.warning("addition agent: missing required field %s", field)
                return False
        if work_item.get("capability") != self.CAPABILITY_ADD:
            logger.warning(
                "addition agent: unexpected capability %r",
                work_item.get("capability"),
            )
            return False
        payload = work_item.get("payload")
        if not isinstance(payload, dict):
            return False
        return "left" in payload and "right" in payload

    def get_status(self, work_id: str, tenant_id: str) -> Dict[str, Any]:
        """Status is owned by the runtime, not by this agent."""
        return {
            "workId": work_id,
            "tenantId": tenant_id,
            "status": "COMPLETED",
            "result": {
                "message": "Addition agent has no independent state store",
                "agentId": ADDITION_AGENT_ID,
            },
        }

    @staticmethod
    def _operand_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Accept the agent payload at both real entry points.

        ``AgentBody.execute(work_item)`` passes the payload as-is. The
        ecosystem pipeline builds its invocation contract from the whole
        ProcessingEnvelope input (which *is* the work item), so operands arrive
        one level deeper. Unwrapping only when the nested object actually looks
        like a work item keeps both paths correct without changing the runtime
        for other agents.
        """
        if "left" in payload and "right" in payload:
            return payload
        nested = payload.get("payload")
        if isinstance(nested, dict) and "left" in nested and "right" in nested:
            return nested
        return payload

    @staticmethod
    def _error(message: str, error_type: str) -> Dict[str, Any]:
        return {"success": False, "error": {"message": message, "type": error_type}}


def create_addition_handler(config: Optional[Dict[str, Any]] = None):
    """Lambda-style handler for the addition agent (local harness parity)."""
    agent = AdditionAgent(config)

    def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        import json

        results = []
        for record in event.get("Records", []):
            try:
                body = record.get("body", {})
                work_item = json.loads(body) if isinstance(body, str) else body
                results.append(
                    {
                        "workId": (work_item or {}).get("workId"),
                        "result": agent.process_work(work_item),
                    }
                )
            except Exception as exc:  # pragma: no cover - defensive
                results.append(
                    {"workId": record.get("messageId"), "error": str(exc)}
                )
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"processed": len(event.get("Records", [])), "results": results}
            ),
        }

    return handler


__all__ = [
    "ADDITION_AGENT_ID",
    "ADDITION_CAPABILITY",
    "ADDITION_WORK_TYPE",
    "ADDITION_AGENT_VERSION",
    "AdditionAgent",
    "AdditionInputError",
    "add_operands",
    "create_addition_handler",
]
