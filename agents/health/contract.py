"""Health State Contract implementation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class HealthStatus(str, Enum):
    ALIVE = "ALIVE"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


@dataclass(frozen=True)
class HealthState:
    component_id: str
    component_type: str
    status: HealthStatus
    observed_at: datetime
    valid_until: datetime
    source: str

    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        if self.observed_at.tzinfo is None:
            self.observed_at = self.observed_at.replace(tzinfo=timezone.utc)
        if self.valid_until.tzinfo is None:
            self.valid_until = self.valid_until.replace(tzinfo=timezone.utc)
        return self.status == HealthStatus.ALIVE and now <= self.valid_until

    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        return now > self.valid_until


def evaluate_overall(states: list[HealthState]) -> bool:
    if not states:
        return False
    return all(s.is_valid() for s in states)


def validate_state(state: HealthState) -> None:
    if not state.component_id or not state.component_type:
        raise ValueError("component_id and component_type required")
    if not isinstance(state.status, HealthStatus):
        raise ValueError("invalid status")
    if state.observed_at > state.valid_until:
        raise ValueError("observed_at must be <= valid_until")
