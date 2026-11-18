"""Reader agent-admission gate (DISABLE must block new agent orders).

The reader persists an order before dispatch. Without an admission check, a
DISABLED agent still receives orders through POST /orders. These tests prove
the gate rejects before any write and uses the same decision function as the
worker and dispatch ingress.
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST"
CLIENT = "client-test"
OWNER = "owner-1"
TENANT = "tenant-a"
PROFILE = "aprof_gate"

os.environ.setdefault("ORDERS_TABLE", "mays-orders")
os.environ.setdefault(
    "ORDERS_SQS_QUEUE_URL",
    "https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-orders-queue")
os.environ.setdefault("ORDERS_COGNITO_ISSUER", ISSUER)
os.environ.setdefault("ORDERS_COGNITO_CLIENT_ID", CLIENT)

_SPEC = importlib.util.spec_from_file_location(
    "orders_reader_gate", os.path.join(_REPO_ROOT, "lambda", "orders_reader.py"))
orders_reader = importlib.util.module_from_spec(_SPEC)
sys.modules["orders_reader_gate"] = orders_reader
_SPEC.loader.exec_module(orders_reader)

from agents.ecosystem.worker_authorization import (  # noqa: E402
    check_worker_entitlement,
)


class FakeOrdersTable:
    def __init__(self):
        self.puts = []
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        self.puts.append(dict(Item))
        self.items[Item["pk"]] = dict(Item)

    def update_item(self, **kwargs):
        return None


class ProfileTable:
    def __init__(self, rows):
        self.rows = {r["apiProfileId"]: dict(r) for r in rows}

    def get_item(self, Key):
        row = self.rows.get(Key["apiProfileId"])
        return {"Item": dict(row)} if row else {}


class Resolver:
    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error

    def find_entitlements(self, user_id):
        if self.error:
            raise self.error
        return [dict(r) for r in self.rows if r.get("userId") == user_id]


def profile(owner=OWNER, tenant=TENANT, status="ACTIVE"):
    return {"apiProfileId": PROFILE, "status": status,
            "ownerUserId": owner, "tenantId": tenant}


def entitlement(agent="ats-agent", tenant=TENANT, profile_id=None, **extra):
    row = {"userId": OWNER, "tenantId": tenant, "agentId": agent,
           "entitlementId": f"ent-{agent}"}
    if profile_id is not None:
        row["apiProfileId"] = profile_id
    row.update(extra)
    return row


def body(agent="ats-agent", capability="analyze.job"):
    return {
        "orderType": "agent.execution",
        "agentOrder": {
            "schemaVersion": "1.0",
            "target": {"agentId": agent, "capability": capability},
            "input": {"schemaVersion": "1.0", "data": {"job": {}}},
            "metadata": {"requestId": "corr-gate", "apiProfileRef": PROFILE},
        },
    }


def event(payload):
    return {
        "routeKey": "POST /orders",
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "iss": ISSUER, "sub": OWNER, "token_use": "access",
            "client_id": CLIENT, "aud": CLIENT,
            "custom:tenant_id": TENANT,
        }}}},
        "body": json.dumps(payload),
    }


class TestReaderAgentGate(unittest.TestCase):
    def setUp(self):
        self.table = FakeOrdersTable()
        self.profile_table = ProfileTable([profile()])
        self.sent = []
        self._send = patch.object(orders_reader, "_send_order_dispatch",
                                  side_effect=self.sent.append)
        self._send.start()

    def tearDown(self):
        self._send.stop()

    def post(self, payload, rows, error=None):
        return orders_reader.handler(
            event(payload), None, self.table,
            profile_table=self.profile_table,
            entitlement_resolver=Resolver(rows, error=error))

    def test_enabled_agent_order_is_accepted_and_dispatched(self):
        resp = self.post(body(), [entitlement()])
        self.assertEqual(201, resp["statusCode"], resp["body"])
        self.assertEqual(1, len(self.table.puts))
        self.assertEqual(1, len(self.sent))

    def test_disabled_agent_order_is_blocked_before_persist(self):
        resp = self.post(body(), [])
        self.assertEqual(403, resp["statusCode"])
        self.assertIn("AGENT_ORDER_REJECTED", resp["body"])
        self.assertEqual([], self.table.puts)
        self.assertEqual([], self.sent)
        self.assertEqual({}, self.table.items)

    def test_other_agent_still_works_when_ats_is_disabled(self):
        blocked = self.post(body(), [])
        self.assertEqual(403, blocked["statusCode"])
        allowed = self.post(body("addition_agent", "math.add"),
                            [entitlement("addition_agent")])
        self.assertEqual(201, allowed["statusCode"], allowed["body"])

    def test_tenant_mismatch_is_rejected(self):
        resp = self.post(body(), [entitlement(tenant="tenant-other")])
        self.assertEqual(403, resp["statusCode"])
        self.assertEqual([], self.table.puts)

    def test_profile_bound_row_requires_matching_profile(self):
        denied = self.post(body(), [entitlement(profile_id="aprof_other")])
        self.assertEqual(403, denied["statusCode"])
        allowed = self.post(body(), [entitlement(profile_id=PROFILE)])
        self.assertEqual(201, allowed["statusCode"], allowed["body"])

    def test_expired_entitlement_is_rejected(self):
        resp = self.post(body(), [
            entitlement(validUntil="2020-01-01T00:00:00+00:00")])
        self.assertEqual(403, resp["statusCode"])
        self.assertEqual([], self.table.puts)

    def test_missing_entitlement_store_fails_closed(self):
        with patch.object(orders_reader, "ENTITLEMENTS_TABLE", ""):
            resp = orders_reader.handler(
                event(body()), None, self.table,
                profile_table=self.profile_table)
        self.assertEqual(503, resp["statusCode"])
        self.assertEqual([], self.table.puts)

    def test_resolver_outage_is_503_not_silent_allow(self):
        resp = self.post(body(), [], error=RuntimeError("store down"))
        self.assertEqual(503, resp["statusCode"])
        self.assertEqual([], self.table.puts)
        self.assertEqual([], self.sent)

    def test_gate_matches_worker_decision_for_every_fixture(self):
        cases = [
            [entitlement()],
            [entitlement("addition_agent")],
            [entitlement(tenant="other")],
            [entitlement(profile_id=PROFILE)],
            [entitlement(profile_id="aprof_other")],
            [entitlement(validUntil="2020-01-01T00:00:00+00:00")],
            [],
        ]
        for rows in cases:
            decision = check_worker_entitlement(
                user_id=OWNER, tenant_id=TENANT, agent_id="ats-agent",
                work_id=None, resolver=Resolver(rows),
                api_profile_id=PROFILE)
            self.table = FakeOrdersTable()
            resp = self.post(body(), rows)
            with self.subTest(rows=rows):
                self.assertEqual(
                    decision.authorized, resp["statusCode"] == 201,
                    f"worker={decision.reason} reader={resp['statusCode']}")

    def test_retail_order_is_not_affected_by_the_gate(self):
        payload = {
            "customer": {"name": "Retail", "email": "retail@example.com"},
            "items": [{"sku": "SKU-R", "quantity": 1, "unitPrice": 10}],
            "currency": "EUR",
        }
        with patch.object(orders_reader, "_send_order_created", return_value=None):
            resp = self.post(payload, [])
        self.assertEqual(201, resp["statusCode"], resp["body"])


if __name__ == "__main__":
    unittest.main()
