"""R08-C0A contract for resumable RIS erasure operations.

This module defines validation and serialization only.  It deliberately does
not create a DynamoDB client, delete data, write receipts, or execute G5.
Persistence implementations must use the item projection and conditional
version contract documented below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional


SCHEMA_VERSION = 1
OPERATION_RESOURCE_TYPE = "ErasureOperation"
OPERATION_SCOPE_USER = "USER"
OPERATION_SCOPE_CV = "CV"
OPERATION_SCOPES = frozenset({OPERATION_SCOPE_USER, OPERATION_SCOPE_CV})

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"
STATUS_COMPLETED = "COMPLETED"
OPERATION_STATUSES = frozenset({
    STATUS_PENDING, STATUS_RUNNING, STATUS_PARTIAL, STATUS_FAILED,
    STATUS_COMPLETED,
})

PROGRESS_PENDING = "PENDING"
PROGRESS_RUNNING = "RUNNING"
PROGRESS_PARTIAL = "PARTIAL"
PROGRESS_FAILED = "FAILED"
PROGRESS_COMPLETED = "COMPLETED"
PROGRESS_SKIPPED = "SKIPPED"
PROGRESS_STATUSES = frozenset({
    PROGRESS_PENDING, PROGRESS_RUNNING, PROGRESS_PARTIAL,
    PROGRESS_FAILED, PROGRESS_COMPLETED, PROGRESS_SKIPPED,
})

CHECKPOINT_NOT_STARTED = "NOT_STARTED"
CHECKPOINT_IN_PROGRESS = "IN_PROGRESS"
CHECKPOINT_COMPLETED = "COMPLETED"
CHECKPOINT_STATUSES = frozenset({
    CHECKPOINT_NOT_STARTED, CHECKPOINT_IN_PROGRESS, CHECKPOINT_COMPLETED,
})

ERASURE_CATEGORIES = (
    "credentials", "apiProfiles", "workItems", "atsSearchProfiles",
    "cvSearchProfiles", "manualSearchProfiles", "cvDocuments",
    "s3Versions", "systemRecords", "userProfile", "privacyReceipts",
)

_STATUS_TRANSITIONS = {
    STATUS_PENDING: frozenset({STATUS_RUNNING, STATUS_FAILED}),
    STATUS_RUNNING: frozenset({STATUS_RUNNING, STATUS_PARTIAL,
                               STATUS_FAILED, STATUS_COMPLETED}),
    STATUS_PARTIAL: frozenset({STATUS_RUNNING, STATUS_PARTIAL,
                               STATUS_FAILED, STATUS_COMPLETED}),
    STATUS_FAILED: frozenset({STATUS_RUNNING, STATUS_FAILED}),
    STATUS_COMPLETED: frozenset(),
}
_OPAQUE_REF = re.compile(r"^[A-Za-z0-9._:/+=-]{1,512}$")
_FORBIDDEN_NAMES = frozenset({
    "key", "s3key", "s3_key", "objectkey", "object_key", "secret",
    "token", "jwt", "credential", "password", "presignedurl",
    "presigned_url", "downloadurl", "download_url", "content",
    "cvtext", "text", "prompt",
})


class ErasureContractError(ValueError):
    """Raised when an operation or checkpoint violates the contract."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _required_ref(value: Any, name: str, *, opaque: bool = False,
                  reject_uri: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ErasureContractError("INVALID_FIELD", "%s is required" % name)
    value = value.strip()
    if len(value) > 512:
        raise ErasureContractError("INVALID_FIELD", "%s is too long" % name)
    if opaque and not _OPAQUE_REF.fullmatch(value):
        raise ErasureContractError("INVALID_FIELD", "%s is not opaque" % name)
    if reject_uri and "://" in value:
        raise ErasureContractError("SENSITIVE_FIELD", "%s must not be a URI" % name)
    return value


def _timestamp(value: Any, name: str) -> str:
    value = _required_ref(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ErasureContractError("INVALID_TIMESTAMP", "%s is invalid" % name) from exc
    if parsed.tzinfo is None:
        raise ErasureContractError("INVALID_TIMESTAMP", "%s must be UTC" % name)
    return value


def _reject_sensitive(value: Any, path: str = "root") -> None:
    """Reject storage secrets/content from public contract evidence."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).replace("-", "_").lower()
            if normalized in _FORBIDDEN_NAMES:
                raise ErasureContractError(
                    "SENSITIVE_FIELD", "%s contains forbidden field %s" % (path, key))
            _reject_sensitive(child, "%s.%s" % (path, key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_sensitive(child, "%s[%s]" % (path, index))


@dataclass(frozen=True)
class ErasureCheckpointV1:
    """A resumable phase pointer; raw DynamoDB/S3 keys never cross the API."""

    phase: str
    state: str = CHECKPOINT_NOT_STARTED
    cursor_ref: Optional[str] = None
    last_resource_ref: Optional[str] = None
    attempt: int = 0
    updated_at: str = ""

    def __post_init__(self):
        _required_ref(self.phase, "phase", opaque=True, reject_uri=True)
        if self.state not in CHECKPOINT_STATUSES:
            raise ErasureContractError("INVALID_CHECKPOINT_STATE", "invalid checkpoint state")
        for value, name in ((self.cursor_ref, "cursorRef"),
                            (self.last_resource_ref, "lastResourceRef")):
            if value is not None:
                _required_ref(value, name, opaque=True, reject_uri=True)
        if isinstance(self.attempt, bool) or not isinstance(self.attempt, int) or self.attempt < 0:
            raise ErasureContractError("INVALID_FIELD", "attempt must be non-negative")
        if self.updated_at:
            _timestamp(self.updated_at, "updatedAt")

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "schemaVersion": SCHEMA_VERSION,
            "phase": self.phase,
            "state": self.state,
            "attempt": self.attempt,
        }
        if self.cursor_ref is not None:
            result["cursorRef"] = self.cursor_ref
        if self.last_resource_ref is not None:
            result["lastResourceRef"] = self.last_resource_ref
        if self.updated_at:
            result["updatedAt"] = self.updated_at
        return result


@dataclass(frozen=True)
class ErasureProgressV1:
    """Per-category progress, independent from receipt status/evidence."""

    status: str = PROGRESS_PENDING
    affected: int = 0
    checkpoint: Optional[ErasureCheckpointV1] = None
    error_code: Optional[str] = None
    retryable: bool = False

    def __post_init__(self):
        if self.status not in PROGRESS_STATUSES:
            raise ErasureContractError("INVALID_PROGRESS_STATUS", "invalid progress status")
        if isinstance(self.affected, bool) or not isinstance(self.affected, int) or self.affected < 0:
            raise ErasureContractError("INVALID_FIELD", "affected must be non-negative")
        if self.error_code is not None:
            _required_ref(self.error_code, "errorCode", opaque=True)
        if not isinstance(self.retryable, bool):
            raise ErasureContractError("INVALID_FIELD", "retryable must be boolean")
        if self.status in (PROGRESS_PARTIAL, PROGRESS_FAILED) and not self.error_code:
            raise ErasureContractError("MISSING_ERROR", "partial/failed progress needs errorCode")

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": self.status,
            "affected": self.affected,
            "retryable": self.retryable,
        }
        if self.checkpoint is not None:
            result["checkpoint"] = self.checkpoint.to_dict()
        if self.error_code is not None:
            result["errorCode"] = self.error_code
        return result


@dataclass(frozen=True)
class ErasureOperationV1:
    """Versioned durable operation contract; execution remains G5-owned."""

    operation_id: str
    idempotency_key: str
    user_id: str
    tenant_id: str
    partner_application_id: str
    issuer: str
    scope: str
    status: str = STATUS_PENDING
    version: int = 1
    cv_id: Optional[str] = None
    progress: Dict[str, ErasureProgressV1] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    last_error_code: Optional[str] = None

    def __post_init__(self):
        for value, name in (
            (self.operation_id, "operationId"),
            (self.idempotency_key, "idempotencyKey"),
            (self.user_id, "userId"),
            (self.tenant_id, "tenantId"),
            (self.partner_application_id, "partnerApplicationId"),
            (self.issuer, "issuer"),
        ):
            _required_ref(value, name, opaque=True)
        if self.scope not in OPERATION_SCOPES:
            raise ErasureContractError("INVALID_SCOPE", "scope must be USER or CV")
        if self.scope == OPERATION_SCOPE_CV:
            _required_ref(self.cv_id, "cvId", opaque=True)
        elif self.cv_id is not None:
            raise ErasureContractError("INVALID_SCOPE", "USER operation cannot carry cvId")
        if self.status not in OPERATION_STATUSES:
            raise ErasureContractError("INVALID_STATUS", "invalid operation status")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ErasureContractError("INVALID_VERSION", "version must be positive")
        if isinstance(self.retry_count, bool) or not isinstance(self.retry_count, int) or self.retry_count < 0:
            raise ErasureContractError("INVALID_FIELD", "retryCount must be non-negative")
        if self.last_error_code is not None:
            _required_ref(self.last_error_code, "lastErrorCode", opaque=True)
        for value, name in ((self.created_at, "createdAt"), (self.updated_at, "updatedAt"),
                            (self.started_at, "startedAt"), (self.completed_at, "completedAt")):
            if value:
                _timestamp(value, name)
        if not isinstance(self.progress, Mapping):
            raise ErasureContractError("INVALID_FIELD", "progress must be an object")
        for category, item in self.progress.items():
            if category not in ERASURE_CATEGORIES or not isinstance(item, ErasureProgressV1):
                raise ErasureContractError("INVALID_PROGRESS", "invalid progress category")
        _reject_sensitive(self.to_dict())

    def can_transition_to(self, target: str) -> bool:
        return target in _STATUS_TRANSITIONS[self.status]

    def transition(self, target: str, *, now: str,
                   error_code: Optional[str] = None) -> "ErasureOperationV1":
        if target not in OPERATION_STATUSES or not self.can_transition_to(target):
            raise ErasureContractError("INVALID_STATUS_TRANSITION", "%s -> %s is not allowed" % (self.status, target))
        if target in (STATUS_PARTIAL, STATUS_FAILED) and not error_code:
            raise ErasureContractError("MISSING_ERROR", "partial/failed status needs errorCode")
        if target == STATUS_COMPLETED:
            if any(item.status not in (PROGRESS_COMPLETED, PROGRESS_SKIPPED)
                   for item in self.progress.values()):
                raise ErasureContractError("INCOMPLETE_OPERATION", "cannot complete incomplete operation")
        return ErasureOperationV1(
            operation_id=self.operation_id, idempotency_key=self.idempotency_key,
            user_id=self.user_id, tenant_id=self.tenant_id,
            partner_application_id=self.partner_application_id, issuer=self.issuer,
            scope=self.scope, status=target, version=self.version + 1,
            cv_id=self.cv_id, progress=dict(self.progress),
            created_at=self.created_at, updated_at=_timestamp(now, "now"),
            started_at=self.started_at or (now if target == STATUS_RUNNING else None),
            completed_at=now if target == STATUS_COMPLETED else self.completed_at,
            retry_count=self.retry_count + (1 if target == STATUS_RUNNING and self.status in (STATUS_PARTIAL, STATUS_FAILED) else 0),
            last_error_code=error_code,
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": OPERATION_RESOURCE_TYPE,
            "schemaVersion": SCHEMA_VERSION,
            "operationId": self.operation_id,
            "idempotencyKey": self.idempotency_key,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "partnerApplicationId": self.partner_application_id,
            "issuer": self.issuer,
            "scope": self.scope,
            "status": self.status,
            "version": self.version,
            "progress": {key: value.to_dict() for key, value in self.progress.items()},
            "retryCount": self.retry_count,
        }
        if self.cv_id is not None:
            result["cvId"] = self.cv_id
        for value, name in ((self.created_at, "createdAt"), (self.updated_at, "updatedAt"),
                            (self.started_at, "startedAt"), (self.completed_at, "completedAt"),
                            (self.last_error_code, "lastErrorCode")):
            if value:
                result[name] = value
        return result

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Return the logical item shape for conditional DynamoDB persistence.

        Required write rule: Put with ``attribute_not_exists(operationId)``;
        update with ``operationId = :id AND version = :expectedVersion`` and
        increment ``version`` atomically. The implementation is intentionally
        left to C1 and this method performs no AWS operation.
        """
        item = self.to_dict()
        item["idempotencyLookup"] = "%s#%s" % (self.tenant_id, self.idempotency_key)
        item["scopeKey"] = "%s#%s#%s#%s" % (
            self.tenant_id, self.user_id, self.partner_application_id, self.issuer)
        return item


def new_operation(*, operation_id: str, idempotency_key: str, user_id: str,
                  tenant_id: str, partner_application_id: str, issuer: str,
                  scope: str, now: Optional[str] = None,
                  cv_id: Optional[str] = None,
                  progress: Optional[Mapping[str, ErasureProgressV1]] = None) -> ErasureOperationV1:
    """Construct a pending operation without generating identity or timestamps."""
    stamp = now or datetime.now(timezone.utc).isoformat()
    return ErasureOperationV1(
        operation_id=operation_id, idempotency_key=idempotency_key,
        user_id=user_id, tenant_id=tenant_id,
        partner_application_id=partner_application_id, issuer=issuer,
        scope=scope, cv_id=cv_id, created_at=stamp, updated_at=stamp,
        progress=(dict(progress) if progress is not None else {
            category: ErasureProgressV1() for category in ERASURE_CATEGORIES}),
    )


__all__ = [
    "SCHEMA_VERSION", "OPERATION_RESOURCE_TYPE", "OPERATION_SCOPE_USER",
    "OPERATION_SCOPE_CV", "STATUS_PENDING", "STATUS_RUNNING",
    "STATUS_PARTIAL", "STATUS_FAILED", "STATUS_COMPLETED",
    "PROGRESS_PENDING", "PROGRESS_RUNNING", "PROGRESS_PARTIAL",
    "PROGRESS_FAILED", "PROGRESS_COMPLETED", "PROGRESS_SKIPPED",
    "CHECKPOINT_NOT_STARTED", "CHECKPOINT_IN_PROGRESS", "CHECKPOINT_COMPLETED",
    "ERASURE_CATEGORIES", "ErasureContractError", "ErasureCheckpointV1",
    "ErasureProgressV1", "ErasureOperationV1", "new_operation",
]
