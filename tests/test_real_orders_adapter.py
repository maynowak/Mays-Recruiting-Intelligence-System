"""Tests Gate 6: RealMaysOrdersAdapter, Orders-Function, Reader-POST (Gate 6).

Fake-Transport (kein Netz): Mapping, Fehler, Idempotency-Offenheit,
Kontext-Weitergabe, Secret-Freiheit der Logs/Bodies.
"""

import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orders import RealMaysOrdersAdapter, TransientOrdersError, OrderResult, OrdersResultType
from agents.orders.function import process_orders_work


class FakeTransport:
    """Programmierbarer HTTP-Ersatz: (status, payload) oder Exception."""

    def __init__(self):
        self.calls = []
        self.script = {}

    def when(self, method, path, status, payload=None, exc=None):
        self.script[(method, path)] = (status, payload, exc)

    def __call__(self, method, url, headers, body, timeout):
        from urllib.parse import urlparse
        path = urlparse(url).path or "/"
        self.calls.append({"method": method, "path": path, "headers": headers, "body": body})
        status, payload, exc = self.script.get((method, path), (404, {"error": {"code": "NOT_FOUND"}}, None))
        if exc is not None:
            raise exc
        return status, payload


def adapter(transport, token="tok-test"):
    return RealMaysOrdersAdapter(
        base_url="https://api.test",
        token_provider=lambda: token,
        request_fn=transport,
    )


def order_payload(order_id="ord_x1", status="PENDING"):
    return {"orderId": order_id, "status": status, "customer": {"name": "T", "email": "t@x.io"},
            "items": [], "currency": "EUR", "totalAmount": 0,
            "createdAt": "2026-10-01T00:00:00.000Z", "updatedAt": "2026-10-01T00:00:00.000Z"}


class TestRealAdapterContract(unittest.TestCase):
    def test_port_id_and_capabilities(self):
        a = adapter(FakeTransport())
        self.assertEqual(a.port_id, "real-mays-orders-adapter")
        for cap in ("orders.create", "orders.status", "orders.cancel"):
            self.assertTrue(a.can_handle(cap))
        self.assertFalse(a.can_handle("nope"))

    def test_create_posts_and_maps_pending(self):
        t = FakeTransport()
        t.when("POST", "/orders", 201, order_payload("ord_n1", "PENDING"))
        r = adapter(t).submit_order({"workId": "w-1"}, "orders.create",
                                    {"customer": {"name": "T", "email": "t@x.io"},
                                     "items": [{"sku": "S", "quantity": 1, "unitPrice": 5}]},
                                    tenant_id="ten-1", actor_id="u-1")
        self.assertTrue(r.success)
        self.assertEqual(r.order_id, "ord_n1")
        self.assertEqual(r.result_type, OrdersResultType.PENDING)
        call = t.calls[0]
        self.assertEqual(call["headers"]["Authorization"], "Bearer tok-test")
        self.assertEqual(call["body"]["items"][0]["sku"], "S")
        # Kontext landet im Result, nicht als Rate-Objekt im Body
        self.assertEqual(r.data["tenant_id"], "ten-1")

    def test_create_400_controlled(self):
        t = FakeTransport()
        t.when("POST", "/orders", 400, {"error": {"code": "VALIDATION_ERROR", "message": "bad"}})
        r = adapter(t).submit_order({"workId": "w-1"}, "orders.create", {})
        self.assertFalse(r.success)
        self.assertIn("VALIDATION_ERROR", r.reason)

    def test_create_503_controlled_no_retry(self):
        t = FakeTransport()
        t.when("POST", "/orders", 503, {})
        r = adapter(t).submit_order({"workId": "w-1"}, "orders.create", {})
        self.assertFalse(r.success)
        self.assertIn("POST_UNKNOWN", r.reason)
        self.assertFalse(r.data["safe_to_retry"])

    def test_create_timeout_controlled_no_raise(self):
        t = FakeTransport()
        t.when("POST", "/orders", 0, None, exc=TimeoutError("timed out"))
        r = adapter(t).submit_order({"workId": "w-1"}, "orders.create", {})
        self.assertFalse(r.success)
        self.assertIn("POST_UNKNOWN", r.reason)

    def test_server_has_no_idempotency_key(self):
        """Belegt OPEN: zwei POSTs -> zwei OrderIds (kein serverseitiger Dedup)."""
        t = FakeTransport()
        t.when("POST", "/orders", 201, order_payload("ord_a"))
        a = adapter(t)
        r1 = a.submit_order({"workId": "w-1"}, "orders.create", {}, idempotency_key="k-1")
        t.when("POST", "/orders", 201, order_payload("ord_b"))
        r2 = a.submit_order({"workId": "w-1"}, "orders.create", {}, idempotency_key="k-1")
        self.assertNotEqual(r1.order_id, r2.order_id)
        bodies = [c["body"] for c in t.calls]
        self.assertTrue(all("idempotencyKey" not in b for b in bodies))

    def test_get_maps_order(self):
        t = FakeTransport()
        t.when("GET", "/orders/ord_x1", 200, order_payload("ord_x1", "CONFIRMED"))
        r = adapter(t).get_order_status("ord_x1")
        self.assertTrue(r.success)
        self.assertEqual(r.order_id, "ord_x1")

    def test_get_404_is_none(self):
        t = FakeTransport()
        r = adapter(t).get_order_status("ord_nope")
        self.assertIsNone(r)

    def test_get_500_raises_transient(self):
        t = FakeTransport()
        t.when("GET", "/orders/ord_x1", 500, {})
        with self.assertRaises(TransientOrdersError):
            adapter(t).get_order_status("ord_x1")

    def test_cancel_patch_and_409(self):
        t = FakeTransport()
        t.when("PATCH", "/orders/ord_x1/status", 200, order_payload("ord_x1", "CANCELLED"))
        r = adapter(t).submit_order({"workId": "w-1"}, "orders.cancel", {"orderId": "ord_x1"})
        self.assertTrue(r.success)
        self.assertEqual(t.calls[0]["body"], {"status": "CANCELLED"})
        t.when("PATCH", "/orders/ord_x1/status", 409,
               {"error": {"code": "INVALID_TRANSITION", "message": "no"}})
        r2 = adapter(t).submit_order({"workId": "w-1"}, "orders.cancel", {"orderId": "ord_x1"})
        self.assertFalse(r2.success)
        self.assertIn("INVALID_TRANSITION", r2.reason)

    def test_unsupported_capability_controlled(self):
        r = adapter(FakeTransport()).submit_order({"workId": "w-1"}, "nope", {})
        self.assertFalse(r.success)
        self.assertIn("UNSUPPORTED_CAPABILITY", r.reason)


class TestOrdersFunction(unittest.TestCase):
    def test_status_delegates_to_port(self):
        seen = {}

        class FakeAdapter:
            port_id = "fake"

            def get_order_status(self, order_id):
                seen["order_id"] = order_id
                return OrderResult(True, order_id, OrdersResultType.APPROVED, "ok", {"order": {}})

        out = process_orders_work(
            {"workId": "w-f", "capability": "orders.status",
             "payload": {"orderId": "ord_f1"}},
            adapter_factory=lambda work: FakeAdapter())
        self.assertTrue(out["success"])
        self.assertEqual(seen["order_id"], "ord_f1")
        self.assertEqual(out["agentId"], "orders_function")

    def test_transient_propagates_for_retry(self):
        class FakeAdapter:
            port_id = "fake"

            def get_order_status(self, order_id):
                raise TransientOrdersError("down", "status", 503)

        with self.assertRaises(TransientOrdersError):
            process_orders_work(
                {"workId": "w-f", "capability": "orders.status",
                 "payload": {"orderId": "ord_f1"}},
                adapter_factory=lambda work: FakeAdapter())

    def test_missing_order_id_validation(self):
        out = process_orders_work({"workId": "w-f", "capability": "orders.status", "payload": {}})
        self.assertFalse(out["success"])


class TestReaderPost(unittest.TestCase):
    def _reader(self):
        spec = importlib.util.spec_from_file_location(
            "orders_reader_uut",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "lambda", "orders_reader.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["orders_reader_uut"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_post_validates_and_returns_201(self):
        mod = self._reader()
        sent = {}

        class FakeTable:
            def put_item(self, Item, ConditionExpression=None):
                sent["item"] = Item

        mod._send_order_created = lambda order_id: sent.setdefault("sqs", order_id)
        resp = mod.handler(
            {"routeKey": "POST /orders",
             "body": json.dumps({"customer": {"name": "T", "email": "t@x.io"},
                                 "items": [{"sku": "S", "quantity": 2, "unitPrice": 100}]})},
            None, table=FakeTable())
        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["status"], "PENDING")
        self.assertEqual(body["totalAmount"], 200)
        self.assertTrue(body["orderId"].startswith("ord_"))
        self.assertEqual(sent["sqs"], body["orderId"])

    def test_post_rejects_float_price(self):
        mod = self._reader()

        class FakeTable:
            def put_item(self, Item, ConditionExpression=None):
                raise AssertionError("darf nicht speichern")

        resp = mod.handler(
            {"routeKey": "POST /orders",
             "body": json.dumps({"customer": {"name": "T", "email": "t@x.io"},
                                 "items": [{"sku": "S", "quantity": 1, "unitPrice": 1.0}]})},
            None, table=FakeTable())
        self.assertEqual(resp["statusCode"], 400)

    def test_post_rejects_empty_items(self):
        mod = self._reader()

        class FakeTable:
            def put_item(self, Item, ConditionExpression=None):
                raise AssertionError("darf nicht speichern")

        resp = mod.handler(
            {"routeKey": "POST /orders",
             "body": json.dumps({"customer": {"name": "T", "email": "t@x.io"}, "items": []})},
            None, table=FakeTable())
        self.assertEqual(resp["statusCode"], 400)

    def test_engine_wrapped_payload_unwrapped(self):
        """Engine-Pfad (payload.payload) wird normalisiert (live belegt)."""
        from agents.orders.function import _payload, _token
        work = {"workId": "w-e", "capability": "orders.status",
                "payload": {"workId": "w-e", "capability": "orders.status",
                            "payload": {"orderId": "ord_deep"},
                            "auth": {"idToken": "tok-deep"}}}
        payload = _payload(work)
        self.assertEqual(payload.get("orderId"), "ord_deep")
        self.assertEqual(_token(work, payload), "tok-deep")


if __name__ == "__main__":
    unittest.main()
