"""Tests Gate 08: Worker Entitlement Re-check (execution-time authorization).

Proves: fresh server-side entitlement verification immediately before
agent execution — SQS is activation, not authorization.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_body import AgentBody  # noqa: E402
from agents.ecosystem.registry import (  # noqa: E402
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
)
from agents.ecosystem.worker_authorization import (  # noqa: E402
    DynamoDBEntitlementResolver,
    check_worker_entitlement,
    is_entitlement_valid,
)
from agents.runtime.pipeline import process_record  # noqa: E402


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _row(user="u1", tenant="t1", agent="reference_agent", eid="e1", **kw):
    row = {"userId": user, "tenantId": tenant, "agentId": agent,
           "entitlementId": eid}
    row.update(kw)
    return row


class DictResolver:
    """In-memory entitlement store (call counting + failure injection)."""

    def __init__(self, rows=None, fail=None):
        self._rows = list(rows or [])
        self.calls = 0
        self.fail = fail

    def revoke_all(self):
        self._rows = []

    def find_entitlements(self, user_id):
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return [dict(r) for r in self._rows if r.get("userId") == user_id]


class FakeTable:
    """DDB table with conditional-write + minimal update semantics."""

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


def _work(work_id="w-1", user="u1", tenant="t1", agent="reference_agent",
          capability="reference.echo"):
    return {"workId": work_id, "type": "agent_%s" % agent,
            "tenantId": tenant, "userId": user,
            "idempotencyKey": "key-%s" % work_id,
            "agentId": agent, "capability": capability,
            "payload": {"message": "hello"}}


def _run(work, resolver, table=None, registry=None):
    table = table if table is not None else FakeTable()
    registry = registry if registry is not None else AgentRegistry()
    record = {"messageId": "msg-1", "body": json.dumps(work)}
    out = process_record(record, table=table, registry=registry,
                         body=AgentBody(),
                         entitlement_resolver=resolver)
    return out, table


class TestValidityContract(unittest.TestCase):
    def test_no_window_valid(self):
        self.assertTrue(is_entitlement_valid(_row()))

    def test_expired_invalid(self):
        self.assertFalse(is_entitlement_valid(_row(validUntil=_ts(-1))))

    def test_future_start_invalid(self):
        self.assertFalse(is_entitlement_valid(_row(validFrom=_ts(1))))

    def test_open_window_valid(self):
        self.assertTrue(is_entitlement_valid(
            _row(validFrom=_ts(-1), validUntil=_ts(1))))


class TestRecheckUnit(unittest.TestCase):
    def test_revoked_between_checks_denied(self):
        """Core freshness proof: same inputs, store changed -> DENIED."""
        resolver = DictResolver([_row()])
        first = check_worker_entitlement("u1", "t1", "reference_agent",
                                         "w-x", resolver=resolver)
        self.assertTrue(first.authorized)
        resolver.revoke_all()
        second = check_worker_entitlement("u1", "t1", "reference_agent",
                                          "w-x", resolver=resolver)
        self.assertFalse(second.authorized)
        self.assertEqual(second.reason, "no-entitlement")


class TestPipelineRecheck(unittest.TestCase):
    def test_01_valid_runs(self):
        out, _ = _run(_work(), DictResolver([_row()]))
        self.assertEqual(out["status"], "COMPLETED")
        self.assertFalse(out.get("denied", False))

    def test_02_missing_denied_consumed(self):
        out, table = _run(_work(), DictResolver([]))
        self.assertEqual(out["status"], "FAILED")
        self.assertTrue(out.get("denied"))
        self.assertEqual(out.get("reason"), "no-entitlement")
        item = table.items["w-1"]
        self.assertEqual(item["status"], "FAILED")
        self.assertIn("ENTITLEMENT_DENIED",
                      json.dumps(item.get("error", {})))

    def test_03_expired_denied(self):
        out, _ = _run(_work(), DictResolver([_row(validUntil=_ts(-1))]))
        self.assertTrue(out.get("denied"))

    def test_04_not_yet_valid_denied(self):
        out, _ = _run(_work(), DictResolver([_row(validFrom=_ts(1))]))
        self.assertTrue(out.get("denied"))

    def test_05_wrong_user_denied(self):
        out, _ = _run(_work(user="uX"), DictResolver([_row()]))
        self.assertTrue(out.get("denied"))

    def test_06_wrong_tenant_denied(self):
        out, _ = _run(_work(tenant="tX"), DictResolver([_row()]))
        self.assertTrue(out.get("denied"))
        self.assertEqual(out.get("reason"), "tenant-mismatch")

    def test_07_wrong_agent_denied(self):
        registry = AgentRegistry()
        registry.register("other-agent", AgentDescriptor(
            agent_id="other-agent", name="o", version="1",
            status=AgentStatus.ACTIVE, capabilities=["other.cap"]))
        out, _ = _run(_work(agent="other-agent", capability="other.cap"),
                       DictResolver([_row()]), registry=registry)
        self.assertTrue(out.get("denied"))
        self.assertEqual(out.get("reason"), "no-entitlement")

    def test_09_tampered_tenant_denied(self):
        out, _ = _run(_work(tenant="tenant-evil"),
                       DictResolver([_row()]))
        self.assertTrue(out.get("denied"))

    def test_11_missing_user_denied_no_guess(self):
        work = _work()
        del work["userId"]
        out, _ = _run(work, DictResolver([_row()]))
        self.assertTrue(out.get("denied"))
        self.assertEqual(out.get("reason"), "missing-identity")

    def test_12_revoked_before_retry_denied(self):
        """Revoked between attempts: retry path re-checks current state."""
        table = FakeTable()
        table.items["w-r"] = {"workId": "w-r", "attempt_no": 1,
                              "processing_id": "p1", "status": "FAILED",
                              "tenantId": "t1"}
        out, _ = _run(_work(work_id="w-r"), DictResolver([]), table=table)
        self.assertTrue(out.get("denied"))
        self.assertEqual(out.get("attempt_no"), 2)

    def test_14_inactive_agent_blocked_despite_entitlement(self):
        registry = AgentRegistry()
        registry.register("old-agent", AgentDescriptor(
            agent_id="old-agent", name="o", version="1",
            status=AgentStatus.INACTIVE, capabilities=["old.cap"]))
        with self.assertRaises(ValueError):
            _run(_work(agent="old-agent", capability="old.cap"),
                 DictResolver([_row(agent="old-agent")]),
                 registry=registry)

    def test_15_unknown_status_blocked_despite_entitlement(self):
        registry = AgentRegistry()
        registry.register("mystery-agent", AgentDescriptor(
            agent_id="mystery-agent", name="m", version="1",
            status=None, capabilities=["mystery.cap"]))
        with self.assertRaises(ValueError):
            _run(_work(agent="mystery-agent", capability="mystery.cap"),
                 DictResolver([_row(agent="mystery-agent")]),
                 registry=registry)

    def test_16_transient_is_not_denied(self):
        """Store unreachable: raise (retry), no execution, no false DENIED."""
        table = FakeTable()
        with self.assertRaises(RuntimeError):
            _run(_work(), DictResolver([], fail=RuntimeError("boom")),
                 table=table)
        self.assertEqual(table.items["w-1"]["status"], "FAILED")
        self.assertNotIn("ENTITLEMENT_DENIED",
                         json.dumps(table.items["w-1"].get("error", {})))

    def test_17_duplicate_skips_recheck_keeps_idempotency(self):
        """Completed duplicate: stored outcome, no new run, no re-check."""
        table = FakeTable()
        resolver = DictResolver([_row()])
        first, _ = _run(_work(), resolver, table=table)
        self.assertEqual(first["status"], "COMPLETED")
        calls_after_first = resolver.calls
        second, _ = _run(_work(), resolver, table=table)
        self.assertTrue(second.get("duplicate"))
        self.assertEqual(second["status"], "COMPLETED")
        self.assertEqual(resolver.calls, calls_after_first)

    def test_resolver_construction_is_lazy(self):
        """Production resolver builds without AWS calls (lazy table)."""
        r = DynamoDBEntitlementResolver()
        self.assertIsNotNone(r)


if __name__ == "__main__":
    unittest.main()
