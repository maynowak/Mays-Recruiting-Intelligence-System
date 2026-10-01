"""Tests Gate 7: ATS als erster echter Domain Agent (Gate 7).

Netzfrei (ATSHttpClient.analyze wird per Monkeypatch stubbed):
Registration, Discovery-Unterscheidung, Eligibility, Invocation,
Result-Contract, Negative (falsch/Duplikat/Retry/Eligibility).
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_body import AgentBody
from agents.ats_agent.agent import ATSAgent
from agents.ats_agent.registry import get_ats_descriptor, ATS_ANALYZE_CAPABILITY, ATS_WORK_TYPE
from agents.ecosystem.discovery import AgentDiscovery
from agents.ecosystem.eligibility import EligibilityPipeline
from agents.ecosystem.event_hook import EventHook
from agents.ecosystem.registry import AgentRegistry, AgentStatus
from agents.ecosystem.routing import AgentRouter as EcosystemRouter
from agents.runtime.pipeline import ensure_reference_agent, process_record


ATS_ANALYSIS = {"analysis": {"score": 87, "requirements": [{"id": "r1"}]}, "jobTitle": "QA Engineer"}


def stub_analyze_ok(self, job, profile=None):
    assert isinstance(job, dict) and job.get("title"), "Job-Titel erwartet"
    return dict(ATS_ANALYSIS)


def stub_analyze_fail(self, job, profile=None):
    from agents.ats_agent.agent import ATSAPIError
    raise ATSAPIError("simulierter API-Fehler")


def ats_work(work_id="ats-1", capability="analyze.job", job=None):
    return {
        "workId": work_id,
        "type": "ats_process",
        "tenantId": "tenant-gate7",
        "idempotencyKey": f"key-{work_id}",
        "agentId": "ats-agent",
        "capability": capability,
        "payload": {"job": job if job is not None else {"title": "QA Engineer (synthetic)"},
                    "profile": {}},
    }


def record(work, message_id="msg-ats-1"):
    import json
    return {"messageId": message_id, "body": json.dumps(work)}


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


class TestATSRegistration(unittest.TestCase):
    def test_descriptor_fields(self):
        d = get_ats_descriptor()
        self.assertEqual(d.agent_id, "ats-agent")
        self.assertEqual(d.version, "1.0.0")
        self.assertEqual(d.status, AgentStatus.ACTIVE)
        self.assertIn("analyze.job", d.capabilities)
        self.assertEqual(d.execution_profile.value, "LAMBDA")
        self.assertEqual(d.risk_level, "low")

    def test_bootstrap_registers_all_three_without_override(self):
        registry, body = ensure_reference_agent(AgentRegistry(), AgentBody())
        for agent_id in ("reference_agent", "orders_function", "ats-agent"):
            self.assertTrue(registry.is_registered(agent_id))
        routes = body.router.get_routes()
        self.assertIn("agent:ats-agent", routes)
        self.assertIn("analyze.job", routes)


class TestATSDiscoveryEligibility(unittest.TestCase):
    def test_discovery_distinguishes_ats_from_reference(self):
        registry, _ = ensure_reference_agent(AgentRegistry(), AgentBody())
        discovery = AgentDiscovery(registry)
        ats_hits = discovery.find(capability="analyze.job", status=AgentStatus.ACTIVE)
        self.assertEqual([h.agent_id for h in ats_hits], ["ats-agent"])
        echo_hits = discovery.find(capability="reference.echo", status=AgentStatus.ACTIVE)
        self.assertEqual([h.agent_id for h in echo_hits], ["reference_agent"])

    def test_eligibility_rejects_retired(self):
        from agents.ecosystem.registry import AgentDescriptor
        registry = AgentRegistry()
        registry.register("old-ats", AgentDescriptor(
            agent_id="old-ats", name="old", version="0.1",
            status=AgentStatus.RETIRED, capabilities=["analyze.job"]))
        checker = EligibilityPipeline(registry)
        from agents.ecosystem.discovery import DiscoveryResult
        from agents.ecosystem.event_hook import create_processing_envelope_from_event
        env = create_processing_envelope_from_event(
            {"event_type": "EVENT", "tenant_id": "t",
             "payload": {"capability": "analyze.job"}})
        res = checker.check_candidates(
            [DiscoveryResult("old-ats", registry.get("old-ats"), "x")], env)
        self.assertEqual(len(res.eligible), 0)
        self.assertEqual(len(res.rejected), 1)


class TestATSInvocation(unittest.TestCase):
    def test_success_result_fits_runtime_contract(self):
        from agents.ats_agent.agent import ATSHttpClient
        orig = ATSHttpClient.analyze
        ATSHttpClient.analyze = stub_analyze_ok
        try:
            agent = ATSAgent()
            out = agent.process_work(ats_work())
        finally:
            ATSHttpClient.analyze = orig
        self.assertTrue(out["success"])
        self.assertEqual(out["data"]["jobTitle"], "QA Engineer (synthetic)")
        self.assertIn("analysis", out["data"])
        self.assertIn("metrics", out)

    def test_api_error_controlled(self):
        from agents.ats_agent.agent import ATSHttpClient
        orig = ATSHttpClient.analyze
        ATSHttpClient.analyze = stub_analyze_fail
        try:
            agent = ATSAgent()
            out = agent.process_work(ats_work())
        finally:
            ATSHttpClient.analyze = orig
        self.assertFalse(out["success"])
        self.assertEqual(out["error"]["type"], "ATSAPIError")

    def test_pipeline_end_to_end_with_stubbed_api(self):
        from agents.ats_agent.agent import ATSHttpClient
        orig = ATSHttpClient.analyze
        ATSHttpClient.analyze = stub_analyze_ok
        try:
            table = FakeTable()
            out = process_record(record(ats_work()),
                                 table=table, registry=AgentRegistry(), body=AgentBody())
        finally:
            ATSHttpClient.analyze = orig
        self.assertEqual(out["status"], "COMPLETED")
        self.assertEqual(out["agent_id"], "ats-agent")
        self.assertEqual(table.items["ats-1"]["status"], "COMPLETED")

    def test_non_ats_item_not_routed_to_ats(self):
        from agents.ats_agent.agent import ATSHttpClient
        orig = ATSHttpClient.analyze
        ATSHttpClient.analyze = stub_analyze_ok
        try:
            table = FakeTable()
            echo = {"workId": "echo-1", "type": "agent_reference_agent",
                    "tenantId": "t", "idempotencyKey": "k-echo",
                    "agentId": "reference_agent", "capability": "reference.echo",
                    "payload": {"message": "hi"}}
            out = process_record(record(echo), table=table,
                                 registry=AgentRegistry(), body=AgentBody())
        finally:
            ATSHttpClient.analyze = orig
        self.assertEqual(out["agent_id"], "reference_agent")

    def test_duplicate_no_second_run(self):
        from agents.ats_agent.agent import ATSHttpClient
        orig = ATSHttpClient.analyze
        ATSHttpClient.analyze = stub_analyze_ok
        try:
            table = FakeTable()
            reg, body = AgentRegistry(), AgentBody()
            first = process_record(record(ats_work()), table=table, registry=reg, body=body)
            second = process_record(record(ats_work(), "msg-2"), table=table,
                                    registry=reg, body=body)
        finally:
            ATSHttpClient.analyze = orig
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["attempt_no"], 1)


if __name__ == "__main__":
    unittest.main()
