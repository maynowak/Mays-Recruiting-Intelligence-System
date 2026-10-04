"""Tests Gate B3: entitlement queries use IndexName="gsi-user".

Every test asserts the captured DynamoDB query kwargs (not only the
return value): without IndexName the live query answers
ValidationException (table PK is entitlementId, not userId).
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lambda"))

from agents.ecosystem.worker_authorization import (  # noqa: E402
    DynamoDBEntitlementResolver,
    check_worker_entitlement,
)


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _row(user="u1", tenant="t1", agent="reference_agent", **kw):
    row = {"entitlementId": "ent-1", "userId": user, "tenantId": tenant,
           "agentId": agent}
    row.update(kw)
    return row


class CapturingTable:
    """Fake DynamoDB table recording query kwargs."""

    def __init__(self, items=None, fail=None):
        self.items = list(items or [])
        self.calls = []
        self.fail = fail

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail is not None:
            raise self.fail
        return {"Items": [dict(i) for i in self.items]}

    def index_names(self):
        return [c.get("IndexName") for c in self.calls]


class ResolverCase(unittest.TestCase):
    def _check(self, table, user="u1", tenant="t1", agent="reference_agent",
               profile=None):
        resolver = DynamoDBEntitlementResolver(table=table)
        decision = check_worker_entitlement(
            user, tenant, agent, "w-1", resolver=resolver,
            api_profile_id=profile)
        self.assertTrue(len(table.calls) >= 1)
        for call in table.calls:
            self.assertEqual(call.get("IndexName"), "gsi-user")
            self.assertIsNotNone(call.get("KeyConditionExpression"))
        return decision

    def test_A_user_wide_authorized(self):
        table = CapturingTable([_row()])
        d = self._check(table)
        self.assertTrue(d.authorized)

    def test_B_profile_bound_authorized(self):
        table = CapturingTable([_row(apiProfileId="aprof_1")])
        d = self._check(table, profile="aprof_1")
        self.assertTrue(d.authorized)

    def test_C_expired_denied(self):
        table = CapturingTable([_row(validUntil=_ts(-1))])
        d = self._check(table)
        self.assertFalse(d.authorized)

    def test_D_wrong_tenant_denied(self):
        table = CapturingTable([_row()])
        d = self._check(table, tenant="tX")
        self.assertFalse(d.authorized)
        self.assertEqual(d.reason, "tenant-mismatch")

    def test_E_wrong_agent_denied(self):
        table = CapturingTable([_row()])
        d = self._check(table, agent="other-agent")
        self.assertFalse(d.authorized)

    def test_F_none_denied(self):
        table = CapturingTable([])
        d = self._check(table)
        self.assertFalse(d.authorized)
        self.assertEqual(d.reason, "no-entitlement")

    def test_G_store_failure_propagates(self):
        table = CapturingTable(fail=RuntimeError("db down"))
        with self.assertRaises(RuntimeError):
            self._check(table)

    def test_index_constant(self):
        self.assertEqual(DynamoDBEntitlementResolver.USER_INDEX, "gsi-user")


class HandlerCase(unittest.TestCase):
    def _handler(self):
        import handler as h
        return h

    def _table(self, h, items):
        table = CapturingTable(items)

        class FakeDDB:
            def Table(self, name):
                self.name = name
                return table

        return table, patch.object(h, "_get_dynamodb",
                                   return_value=FakeDDB())

    def test_handler_list_uses_index(self):
        h = self._handler()
        table = CapturingTable([_row(), _row(agent="other")])
        with patch.dict(os.environ, {"ENTITLEMENTS_TABLE": "t"}):
            with patch.object(h, "_get_dynamodb") as mock_ddb:
                mock_ddb.return_value.Table.return_value = table
                rows = h._get_entitlements("u1", "t1")
        self.assertEqual(table.index_names(), ["gsi-user"])
        self.assertEqual(len(rows), 2)

    def test_handler_single_uses_index(self):
        h = self._handler()
        table = CapturingTable([_row()])
        with patch.dict(os.environ, {"ENTITLEMENTS_TABLE": "t"}):
            with patch.object(h, "_get_dynamodb") as mock_ddb:
                mock_ddb.return_value.Table.return_value = table
                row = h._get_entitlement_for_agent(
                    "u1", "reference_agent", "t1")
        self.assertEqual(table.index_names(), ["gsi-user"])
        self.assertIsNotNone(row)
        self.assertEqual(row["agentId"], "reference_agent")


if __name__ == "__main__":
    unittest.main()
