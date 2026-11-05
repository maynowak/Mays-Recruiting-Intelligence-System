"""Local-only deletion evidence and restore reconciliation contract.

This module deliberately has no AWS/runtime wiring.  It records only hashed,
synthetic resource references and reuses the identity shape of
``ErasureExecutionContextV1``.  A restore is never mutated automatically:
reconciliation reports whether a human/approved erasure execution is needed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Iterable, Mapping


SCHEMA_VERSION = 1
EXPECTED_PRESENT = "PRESENT_BEFORE_ERASURE"
EXPECTED_ABSENT = "ABSENT_AFTER_ERASURE"
LEDGER_STATES = frozenset({EXPECTED_PRESENT, EXPECTED_ABSENT})
KNOWN_RESOURCE_TYPES = frozenset({
    "USER_PROFILE", "API_PROFILE", "WORK_ITEM", "CV_DOCUMENT",
    "S3_OBJECT", "APPLICATION",
})


class DeletionLedgerError(ValueError):
    """Fail-closed local contract violation."""


@dataclass(frozen=True)
class LedgerScope:
    user_id: str
    tenant_id: str
    partner_application_id: str
    issuer: str
    scope: str = "USER"

    def validate(self) -> None:
        if any(not isinstance(v, str) or not v.strip() for v in (
            self.user_id, self.tenant_id, self.partner_application_id,
            self.issuer, self.scope,
        )):
            raise DeletionLedgerError("INVALID_SCOPE")


@dataclass(frozen=True)
class DeletionLedgerEntry:
    ledger_id: str
    operation_id: str
    scope: LedgerScope
    resource_type: str
    resource_ref_digest: str
    expected_state: str = EXPECTED_PRESENT
    state: str = EXPECTED_PRESENT
    version: int = 1
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.scope.validate()
        if self.schema_version != SCHEMA_VERSION:
            raise DeletionLedgerError("UNSUPPORTED_SCHEMA_VERSION")
        if not self.operation_id or not self.ledger_id:
            raise DeletionLedgerError("INVALID_LEDGER_ID")
        if self.resource_type not in KNOWN_RESOURCE_TYPES:
            raise DeletionLedgerError("UNKNOWN_RESOURCE_TYPE")
        if self.expected_state not in LEDGER_STATES or self.state not in LEDGER_STATES:
            raise DeletionLedgerError("INVALID_LEDGER_STATE")
        if len(self.resource_ref_digest) != 64:
            raise DeletionLedgerError("INVALID_RESOURCE_DIGEST")
        if self.version < 1:
            raise DeletionLedgerError("INVALID_VERSION")

    def snapshot(self) -> dict:
        return {
            "schemaVersion": self.schema_version,
            "ledgerId": self.ledger_id,
            "operationId": self.operation_id,
            "userId": self.scope.user_id,
            "tenantId": self.scope.tenant_id,
            "partnerApplicationId": self.scope.partner_application_id,
            "issuer": self.scope.issuer,
            "scope": self.scope.scope,
            "resourceType": self.resource_type,
            "resourceRefDigest": self.resource_ref_digest,
            "expectedState": self.expected_state,
            "state": self.state,
            "version": self.version,
        }


@dataclass(frozen=True)
class RestoreReconciliation:
    status: str
    required: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()
    error_code: str | None = None


def resource_digest(resource_ref: str) -> str:
    if not isinstance(resource_ref, str) or not resource_ref:
        raise DeletionLedgerError("INVALID_RESOURCE_REFERENCE")
    return hashlib.sha256(resource_ref.encode("utf-8")).hexdigest()


class LocalDeletionLedger:
    """In-memory conditional ledger used by synthetic restore tests only."""

    def __init__(self) -> None:
        self._entries: dict[str, DeletionLedgerEntry] = {}

    def capture(self, *, operation_id: str, scope: LedgerScope,
                resource_type: str, resource_ref: str) -> DeletionLedgerEntry:
        scope.validate()
        digest = resource_digest(resource_ref)
        ledger_id = hashlib.sha256(
            f"{operation_id}|{scope.tenant_id}|{scope.user_id}|"
            f"{scope.partner_application_id}|{scope.issuer}|{scope.scope}|"
            f"{resource_type}".encode("utf-8")).hexdigest()
        entry = DeletionLedgerEntry(
            ledger_id=ledger_id, operation_id=operation_id, scope=scope,
            resource_type=resource_type, resource_ref_digest=digest,
        )
        existing = self._entries.get(ledger_id)
        if existing is not None and existing != entry:
            raise DeletionLedgerError("LEDGER_CONFLICT")
        self._entries[ledger_id] = existing or entry
        return self._entries[ledger_id]

    def mark_erasure_result(self, *, operation_id: str, scope: LedgerScope,
                            resource_type: str, resource_ref: str,
                            complete: bool) -> DeletionLedgerEntry:
        entry = self.capture(operation_id=operation_id, scope=scope,
                             resource_type=resource_type,
                             resource_ref=resource_ref)
        if not complete:
            return entry
        updated = replace(entry, state=EXPECTED_ABSENT, version=entry.version + 1)
        self._entries[entry.ledger_id] = updated
        return updated

    def reconcile_restore(self, *, operation_id: str, scope: LedgerScope,
                          restored_resources: Iterable[Mapping[str, str]]
                          ) -> RestoreReconciliation:
        scope.validate()
        relevant = [e for e in self._entries.values()
                    if e.operation_id == operation_id and e.scope == scope]
        if not relevant:
            return RestoreReconciliation("BLOCKED", error_code="MISSING_LEDGER_EVIDENCE")
        restored = []
        for resource in restored_resources:
            if not isinstance(resource, Mapping):
                return RestoreReconciliation("BLOCKED", error_code="UNKNOWN_INVENTORY")
            if resource.get("tenantId") != scope.tenant_id or resource.get("userId") != scope.user_id:
                continue
            if resource.get("partnerApplicationId") != scope.partner_application_id or resource.get("issuer") != scope.issuer:
                continue
            resource_type = resource.get("resourceType")
            resource_ref = resource.get("resourceRef")
            if resource_type not in KNOWN_RESOURCE_TYPES or not isinstance(resource_ref, str):
                return RestoreReconciliation("BLOCKED", error_code="UNKNOWN_INVENTORY")
            digest = resource_digest(resource_ref)
            if any(e.resource_type == resource_type and e.resource_ref_digest == digest
                   and e.state == EXPECTED_ABSENT for e in relevant):
                restored.append(f"{resource_type}:{digest}")
        missing = [e.ledger_id for e in relevant if e.state == EXPECTED_ABSENT]
        if restored:
            return RestoreReconciliation("RECONCILIATION_REQUIRED",
                                         required=tuple(missing),
                                         unexpected=tuple(restored),
                                         error_code="RESTORED_ERASED_RESOURCE")
        return RestoreReconciliation("CLEAN")

    def snapshot(self, *, operation_id: str | None = None) -> tuple[dict, ...]:
        entries = self._entries.values()
        if operation_id is not None:
            entries = (e for e in entries if e.operation_id == operation_id)
        return tuple(e.snapshot() for e in entries)


__all__ = ["DeletionLedgerError", "LedgerScope", "DeletionLedgerEntry",
           "RestoreReconciliation", "LocalDeletionLedger", "resource_digest",
           "EXPECTED_PRESENT", "EXPECTED_ABSENT"]
