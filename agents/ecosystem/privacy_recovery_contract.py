"""Versioned, local-only restore/reconciliation contract for R08."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Mapping


SCHEMA_VERSION = 1
RECOVERY_STATUSES = frozenset({"PLANNED", "RESTORING", "REPLAYING", "RECONCILED", "BLOCKED", "FAILED"})
PHASES = ("RESTORE_STAGING", "REPLAY_DELETIONS", "VERIFY_CREDENTIAL_REVOCATION",
          "VERIFY_SUBJECT_INACCESSIBILITY", "RECONCILED", "PROMOTION_GATE")
CHECKPOINT_STATES = frozenset({"NOT_STARTED", "IN_PROGRESS", "COMPLETED"})
_OPAQUE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


class RecoveryContractError(ValueError):
    pass


def _opaque(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise RecoveryContractError(f"INVALID_{name.upper()}")
    lowered = value.lower()
    if any(token in lowered for token in ("arn:", "s3://", "https://", "secret", "token", "password")):
        raise RecoveryContractError(f"SENSITIVE_{name.upper()}")
    if not _OPAQUE.fullmatch(value):
        raise RecoveryContractError(f"INVALID_{name.upper()}")
    return value


@dataclass(frozen=True)
class RecoveryCheckpointV1:
    phase: str
    state: str = "NOT_STARTED"
    cursor_ref: str | None = None
    last_resource_ref: str | None = None
    attempt: int = 0
    version: int = 1
    updated_at: str = ""
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecoveryContractError("UNSUPPORTED_SCHEMA_VERSION")
        if self.phase not in PHASES or self.state not in CHECKPOINT_STATES:
            raise RecoveryContractError("INVALID_CHECKPOINT")
        if self.attempt < 0 or self.version < 1 or not self.updated_at:
            raise RecoveryContractError("INVALID_CHECKPOINT_VERSION")
        if self.cursor_ref is not None:
            _opaque(self.cursor_ref, "cursor_ref")
        if self.last_resource_ref is not None:
            _opaque(self.last_resource_ref, "last_resource_ref")


@dataclass(frozen=True)
class RecoveryPlanV1:
    recovery_id: str
    source_snapshot_ref: str
    restore_point: str
    deletion_ledger_ref: str
    status: str = "PLANNED"
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    target: str = "STAGING"
    phases: Mapping[str, RecoveryCheckpointV1] | None = None
    promotion_eligible: bool = False
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecoveryContractError("UNSUPPORTED_SCHEMA_VERSION")
        for value, name in ((self.recovery_id, "recovery_id"),
                            (self.source_snapshot_ref, "source_snapshot_ref"),
                            (self.deletion_ledger_ref, "deletion_ledger_ref")):
            _opaque(value, name)
        if self.target != "STAGING" or self.status not in RECOVERY_STATUSES:
            raise RecoveryContractError("INVALID_RECOVERY_TARGET_OR_STATUS")
        if self.version < 1 or not self.created_at or not self.updated_at:
            raise RecoveryContractError("INVALID_RECOVERY_VERSION")
        try:
            parsed_restore_point = datetime.fromisoformat(self.restore_point.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError) as exc:
            raise RecoveryContractError("INVALID_RESTORE_POINT") from exc
        if parsed_restore_point.tzinfo is None or parsed_restore_point.utcoffset() is None:
            raise RecoveryContractError("INVALID_RESTORE_POINT")
        phases = self.phases or {}
        if any(key not in PHASES for key in phases) or any(
                checkpoint.phase != key for key, checkpoint in phases.items()):
            raise RecoveryContractError("INVALID_RECOVERY_PHASES")
        if self.promotion_eligible and not all(
                phases.get(phase) and phases[phase].state == "COMPLETED"
                for phase in PHASES):
            raise RecoveryContractError("PROMOTION_REQUIRES_COMPLETED_PHASES")

    def complete_phase(self, phase: str, *, now: str, expected_version: int,
                       cursor_ref: str | None = None) -> "RecoveryPlanV1":
        if expected_version != self.version:
            raise RecoveryContractError("STALE_RECOVERY_VERSION")
        if phase not in PHASES:
            raise RecoveryContractError("INVALID_RECOVERY_PHASE")
        phases = dict(self.phases or {})
        next_phase = next((candidate for candidate in PHASES
                           if not (phases.get(candidate)
                                   and phases[candidate].state == "COMPLETED")), None)
        if phase != next_phase:
            raise RecoveryContractError("INVALID_PHASE_ORDER")
        phases[phase] = RecoveryCheckpointV1(
            phase=phase, state="COMPLETED", cursor_ref=cursor_ref,
            attempt=(phases[phase].attempt + 1 if phase in phases else 1),
            version=(phases[phase].version + 1 if phase in phases else 1),
            updated_at=now)
        all_complete = all(phases.get(item) and phases[item].state == "COMPLETED" for item in PHASES)
        return replace(self, phases=phases, status="RECONCILED" if all_complete else "REPLAYING",
                       version=self.version + 1, updated_at=now,
                       promotion_eligible=all_complete)


def recovery_fingerprint(plan: RecoveryPlanV1) -> str:
    material = "|".join((plan.recovery_id, plan.source_snapshot_ref,
                         plan.restore_point, plan.deletion_ledger_ref))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


__all__ = ["SCHEMA_VERSION", "RecoveryContractError", "RecoveryCheckpointV1",
           "RecoveryPlanV1", "recovery_fingerprint", "PHASES"]
