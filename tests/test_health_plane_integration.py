"""
Integration-level tests: the health plane is actually EMITTED by the
runtime pipeline (Gate-02 P3).

`tests/test_health_plane.py` verifies the state machine in isolation.
These tests prove the wiring: real `process_record` calls against a fake
DynamoDB table produce the expected HEALTH_* transitions at the real
processing boundaries.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.event_hook import TriggerType
from agents.ecosystem.health_plane import Component, HealthTracker
from agents.ecosystem.registry import AgentRegistry
from agents.runtime.pipeline import process_record


def work_item(work_id="work-1", capability="reference.echo",
              agent_id="reference_agent",
              work_type="agent_reference_agent", tenant="tenant-test"):
    return {
        "workId": work_id,
        "type": work_type,
        "tenantId": tenant,
        "idempotencyKey": "key-%s" % work_id,
        "agentId": agent_id,
        "capability": capability,
        "payload": {"message": "hello"},
    }


def record(work, message_id="msg-1"):
    return {"messageId": message_id, "body": json.dumps(work)}


class FakeTable:
    """Minimal fake reproducing the conditional-write semantics used."""

    def __init__(self):
        self.items = {}
        self.updates = []

    def put_item(self, Item, ConditionExpression=None):
        key = Item["workId"]
        if ConditionExpression and "attribute_not_exists" in ConditionExpression:
            if key in self.items:
                err = Exception("conditional")
                err.response = {"Error": {"Code": "ConditionalCheckFailedException"}}
                raise err
        self.items[key] = Item
        return {}

    def get_item(self, Key):
        return {"Item": self.items.get(Key["workId"])} if Key.get("workId") in self.items else {}

    def update_item(self, Key, **kwargs):
        self.updates.append((Key, kwargs))
        return {"Attributes": self.items.get(Key["workId"], {})}

    def query(self, **kwargs):
        return {"Items": list(self.items.values())}


class RecordingTracker(HealthTracker):
    """HealthTracker that keeps every event it produced."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.emitted = []

    def _emit(self, trigger, *args, **kwargs):
        event = super()._emit(trigger, *args, **kwargs)
        self.emitted.append(event)
        return event


class TestPipelineEmitsHealthEvents(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.registry = AgentRegistry()
        self.tracker = RecordingTracker()

    def _run(self, work, message_id="msg-1"):
        return process_record(
            record(work, message_id),
            table=self.table,
            registry=self.registry,
            health_tracker=self.tracker,
        )

    def test_successful_run_emits_no_degraded(self):
        """Healthy processing must not fabricate a degradation."""
        self._run(work_item())
        types = [e.event_type for e in self.tracker.emitted]
        self.assertNotIn(TriggerType.HEALTH_DEGRADED, types)
        self.assertNotIn(TriggerType.HEALTH_RECOVERED, types)

    def test_recovery_after_degradation_emits_both(self):
        """The real Gate-02 scenario: fail, then succeed."""
        # Force a degradation directly, then process successfully.
        self.tracker.record_failure(
            Component.AGENT_EXECUTION, tenant_id="tenant-test",
            reason="AGENT_ERROR")
        self._run(work_item())
        types = [e.event_type for e in self.tracker.emitted]
        self.assertEqual(types, [
            TriggerType.HEALTH_DEGRADED,
            TriggerType.HEALTH_RECOVERED,
        ])

    def test_no_duplicate_recovery_across_successes(self):
        self.tracker.record_failure(
            Component.AGENT_EXECUTION, tenant_id="tenant-test")
        self._run(work_item(work_id="w1"), message_id="m1")
        self._run(work_item(work_id="w2"), message_id="m2")
        types = [e.event_type for e in self.tracker.emitted]
        self.assertEqual(types.count(TriggerType.HEALTH_RECOVERED), 1)

    def test_health_events_carry_work_identifiers(self):
        self.tracker.record_failure(
            Component.AGENT_EXECUTION, tenant_id="tenant-test")
        self._run(work_item(work_id="work-42", tenant="tenant-test"))
        recovered = [e for e in self.tracker.emitted
                     if e.event_type is TriggerType.HEALTH_RECOVERED]
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].work_id, "work-42")
        self.assertEqual(recovered[0].tenant_id, "tenant-test")

    def test_health_events_never_contain_payload(self):
        self._run(work_item())
        serialized = json.dumps([e.to_dict() for e in self.tracker.emitted])
        self.assertNotIn("hello", serialized)  # the payload message
        self.assertNotIn("payload", serialized)

    def test_absent_tracker_preserves_legacy_behaviour(self):
        """health_tracker=None must behave exactly as before P3."""
        result = process_record(record(work_item()), table=self.table,
                                registry=self.registry)
        self.assertEqual(result["status"], "COMPLETED")

    def test_entitlement_denial_is_not_a_degradation(self):
        """DENIED is correct behaviour, not an operational failure."""
        class DenyingResolver:
            def resolve_for_agent(self, user_id, agent_id, tenant_id=None):
                return None

        from agents.ecosystem.worker_authorization import (
            WorkerAuthDecision,
        )

        class DeniedResolver:
            def resolve_for_agent(self, user_id, agent_id, tenant_id=None):
                return [WorkerAuthDecision(
                    authorized=False,
                    reason="no entitlement",
                )]

        result = process_record(
            record(work_item()),
            table=self.table,
            registry=self.registry,
            entitlement_resolver=DeniedResolver(),
            health_tracker=self.tracker,
        )
        self.assertEqual(result["status"], "FAILED")
        self.assertTrue(result.get("denied"))
        self.assertEqual(
            [e.event_type for e in self.tracker.emitted
             if e.event_type is TriggerType.HEALTH_DEGRADED], [],
            "entitlement denial must not mark the runtime degraded")


if __name__ == "__main__":
    unittest.main()