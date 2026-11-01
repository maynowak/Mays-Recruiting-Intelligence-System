"""R08-C0F-1 fenced S3 erasure phase contract.

This module does not create an S3 client and does not delete objects.  It
models the durable phase ledger and requires an adapter that can enforce the
attempt token before every S3 action.  Without that capability execution is
rejected, because an authorization check outside S3 cannot fence a stale
worker by itself.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from agents.ecosystem.privacy_erasure_contract import (
    ErasureExecutionContextV1,
    FREEZE_ACTIVE,
    OPERATION_RESOURCE_TYPE,
    STATUS_RUNNING,
)


PHASE_INVENTORY = "INVENTORY"
PHASE_DELETE = "DELETE"
PHASE_VERIFY = "VERIFY"
PHASE_RETRY = "RETRY"
PHASE_COMPLETED = "COMPLETED"
PHASE_ACTION_STARTED = "ACTION_STARTED"
PHASE_ACTION_FINISHED = "ACTION_FINISHED"


class S3ErasureError(RuntimeError):
    """Base error for the fail-closed S3 phase contract."""


class S3ErasureUnavailable(S3ErasureError):
    """The phase store or fenced adapter is unavailable."""


class S3ErasureConflict(S3ErasureError):
    """A stale attempt, scope, freeze or phase version was rejected."""


class S3ErasureUnknownResult(S3ErasureError):
    """An S3 result is unknown and therefore cannot advance completion."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attempt_id() -> str:
    return "s3a-" + uuid.uuid4().hex


@dataclass(frozen=True)
class S3VersionRef:
    """Internal object reference; never returned in a public response."""

    key: str
    version_id: str
    delete_marker: bool = False


@dataclass(frozen=True)
class S3ErasurePhaseV1:
    operation_id: str
    scope: str
    operation_version: int
    freeze_version: int
    attempt_id: str
    phase: str
    version: int = 1
    cursor_ref: Optional[str] = None
    remaining: Optional[int] = None
    last_action: Optional[str] = None
    last_outcome: Optional[str] = None
    error_code: Optional[str] = None
    updated_at: str = ""
    events: tuple = field(default_factory=tuple)

    def __post_init__(self):
        if not self.operation_id or not self.attempt_id:
            raise ValueError("operation and attempt are required")
        if self.scope not in ("USER", "CV"):
            raise ValueError("invalid S3 erasure scope")
        if self.operation_version < 1 or self.freeze_version < 1 or self.version < 1:
            raise ValueError("phase versions must be positive")
        if self.cursor_ref and "://" in self.cursor_ref:
            raise ValueError("cursor reference must be opaque")
        if self.remaining is not None and self.remaining < 0:
            raise ValueError("remaining must be non-negative")

    def public_dict(self) -> Dict[str, Any]:
        """Safe checkpoint projection; no key, URL or version ID is exposed."""
        return {
            "operationId": self.operation_id,
            "scope": self.scope,
            "phase": self.phase,
            "version": self.version,
            "attemptId": self.attempt_id,
            "remaining": self.remaining,
            "lastAction": self.last_action,
            "lastOutcome": self.last_outcome,
            "errorCode": self.error_code,
            "updatedAt": self.updated_at,
        }


class S3ErasurePhaseRepository:
    """DynamoDB-shaped durable phase ledger with atomic guard fencing."""

    def __init__(self, *, client: Any, phase_table_name: str,
                 guard_table_name: str, operation_table_name: str,
                 enabled: Optional[bool] = None):
        self.client = client
        self.phase_table_name = phase_table_name
        self.guard_table_name = guard_table_name
        self.operation_table_name = operation_table_name
        if enabled is None:
            enabled = os.environ.get(
                "ERASURE_S3_PHASE_REPOSITORY_ENABLED", "false").lower() == "true"
        self.enabled = bool(enabled)

    def _ensure(self):
        if not self.enabled:
            raise S3ErasureUnavailable("S3 erasure phase repository is disabled")
        if not self.client or not hasattr(self.client, "transact_write_items"):
            raise S3ErasureUnavailable("S3 phase transaction client unavailable")

    @staticmethod
    def _guard_key(ctx: ErasureExecutionContextV1) -> str:
        from agents.ecosystem.privacy_erasure_contract import freeze_resource_id
        return freeze_resource_id(
            user_id=ctx.user_id, tenant_id=ctx.tenant_id,
            partner_application_id=ctx.partner_application_id,
            issuer=ctx.issuer, scope=ctx.scope, cv_id=ctx.cv_id)

    def _checks(self, ctx: ErasureExecutionContextV1) -> List[Dict[str, Any]]:
        return [
            {"ConditionCheck": {
                "TableName": self.guard_table_name,
                "Key": {"resourceId": {"S": self._guard_key(ctx)}},
                "ConditionExpression": (
                    "resourceType = :fr AND #s = :active AND operationId = :op "
                    "AND version = :fv AND userId = :u AND tenantId = :t "
                    "AND partnerApplicationId = :p AND issuer = :i"),
                "ExpressionAttributeNames": {"#s": "state"},
                "ExpressionAttributeValues": {
                    ":fr": {"S": "ErasureWriteFreeze"},
                    ":active": {"S": FREEZE_ACTIVE},
                    ":op": {"S": ctx.operation_id},
                    ":fv": {"N": str(ctx.freeze_version)},
                    ":u": {"S": ctx.user_id}, ":t": {"S": ctx.tenant_id},
                    ":p": {"S": ctx.partner_application_id},
                    ":i": {"S": ctx.issuer},
                },
            }},
            {"ConditionCheck": {
                "TableName": self.operation_table_name,
                "Key": {"resourceId": {"S": ctx.operation_id}},
                "ConditionExpression": (
                    "resourceType = :rt AND #s = :running AND version = :ov "
                    "AND userId = :u AND tenantId = :t "
                    "AND partnerApplicationId = :p AND issuer = :i"),
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {
                    ":rt": {"S": OPERATION_RESOURCE_TYPE},
                    ":running": {"S": STATUS_RUNNING},
                    ":ov": {"N": str(ctx.operation_version)},
                    ":u": {"S": ctx.user_id}, ":t": {"S": ctx.tenant_id},
                    ":p": {"S": ctx.partner_application_id},
                    ":i": {"S": ctx.issuer},
                },
            }},
        ]

    def _write(self, ctx: ErasureExecutionContextV1, phase_action: Dict[str, Any]):
        self._ensure()
        try:
            self.client.transact_write_items(
                TransactItems=self._checks(ctx) + [phase_action])
        except Exception as exc:
            if "ConditionalCheckFailed" in str(exc) or "conditional" in str(exc).lower():
                raise S3ErasureConflict("S3 phase fencing conflict") from exc
            raise S3ErasureUnavailable("S3 phase transaction failed") from exc

    def begin(self, ctx: ErasureExecutionContextV1, *, expected_version: int,
              attempt_id: Optional[str] = None) -> S3ErasurePhaseV1:
        """Atomically claim a new attempt or resume a RETRY phase."""
        attempt = attempt_id or _attempt_id()
        if expected_version == 0:
            item = {
                "resourceId": f"s3-erasure#{ctx.operation_id}",
                "resourceType": "S3ErasurePhase",
                "operationId": ctx.operation_id, "scope": ctx.scope,
                "operationVersion": ctx.operation_version,
                "freezeVersion": ctx.freeze_version, "attemptId": attempt,
                "phase": PHASE_INVENTORY, "version": 1,
                "updatedAt": _now(),
            }
            action = {"Put": {"TableName": self.phase_table_name,
                              "Item": {
                                  **{k: {"S": v} if isinstance(v, str)
                                     else {"N": str(v)} for k, v in item.items()},
                                  "events": {"L": []},
                              },
                              "ConditionExpression": "attribute_not_exists(resourceId)"}}
        else:
            action = {"Update": {
                "TableName": self.phase_table_name,
                "Key": {"resourceId": {"S": f"s3-erasure#{ctx.operation_id}"}},
                "UpdateExpression": (
                    "SET attemptId = :a, phase = :p, #v = :newv, updatedAt = :now"),
                "ConditionExpression": "#v = :oldv AND phase = :retry",
                "ExpressionAttributeNames": {"#v": "version"},
                "ExpressionAttributeValues": {
                    ":a": {"S": attempt}, ":p": {"S": PHASE_INVENTORY},
                    ":newv": {"N": str(expected_version + 1)},
                    ":oldv": {"N": str(expected_version)},
                    ":retry": {"S": PHASE_RETRY}, ":now": {"S": _now()},
                },
            }}
        self._write(ctx, action)
        return S3ErasurePhaseV1(
            operation_id=ctx.operation_id, scope=ctx.scope,
            operation_version=ctx.operation_version,
            freeze_version=ctx.freeze_version, attempt_id=attempt,
            phase=PHASE_INVENTORY, version=max(1, expected_version + 1),
            updated_at=_now())

    def record(self, ctx: ErasureExecutionContextV1, phase: S3ErasurePhaseV1,
               *, action: str, outcome: str, next_phase: str,
               error_code: Optional[str] = None,
               remaining: Optional[int] = None) -> S3ErasurePhaseV1:
        """Persist action outcome and advance the fenced phase by one version."""
        new_version = phase.version + 1
        update = {"Update": {
            "TableName": self.phase_table_name,
            "Key": {"resourceId": {"S": f"s3-erasure#{ctx.operation_id}"}},
            "UpdateExpression": (
                "SET phase = :p, #v = :newv, lastAction = :a, "
                "lastOutcome = :o, attemptId = :attempt, updatedAt = :now "
                ", events = list_append(if_not_exists(events, :empty), :event)"),
            "ConditionExpression": (
                "#v = :oldv AND attemptId = :attempt AND phase <> :completed"),
            "ExpressionAttributeNames": {"#v": "version"},
            "ExpressionAttributeValues": {
                ":p": {"S": next_phase}, ":newv": {"N": str(new_version)},
                ":oldv": {"N": str(phase.version)}, ":a": {"S": action},
                ":o": {"S": outcome}, ":attempt": {"S": phase.attempt_id},
                ":completed": {"S": PHASE_COMPLETED}, ":now": {"S": _now()},
                ":event": {"L": [{"M": {
                    "action": {"S": action}, "outcome": {"S": outcome},
                    "attemptId": {"S": phase.attempt_id},
                    "at": {"S": _now()},
                }}]},
                ":empty": {"L": []},
            },
        }}
        self._write(ctx, update)
        return S3ErasurePhaseV1(
            operation_id=phase.operation_id, scope=phase.scope,
            operation_version=phase.operation_version,
            freeze_version=phase.freeze_version, attempt_id=phase.attempt_id,
            phase=next_phase, version=new_version,
            last_action=action, last_outcome=outcome,
            error_code=error_code, remaining=remaining, updated_at=_now())


class FencedS3Adapter:
    """Adapter contract; implementations must enforce attempt fencing."""

    supports_fencing = False

    def inventory(self, *, attempt_id: str, cursor_ref: Optional[str] = None):
        raise NotImplementedError

    def delete_version(self, *, attempt_id: str, object_ref: S3VersionRef):
        raise NotImplementedError


class FencedS3ErasureOrchestrator:
    """Inventory/delete/re-inventory orchestration without an S3 client."""

    def __init__(self, *, phases: S3ErasurePhaseRepository,
                 adapter: FencedS3Adapter, enabled: Optional[bool] = None):
        self.phases = phases
        self.adapter = adapter
        if enabled is None:
            enabled = os.environ.get("ERASURE_S3_EXECUTION_ENABLED", "false").lower() == "true"
        self.enabled = bool(enabled)

    def _inventory_all(self, attempt_id: str) -> List[S3VersionRef]:
        """Consume every adapter page; cursor refs never enter public output."""
        result: List[S3VersionRef] = []
        cursor: Optional[str] = None
        while True:
            page = self.adapter.inventory(attempt_id=attempt_id,
                                           cursor_ref=cursor)
            if isinstance(page, tuple):
                objects, next_cursor = page
            else:
                objects, next_cursor = page, None
            result.extend(list(objects or []))
            if not next_cursor:
                return result
            if not isinstance(next_cursor, str) or "://" in next_cursor:
                raise S3ErasureUnknownResult("invalid S3 pagination cursor")
            cursor = next_cursor

    def run(self, ctx: ErasureExecutionContextV1, *, expected_version: int,
            attempt_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.enabled or not self.adapter.supports_fencing:
            raise S3ErasureUnavailable("fenced S3 execution is disabled")
        if ctx.scope not in ("USER", "CV"):
            raise S3ErasureConflict("invalid S3 erasure scope")
        phase = self.phases.begin(ctx, expected_version=expected_version,
                                  attempt_id=attempt_id)
        try:
            phase = self.phases.record(
                ctx, phase, action="inventory", outcome="STARTED",
                next_phase=PHASE_ACTION_STARTED)
            inventory = self._inventory_all(phase.attempt_id)
            phase = self.phases.record(
                ctx, phase, action="inventory", outcome="SUCCEEDED",
                next_phase=PHASE_DELETE, remaining=len(inventory))
            for obj in inventory:
                phase = self.phases.record(
                    ctx, phase, action="delete", outcome="STARTED",
                    next_phase=PHASE_ACTION_STARTED,
                    remaining=phase.remaining)
                self.adapter.delete_version(attempt_id=phase.attempt_id,
                                            object_ref=obj)
                phase = self.phases.record(
                    ctx, phase, action="delete", outcome="SUCCEEDED",
                    next_phase=PHASE_DELETE,
                    remaining=max(0, (phase.remaining or 1) - 1))
            phase = self.phases.record(
                ctx, phase, action="inventory", outcome="STARTED",
                next_phase=PHASE_ACTION_STARTED)
            remaining = self._inventory_all(phase.attempt_id)
            if remaining:
                self.phases.record(
                    ctx, phase, action="verify", outcome="REMAINING",
                    next_phase=PHASE_RETRY, remaining=len(remaining),
                    error_code="S3_OBJECTS_REMAIN")
                return {"complete": False, "phase": PHASE_RETRY,
                        "remaining": len(remaining)}
            self.phases.record(
                ctx, phase, action="verify", outcome="EMPTY",
                next_phase=PHASE_COMPLETED, remaining=0)
            return {"complete": True, "phase": PHASE_COMPLETED, "remaining": 0}
        except S3ErasureError:
            raise
        except Exception as exc:
            # Unknown S3 outcomes never advance to COMPLETED. The durable
            # ledger records the retry boundary when possible.
            try:
                self.phases.record(
                    ctx, phase, action="unknown", outcome="UNKNOWN",
                    next_phase=PHASE_RETRY, error_code="S3_RESULT_UNKNOWN")
            except Exception:
                pass
            raise S3ErasureUnknownResult("S3 result is unknown") from exc


__all__ = [
    "PHASE_INVENTORY", "PHASE_DELETE", "PHASE_VERIFY", "PHASE_RETRY",
    "PHASE_COMPLETED", "S3VersionRef", "S3ErasurePhaseV1",
    "S3ErasurePhaseRepository", "FencedS3Adapter",
    "FencedS3ErasureOrchestrator", "S3ErasureError", "S3ErasureUnavailable",
    "S3ErasureConflict", "S3ErasureUnknownResult",
]
