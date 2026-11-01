"""R08-C0F-2D versioned legacy upload-ticket cutover evidence."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple


CUTOVER_BLOCKED = "BLOCKED"
CUTOVER_PROVEN = "PROVEN"


class UploadCutoverError(RuntimeError):
    pass


class UploadCutoverConflict(UploadCutoverError):
    pass


class UploadCutoverUnavailable(UploadCutoverError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return result if result.tzinfo else None


@dataclass(frozen=True)
class UploadCutoverEvidenceV1:
    expected_issuers: Tuple[str, ...]
    covered_issuers: Tuple[str, ...]
    expected_paths: Tuple[str, ...]
    covered_paths: Tuple[str, ...]
    ledger_registration_verified: bool
    unknown_legacy_tickets: bool
    historical_max_expiry: Optional[str]
    active_actions_known_zero: bool
    inventory_complete: bool
    inventory_empty: bool
    evidence_ref: str

    def reasons(self, *, now: Optional[datetime] = None) -> Tuple[str, ...]:
        reasons = []
        if not self.expected_issuers or set(self.covered_issuers) != set(self.expected_issuers):
            reasons.append("ISSUER_COVERAGE_INCOMPLETE")
        if not self.expected_paths or set(self.covered_paths) != set(self.expected_paths):
            reasons.append("UPLOAD_PATH_COVERAGE_INCOMPLETE")
        if not self.ledger_registration_verified:
            reasons.append("LEDGER_REGISTRATION_UNPROVEN")
        if self.unknown_legacy_tickets:
            reasons.append("UNKNOWN_LEGACY_TICKETS")
        expiry = _parse(self.historical_max_expiry)
        if expiry is None:
            reasons.append("HISTORICAL_MAX_EXPIRY_UNKNOWN")
        elif expiry > (now or datetime.now(timezone.utc)):
            reasons.append("HISTORICAL_TICKETS_MAY_BE_VALID")
        if not self.active_actions_known_zero:
            reasons.append("ACTIVE_UPLOAD_ACTIONS_UNKNOWN_OR_PRESENT")
        if not self.inventory_complete:
            reasons.append("FINAL_INVENTORY_INCOMPLETE")
        if not self.inventory_empty:
            reasons.append("FINAL_INVENTORY_NOT_EMPTY")
        if not self.evidence_ref or "://" in self.evidence_ref:
            reasons.append("EVIDENCE_REFERENCE_INVALID")
        return tuple(reasons)


@dataclass(frozen=True)
class UploadCutoverStateV1:
    cutover_id: str
    introduced_at: str
    effective_at: Optional[str]
    status: str
    version: int
    evidence: UploadCutoverEvidenceV1

    def evaluate(self, *, now: Optional[datetime] = None) -> "UploadCutoverStateV1":
        reasons = self.evidence.reasons(now=now)
        return replace(self, status=CUTOVER_PROVEN if not reasons else CUTOVER_BLOCKED)

    def public_dict(self) -> Dict[str, Any]:
        return {
            "cutoverId": self.cutover_id,
            "introducedAt": self.introduced_at,
            "effectiveAt": self.effective_at,
            "status": self.status,
            "version": self.version,
            "reasons": list(self.evidence.reasons()),
        }


class UploadCutoverRepository:
    """Versioned durable repository over an injected DynamoDB-shaped table."""

    def __init__(self, *, table: Any = None, table_name: Optional[str] = None,
                 enabled: Optional[bool] = None):
        self.table = table
        self.table_name = table_name or os.environ.get("UPLOAD_CUTOVER_TABLE")
        self.enabled = (os.environ.get(
            "ERASURE_UPLOAD_CUTOVER_ENABLED", "false").lower() == "true"
                        if enabled is None else bool(enabled))

    def _ensure(self):
        if not self.enabled or self.table is None or not self.table_name:
            raise UploadCutoverUnavailable("upload cutover repository unavailable")

    def save(self, state: UploadCutoverStateV1, *, expected_version: int):
        self._ensure()
        item = {
            "resourceId": state.cutover_id, "resourceType": "UploadCutoverV1",
            "introducedAt": state.introduced_at,
            "effectiveAt": state.effective_at,
            "status": state.status, "version": state.version,
            "evidence": {
                "expectedIssuers": list(state.evidence.expected_issuers),
                "coveredIssuers": list(state.evidence.covered_issuers),
                "expectedPaths": list(state.evidence.expected_paths),
                "coveredPaths": list(state.evidence.covered_paths),
                "ledgerRegistrationVerified": state.evidence.ledger_registration_verified,
                "unknownLegacyTickets": state.evidence.unknown_legacy_tickets,
                "historicalMaxExpiry": state.evidence.historical_max_expiry,
                "activeActionsKnownZero": state.evidence.active_actions_known_zero,
                "inventoryComplete": state.evidence.inventory_complete,
                "inventoryEmpty": state.evidence.inventory_empty,
                "evidenceRef": state.evidence.evidence_ref,
            },
        }
        try:
            condition = "attribute_not_exists(resourceId)" if expected_version == 0 \
                else "resourceType = :rt AND version = :v"
            values = {} if expected_version == 0 else {
                ":rt": "UploadCutoverV1", ":v": expected_version}
            kwargs = {"Item": item, "ConditionExpression": condition}
            if values:
                kwargs["ExpressionAttributeValues"] = values
            self.table.put_item(**kwargs)
        except Exception as exc:
            if "ConditionalCheckFailed" in str(exc) or "conditional" in str(exc).lower():
                raise UploadCutoverConflict("cutover version conflict") from exc
            raise UploadCutoverUnavailable("cutover persistence failed") from exc
        return state


__all__ = [
    "CUTOVER_BLOCKED", "CUTOVER_PROVEN", "UploadCutoverEvidenceV1",
    "UploadCutoverStateV1", "UploadCutoverRepository", "UploadCutoverError",
    "UploadCutoverConflict", "UploadCutoverUnavailable",
]
