"""R08-C0F-1 fenced S3 erasure phase contract.

This module does not create an S3 client and does not delete objects.  It
models the durable phase ledger and requires an adapter that can enforce the
attempt token before every S3 action.  Without that capability execution is
rejected, because an authorization check outside S3 cannot fence a stale
worker by itself.
"""

from __future__ import annotations

import os
import base64
import json
import threading
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


class S3QuiescenceBlocked(S3ErasureError):
    """The subject cannot yet be proven quiet for S3 erasure."""


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
class UploadTicketEvidence:
    """Ticket evidence without URL, object key or storage identifiers."""

    ticket_ref: str
    expires_at: Optional[str]


@dataclass(frozen=True)
class S3QuiescenceAssessment:
    ready: bool
    reasons: tuple = field(default_factory=tuple)

    def public_dict(self) -> Dict[str, Any]:
        return {"ready": self.ready, "reasons": list(self.reasons)}


@dataclass(frozen=True)
class S3QuiescenceLease:
    operation_id: str
    attempt_id: str
    lease_id: str


class InMemoryS3QuiescenceLeaseStore:
    """Thread-safe local exclusive lease fake; never used in production."""

    def __init__(self):
        self._lock = threading.Lock()
        self._leases: Dict[str, S3QuiescenceLease] = {}

    def acquire(self, operation_id: str, attempt_id: str) -> S3QuiescenceLease:
        with self._lock:
            if operation_id in self._leases:
                raise S3ErasureConflict("another S3 worker owns the quiescence lease")
            lease = S3QuiescenceLease(operation_id, attempt_id, "lease-" + uuid.uuid4().hex)
            self._leases[operation_id] = lease
            return lease

    def is_current(self, lease: S3QuiescenceLease) -> bool:
        with self._lock:
            return self._leases.get(lease.operation_id) == lease

    def release(self, lease: S3QuiescenceLease) -> None:
        with self._lock:
            if self._leases.get(lease.operation_id) != lease:
                raise S3ErasureConflict("stale S3 quiescence lease")
            del self._leases[lease.operation_id]


class S3QuiescenceCoordinator:
    """Local-verifiable quiescence gate; disabled unless explicitly enabled."""

    def __init__(self, *, lease_store: Any, enabled: Optional[bool] = None,
                 clock: Any = None):
        self.lease_store = lease_store
        self.enabled = (os.environ.get(
            "ERASURE_S3_QUIESCENCE_ENABLED", "false").lower() == "true"
                        if enabled is None else bool(enabled))
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def assess(self, *, freeze_active: bool,
               new_tickets_blocked: bool,
               tickets: Iterable[UploadTicketEvidence],
               active_actions: Optional[int],
               inventory_complete: bool,
               inventory_empty: bool,
               unregistered_tickets_unknown: bool = False,
               object_lock_blocked: bool = False,
               object_lock_unknown: bool = False) -> S3QuiescenceAssessment:
        reasons: List[str] = []
        if not freeze_active:
            reasons.append("FREEZE_NOT_ACTIVE")
        if not new_tickets_blocked:
            reasons.append("UPLOAD_TICKETS_NOT_BLOCKED")
        if unregistered_tickets_unknown:
            reasons.append("UNREGISTERED_TICKETS_UNKNOWN")
        now = self.clock()
        for ticket in tickets:
            if not ticket.ticket_ref or not ticket.expires_at:
                reasons.append("TICKET_EXPIRY_UNKNOWN")
                continue
            try:
                expiry = datetime.fromisoformat(ticket.expires_at.replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    reasons.append("TICKET_EXPIRY_UNKNOWN")
                elif expiry > now:
                    reasons.append("TICKET_STILL_VALID")
            except (TypeError, ValueError):
                reasons.append("TICKET_EXPIRY_UNKNOWN")
        if active_actions is None:
            reasons.append("ACTIVE_ACTIONS_UNKNOWN")
        elif active_actions != 0:
            reasons.append("ACTIVE_ACTIONS_PRESENT")
        if not inventory_complete:
            reasons.append("INVENTORY_INCOMPLETE")
        if not inventory_empty:
            reasons.append("OBJECTS_REMAIN")
        if object_lock_blocked:
            reasons.append("OBJECT_LOCK_BLOCKED")
        if object_lock_unknown:
            reasons.append("OBJECT_LOCK_UNKNOWN")
        return S3QuiescenceAssessment(not reasons, tuple(reasons))

    def begin(self, *, ctx: ErasureExecutionContextV1,
              attempt_id: str, assessment: S3QuiescenceAssessment
              ) -> S3QuiescenceLease:
        if not self.enabled:
            raise S3ErasureUnavailable("S3 quiescence is disabled")
        if not assessment.ready:
            raise S3QuiescenceBlocked("S3 quiescence is not proven")
        return self.lease_store.acquire(ctx.operation_id, attempt_id)

    def assert_current(self, lease: S3QuiescenceLease) -> None:
        if not self.lease_store.is_current(lease):
            raise S3ErasureConflict("stale S3 quiescence worker")

    def complete(self, *, lease: S3QuiescenceLease,
                 final_assessment: S3QuiescenceAssessment) -> None:
        self.assert_current(lease)
        if not final_assessment.ready:
            raise S3QuiescenceBlocked("final S3 quiescence proof failed")
        self.lease_store.release(lease)


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


class FencedS3VersionedAdapter(FencedS3Adapter):
    """Local/test adapter for versioned S3-shaped clients.

    The client is injected and must expose ``list_object_versions`` and
    ``delete_object``.  No boto3 client is constructed here.  A trusted
    ``before_action`` callback revalidates the attempt before every S3 call;
    the callback must fail closed when the operation/freeze/attempt is stale.
    """

    local_only = True

    def __init__(self, *, client: Any, bucket: str, prefix: str,
                 before_action: Any):
        if not client or not bucket or not prefix or not callable(before_action):
            raise ValueError("client, bucket, prefix and fencing callback are required")
        self.client = client
        self.bucket = bucket
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"
        self.before_action = before_action
        self.supports_fencing = True

    @staticmethod
    def _cursor(value: Dict[str, str]) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: Optional[str]) -> Dict[str, str]:
        if not cursor:
            return {}
        if "://" in cursor:
            raise S3ErasureConflict("invalid S3 pagination cursor")
        padded = cursor + "=" * (-len(cursor) % 4)
        try:
            value = json.loads(base64.urlsafe_b64decode(padded).decode())
        except Exception as exc:
            raise S3ErasureConflict("invalid S3 pagination cursor") from exc
        if not isinstance(value, dict):
            raise S3ErasureConflict("invalid S3 pagination cursor")
        return {str(key): str(item) for key, item in value.items()}

    def inventory(self, *, attempt_id: str,
                  cursor_ref: Optional[str] = None):
        self.before_action(attempt_id, "inventory")
        kwargs: Dict[str, Any] = {"Bucket": self.bucket, "Prefix": self.prefix}
        marker = self._decode_cursor(cursor_ref)
        if marker.get("key"):
            kwargs["KeyMarker"] = marker["key"]
        if marker.get("version"):
            kwargs["VersionIdMarker"] = marker["version"]
        response = self.client.list_object_versions(**kwargs)
        refs = []
        for item in response.get("Versions", []) or []:
            key = item.get("Key")
            version_id = item.get("VersionId")
            if key and version_id and key.startswith(self.prefix):
                refs.append(S3VersionRef(key, version_id, False))
        for item in response.get("DeleteMarkers", []) or []:
            key = item.get("Key")
            version_id = item.get("VersionId")
            if key and version_id and key.startswith(self.prefix):
                refs.append(S3VersionRef(key, version_id, True))
        if response.get("IsTruncated"):
            next_key = response.get("NextKeyMarker")
            next_version = response.get("NextVersionIdMarker")
            if not next_key or not next_version:
                raise S3ErasureUnknownResult("truncated S3 page has no marker")
            return refs, self._cursor({"key": next_key, "version": next_version})
        return refs, None

    def delete_version(self, *, attempt_id: str,
                       object_ref: S3VersionRef):
        self.before_action(attempt_id, "delete")
        if not object_ref.key.startswith(self.prefix) or not object_ref.version_id:
            raise S3ErasureConflict("S3 object is outside the authorized prefix")
        # VersionId is mandatory: an unversioned delete would create a new
        # delete marker and cannot prove removal of the intended version.
        return self.client.delete_object(
            Bucket=self.bucket, Key=object_ref.key,
            VersionId=object_ref.version_id)


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
    "UploadTicketEvidence", "S3QuiescenceAssessment",
    "S3QuiescenceLease", "InMemoryS3QuiescenceLeaseStore",
    "S3QuiescenceCoordinator", "S3QuiescenceBlocked",
    "S3ErasurePhaseRepository", "FencedS3Adapter",
    "FencedS3VersionedAdapter",
    "FencedS3ErasureOrchestrator", "S3ErasureError", "S3ErasureUnavailable",
    "S3ErasureConflict", "S3ErasureUnknownResult",
]
