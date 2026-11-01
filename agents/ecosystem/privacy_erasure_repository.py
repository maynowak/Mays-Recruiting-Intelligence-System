"""Fail-closed DynamoDB repository for R08-C0B erasure operations.

The repository persists only the C0A operation/checkpoint contract.  It does
not execute an erasure, write Privacy Receipts, create an AWS client, or scan a
table.  Production writes remain disabled until retention and policy approval
explicitly enables ``ERASURE_OPERATION_REPOSITORY_ENABLED``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from agents.ecosystem.privacy_erasure_contract import (
    ErasureContractError,
    ErasureOperationV1,
    ErasureProgressV1,
    ErasureCheckpointV1,
    OPERATION_RESOURCE_TYPE,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PARTIAL,
    STATUS_PENDING,
    STATUS_RUNNING,
    operation_fingerprint,
)


logger = logging.getLogger(__name__)
ENABLED_ENV = "ERASURE_OPERATION_REPOSITORY_ENABLED"
IDEMPOTENCY_RESOURCE_TYPE = "ErasureOperationIdempotency"
IDEMPOTENCY_PREFIX = "erasure-idempotency#"


class ErasureRepositoryError(RuntimeError):
    """Base error with an operator-safe code."""

    code = "ERASURE_REPOSITORY_ERROR"


class ErasureRepositoryDisabled(ErasureRepositoryError):
    code = "ERASURE_REPOSITORY_DISABLED"


class ErasureRepositoryUnavailable(ErasureRepositoryError):
    code = "ERASURE_REPOSITORY_UNAVAILABLE"


class ErasureOperationNotFound(ErasureRepositoryError):
    code = "ERASURE_OPERATION_NOT_FOUND"


class ErasureOperationConflict(ErasureRepositoryError):
    code = "ERASURE_OPERATION_CONFLICT"


class ErasureOperationVersionConflict(ErasureOperationConflict):
    code = "ERASURE_OPERATION_VERSION_CONFLICT"


class ErasureScope:
    """Verified identity passed by the caller; never client-selected fields."""

    def __init__(self, user_id: str, tenant_id: str,
                 partner_application_id: str, issuer: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.partner_application_id = partner_application_id
        self.issuer = issuer
        for value, name in ((user_id, "userId"), (tenant_id, "tenantId"),
                            (partner_application_id, "partnerApplicationId"),
                            (issuer, "issuer")):
            if not isinstance(value, str) or not value.strip():
                raise ErasureRepositoryError("verified scope is incomplete")

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> "ErasureScope":
        if not isinstance(context, Mapping):
            raise ErasureRepositoryError("verified scope is required")

        def value(camel: str, snake: str) -> Any:
            return context.get(camel, context.get(snake))

        return cls(value("userId", "user_id"), value("tenantId", "tenant_id"),
                   value("partnerApplicationId", "partner_application_id"),
                   value("issuer", "issuer"))

    def matches(self, operation: ErasureOperationV1) -> bool:
        return (operation.user_id == self.user_id
                and operation.tenant_id == self.tenant_id
                and operation.partner_application_id == self.partner_application_id
                and operation.issuer == self.issuer)

    def scope_key(self) -> str:
        return "%s#%s#%s#%s" % (
            self.tenant_id, self.user_id, self.partner_application_id,
            self.issuer)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _idempotency_key(scope: ErasureScope, key: str) -> str:
    raw = "%s#%s" % (scope.scope_key(), key)
    return IDEMPOTENCY_PREFIX + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _conditional_failure(exc: Exception) -> bool:
    text = str(exc).lower()
    return "conditionalcheckfailed" in text or "conditional check" in text


class ErasureOperationRepository:
    """Conditional, identity-bound repository; disabled by default."""

    def __init__(self, *, table: Any = None, table_name: Optional[str] = None,
                 enabled: Optional[bool] = None):
        self.table = table
        self.table_name = table_name or os.environ.get("ERASURE_OPERATION_TABLE")
        if enabled is None:
            enabled = os.environ.get(ENABLED_ENV, "false").strip().lower() == "true"
        self.enabled = bool(enabled)

    def _ensure_available(self) -> None:
        if not self.enabled:
            raise ErasureRepositoryDisabled("erasure operation repository is disabled")
        if self.table is None or not self.table_name:
            raise ErasureRepositoryUnavailable("erasure operation store is unavailable")

    @staticmethod
    def _assert_scope(operation: ErasureOperationV1, scope: ErasureScope) -> None:
        if not scope.matches(operation):
            raise ErasureOperationNotFound("operation not found")

    @staticmethod
    def _item(operation: ErasureOperationV1) -> Dict[str, Any]:
        item = operation.to_dynamodb_item()
        item["requestFingerprint"] = operation_fingerprint(operation)
        return item

    @staticmethod
    def _parse(item: Mapping[str, Any]) -> ErasureOperationV1:
        try:
            return ErasureOperationV1.from_dict(item)
        except (ErasureContractError, TypeError, ValueError) as exc:
            raise ErasureRepositoryError("stored operation is invalid") from exc

    def _get_raw(self, resource_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.table.get_item(Key={"resourceId": resource_id},
                                           ConsistentRead=True)
        except Exception as exc:
            raise ErasureRepositoryUnavailable("operation read failed") from exc
        return response.get("Item")

    def _get_owned(self, operation_id: str, scope: ErasureScope) -> ErasureOperationV1:
        item = self._get_raw(operation_id)
        if not item or item.get("resourceType") != OPERATION_RESOURCE_TYPE:
            raise ErasureOperationNotFound("operation not found")
        operation = self._parse(item)
        self._assert_scope(operation, scope)
        return operation

    def create(self, operation: ErasureOperationV1,
               context: Mapping[str, Any]) -> ErasureOperationV1:
        """Create once or return the exact idempotent replay."""
        self._ensure_available()
        scope = ErasureScope.from_context(context)
        self._assert_scope(operation, scope)
        if operation.status != STATUS_PENDING or operation.version != 1:
            raise ErasureOperationConflict("new operation must be PENDING version 1")

        marker_id = _idempotency_key(scope, operation.idempotency_key)
        fingerprint = operation_fingerprint(operation)
        try:
            existing_marker = self._get_raw(marker_id)
            if existing_marker:
                return self._replay_marker(existing_marker, fingerprint, scope)
            marker = {
                "resourceId": marker_id,
                "resourceType": IDEMPOTENCY_RESOURCE_TYPE,
                "operationId": operation.operation_id,
                "requestFingerprint": fingerprint,
                "scopeKey": scope.scope_key(),
                "createdAt": operation.created_at or _now(),
            }
            self.table.transact_write_items(TransactItems=[
                {"Put": {"TableName": self.table_name,
                         "Item": self._item(operation),
                         "ConditionExpression": "attribute_not_exists(resourceId)"}},
                {"Put": {"TableName": self.table_name,
                         "Item": marker,
                         "ConditionExpression": "attribute_not_exists(resourceId)"}},
            ])
            return operation
        except ErasureRepositoryError:
            raise
        except Exception as exc:
            if _conditional_failure(exc):
                marker_after_race = self._get_raw(marker_id)
                if marker_after_race:
                    return self._replay_marker(marker_after_race, fingerprint, scope)
                raise ErasureOperationConflict("operation creation conflict") from exc
            raise ErasureRepositoryUnavailable("operation create failed") from exc

    def _replay_marker(self, marker: Mapping[str, Any], fingerprint: str,
                       scope: ErasureScope) -> ErasureOperationV1:
        if marker.get("resourceType") != IDEMPOTENCY_RESOURCE_TYPE:
            raise ErasureOperationConflict("idempotency key conflict")
        if marker.get("scopeKey") != scope.scope_key() \
                or marker.get("requestFingerprint") != fingerprint:
            raise ErasureOperationConflict("idempotency key reused with different request")
        return self._get_owned(marker.get("operationId"), scope)

    def get(self, operation_id: str,
            context: Mapping[str, Any]) -> ErasureOperationV1:
        self._ensure_available()
        return self._get_owned(operation_id, ErasureScope.from_context(context))

    def update(self, operation: ErasureOperationV1, *, expected_version: int,
               context: Mapping[str, Any]) -> ErasureOperationV1:
        """Compare-and-swap the complete operation item atomically."""
        self._ensure_available()
        scope = ErasureScope.from_context(context)
        self._assert_scope(operation, scope)
        if (isinstance(expected_version, bool) or not isinstance(expected_version, int)
                or expected_version < 1 or operation.version != expected_version + 1):
            raise ErasureOperationVersionConflict("invalid expected operation version")
        item = self._item(operation)
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression=(
                    "resourceType = :rt AND version = :v AND userId = :u "
                    "AND tenantId = :t AND partnerApplicationId = :p AND issuer = :i"),
                ExpressionAttributeValues={
                    ":rt": OPERATION_RESOURCE_TYPE, ":v": expected_version,
                    ":u": scope.user_id, ":t": scope.tenant_id,
                    ":p": scope.partner_application_id, ":i": scope.issuer,
                },
            )
        except Exception as exc:
            if _conditional_failure(exc):
                raise ErasureOperationVersionConflict("operation version conflict") from exc
            raise ErasureRepositoryUnavailable("operation update failed") from exc
        return operation

    def save_checkpoint(self, operation_id: str, category: str,
                        progress: ErasureProgressV1, *, expected_version: int,
                        context: Mapping[str, Any], now: Optional[str] = None
                        ) -> ErasureOperationV1:
        """CAS one category checkpoint and preserve all other progress."""
        operation = self.get(operation_id, context)
        updated_progress = dict(operation.progress)
        updated_progress[category] = progress
        updated = replace(operation, progress=updated_progress,
                          version=operation.version + 1,
                          updated_at=now or _now())
        return self.update(updated, expected_version=expected_version,
                           context=context)

    def get_checkpoint(self, operation_id: str, category: str,
                       context: Mapping[str, Any]) -> Optional[ErasureCheckpointV1]:
        operation = self.get(operation_id, context)
        progress = operation.progress.get(category)
        return progress.checkpoint if progress else None

    def resume(self, operation_id: str, *, context: Mapping[str, Any],
               now: Optional[str] = None) -> ErasureOperationV1:
        """Resume PENDING/PARTIAL/FAILED with a versioned RUNNING update."""
        operation = self.get(operation_id, context)
        if operation.status == STATUS_COMPLETED:
            raise ErasureOperationConflict("completed operation cannot resume")
        if operation.status == STATUS_RUNNING:
            return operation
        resumed = operation.transition(STATUS_RUNNING, now=now or _now())
        return self.update(resumed, expected_version=operation.version,
                           context=context)


__all__ = [
    "ENABLED_ENV", "ErasureRepositoryError", "ErasureRepositoryDisabled",
    "ErasureRepositoryUnavailable", "ErasureOperationNotFound",
    "ErasureOperationConflict", "ErasureOperationVersionConflict",
    "ErasureScope", "ErasureOperationRepository",
]
