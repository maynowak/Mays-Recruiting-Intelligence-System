"""In-memory conditional recovery repository for local synthetic tests only."""

from __future__ import annotations

from dataclasses import replace
from .privacy_recovery_contract import RecoveryContractError, RecoveryPlanV1, recovery_fingerprint


class LocalRecoveryRepository:
    def __init__(self) -> None:
        self._plans: dict[str, tuple[str, RecoveryPlanV1]] = {}

    def create(self, plan: RecoveryPlanV1) -> RecoveryPlanV1:
        existing = self._plans.get(plan.recovery_id)
        fingerprint = recovery_fingerprint(plan)
        if existing:
            if existing[0] != fingerprint:
                raise RecoveryContractError("RECOVERY_ID_CONFLICT")
            return existing[1]
        self._plans[plan.recovery_id] = (fingerprint, plan)
        return plan

    def get(self, recovery_id: str) -> RecoveryPlanV1:
        try:
            return self._plans[recovery_id][1]
        except KeyError as exc:
            raise RecoveryContractError("RECOVERY_NOT_FOUND") from exc

    def complete_phase(self, recovery_id: str, phase: str, *, now: str,
                       expected_version: int, cursor_ref: str | None = None) -> RecoveryPlanV1:
        plan = self.get(recovery_id)
        updated = plan.complete_phase(phase, now=now,
                                      expected_version=expected_version,
                                      cursor_ref=cursor_ref)
        self._plans[recovery_id] = (self._plans[recovery_id][0], updated)
        return updated


__all__ = ["LocalRecoveryRepository"]
