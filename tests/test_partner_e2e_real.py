"""A07 — full local end-to-end with the real application ports.

Skipped unless ``MO_ORDERS_SRC`` points at the Mays-Orders ``lambda/src``.

    MO_ORDERS_SRC=/path/to/mays-order-aws/lambda/src \
        python -m pytest tests/test_partner_e2e_real.py -q
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "partner-addition-demo")
MO_SRC = os.environ.get("MO_ORDERS_SRC")

if MO_SRC and os.path.isdir(MO_SRC):
    sys.path.insert(0, MO_SRC)
sys.path.insert(0, DEMO)
sys.path.insert(0, ROOT)

RESULT_SECRET = "local-result-secret"


class ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


@unittest.skipUnless(MO_SRC and os.path.isdir(MO_SRC),
                     "MO_ORDERS_SRC not set")
class PartnerE2E(unittest.TestCase):
    def setUp(self):
        import identity as mo_identity
        import order_service as mo_orders
        import result_handler as mo_result_handler
        from app_ports import (InMemoryOrdersTable as Table, LocalSqsBus,
                               OrdersApplicationAdapter, RisApplicationAdapter)
        from agents.transport import VerifiedContext
        from demo_core import DemoService

        os.environ["ORDERS_TABLE"] = "orders"
        os.environ["ORDERS_COGNITO_ISSUER"] = (
            "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_P")
        os.environ["ORDERS_COGNITO_CLIENT_ID"] = "client-a"
        os.environ["ORDER_RESULT_SERVICE_SECRET"] = RESULT_SECRET

        self.alice = mo_identity.OwnerIdentity(
            issuer=os.environ["ORDERS_COGNITO_ISSUER"],
            subject="partner-a-user", client_id="client-a")
        self.bob = mo_identity.OwnerIdentity(
            issuer=os.environ["ORDERS_COGNITO_ISSUER"],
            subject="partner-b-user", client_id="client-a")
        self.table = Table()
        self.service = mo_orders.OrderService("orders", client=self.table)
        # Both the HTTP handler and the A06 consumer build their own boto3
        # table; the local E2E injects the in-memory one into both.
        from unittest.mock import patch
        self._patches = [
            patch.object(__import__("index"), "create_order_service",
                         return_value=self.service),
            patch.object(mo_result_handler, "create_order_service",
                         return_value=self.service),
        ]
        for p in self._patches:
            p.start()
        self.bus = LocalSqsBus()
        self.orders = OrdersApplicationAdapter(self.service, self.alice,
                                               self.bus)
        self.context = VerifiedContext(
            context_ref="ctx-partner-a", tenant_id="tenant-a",
            owner_id="partner-a-user", api_profile_id="profile-a",
            partner_application_id="partner-a",
            issuer="https://cognito.internal")

        class Resolver:
            def __init__(self, allow=True, tenant="tenant-a", profile="profile-a"):
                self.allow, self.tenant, self.profile = allow, tenant, profile

            def find_entitlements(self, user_id):
                if not self.allow:
                    return []
                return [{"entitlementId": "e1", "userId": user_id,
                         "tenantId": self.tenant, "agentId": "addition_agent",
                         "apiProfileId": self.profile,
                         "validFrom": "2026-01-01T00:00:00+00:00",
                         "validUntil": "2030-01-01T00:00:00+00:00"}]

        self.Resolver = Resolver
        self.ris = RisApplicationAdapter(
            self.bus, self.context, result_secret=RESULT_SECRET,
            orders_consumer=mo_result_handler.handler,
            resolver=Resolver())
        self.demo = DemoService(ris=self.ris, orders=self.orders)
        self.alice_orders = self.orders
        self.bob_orders = OrdersApplicationAdapter(self.service, self.bob,
                                                   self.bus)

    def tearDown(self):
        for p in getattr(self, "_patches", []):
            p.stop()

    # -- helpers ---------------------------------------------------------
    def _order(self, left=17, right=25):
        created = self.demo.create_order({"left": left, "right": right})
        return created["orderId"]

    def _result_for(self, order_id):
        for envelope in self.ris._outcomes.values():
            if envelope["orderId"] == order_id:
                return envelope
        raise AssertionError("no result envelope produced")

    # -- E02 happy path --------------------------------------------------
    def test_partner_a_gets_42_through_the_real_stack(self):
        created = self.demo.create_order({"left": 17, "right": 25})
        self.assertTrue(created["orderId"].startswith("ord_"))
        self.assertTrue(created["workId"].startswith("work-"))

        order = self.demo.read_order(created["orderId"])
        self.assertEqual("COMPLETED", order["status"])
        self.assertEqual(42, order["result"]["sum"])
        # the fachliche order status is untouched
        self.assertEqual("PENDING", order["orderStatus"])

    def test_dispatch_envelope_uses_the_bound_work_id(self):
        order_id = self._order()
        stored = self.table.items[order_id]
        result = self._result_for(order_id)
        self.assertEqual(stored["expectedWorkId"],
                         result["execution"]["workId"])
        self.assertEqual("ORDER_RESULT", result["messageType"])

    def test_work_item_reaches_the_addition_agent_unchanged(self):
        order_id = self._order(7, 8)
        self.assertEqual(15, self.demo.read_order(order_id)["result"]["sum"])

    def test_no_secret_in_transport_or_response(self):
        order_id = self._order()
        stored = self.table.items[order_id]
        result = self._result_for(order_id)
        payload = json.dumps({"stored": stored, "result": result,
                              "view": self.demo.read_order(order_id)})
        self.assertNotIn("ris_", payload)
        self.assertNotIn(RESULT_SECRET, payload)
        self.assertNotIn("serviceSignature", payload)

    # -- E03 negatives ---------------------------------------------------
    def test_partner_b_cannot_read_a_foreign_order(self):
        from demo_core import DemoError

        order_id = self._order()
        with self.assertRaises(DemoError) as ctx:
            self.bob_orders.get(order_id)
        self.assertEqual(404, ctx.exception.status)

    def test_missing_dispatch_message_never_reports_success(self):
        from app_ports import LocalSqsBus
        from demo_core import DemoError

        empty_bus = LocalSqsBus()
        adapter = type(self.ris)(empty_bus, self.context,
                                 result_secret=RESULT_SECRET,
                                 orders_consumer=lambda e: None)
        with self.assertRaises(DemoError) as ctx:
            adapter.submit("addition_agent", "math.add",
                           {"left": 1, "right": 2}, "k")
        self.assertEqual(503, ctx.exception.status)

    def test_foreign_tenant_is_denied(self):
        from app_ports import LocalSqsBus, OrdersApplicationAdapter
        from demo_core import DemoError

        # own bus so the normal consumer cannot take the message
        bus = LocalSqsBus()
        orders = OrdersApplicationAdapter(self.service, self.alice, bus,
                                          context_ref="ctx-partner-a")
        order_id = orders.create("demo", "math.add",
                                 {"left": 17, "right": 25})
        adapter = type(self.ris)(
            bus, self.context, result_secret=RESULT_SECRET,
            orders_consumer=lambda e: None,
            resolver=self.Resolver(tenant="tenant-other"))
        with self.assertRaises(DemoError) as ctx:
            adapter.submit("addition_agent", "math.add",
                           {"left": 17, "right": 25}, "k")
        self.assertEqual(403, ctx.exception.status)
        self.assertNotIn("processing", self.table.items[order_id])

    def test_unsupported_capability_is_denied(self):
        from demo_core import DemoError

        self._order()
        envelope = dict(self.orders.last_dispatch)
        envelope["recipient"] = {"system": "ris",
                                 "agentId": "addition_agent",
                                 "capability": "math.divide"}
        self.bus.send("agent-dispatch", envelope)
        with self.assertRaises(DemoError) as ctx:
            self.ris.submit("addition_agent", "math.divide",
                            {"left": 17, "right": 25}, "k2")
        self.assertEqual(403, ctx.exception.status)

    def test_missing_identity_reference_blocks_dispatch(self):
        import dispatch as mo_dispatch

        body = {
            "orderType": "agent.execution",
            "agentOrder": {
                "schemaVersion": "1.0",
                "target": {"agentId": "addition_agent",
                           "capability": "math.add"},
                "input": {"data": {"left": 17, "right": 25}},
                "metadata": {"source": "demo", "requestId": "req-x"},
            },
        }
        order_id = self.service.create_order(body, self.alice)["orderId"]
        bound = self.service.prepare_dispatch(order_id, self.alice)
        with self.assertRaises(mo_dispatch.DispatchRejected) as ctx:
            self.service.dispatch_envelope(order_id, bound["workId"])
        self.assertEqual("missing_identity_reference", ctx.exception.code)

    def test_repeated_dispatch_does_not_duplicate_the_execution(self):
        order_id = self._order()
        before = len([e for e in self.ris._outcomes.values()
                      if e["orderId"] == order_id])
        again = self.service.prepare_dispatch(order_id, self.alice)
        self.assertTrue(again["reused"])
        after = len([e for e in self.ris._outcomes.values()
                     if e["orderId"] == order_id])
        self.assertEqual(before, after)

    def test_duplicate_result_is_idempotent(self):
        import result_envelope as mo_result

        order_id = self._order()
        envelope = self._result_for(order_id)
        parsed = mo_result.validate_result_envelope(envelope)
        first = self.service.apply_result(parsed)
        second = self.service.apply_result(parsed)
        self.assertEqual(first["idempotencyKey"], second["idempotencyKey"])
        self.assertEqual(1, len(self.table.items))

    def test_wrong_work_id_is_rejected(self):
        import result_envelope as mo_result

        order_id = self._order()
        envelope = json.loads(json.dumps(self._result_for(order_id)))
        envelope["execution"]["workId"] = "work-foreign"
        with self.assertRaises(mo_result.ResultRejected) as ctx:
            self.service.apply_result(
                mo_result.validate_result_envelope(envelope))
        self.assertEqual("work_mismatch", ctx.exception.code)

    def test_stale_attempt_is_rejected(self):
        import result_envelope as mo_result

        order_id = self._order()
        self.table.items[order_id]["processing"] = {
            "schemaVersion": "1.0", "status": "RUNNING", "attempt": 9}
        envelope = self._result_for(order_id)
        with self.assertRaises(mo_result.ResultRejected) as ctx:
            self.service.apply_result(
                mo_result.validate_result_envelope(envelope))
        self.assertEqual("stale_attempt", ctx.exception.code)

    def test_cancelled_order_accepts_no_result(self):
        import result_envelope as mo_result

        order_id = self._order()
        self.table.items[order_id]["status"] = "CANCELLED"
        envelope = self._result_for(order_id)
        with self.assertRaises(mo_result.ResultRejected) as ctx:
            self.service.apply_result(
                mo_result.validate_result_envelope(envelope))
        self.assertEqual("order_cancelled", ctx.exception.code)

    def test_tampered_result_signature_is_rejected(self):
        import result_handler as mo_result_handler
        import result_envelope as mo_result

        order_id = self._order()
        envelope = self._result_for(order_id)
        body = json.dumps(envelope)
        record = {"messageId": envelope["messageId"], "body": body,
                  "messageAttributes": {"serviceSignature": {
                      "stringValue": "forged"}}}
        response = mo_result_handler.handler({"Records": [record]}, None)
        self.assertEqual(1, json.loads(response["body"])["rejected"])

    def test_html_contains_no_credentials(self):
        import app as demo_app

        self.assertNotIn("ris_", demo_app.PAGE)
        self.assertNotIn(RESULT_SECRET, demo_app.PAGE)


if __name__ == "__main__":
    unittest.main()
