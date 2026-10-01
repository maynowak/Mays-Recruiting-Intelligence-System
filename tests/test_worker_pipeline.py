"""Tests fuer Gate-5-Pipeline: Worker -> Agent Body -> Ecosystem (Gate 5).

Belegt mit Fake-Tabelle (Conditional-Write-Semantik) und echten
Registry-/Discovery-/Eligibility-/Router-/Engine-Klassen:
- Happy Path ueber Ecosystem-Auswahl (kein hartcodierter Agent)
- Duplikat -> kein zweiter fachlicher Run
- Retry -> neuer Attempt desselben Processings
- Ungueltig/kein Agent -> keine Registrierung, keine Ausfuehrung
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_body import AgentBody
from agents.ecosystem.registry import AgentRegistry
from agents.runtime.pipeline import process_record


def work_item(work_id="work-1", capability="reference.echo", agent_id="reference_agent",
              work_type="agent_reference_agent", tenant="tenant-test"):
    return {
        "workId": work_id,
        "type": work_type,
        "tenantId": tenant,
        "idempotencyKey": f"key-{work_id}",
        "agentId": agent_id,
        "capability": capability,
        "payload": {"message": "hello"},
    }


def record(work, message_id="msg-1"):
    import json
    return {"messageId": message_id, "body": json.dumps(work)}


class FakeTable:
    """DDB-Tabelle mit Conditional-Write-Semantik."""

    class ConditionalFailed(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "ConditionalCheckFailedException"}}

    def __init__(self):
        self.items = {}
        self.puts = 0

    def put_item(self, Item, ConditionExpression=None):
        if ConditionExpression == "attribute_not_exists(workId)" and Item["workId"] in self.items:
            raise FakeTable.ConditionalFailed()
        self.items[Item["workId"]] = dict(Item)
        self.puts += 1

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None):
        item = self.items[Key["workId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        # minimaler Parser fuer die in pipeline.py verwendeten SET/REMOVE-Ausdruecke
        expr = UpdateExpression.split("REMOVE")[0].strip()
        set_part = expr[len("SET "):] if expr.startswith("SET ") else expr
        for assign in set_part.split(","):
            left, right = [s.strip() for s in assign.split("=", 1)]
            field = names.get(left, left)
            item[field] = values[right]
        if "REMOVE" in UpdateExpression:
            item.pop("error", None)


def fresh_wiring():
    return AgentRegistry(), AgentBody()


class TestWorkerPipeline(unittest.TestCase):
    def test_happy_path_selects_reference_agent_via_ecosystem(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        out = process_record(record(work_item()), table=table, registry=registry, body=body)
        self.assertEqual(out["status"], "COMPLETED")
        self.assertFalse(out["duplicate"])
        self.assertEqual(out["agent_id"], "reference_agent")
        self.assertEqual(out["attempt_no"], 1)
        self.assertIn("processing_id", out)
        item = table.items["work-1"]
        self.assertEqual(item["status"], "COMPLETED")
        self.assertEqual(item["attempt_no"], 1)
        self.assertEqual(item["sequence_no"], 1)
        self.assertTrue(item["processing_id"])
        self.assertTrue(item["execution_id"])
        self.assertTrue(item["result_reference"].startswith("work:work-1:attempt:1"))
        self.assertTrue(out["result"]["success"])
        echoed = out["result"]["data"]["echoed"]
        self.assertEqual(echoed["workId"], "work-1")
        self.assertEqual(echoed["payload"], {"message": "hello"})

    def test_selection_by_capability_not_hardcoded(self):
        """Zweiter Agent mit anderer Capability -> Auswahl folgt Capability."""
        from agents.ecosystem.registry import AgentDescriptor, AgentStatus
        table = FakeTable()
        registry, body = fresh_wiring()
        registry.register("other_agent", AgentDescriptor(
            agent_id="other_agent", name="other", version="1.0.0",
            status=AgentStatus.ACTIVE, capabilities=["other.cap"],
        ))
        calls = []

        def other_handler(work):
            calls.append(work["workId"])
            return {"success": True, "data": {"via": "other"}}

        body.register_agent(capability="other.cap", handler=other_handler)
        out = process_record(
            record(work_item("work-9", capability="other.cap", agent_id=None)),
            table=table, registry=registry, body=body,
        )
        self.assertEqual(out["agent_id"], "other_agent")
        self.assertEqual(calls, ["work-9"])

    def test_duplicate_delivery_no_second_run(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        first = process_record(record(work_item()), table=table, registry=registry, body=body)
        self.assertFalse(first["duplicate"])
        puts_after_first = table.puts
        second = process_record(record(work_item(), message_id="msg-2"),
                                table=table, registry=registry, body=body)
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["status"], "COMPLETED")
        self.assertEqual(second["attempt_no"], 1)
        # kein neuer Put, kein neuer Run: Zustand unveraendert
        self.assertEqual(table.puts, puts_after_first)
        self.assertEqual(table.items["work-1"]["attempt_no"], 1)

    def test_retry_after_failure_is_new_attempt(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        attempts = []

        from agents.ecosystem.registry import AgentDescriptor, AgentStatus

        registry.register("flaky", AgentDescriptor(
            agent_id="flaky", name="flaky", version="1.0.0",
            status=AgentStatus.ACTIVE, capabilities=["flaky.cap"],
        ))

        def flaky(work):
            attempts.append(work["workId"])
            if len(attempts) == 1:
                raise RuntimeError("transient boom")
            return {"success": True, "data": {"recovered": True}}

        body.register_agent(capability="flaky.cap", handler=flaky)
        body.register_agent(agent_id="flaky", handler=flaky)
        rec = record(work_item("work-r", capability="flaky.cap", agent_id="flaky"))

        with self.assertRaises(RuntimeError):
            process_record(rec, table=table, registry=registry, body=body)
        self.assertEqual(table.items["work-r"]["status"], "FAILED")
        self.assertEqual(table.items["work-r"]["attempt_no"], 1)

        out = process_record(rec, table=table, registry=registry, body=body)
        self.assertEqual(out["status"], "COMPLETED")
        self.assertFalse(out["duplicate"])
        self.assertEqual(out["attempt_no"], 2)
        self.assertEqual(attempts, ["work-r", "work-r"])
        self.assertNotIn("error", table.items["work-r"])

    def test_invalid_work_item_no_registration(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        bad = {"workId": "work-bad"}  # Pflichtfelder fehlen
        with self.assertRaises(ValueError):
            process_record(record(bad), table=table, registry=registry, body=body)
        self.assertEqual(table.items, {})

    def test_no_eligible_agent_no_registration(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        orphan = work_item("work-o", capability="unknown.cap", agent_id="ghost")
        with self.assertRaises(ValueError):
            process_record(record(orphan), table=table, registry=registry, body=body)
        self.assertEqual(table.items, {})

    def test_float_results_persisted_ddb_safe(self):
        """Executor-Metriken (durationMs float) duerfen Persistenz nicht brechen."""
        from decimal import Decimal

        class StrictTable(FakeTable):
            def _reject_floats(self, value):
                if isinstance(value, float):
                    raise TypeError("Float types are not supported")
                if isinstance(value, dict):
                    for v in value.values():
                        self._reject_floats(v)
                if isinstance(value, list):
                    for v in value:
                        self._reject_floats(v)

            def put_item(self, Item, ConditionExpression=None):
                self._reject_floats(Item)
                super().put_item(Item, ConditionExpression)

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None):
        # Regression-Waechter: reservierte DDB-Woerter duerfen nur via
        # ExpressionAttributeNames (#-Platzhalter) vorkommen (live belegt:
        # error, result, status).
        import re
        bare = re.sub(r"#[A-Za-z_]+", "#x", UpdateExpression)
        for word in ("error", "result", "status"):
            assert word not in re.sub(r"#x", "", bare).split(), \
                f"reserviertes Wort '{word}' ohne Platzhalter: {UpdateExpression}"
        self._reject_floats(ExpressionAttributeValues)
        super().update_item(Key, UpdateExpression, ExpressionAttributeNames,
                            ExpressionAttributeValues)

        table = StrictTable()
        registry, body = fresh_wiring()
        out = process_record(record(work_item()), table=table, registry=registry, body=body)
        self.assertEqual(out["status"], "COMPLETED")
        stored = table.items["work-1"]["result"]
        self.assertIsInstance(stored["metrics"]["durationMs"], Decimal)


if __name__ == "__main__":
    unittest.main()
