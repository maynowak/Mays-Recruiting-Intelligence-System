"""Tests Gate 07: zentrale Agent-Status-Normalisierung (fail-closed).

Alle Faelle verwenden die zentrale Entscheidung
(agents.ecosystem.agent_status) — keine zweite Test-Logik.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.agent_status import (  # noqa: E402
    is_executable_status,
    normalize_agent_status,
)
from agents.ecosystem.eligibility import check_eligibility  # noqa: E402
from agents.ecosystem.registry import (  # noqa: E402
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
)


def _descriptor(status):
    return AgentDescriptor(agent_id="test-agent", name="t", version="1",
                           status=status, capabilities=["test.cap"])


class TestNormalize(unittest.TestCase):
    def test_active_executable(self):
        self.assertTrue(is_executable_status("ACTIVE"))

    def test_active_lowercase_executable(self):
        self.assertTrue(is_executable_status("active"))

    def test_active_padded_executable(self):
        self.assertTrue(is_executable_status(" Active "))

    def test_inactive_blocked(self):
        self.assertFalse(is_executable_status("INACTIVE"))

    def test_deprecated_blocked(self):
        self.assertFalse(is_executable_status("DEPRECATED"))

    def test_retired_blocked(self):
        self.assertFalse(is_executable_status("RETIRED"))

    def test_registered_blocked(self):
        self.assertFalse(is_executable_status("REGISTERED"))

    def test_available_blocked(self):
        self.assertFalse(is_executable_status("AVAILABLE"))

    def test_failed_blocked(self):
        self.assertFalse(is_executable_status("FAILED"))

    def test_unknown_blocked(self):
        self.assertFalse(is_executable_status("NOPE"))
        self.assertIsNone(normalize_agent_status("NOPE"))

    def test_empty_blocked(self):
        self.assertFalse(is_executable_status(""))
        self.assertFalse(is_executable_status("   "))

    def test_none_blocked(self):
        self.assertFalse(is_executable_status(None))
        self.assertIsNone(normalize_agent_status(None))

    def test_non_string_blocked(self):
        self.assertFalse(is_executable_status(123))

    def test_enum_members(self):
        self.assertTrue(is_executable_status(AgentStatus.ACTIVE))
        self.assertFalse(is_executable_status(AgentStatus.INACTIVE))
        self.assertEqual(normalize_agent_status("active"), AgentStatus.ACTIVE)


class TestEligibilityStatus(unittest.TestCase):
    def test_active_eligible(self):
        check = check_eligibility("test-agent", _descriptor(AgentStatus.ACTIVE),
                                  capability="test.cap")
        self.assertTrue(check.eligible)

    def test_inactive_ineligible(self):
        check = check_eligibility("test-agent", _descriptor(AgentStatus.INACTIVE),
                                  capability="test.cap")
        self.assertFalse(check.eligible)

    def test_unknown_ineligible(self):
        check = check_eligibility("test-agent", _descriptor(None),
                                  capability="test.cap")
        self.assertFalse(check.eligible)


class TestPipelineStatusBoundary(unittest.TestCase):
    def _run(self, status, agent_id="blocked-agent", capability="test.blocked-cap"):
        from agents.agent_body import AgentBody
        from agents.runtime.pipeline import process_record

        registry = AgentRegistry()
        registry.register(agent_id, AgentDescriptor(
            agent_id=agent_id, name="b", version="1", status=status,
            capabilities=[capability]))
        body = AgentBody()

        class FakeTable:
            class ConditionalFailed(Exception):
                @property
                def response(self):
                    return {"Error": {"Code": "ConditionalCheckFailedException"}}

            def __init__(self):
                self.items = {}

            def put_item(self, Item, ConditionExpression=None):
                if (ConditionExpression == "attribute_not_exists(workId)"
                        and Item["workId"] in self.items):
                    raise FakeTable.ConditionalFailed()
                self.items[Item["workId"]] = dict(Item)

            def get_item(self, Key):
                item = self.items.get(Key["workId"])
                return {"Item": dict(item)} if item else {}

        table = FakeTable()
        work = {"workId": "work-blocked-1", "type": "agent_x",
                "tenantId": "t", "idempotencyKey": "k1",
                "agentId": agent_id, "capability": capability}
        record = {"messageId": "msg-1", "body": json.dumps(work)}
        with self.assertRaises(ValueError):
            process_record(record, table=table, registry=registry, body=body)
        running = [i for i in table.items.values()
                   if i.get("status") == "RUNNING"]
        self.assertEqual(running, [])

    def test_pipeline_does_not_execute_inactive(self):
        self._run(AgentStatus.INACTIVE)

    def test_pipeline_does_not_execute_unknown(self):
        self._run(None, agent_id="unknown-agent",
                   capability="test.unknown-cap")


class TestActiveBehaviorIntact(unittest.TestCase):
    def test_reference_echo_still_runs(self):
        from agents.agent_body import AgentBody
        from agents.ecosystem.registry import AgentRegistry
        from agents.runtime.pipeline import process_record

        registry = AgentRegistry()
        body = AgentBody()
        work = {"workId": "work-active-1", "type": "agent_reference_agent",
                "tenantId": "t", "idempotencyKey": "k-active",
                "agentId": "reference_agent", "capability": "reference.echo",
                "payload": {"message": "hello"}}
        record = {"messageId": "msg-a", "body": json.dumps(work)}

        class FakeTable:
            class ConditionalFailed(Exception):
                @property
                def response(self):
                    return {"Error": {"Code": "ConditionalCheckFailedException"}}

            def __init__(self):
                self.items = {}

            def put_item(self, Item, ConditionExpression=None):
                if (ConditionExpression == "attribute_not_exists(workId)"
                        and Item["workId"] in self.items):
                    raise FakeTable.ConditionalFailed()
                self.items[Item["workId"]] = dict(Item)

            def get_item(self, Key):
                item = self.items.get(Key["workId"])
                return {"Item": dict(item)} if item else {}

            def update_item(self, Key, UpdateExpression,
                            ExpressionAttributeNames=None,
                            ExpressionAttributeValues=None):
                pass

        table = FakeTable()
        out = process_record(record, table=table, registry=registry, body=body)
        self.assertEqual(out["workId"], "work-active-1")


if __name__ == "__main__":
    unittest.main()
