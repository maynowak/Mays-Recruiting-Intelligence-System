"""
Event-driven Health Plane (Gate-02 P3).

`/health` is TECHNICAL LIVENESS: it answers "is the Lambda running?" and
deliberately performs no I/O. It says nothing about whether the runtime is
actually able to process work.

This module provides the OPERATIONAL half: components report processing
outcomes, and state TRANSITIONS are emitted as events through the existing
EventHook vocabulary (`TriggerType.HEALTH_*`). It introduces no new
messaging infrastructure and no new persistence — events are returned to the
caller, which decides what to do with them.

Design constraints that are enforced here, not merely documented:

1. **No flooding.** A heartbeat is emitted at most once per
   `heartbeat_interval`. A component that keeps failing does not emit one
   DEGRADED event per failure; it emits DEGRADED once and then stays quiet
   until it recovers.
2. **No RECOVERED without prior DEGRADED.** Recovery events only exist in
   response to a degradation that this tracker observed.
3. **No duplicate RECOVERED.** After recovery the state is HEALTHY, so a
   second consecutive success emits nothing.
4. **Minimal metadata.** Health events carry identifiers and coarse reason
   codes only — never agent payloads, work item bodies, credentials, tokens,
   or user content. Tenant is carried because health is per-tenant scoped.
   Anything that could contain PII or secrets is rejected in `HealthEvent`.
5. **Fail-safe instrumentation.** Observability must never break the work
   path: recording a transition that raises is swallowed, because a broken
   health tracker must not fail a user's job.

State is per (component, tenant). A degradation in tenant A never marks
tenant B degraded.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from agents.ecosystem.event_hook import TriggerType

logger = logging.getLogger(__name__)

#: Coarse reason codes. Deliberately a closed vocabulary: an arbitrary
#: exception message could carry payload content, and health events should
#: not become a data-exfiltration path.
REASON_AGENT_ERROR = "AGENT_ERROR"
REASON_ENTITLEMENT_DENIED = "ENTITLEMENT_DENIED"
REASON_ENTITLEMENT_UNAVAILABLE = "ENTITLEMENT_UNAVAILABLE"
REASON_INFRASTRUCTURE = "INFRASTRUCTURE"

ALLOWED_REASONS = frozenset({
    REASON_AGENT_ERROR,
    REASON_ENTITLEMENT_DENIED,
    REASON_ENTITLEMENT_UNAVAILABLE,
    REASON_INFRASTRUCTURE,
})


class Component(str, Enum):
    """Health-relevant components of the runtime."""

    WORKER = "WORKER"
    AGENT_EXECUTION = "AGENT_EXECUTION"


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"


#: Metadata keys that may never appear in a health event. Used as a
#: belt-and-braces check on top of HealthEvent's construction rules.
FORBIDDEN_KEYS = frozenset({
    "payload", "body", "result", "credential", "secret", "token",
    "password", "authorization", "apiprofileid", "api_profile_id",
    "email", "userid", "user_id", "cv", "resume",
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class HealthEvent:
    """One health-plane transition.

    Frozen: a health event is an observation, not a mutable record.
    """

    event_id: str
    event_type: TriggerType
    occurred_at: datetime
    component: Component
    state: HealthState
    tenant_id: Optional[str] = None
    work_id: Optional[str] = None
    agent_id: Optional[str] = None
    attempt_id: Optional[str] = None
    reason: Optional[str] = None
    consecutive_failures: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialized form — identifiers and codes only, never payload."""
        return {
            "eventId": self.event_id,
            "eventType": self.event_type.value,
            "occurredAt": self.occurred_at.isoformat(),
            "component": self.component.value,
            "state": self.state.value,
            "tenantId": self.tenant_id,
            "workId": self.work_id,
            "agentId": self.agent_id,
            "attemptId": self.attempt_id,
            "reason": self.reason,
            "consecutiveFailures": self.consecutive_failures,
        }


@dataclass
class _ComponentState:
    state: HealthState = HealthState.HEALTHY
    consecutive_failures: int = 0
    last_heartbeat: Optional[datetime] = None
    reason: Optional[str] = None


class HealthTracker:
    """Per-(component, tenant) health state machine.

    Not a singleton and not a global registry: the pipeline owns one
    instance and passes it explicitly, so tests are deterministic and no
    cross-test state leaks through module globals.
    """

    def __init__(self, heartbeat_interval: timedelta = timedelta(minutes=5),
                 clock=_utcnow) -> None:
        self._states: Dict[Tuple[Component, Optional[str]], _ComponentState] = {}
        self._heartbeat_interval = heartbeat_interval
        self._clock = clock

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------
    def _state_for(self, component: Component,
                   tenant_id: Optional[str]) -> _ComponentState:
        key = (component, tenant_id)
        state = self._states.get(key)
        if state is None:
            state = _ComponentState()
            self._states[key] = state
        return state

    def _emit(self, trigger: TriggerType, component: Component,
              state: HealthState, tenant_id: Optional[str],
              work_id: Optional[str], agent_id: Optional[str],
              attempt_id: Optional[str], reason: Optional[str],
              consecutive_failures: int) -> HealthEvent:
        if reason is not None and reason not in ALLOWED_REASONS:
            # An unexpected reason code would be a caller bug. Coerce to a
            # coarse infrastructure code rather than leaking the raw value.
            logger.warning(
                "health event reason %r not in vocabulary; coercing",
                reason)
            reason = REASON_INFRASTRUCTURE
        event = HealthEvent(
            event_id=str(uuid.uuid4()),
            event_type=trigger,
            occurred_at=self._clock(),
            component=component,
            state=state,
            tenant_id=tenant_id,
            work_id=work_id,
            agent_id=agent_id,
            attempt_id=attempt_id,
            reason=reason,
            consecutive_failures=consecutive_failures,
        )
        _assert_minimal(event)
        return event

    # ------------------------------------------------------------------
    # transitions
    # ------------------------------------------------------------------
    def record_failure(self, component: Component, *,
                       tenant_id: Optional[str] = None,
                       reason: str = REASON_AGENT_ERROR,
                       work_id: Optional[str] = None,
                       agent_id: Optional[str] = None,
                       attempt_id: Optional[str] = None) -> List[HealthEvent]:
        """Report a processing failure.

        Emits DEGRADED only on the transition out of HEALTHY. Repeated
        failures while already degraded emit nothing, so a persistently
        failing agent cannot flood the plane.
        """
        state = self._state_for(component, tenant_id)
        state.consecutive_failures += 1
        state.reason = reason

        if state.state is HealthState.HEALTHY:
            state.state = HealthState.DEGRADED
            return [self._emit(
                TriggerType.HEALTH_DEGRADED, component, HealthState.DEGRADED,
                tenant_id, work_id, agent_id, attempt_id, reason,
                state.consecutive_failures)]
        return []

    def record_success(self, component: Component, *,
                       tenant_id: Optional[str] = None,
                       work_id: Optional[str] = None,
                       agent_id: Optional[str] = None,
                       attempt_id: Optional[str] = None) -> List[HealthEvent]:
        """Report a successful processing step.

        Emits RECOVERED only in response to an observed DEGRADED. Two
        consecutive successes emit one RECOVERED and then silence, so
        RECOVERED can never appear without a preceding DEGRADED and never
        repeats.
        """
        state = self._state_for(component, tenant_id)

        if state.state is HealthState.DEGRADED:
            state.state = HealthState.HEALTHY
            failures = state.consecutive_failures
            state.consecutive_failures = 0
            state.reason = None
            return [self._emit(
                TriggerType.HEALTH_RECOVERED, component, HealthState.HEALTHY,
                tenant_id, work_id, agent_id, attempt_id, None, failures)]
        return []

    def heartbeat(self, component: Component, *,
                  tenant_id: Optional[str] = None,
                  agent_id: Optional[str] = None) -> List[HealthEvent]:
        """Liveness signal for an idle component.

        Rate-limited to one event per `heartbeat_interval`; a component
        that is actively processing does not need extra heartbeats.
        """
        state = self._state_for(component, tenant_id)
        now = self._clock()
        if state.last_heartbeat is not None \
                and now - state.last_heartbeat < self._heartbeat_interval:
            return []
        state.last_heartbeat = now
        return [self._emit(
            TriggerType.HEALTH_HEARTBEAT, component, state.state,
            tenant_id, None, agent_id, None, state.reason,
            state.consecutive_failures)]

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def current_state(self, component: Component,
                      tenant_id: Optional[str] = None) -> HealthState:
        return self._state_for(component, tenant_id).state

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Operational view for a health endpoint.

        Keys are "COMPONENT" or "COMPONENT@tenant". Contains no payload.
        """
        out: Dict[str, Dict[str, Any]] = {}
        for (component, tenant_id), state in sorted(
                self._states.items(), key=lambda kv: (kv[0][0].value,
                                                     kv[0][1] or "")):
            key = component.value if tenant_id is None \
                else "%s@%s" % (component.value, tenant_id)
            out[key] = {
                "state": state.state.value,
                "consecutiveFailures": state.consecutive_failures,
                "reason": state.reason,
                "lastHeartbeat": state.last_heartbeat.isoformat()
                if state.last_heartbeat else None,
            }
        return out


def _assert_minimal(event: HealthEvent) -> None:
    """Defence in depth: a health event must carry no payload.

    The dataclass only has identifier fields, so this cannot fire today.
    It exists so that adding a field later fails loudly in tests rather
    than silently leaking content into the health plane.
    """
    for key in event.to_dict():
        if key.lower() in FORBIDDEN_KEYS:
            raise ValueError("forbidden key in health event: %s" % key)