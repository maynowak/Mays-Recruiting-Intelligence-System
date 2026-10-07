"""
Tests for the event-driven Health Plane (Gate-02 P3).

The `TriggerType.HEALTH_*` members existed as enum values with nothing
emitting them. These tests pin the transition semantics that the runtime
relies on, and the anti-flooding / anti-leak guarantees.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.event_hook import TriggerType
from agents.ecosystem.health_plane import (
    ALLOWED_REASONS,
    Component,
    HealthState,
    HealthTracker,
    REASON_AGENT_ERROR,
)


class _Clock:
    """Manually advanced clock — deterministic heartbeat tests."""

    def __init__(self, start=None):
        self.now = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)
        return self.now


class TestDegradedTransition:
    def test_first_failure_emits_degraded(self):
        tracker = HealthTracker()
        events = tracker.record_failure(Component.AGENT_EXECUTION)
        assert len(events) == 1
        assert events[0].event_type is TriggerType.HEALTH_DEGRADED
        assert events[0].state is HealthState.DEGRADED
        assert tracker.current_state(Component.AGENT_EXECUTION) \
            is HealthState.DEGRADED

    def test_repeated_failures_do_not_flood(self):
        """DEGRADED is a TRANSITION, not a per-failure notification."""
        tracker = HealthTracker()
        for _ in range(50):
            events = tracker.record_failure(Component.AGENT_EXECUTION)
        assert events == []
        assert tracker.current_state(Component.AGENT_EXECUTION) \
            is HealthState.DEGRADED

    def test_consecutive_failure_count_is_tracked(self):
        tracker = HealthTracker()
        tracker.record_failure(Component.AGENT_EXECUTION)
        for _ in range(4):
            tracker.record_failure(Component.AGENT_EXECUTION)
        events = tracker.record_success(Component.AGENT_EXECUTION)
        assert events[0].consecutive_failures == 5


class TestRecoveredTransition:
    def test_success_after_degraded_emits_recovered(self):
        tracker = HealthTracker()
        tracker.record_failure(Component.AGENT_EXECUTION)
        events = tracker.record_success(Component.AGENT_EXECUTION)
        assert len(events) == 1
        assert events[0].event_type is TriggerType.HEALTH_RECOVERED
        assert events[0].state is HealthState.HEALTHY
        assert tracker.current_state(Component.AGENT_EXECUTION) \
            is HealthState.HEALTHY

    def test_recovered_requires_prior_degraded(self):
        """No RECOVERED without an observed DEGRADED."""
        tracker = HealthTracker()
        for _ in range(10):
            events = tracker.record_success(Component.AGENT_EXECUTION)
        assert events == []

    def test_no_duplicate_recovered(self):
        tracker = HealthTracker()
        tracker.record_failure(Component.AGENT_EXECUTION)
        assert len(tracker.record_success(Component.AGENT_EXECUTION)) == 1
        assert tracker.record_success(Component.AGENT_EXECUTION) == []
        assert tracker.record_success(Component.AGENT_EXECUTION) == []

    def test_full_cycle_emits_one_degraded_one_recovered(self):
        tracker = HealthTracker()
        emitted = []
        emitted += tracker.record_failure(Component.AGENT_EXECUTION)
        emitted += tracker.record_failure(Component.AGENT_EXECUTION)
        emitted += tracker.record_success(Component.AGENT_EXECUTION)
        emitted += tracker.record_success(Component.AGENT_EXECUTION)
        assert [e.event_type for e in emitted] == [
            TriggerType.HEALTH_DEGRADED, TriggerType.HEALTH_RECOVERED]


class TestHeartbeat:
    def test_first_heartbeat_emits(self):
        tracker = HealthTracker()
        events = tracker.heartbeat(Component.WORKER)
        assert len(events) == 1
        assert events[0].event_type is TriggerType.HEALTH_HEARTBEAT

    def test_heartbeat_is_rate_limited(self):
        clock = _Clock()
        tracker = HealthTracker(clock=clock)
        assert len(tracker.heartbeat(Component.WORKER)) == 1
        # within interval -> silent
        clock.advance(minutes=1)
        assert tracker.heartbeat(Component.WORKER) == []
        clock.advance(minutes=1)
        assert tracker.heartbeat(Component.WORKER) == []
        # interval elapsed -> emits again
        clock.advance(minutes=4)
        assert len(tracker.heartbeat(Component.WORKER)) == 1

    def test_heartbeat_reports_current_state(self):
        tracker = HealthTracker()
        tracker.record_failure(Component.WORKER)
        events = tracker.heartbeat(Component.WORKER)
        assert events[0].state is HealthState.DEGRADED


class TestTenantIsolation:
    def test_failure_in_one_tenant_does_not_degrade_another(self):
        tracker = HealthTracker()
        tracker.record_failure(Component.AGENT_EXECUTION, tenant_id='tenant-a')
        assert tracker.current_state(Component.AGENT_EXECUTION, 'tenant-a') \
            is HealthState.DEGRADED
        assert tracker.current_state(Component.AGENT_EXECUTION, 'tenant-b') \
            is HealthState.HEALTHY

    def test_recovery_is_scoped_to_the_tenant(self):
        tracker = HealthTracker()
        tracker.record_failure(Component.AGENT_EXECUTION, tenant_id='tenant-a')
        events = tracker.record_success(Component.AGENT_EXECUTION,
                                        tenant_id='tenant-b')
        assert events == []  # tenant-b was never degraded
        assert tracker.current_state(Component.AGENT_EXECUTION, 'tenant-a') \
            is HealthState.DEGRADED


class TestMinimalMetadata:
    def test_event_contains_no_payload_fields(self):
        tracker = HealthTracker()
        events = tracker.record_failure(
            Component.AGENT_EXECUTION, tenant_id='t1', work_id='w1',
            agent_id='a1', attempt_id='0')
        payload = events[0].to_dict()
        assert set(payload) == {
            'eventId', 'eventType', 'occurredAt', 'component', 'state',
            'tenantId', 'workId', 'agentId', 'attemptId', 'reason',
            'consecutiveFailures'}

    def test_no_user_or_credential_identifiers_leak(self):
        """Health events must never carry user identity or credentials."""
        tracker = HealthTracker()
        events = tracker.record_failure(
            Component.AGENT_EXECUTION, tenant_id='t1')
        serialized = str(events[0].to_dict()).lower()
        for forbidden in ('userid', 'user_id', 'email', 'credential',
                          'secret', 'token', 'password', 'apiprofile'):
            assert forbidden not in serialized

    def test_unknown_reason_code_is_coerced_not_leaked(self):
        """A raw exception message must never reach the health plane."""
        tracker = HealthTracker()
        secret = "postgres://user:hunter2@host/db"
        events = tracker.record_failure(Component.AGENT_EXECUTION,
                                        reason=secret)
        assert events[0].reason == 'INFRASTRUCTURE'
        assert 'hunter2' not in str(events[0].to_dict())

    def test_known_reason_codes_pass_through(self):
        # Je eigener Tracker: nach der ersten Degradierung emittiert
        # record_failure bewusst nichts mehr (anti-flooding), was hier
        # nichts zu pruefen haette.
        for reason in ALLOWED_REASONS:
            tracker = HealthTracker()
            events = tracker.record_failure(Component.AGENT_EXECUTION,
                                            reason=reason)
            assert len(events) == 1, reason
            assert events[0].reason == reason


class TestSnapshot:
    def test_snapshot_keys_include_tenant(self):
        tracker = HealthTracker()
        tracker.record_failure(Component.WORKER)
        tracker.record_failure(Component.AGENT_EXECUTION, tenant_id='t1')
        snap = tracker.snapshot()
        assert snap['WORKER']['state'] == 'DEGRADED'
        assert snap['AGENT_EXECUTION@t1']['state'] == 'DEGRADED'

    def test_snapshot_has_no_sensitive_data(self):
        tracker = HealthTracker()
        tracker.record_failure(Component.AGENT_EXECUTION, tenant_id='t1')
        assert 'payload' not in str(tracker.snapshot()).lower()


class TestInstrumentationIsFailSafe:
    def test_pipeline_never_fails_because_of_health_tracking(self):
        """A broken tracker must not break the work path."""
        from agents.runtime import pipeline

        class ExplodingTracker:
            def record_failure(self, *a, **kw):
                raise RuntimeError("health subsystem down")

            def record_success(self, *a, **kw):
                raise RuntimeError("health subsystem down")

        record = {
            "messageId": "m1",
            "body": '{"workId":"w1","type":"t","tenantId":"t1",'
                    '"idempotencyKey":"k1","payload":{}}'
        }
        # No table -> _resolve_table() may fail; the point is that a health
        # error is not the thing that surfaces. Use a permissive harness.
        try:
            pipeline.process_record(record, table=object(),
                                    health_tracker=ExplodingTracker())
        except Exception as exc:
            assert "health subsystem down" not in str(exc)