"""MO-compatible create payload → RIS agent-order dispatch.

Covers the real runtime path of the integration gate:

  Mays-Orders OrderV1 create payload (orderType + agentOrder + root-level
  ``orderDescription``)
      -> POST /orders (lambda/orders_reader.py)
      -> schema/identity/secret/entitlement gates (unchanged)
      -> ORDER_DISPATCH envelope on the RIS dispatch queue

and the outbound leg:

  RealMaysOrdersAdapter.submit_order("orders.create", payload)
      -> POST /orders body that carries the complete MO payload and no
         unknown fields.

Mays-Orders forbids combining ``customer``/``items``/``currency`` with an
``agentOrder`` (its own validation.py), so agent payloads here carry only
``orderType``, ``orderDescription`` and ``agentOrder``.

No AWS calls: the table, profile store, entitlement resolver, dispatch send
and HTTP transport are fakes.
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
PROFILE = "aprof_mo"

os.environ.setdefault("ORDERS_TABLE", "ris-dev2-mays-orders")
os.environ.setdefault(
    "ORDERS_SQS_QUEUE_URL",
    "https://sqs.eu-central-1.amazonaws.com/262370457690/"
    "ris-dev2-mays-orders-orders-queue")
os.environ.setdefault("ORDERS_COGNITO_ISSUER", ISSUER)
os.environ.setdefault("ORDERS_COGNITO_CLIENT_ID", CLIENT)

_SPEC = importlib.util.spec_from_file_location(
    "orders_reader_mo", os.path.join(_REPO_ROOT, "lambda", "orders_reader.py"))
orders_reader = importlib.util.module_from_spec(_SPEC)
sys.modules["orders_reader_mo"] = orders_reader
_SPEC.loader.exec_module(orders_reader)

from agents.orders.agent_order import MAX_ORDER_DESCRIPTION_LENGTH  # noqa: E402
from agents.orders.real import RealMaysOrdersAdapter  # noqa: E402


class FakeOrdersTable:
    def __init__(self):
        self.puts = []
        self.items = {}
        self.updates = []

    def put_item(self, Item, ConditionExpression=None):
        self.puts.append(dict(Item))
        self.items[Item["pk"]] = dict(Item)

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        return None


class ProfileTable:
    def __init__(self, rows):
        self.rows = {r["apiProfileId"]: dict(r) for r in rows}

    def get_item(self, Key):
        row = self.rows.get(Key["apiProfileId"])
        return {"Item": dict(row)} if row else {}


class Resolver:
    def __init__(self, rows):
        self.rows = rows

    def find_entitlements(self, user_id):
        return [dict(r) for r in self.rows if r.get("userId") == user_id]


def mo_agent_order(agent="ats-agent", capability="analyze.job"):
    return {
        "schemaVersion": "1.0",
        "target": {"agentId": agent, "capability": capability},
        "input": {"schemaVersion": "1.0",
                  "data": {"job": {"title": "Senior Python Engineer"},
                           "profile": {"skills": "Python"}}},
        "metadata": {"source": "mays-orders", "requestId": "corr-mo-1",
                     "apiProfileRef": PROFILE},
    }


def mo_agent_payload(description="Analyse für Bewerber 4711"):
    """MO agent create payload: no retail fields (MO forbids the mix)."""
    return {
        "orderType": "agent.execution",
        "orderDescription": description,
        "agentOrder": mo_agent_order(),
    }


def mo_retail_payload():
    return {
        "customer": {"name": "Mays GmbH", "email": "ops@example.com"},
        "items": [{"sku": "ATS", "quantity": 1, "unitPrice": 100}],
        "currency": "EUR",
    }


def event(payload):
    return {
        "routeKey": "POST /orders",
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "iss": ISSUER, "sub": OWNER, "token_use": "access",
            "client_id": CLIENT, "aud": CLIENT,
        }}}},
        "body": json.dumps(payload),
    }


class TestMoCreateToRisDispatch(unittest.TestCase):
    def setUp(self):
        self.table = FakeOrdersTable()
        self.profile_table = ProfileTable([{
            "apiProfileId": PROFILE, "status": "ACTIVE",
            "ownerUserId": OWNER, "tenantId": TENANT}])
        self.entitlements = Resolver([{
            "userId": OWNER, "tenantId": TENANT, "agentId": "ats-agent",
            "entitlementId": "ent-mo"}])
        self.dispatched = []
        self._send = patch.object(orders_reader, "_send_order_dispatch",
                                  side_effect=self.dispatched.append)
        self._send.start()

    def tearDown(self):
        self._send.stop()

    def post(self, payload):
        return orders_reader.handler(
            event(payload), None, self.table,
            profile_table=self.profile_table,
            entitlement_resolver=self.entitlements)

    def test_mo_payload_is_accepted_validated_and_dispatched(self):
        description = "Analyse für Bewerber 4711"
        response = self.post(mo_agent_payload(description))
        self.assertEqual(201, response["statusCode"], response["body"])

        self.assertEqual(1, len(self.table.puts))
        self.assertEqual(1, len(self.dispatched))
        stored = self.table.puts[0]

        # orderDescription is folded into the AgentOrder V1 body
        self.assertEqual(description, stored["agentOrder"]["orderDescription"])
        self.assertEqual("1.0", stored["agentOrder"]["schemaVersion"])

        # nothing MO-root-level leaks into the RIS order row
        for leaked in ("orderDescription", "customer", "items", "currency",
                       "totalAmount"):
            self.assertNotIn(leaked, stored)

        # the dispatch envelope carries the execution payload only
        envelope = self.dispatched[0]
        self.assertEqual(stored["orderId"], envelope["orderId"])
        self.assertEqual("corr-mo-1", envelope["correlationId"])
        self.assertEqual(mo_agent_order()["input"]["data"],
                         envelope["payload"])
        self.assertEqual(stored["expectedWorkId"],
                         envelope["execution"]["workId"])
        self.assertNotIn("orderDescription", envelope["payload"])

    def test_description_at_limit_is_accepted(self):
        description = "x" * MAX_ORDER_DESCRIPTION_LENGTH
        response = self.post(mo_agent_payload(description))
        self.assertEqual(201, response["statusCode"], response["body"])
        self.assertEqual(description,
                         self.table.puts[0]["agentOrder"]["orderDescription"])

    def test_description_over_limit_is_rejected_without_truncation(self):
        response = self.post(
            mo_agent_payload("x" * (MAX_ORDER_DESCRIPTION_LENGTH + 1)))
        self.assertEqual(400, response["statusCode"])
        self.assertIn("VALIDATION_ERROR", response["body"])
        self.assertEqual([], self.table.puts)
        self.assertEqual([], self.dispatched)

    def test_conflicting_descriptions_are_rejected(self):
        payload = mo_agent_payload("root description")
        payload["agentOrder"]["orderDescription"] = "body description"
        response = self.post(payload)
        self.assertEqual(400, response["statusCode"])
        self.assertIn("disagree", response["body"])
        self.assertEqual([], self.table.puts)

    def test_identical_descriptions_at_both_levels_are_accepted(self):
        payload = mo_agent_payload("same description")
        payload["agentOrder"]["orderDescription"] = "same description"
        response = self.post(payload)
        self.assertEqual(201, response["statusCode"], response["body"])
        self.assertEqual("same description",
                         self.table.puts[0]["agentOrder"]["orderDescription"])

    def test_unknown_root_field_is_rejected(self):
        payload = mo_agent_payload()
        payload["shippingAddress"] = "Main St 1"
        response = self.post(payload)
        self.assertEqual(400, response["statusCode"])
        self.assertIn("unsupported field", response["body"])
        self.assertEqual([], self.table.puts)
        self.assertEqual([], self.dispatched)

    def test_retail_fields_with_agent_order_are_rejected(self):
        payload = mo_agent_payload()
        payload["customer"] = {"name": "T", "email": "t@x.io"}
        response = self.post(payload)
        self.assertEqual(400, response["statusCode"])
        self.assertEqual([], self.table.puts)

    def test_unknown_agent_order_field_is_still_rejected(self):
        payload = mo_agent_payload()
        payload["agentOrder"]["priority"] = 1
        response = self.post(payload)
        self.assertEqual(400, response["statusCode"])
        self.assertIn("unknown field", response["body"])
        self.assertEqual([], self.table.puts)

    def test_retail_order_is_unaffected(self):
        with patch.object(orders_reader, "_send_order_created", return_value=None):
            response = self.post(mo_retail_payload())
        self.assertEqual(201, response["statusCode"], response["body"])


class TestRealAdapterForwardsCompleteMoPayload(unittest.TestCase):
    def _adapter(self):
        self.sent = []

        def request_fn(method, url, headers, body, timeout):
            self.sent.append({"method": method, "url": url, "body": body})
            return 201, {"orderId": "ord_mo01", "status": "PENDING"}

        return RealMaysOrdersAdapter(request_fn=request_fn)

    def test_agent_create_forwards_order_type_agent_order_and_description(self):
        adapter = self._adapter()
        payload = mo_agent_payload("vollständiger MO-Payload")
        result = adapter.submit_order({}, "orders.create", payload=payload)

        self.assertTrue(result.success)
        self.assertEqual(1, len(self.sent))
        self.assertTrue(self.sent[0]["url"].endswith("/orders"))
        body = self.sent[0]["body"]
        self.assertEqual(
            {"orderType", "orderDescription", "agentOrder"}, set(body))
        for key in ("orderType", "orderDescription", "agentOrder"):
            self.assertEqual(payload[key], body[key])

    def test_agent_create_never_sends_retail_fields(self):
        adapter = self._adapter()
        payload = mo_agent_payload("agent with retail leftovers")
        payload["customer"] = {"name": "T", "email": "t@x.io"}
        adapter.submit_order({}, "orders.create", payload=payload)
        body = self.sent[0]["body"]
        self.assertNotIn("customer", body)

    def test_agent_create_never_forwards_unknown_caller_keys(self):
        adapter = self._adapter()
        payload = mo_agent_payload("payload with internal key")
        payload["traceId"] = "internal-123"
        adapter.submit_order({}, "orders.create", payload=payload)
        body = self.sent[0]["body"]
        self.assertNotIn("traceId", body)

    def test_retail_create_payload_still_works(self):
        adapter = self._adapter()
        payload = mo_retail_payload()
        adapter.submit_order({}, "orders.create", payload=payload)
        body = self.sent[0]["body"]
        self.assertEqual("EUR", body["currency"])
        self.assertEqual(payload["customer"], body["customer"])
        self.assertEqual(payload["items"], body["items"])
        self.assertEqual(
            {"customer", "items", "currency"}, set(body))


if __name__ == "__main__":
    unittest.main()
