"""Fail-closed DynamoDB deletion evidence for restore reconciliation.

The repository stores opaque resource-reference digests only. It is disabled
unless explicitly enabled by its caller, and it never deletes ledger rows or
turns restored data back into an active state. The local contract in
``privacy_deletion_ledger`` remains the source of the value/reconciliation
rules; this module supplies conditional durable persistence for that contract.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Iterable, Mapping

from boto3.dynamodb.conditions import Key

from agents.ecosystem.privacy_deletion_ledger import (
    DeletionLedgerEntry,
    DeletionLedgerError,
    LedgerScope,
    RestoreReconciliation,
    EXPECTED_ABSENT,
    EXPECTED_PRESENT,
    KNOWN_RESOURCE_TYPES,
    resource_digest,
)


class DurableDeletionLedgerError(RuntimeError):
    """Base error for unavailable or conflicting durable ledger evidence."""


class DurableDeletionLedgerUnavailable(DurableDeletionLedgerError):
    """The ledger is disabled, missing, or could not be read/written."""


class DurableDeletionLedgerConflict(DurableDeletionLedgerError):
    """An idempotency or version conflict requires fail-closed handling."""


def _ledger_id(operation_id: str, scope: LedgerScope, resource_type: str) -> str:
    return hashlib.sha256(
        "|".join((operation_id, scope.tenant_id, scope.user_id,
                   scope.partner_application_id, scope.issuer, scope.scope,
                   resource_type)).encode("utf-8")
    ).hexdigest()


def _scope_key(scope: LedgerScope) -> str:
    material = json.dumps(
        [scope.tenant_id, scope.user_id, scope.partner_application_id,
         scope.issuer, scope.scope], separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class DurableDeletionLedger:
    """Conditional, identity-bound ledger backed by an injected DynamoDB table.

    The caller must inject the table so this module does not create AWS
    clients. ``enabled`` defaults to ``DELETION_LEDGER_ENABLED=false``. The
    table uses ``ledgerId`` as its primary key and ``gsi-operation`` on
    ``operationId``/``ledgerId`` for scoped reconciliation reads.
    """

    def __init__(self, *, table: Any = None, table_name: str | None = None,
                 enabled: bool | None = None):
        self.table = table
        self.table_name = table_name or os.environ.get("DELETION_LEDGER_TABLE")
        if enabled is None:
            enabled = os.environ.get("DELETION_LEDGER_ENABLED", "false").lower() == "true"
        self.enabled = bool(enabled)

    def _ensure_available(self) -> None:
        if not self.enabled:
            raise DurableDeletionLedgerUnavailable("deletion ledger is disabled")
        if self.table is None or not self.table_name:
            raise DurableDeletionLedgerUnavailable("deletion ledger is unavailable")

    @staticmethod
    def _item(entry: DeletionLedgerEntry) -> dict[str, Any]:
        item = entry.snapshot()
        item.update({
            "ledgerId": entry.ledger_id,
            "operationId": entry.operation_id,
            "scopeKey": _scope_key(entry.scope),
            "resourceType": entry.resource_type,
        })
        return item

    @staticmethod
    def _parse(item: Mapping[str, Any]) -> DeletionLedgerEntry:
        try:
            scope = LedgerScope(
                user_id=item["userId"], tenant_id=item["tenantId"],
                partner_application_id=item["partnerApplicationId"],
                issuer=item["issuer"], scope=item["scope"],
            )
            return DeletionLedgerEntry(
                ledger_id=item["ledgerId"], operation_id=item["operationId"],
                scope=scope, resource_type=item["resourceType"],
                resource_ref_digest=item["resourceRefDigest"],
                expected_state=item["expectedState"], state=item["state"],
                version=int(item["version"]),
                schema_version=int(item["schemaVersion"]),
            )
        except (KeyError, TypeError, ValueError, DeletionLedgerError) as exc:
            raise DurableDeletionLedgerError("invalid stored deletion evidence") from exc

    @staticmethod
    def _conditional_failure(exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        return (isinstance(response, dict)
                and response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException")

    def _get(self, ledger_id: str) -> DeletionLedgerEntry | None:
        try:
            item = self.table.get_item(
                Key={"ledgerId": ledger_id}, ConsistentRead=True,
            ).get("Item")
            return self._parse(item) if item else None
        except DurableDeletionLedgerError:
            raise
        except Exception as exc:
            raise DurableDeletionLedgerUnavailable("deletion ledger read failed") from exc

    def capture(self, *, operation_id: str, scope: LedgerScope,
                resource_type: str, resource_ref: str) -> DeletionLedgerEntry:
        self._ensure_available()
        scope.validate()
        if not operation_id or resource_type not in KNOWN_RESOURCE_TYPES:
            raise DeletionLedgerError("INVALID_LEDGER_INPUT")
        entry = DeletionLedgerEntry(
            ledger_id=_ledger_id(operation_id, scope, resource_type),
            operation_id=operation_id, scope=scope,
            resource_type=resource_type,
            resource_ref_digest=resource_digest(resource_ref),
        )
        try:
            self.table.put_item(
                Item=self._item(entry),
                ConditionExpression="attribute_not_exists(ledgerId)",
            )
            return entry
        except Exception as exc:
            if not self._conditional_failure(exc):
                raise DurableDeletionLedgerUnavailable("deletion ledger capture failed") from exc
            existing = self._get(entry.ledger_id)
            if existing == entry:
                return existing
            raise DurableDeletionLedgerConflict("deletion ledger idempotency conflict") from exc

    def mark_erasure_result(self, *, operation_id: str, scope: LedgerScope,
                            resource_type: str, resource_ref: str,
                            complete: bool) -> DeletionLedgerEntry:
        current = self.capture(operation_id=operation_id, scope=scope,
                                resource_type=resource_type, resource_ref=resource_ref)
        if not complete or current.state == EXPECTED_ABSENT:
            return current
        updated = DeletionLedgerEntry(
            ledger_id=current.ledger_id, operation_id=current.operation_id,
            scope=current.scope, resource_type=current.resource_type,
            resource_ref_digest=current.resource_ref_digest,
            expected_state=current.expected_state, state=EXPECTED_ABSENT,
            version=current.version + 1, schema_version=current.schema_version,
        )
        try:
            self.table.put_item(
                Item=self._item(updated),
                ConditionExpression=(
                    "version = :v AND #state = :present AND "
                    "operationId = :operation"),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":v": current.version, ":present": EXPECTED_PRESENT,
                    ":operation": operation_id,
                },
            )
            return updated
        except Exception as exc:
            if self._conditional_failure(exc):
                latest = self._get(current.ledger_id)
                if latest and latest.state == EXPECTED_ABSENT:
                    return latest
                raise DurableDeletionLedgerConflict("deletion ledger version conflict") from exc
            raise DurableDeletionLedgerUnavailable("deletion ledger update failed") from exc

    def _operation_entries(self, operation_id: str) -> tuple[DeletionLedgerEntry, ...]:
        try:
            response = self.table.query(
                IndexName="gsi-operation",
                KeyConditionExpression=Key("operationId").eq(operation_id),
                ConsistentRead=False,
            )
            return tuple(self._parse(item) for item in response.get("Items", ()))
        except DurableDeletionLedgerError:
            raise
        except Exception as exc:
            raise DurableDeletionLedgerUnavailable("deletion ledger query failed") from exc

    def reconcile_restore(self, *, operation_id: str, scope: LedgerScope,
                          restored_resources: Iterable[Mapping[str, str]]) -> RestoreReconciliation:
        self._ensure_available()
        scope.validate()
        relevant = tuple(
            entry for entry in self._operation_entries(operation_id)
            if entry.scope == scope
        )
        if not relevant:
            return RestoreReconciliation("BLOCKED", error_code="MISSING_LEDGER_EVIDENCE")
        restored: list[str] = []
        missing = tuple(entry.ledger_id for entry in relevant
                        if entry.state == EXPECTED_ABSENT)
        for resource in restored_resources:
            if not isinstance(resource, Mapping):
                return RestoreReconciliation("BLOCKED", error_code="UNKNOWN_INVENTORY")
            if any(resource.get(field) != getattr(scope, field) for field in (
                    "tenant_id", "user_id", "partner_application_id", "issuer")):
                continue
            resource_type = resource.get("resourceType")
            resource_ref = resource.get("resourceRef")
            if resource_type not in KNOWN_RESOURCE_TYPES or not isinstance(resource_ref, str):
                return RestoreReconciliation("BLOCKED", error_code="UNKNOWN_INVENTORY")
            digest = resource_digest(resource_ref)
            if any(entry.resource_type == resource_type
                   and entry.resource_ref_digest == digest
                   and entry.state == EXPECTED_ABSENT for entry in relevant):
                restored.append(f"{resource_type}:{digest}")
        if restored:
            return RestoreReconciliation(
                "RECONCILIATION_REQUIRED", required=missing,
                unexpected=tuple(restored), error_code="RESTORED_ERASED_RESOURCE",
            )
        return RestoreReconciliation("CLEAN")

    def snapshot(self, *, operation_id: str | None = None) -> tuple[dict, ...]:
        self._ensure_available()
        entries = (self._operation_entries(operation_id)
                   if operation_id is not None else ())
        return tuple(entry.snapshot() for entry in entries)


__all__ = [
    "DurableDeletionLedger", "DurableDeletionLedgerError",
    "DurableDeletionLedgerUnavailable", "DurableDeletionLedgerConflict",
]
