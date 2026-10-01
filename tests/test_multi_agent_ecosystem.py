"""Tests Gate 8: Multi-Agent-Ecosystem (Gate 8).

Registry mit 5 Agents (reference, orders_function, ats-agent, dummy-a,
dummy-b): Discovery-Mehrheit, Eligibility-Filter, Selection A–E,
Shared-Queue-Simulation, Result-Isolation, Duplikat. ATS ohne Netz
(nur Auswahl, keine Ausfuehrung).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_body import AgentBody
from agents.ecosystem.discovery import AgentDiscovery
from agents.ecosystem.eligibility import EligibilityPipeline
from agents.ecosystem.event_hook import create_processing_envelope_from_event
from agents.ecosystem.registry import AgentRegistry, AgentStatus
from agents.ecosystem.routing import AgentRouter as EcosystemRouter
from agents.runtime.pipeline import ensure_reference_agent, process_record


def work(work_id, capability, agent_id=None, work_type="agent_work"):
    return {
        "workId": work_id, "type": work_type, "tenantId": "tenant-gate8",
        "idempotencyKey": f"key-{work_id}", "agentId": agent_id,
        "capability": capability, "payload": {"probe": work_id},
    }


def record(work_item, message_id="m"):
    return {"messageId": message_id, "body": json.dumps(work_item)}


class FakeTable:
    class ConditionalFailed(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "ConditionalCheckFailedException"}}

    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        if ConditionExpression == "attribute_not_exists(workId)" and Item["workId"] in self.items:
            raise FakeTable.ConditionalFailed()
        self.items[Item["workId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None):
        item = self.items[Key["workId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        expr = UpdateExpression.split("REMOVE")[0].strip()
        set_part = expr[len("SET "):] if expr.startswith("SET ") else expr
        for assign in set_part.split(","):
            left, right = [s.strip() for s in assign.split("=", 1)]
            item[names.get(left, left)] = values[right]
        if "REMOVE" in UpdateExpression:
            item.pop("error", None)


def wired():
    return ensure_reference_agent(AgentRegistry(), AgentBody())


class TestMultiRegistration(unittest.TestCase):
    def test_five_agents_registered(self):
        registry, body = wired()
        for agent_id in ("reference_agent", "orders_function", "ats-agent",
                         "dummy-a", "dummy-b"):
            self.assertTrue(registry.is_registered(agent_id))
        routes = body.router.get_routes()
        for key in ("agent:dummy-a", "agent:dummy-b", "agent:ats-agent",
                    "dummy-a", "dummy-b"):
            self.assertIn(key, routes)

    def test_discovery_knows_many_candidates(self):
        registry, _ = wired()
        discovery = AgentDiscovery(registry)
        all_cands = discovery.find(status=AgentStatus.ACTIVE)
        ids = {c.agent_id for c in all_cands}
        self.assertTrue({"dummy-a", "dummy-b", "ats-agent", "reference_agent"} <= ids)


class TestMultiRouting(unittest.TestCase):
    def _select(self, capability, agent_id=None):
        registry, _ = wired()
        discovery = AgentDiscovery(registry)
        env = create_processing_envelope_from_event(
            {"event_type": "EVENT", "tenant_id": "t",
             "payload": {"capability": capability}, "agent_id": agent_id})
        cands = discovery.find_from_envelope(env)
        if not cands:
            cands = discovery.find(capability=capability, agent_id=agent_id,
                                   status=AgentStatus.ACTIVE)
        pipe = EligibilityPipeline(registry).check_candidates(cands, env)
        eligible = [c for c in cands
                    if c.agent_id in {e.agent_id for e in pipe.eligible}]
        decision = EcosystemRouter().select(eligible)
        return decision.agent_id if decision else None

    def test_a_dummy_a(self):
        self.assertEqual(self._select("dummy-a"), "dummy-a")

    def test_b_dummy_b(self):
        self.assertEqual(self._select("dummy-b"), "dummy-b")

    def test_c_ats(self):
        self.assertEqual(self._select("analyze.job", agent_id="ats-agent"), "ats-agent")

    def test_d_reference(self):
        self.assertEqual(self._select("reference.echo"), "reference_agent")

    def test_e_unknown_no_agent(self):
        self.assertIsNone(self._select("nope.unknown"))
        table = FakeTable()
        with self.assertRaises(ValueError):
            process_record(record(work("w-unknown", "nope.unknown")),
                           table=table, registry=AgentRegistry(), body=AgentBody())
        self.assertEqual(table.items, {})


class TestSharedQueueSimulation(unittest.TestCase):
    def test_four_items_each_gets_right_agent_isolated_results(self):
        table = FakeTable()
        registry, body = AgentRegistry(), AgentBody()
        cases = [("w-a", "dummy-a", None, "dummy-a"),
                 ("w-b", "dummy-b", None, "dummy-b"),
                 ("w-r", "reference.echo", "reference_agent", "reference_agent")]
        refs = {}
        for work_id, cap, agent_id, expect in cases:
            out = process_record(record(work(work_id, cap, agent_id)),
                                 table=table, registry=registry, body=body)
            self.assertEqual(out["agent_id"], expect)
            self.assertEqual(out["status"], "COMPLETED")
            refs[work_id] = out["result_reference"]
        # Isolation: Referenzen + Processing-IDs disjunkt, Results zugeordnet
        self.assertEqual(len(set(refs.values())), 3)
        procs = {table.items[w]["processing_id"] for w, _, _, _ in cases}
        self.assertEqual(len(procs), 3)
        self.assertEqual(table.items["w-a"]["result"]["data"]["processed_by"], "dummy-a")
        self.assertEqual(table.items["w-b"]["result"]["data"]["processed_by"], "dummy-b")

    def test_duplicate_per_agent_no_new_run(self):
        table = FakeTable()
        registry, body = AgentRegistry(), AgentBody()
        first = process_record(record(work("w-dup", "dummy-a")),
                               table=table, registry=registry, body=body)
        second = process_record(record(work("w-dup", "dummy-a")),
                                table=table, registry=registry, body=body)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["attempt_no"], 1)


if __name__ == "__main__":
    unittest.main()
