"""Cross-repository contract test against the REAL Mays-Orders validator.

Requires ``MO_ORDERS_SRC`` to point at a Mays-Orders checkout's ``lambda/src``
(the authoritative upstream validator: ``validation.validate_create_order``).
The test is skipped when the environment variable is absent — a mocked
acceptance is explicitly NOT a substitute.

Covered:
  * the body produced by ``RealMaysOrdersAdapter`` passes the real MO validator
  * the MO-normalised ``orderDescription`` parses back into a RIS agent order
  * payloads MO rejects are also rejected by the RIS reader
  * documented divergence: MO allows N items, the RIS composite contract
    requires exactly one for agent execution (asserted, not hidden)
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

MO_SRC = os.environ.get("MO_ORDERS_SRC", "")
if MO_SRC:
    sys.path.insert(0, MO_SRC)

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST"
CLIENT = "client-test"
OWNER = "owner-1"
TENANT = "tenant-a"
PROFILE = "aprof_xrepo"

os.environ.setdefault("ORDERS_TABLE", "ris-dev2-mays-orders")
os.environ.setdefault(
    "ORDERS_SQS_QUEUE_URL",
    "https://sqs.eu-central-1.amazonaws.com/262370457690/"
    "ris-dev2-mays-orders-orders-queue")
os.environ.setdefault("ORDERS_COGNITO_ISSUER", ISSUER)
os.environ.setdefault("ORDERS_COGNITO_CLIENT_ID", CLIENT)


def _load_reader():
    spec = importlib.util.spec_from_file_location(
        "orders_reader_xrepo", os.path.join(_REPO_ROOT, "lambda", "orders_reader.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["orders_reader_xrepo"] = module
    spec.loader.exec_module(module)
    return module


def my_agent_order():
    return {
        "schemaVersion": "1.0",
        "target": {"agentId": "ats-agent", "capability": "analyze.job"},
        "input": {"schemaVersion": "1.0",
                  "data": {"job": {"title": "Senior Python Engineer"},
                           "profile": {"skills": "Python"}}},
        "metadata": {"source": "mays-orders", "requestId": "corr-xrepo",
                     "apiProfileRef": PROFILE},
    }


def _event(payload):
    return {
        "routeKey": "POST /orders",
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "iss": ISSUER, "sub": OWNER, "token_use": "access",
            "client_id": CLIENT, "aud": CLIENT,
        }}}},
        "body": json.dumps(payload),
    }


class _Table:
    def __init__(self):
        self.puts = []

    def put_item(self, Item, ConditionExpression=None):
        self.puts.append(dict(Item))

    def update_item(self, **kwargs):
        return None


class _ProfileTable:
    def get_item(self, Key):
        return {"Item": {"apiProfileId": PROFILE, "status": "ACTIVE",
                         "ownerUserId": OWNER, "tenantId": TENANT}}


class _Resolver:
    def find_entitlements(self, user_id):
        return [{"userId": OWNER, "tenantId": TENANT, "agentId": "ats-agent",
                 "entitlementId": "ent-xrepo"}]


@unittest.skipUnless(MO_SRC, "MO_ORDERS_SRC is required for the real MO validator")
class TestMaysOrdersContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load the REAL upstream modules from the MO checkout. They are loaded
        # by path so no other test's module of the same name can be reused.
        def load(name, filename):
            spec = importlib.util.spec_from_file_location(
                name, os.path.join(MO_SRC, filename))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module

        load("errors", "errors.py")
        load("order_types", "order_types.py")
        cls.mo = load("mo_validation", "validation.py")
        cls.reader = _load_reader()
        cls.table = _Table()
        cls.profile_table = _ProfileTable()
        cls.resolver = _Resolver()

    def _adapter_body(self, payload):
        from agents.orders.real import RealMaysOrdersAdapter

        sent = []

        def request_fn(method, url, headers, body, timeout):
            sent.append(body)
            return 201, {"orderId": "ord_xrepo", "status": "PENDING"}

        RealMaysOrdersAdapter(request_fn=request_fn).submit_order(
            {}, "orders.create", payload=payload)
        self.assertEqual(1, len(sent))
        return sent[0]

    def _post(self, payload):
        with patch.object(self.reader, "_send_order_dispatch",
                          side_effect=lambda envelope: None):
            return self.reader.handler(
                _event(payload), None, self.table,
                profile_table=self.profile_table,
                entitlement_resolver=self.resolver)

    def test_adapter_body_is_accepted_by_real_mo_validator(self):
        body = self._adapter_body({
            "agentOrder": my_agent_order(),
            "customer": {"name": "Mays GmbH", "email": "ops@example.com"},
            "items": [{"sku": "ATS", "quantity": 1, "unitPrice": 100}],
            "currency": "EUR",
        })
        normalised = self.mo.validate_create_order(body)
        self.assertEqual("agent.execution", normalised["orderType"])
        self.assertEqual("ops@example.com", normalised["customer"]["email"])
        self.assertEqual(1, len(normalised["items"]))
        self.assertIn("orderDescription", normalised)

    def test_mo_normalised_description_round_trips_into_ris(self):
        from agents.orders.agent_order import parse_agent_order_description
        from agents.orders.real import RealMaysOrdersAdapter

        sent = []

        def request_fn(method, url, headers, body, timeout):
            sent.append(body)
            return 201, {"orderId": "ord_xrepo", "status": "PENDING"}

        RealMaysOrdersAdapter(request_fn=request_fn).submit_order(
            {}, "orders.create",
            payload={"agentOrder": my_agent_order(),
                     "customer": {"name": "M", "email": "m@example.com"}})
        normalised = self.mo.validate_create_order(sent[0])
        parsed = parse_agent_order_description(normalised["orderDescription"])
        self.assertEqual("corr-xrepo", parsed["metadata"]["requestId"])
        self.assertEqual("ats-agent", parsed["target"]["agentId"])

    def test_payload_accepted_by_mo_is_accepted_by_reader(self):
        body = self._adapter_body({
            "agentOrder": my_agent_order(),
            "customer": {"name": "Mays", "email": "ops@example.com"},
            "items": [{"sku": "ATS", "quantity": 1, "unitPrice": 100}],
            "currency": "EUR",
        })
        self.mo.validate_create_order(body)  # must not raise
        response = self._post(body)
        self.assertEqual(201, response["statusCode"], response["body"])

    def test_payload_rejected_by_mo_is_rejected_by_reader(self):
        cases = [
            {"customer": {"name": "M", "email": "not-an-email"},
             "items": [{"sku": "A", "quantity": 1, "unitPrice": 1}],
             "currency": "EUR"},
            {"customer": {"name": "M", "email": "m@example.com"},
             "items": [{"sku": "A", "quantity": 0, "unitPrice": 1}],
             "currency": "EUR"},
            {"customer": {"name": "M", "email": "m@example.com"},
             "items": [{"sku": "A", "quantity": 1, "unitPrice": 1}],
             "currency": "eur"},
            {"customer": {"name": "", "email": "m@example.com"},
             "items": [{"sku": "A", "quantity": 1, "unitPrice": 1}],
             "currency": "EUR"},
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(Exception):
                    self.mo.validate_create_order(case)
                payload = dict(case)
                payload["orderType"] = "agent.execution"
                payload["orderDescription"] = self._description()
                response = self._post(payload)
                self.assertEqual(400, response["statusCode"])

    def test_documented_divergence_exactly_one_item(self):
        """MO allows N items; the RIS composite contract requires one."""
        from agents.orders.agent_order import serialize_agent_order_description

        two_items = {
            "customer": {"name": "M", "email": "m@example.com"},
            "items": [{"sku": "A", "quantity": 1, "unitPrice": 1},
                      {"sku": "B", "quantity": 1, "unitPrice": 1}],
            "currency": "EUR",
            "orderType": "agent.execution",
            "orderDescription": serialize_agent_order_description(my_agent_order()),
        }
        normalised = self.mo.validate_create_order(two_items)
        self.assertEqual(2, len(normalised["items"]))
        response = self._post(two_items)
        self.assertEqual(400, response["statusCode"])
        self.assertIn("exactly one items", response["body"])

    def _description(self):
        from agents.orders.agent_order import serialize_agent_order_description

        return serialize_agent_order_description(my_agent_order())


if __name__ == "__main__":
    unittest.main()
