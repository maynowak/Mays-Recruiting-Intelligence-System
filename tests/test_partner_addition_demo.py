"""G01 tests — partner addition demo (local only, no AWS, no network).

Covers the demo path A -> Orders -> RIS -> result, the credential boundary and
the negative cases, using the fake adapters only.
"""

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(os.path.dirname(HERE), "examples", "partner-addition-demo")
sys.path.insert(0, DEMO)
sys.path.insert(0, os.path.dirname(HERE))

from demo_core import (  # noqa: E402
    DemoError,
    DemoService,
    FakeOrders,
    FakeRis,
    build_service,
)

KEY = "ris_demo_" + "x" * 40


class TestServiceFlow(unittest.TestCase):
    def setUp(self):
        self.ris = FakeRis(api_key=KEY)
        self.orders = FakeOrders()
        self.service = DemoService(ris=self.ris, orders=self.orders)

    def test_reference_case_17_plus_25(self):
        created = self.service.create_order({"left": 17, "right": 25})
        self.assertEqual("IN_PROGRESS", created["status"])
        self.assertTrue(created["orderId"].startswith("ord_"))
        order_id = created["orderId"]

        # first poll: work moves QUEUED -> RUNNING
        first = self.service.read_order(order_id)
        self.assertIn(first["status"], ("PENDING", "PROCESSING"))
        self.assertIsNone(first["result"])

        # second poll: work completes, result is stored on the order
        done = self.service.read_order(order_id)
        self.assertEqual("DELIVERED", done["status"])
        self.assertEqual({"left": 17, "right": 25, "sum": 42}, done["result"])

    def test_result_is_stable_on_repeated_reads(self):
        order_id = self.service.create_order({"left": 17, "right": 25})["orderId"]
        self.service.read_order(order_id)
        first = self.service.read_order(order_id)
        second = self.service.read_order(order_id)
        self.assertEqual(first["result"], second["result"])
        self.assertEqual("DELIVERED", second["status"])

    def test_negative_operands(self):
        order_id = self.service.create_order({"left": -5, "right": 5})["orderId"]
        self.service.read_order(order_id)
        self.assertEqual(0, self.service.read_order(order_id)["result"]["sum"])

    def test_invalid_body_is_rejected_before_any_order(self):
        for body in ({}, {"left": 17}, {"left": "17", "right": 25},
                     {"left": True, "right": 25}):
            with self.subTest(body=body):
                with self.assertRaises(DemoError):
                    self.service.create_order(body)
        self.assertEqual({}, self.orders._orders)

    def test_unknown_order_is_404(self):
        with self.assertRaises(DemoError) as ctx:
            self.service.read_order("ord_doesnotexist")
        self.assertEqual(404, ctx.exception.status)

    def test_missing_ris_key_fails_without_inventing_a_result(self):
        service = DemoService(ris=FakeRis(api_key=""), orders=FakeOrders())
        created = service.create_order({"left": 17, "right": 25})
        self.assertEqual("FAILED", created["status"])
        order = service.read_order(created["orderId"])
        self.assertIsNone(order["result"])
        self.assertEqual("FAILED", order["status"])


class TestCredentialBoundary(unittest.TestCase):
    def test_key_is_never_in_order_or_response_payloads(self):
        service = DemoService(ris=FakeRis(api_key=KEY), orders=FakeOrders())
        created = service.create_order({"left": 17, "right": 25})
        service.read_order(created["orderId"])
        order = service.read_order(created["orderId"])
        serialized = json.dumps({"created": created, "order": order})
        self.assertNotIn(KEY, serialized)

    def test_build_service_reads_key_from_environment_only(self):
        original = os.environ.get("RIS_API_KEY")
        os.environ["RIS_API_KEY"] = KEY
        try:
            service = build_service()
            self.assertEqual(KEY, service.ris.api_key)
        finally:
            if original is None:
                os.environ.pop("RIS_API_KEY", None)
            else:
                os.environ["RIS_API_KEY"] = original

    def test_no_key_defaults_to_empty_not_a_placeholder(self):
        original = os.environ.pop("RIS_API_KEY", None)
        try:
            self.assertEqual("", build_service().ris.api_key)
        finally:
            if original is not None:
                os.environ["RIS_API_KEY"] = original

    def test_disallowed_capability_is_rejected(self):
        with self.assertRaises(DemoError):
            FakeRis(api_key=KEY).submit("addition_agent", "math.divide",
                                        {"left": 1, "right": 2}, "idem")


class TestHttpTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as demo_app

        cls.service = DemoService(ris=FakeRis(api_key=KEY), orders=FakeOrders())
        cls.server = demo_app.make_server(cls.service, port=0)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def _post(self, path, body):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_page_contains_form_and_no_credential(self):
        status, html = self._get("/")
        self.assertEqual(200, status)
        self.assertIn("Addition beauftragen", html)
        self.assertIn("Status prüfen", html)
        self.assertNotIn(KEY, html)
        self.assertNotIn("X-Api-Credential", html)

    def test_end_to_end_over_http(self):
        status, body = self._post("/api/orders", {"left": 17, "right": 25})
        self.assertEqual(201, status)
        created = json.loads(body)
        self.assertNotIn(KEY, body)

        order_id = created["orderId"]
        for _ in range(3):
            status, body = self._get(f"/api/orders/{order_id}")
            self.assertEqual(200, status)

        order = json.loads(body)
        self.assertEqual("DELIVERED", order["status"])
        self.assertEqual(42, order["result"]["sum"])
        self.assertNotIn(KEY, body)

    def test_invalid_body_is_400(self):
        status, body = self._post("/api/orders", {"left": "x"})
        self.assertEqual(400, status)
        self.assertNotIn(KEY, body)

    def test_unknown_order_is_404(self):
        status, _body = self._get("/api/orders/ord_missing")
        self.assertEqual(404, status)

    def test_health(self):
        status, body = self._get("/health")
        self.assertEqual(200, status)
        self.assertEqual({"status": "ok"}, json.loads(body))


if __name__ == "__main__":
    unittest.main()
