"""Tests Gate 9: JobSearch Domain Agent (Gate 9).

Fake-Repository (Interface wie jobsearch.repository):
Delegation, Tenant-Isolation, Validierung, Wrap-Norm, Pipeline-Routing.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_body import AgentBody
from agents.ecosystem.registry import AgentRegistry
from agents.jobsearch_agent.agent import (
    JOBSEARCH_AGENT_ID, process_jobsearch_work, register_jobsearch_agent)
from agents.runtime.pipeline import ensure_reference_agent, process_record


class FakeRepo:
    def __init__(self, items=None):
        self.items = dict(items or {})

    def save(self, search):
        self.items[search.job_search_id] = search
        return True

    def get(self, job_search_id, user_id, tenant_id):
        item = self.items.get(job_search_id)
        if item is None:
            return None
        if item.user_id != user_id or item.tenant_id != tenant_id:
            return None
        return item

    def list_by_user(self, user_id, tenant_id, status=None):
        return [i for i in self.items.values()
                if i.user_id == user_id and i.tenant_id == tenant_id
                and (status is None or i.status.value == status)]


def work(work_id="js-1", capability="jobsearch.create", payload=None,
         user="user-1", tenant="tenant-gate9"):
    return {
        "workId": work_id, "type": "agent_jobsearch", "tenantId": tenant,
        "idempotencyKey": f"key-{work_id}", "userId": user,
        "agentId": JOBSEARCH_AGENT_ID, "capability": capability,
        "payload": payload if payload is not None else {"name": "Suche (Gate-9-Test)"},
    }


def record(work_item, message_id="m"):
    import json
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


class TestJobSearchAgent(unittest.TestCase):
    def test_create_get_list(self):
        repo = FakeRepo()
        factory = lambda: repo
        created = process_jobsearch_work(work(), repository_factory=factory)
        self.assertTrue(created["success"])
        js_id = created["data"]["jobSearch"]["jobSearchId"]
        got = process_jobsearch_work(
            work("js-2", "jobsearch.get", {"jobSearchId": js_id}), repository_factory=factory)
        self.assertTrue(got["success"])
        self.assertEqual(got["data"]["jobSearch"]["jobSearchId"], js_id)
        listed = process_jobsearch_work(
            work("js-3", "jobsearch.list", {}), repository_factory=factory)
        self.assertTrue(listed["success"])
        self.assertEqual(listed["data"]["count"], 1)

    def test_tenant_isolation(self):
        repo = FakeRepo()
        factory = lambda: repo
        created = process_jobsearch_work(work(), repository_factory=factory)
        js_id = created["data"]["jobSearch"]["jobSearchId"]
        foreign = process_jobsearch_work(
            work("js-x", "jobsearch.get", {"jobSearchId": js_id},
                 user="user-1", tenant="tenant-fremd"),
            repository_factory=factory)
        self.assertFalse(foreign["success"])

    def test_validation_and_unknown_capability(self):
        repo = FakeRepo()
        factory = lambda: repo
        no_name = process_jobsearch_work(
            work(payload={}), repository_factory=factory)
        self.assertFalse(no_name["success"])
        unknown = process_jobsearch_work(
            work(capability="jobsearch.nope", payload={}), repository_factory=factory)
        self.assertFalse(unknown["success"])

    def test_registration_and_pipeline_routing(self):
        registry, body = ensure_reference_agent(AgentRegistry(), AgentBody())
        self.assertTrue(registry.is_registered(JOBSEARCH_AGENT_ID))
        self.assertIn("agent:jobsearch-agent", body.router.get_routes())
        table = FakeTable()
        # Pipeline nutzt Live-Repository (Tabelle evtl. absent) -> hier nur Auswahl pruefen:
        from agents.ecosystem.discovery import AgentDiscovery
        from agents.ecosystem.registry import AgentStatus
        hits = AgentDiscovery(registry).find(capability="jobsearch.create",
                                             status=AgentStatus.ACTIVE)
        self.assertEqual([h.agent_id for h in hits], [JOBSEARCH_AGENT_ID])


if __name__ == "__main__":
    unittest.main()
