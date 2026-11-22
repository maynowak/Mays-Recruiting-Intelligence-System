"""RIS-ANALYSIS-ORDER-BOUNDARY-AUDIT-12A — analysis stays analysis.

These tests pin the ownership boundary:
- the dedicated analysis compute executes only analysis WorkItems,
- analysis code does not create/mutate orders, price, bill, dispatch or deliver,
- Mays-Orders keeps its own lifecycle and result consumer,
- WorkItem idempotency/result persistence still works through the existing
  pipeline.
"""

import json
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "tests", ROOT / "lambda"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from analysis_runner import handler  # noqa: E402
from test_analysis_runner_pipeline import (  # noqa: E402
    build_runtime,
    work,
)

ANALYSIS_FILES = (
    "lambda/analysis_runner.py",
    "agents/analysis/contracts.py",
    "agents/analysis/orchestrator.py",
    "agents/analysis/cv_bridge.py",
    "agents/analysis/job_store.py",
    "agents/analysis/partner.py",
    "agents/analysis_agent/agent.py",
    "agents/parsers/node_adapter.py",
    "agents/parsers/lambda_adapter.py",
)

ORDER_SYMBOLS = (
    "create_order", "update_order_status", "validate_create_order",
    "build_dispatch_envelope", "submit_order", "send_message",
    "ORDER_RESULT", "ORDER_DISPATCH", "totalAmount", "lineTotal",
    "unitPrice", "billing", "pricing",
)


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class StaticBoundaryTest(unittest.TestCase):
    def test_analysis_code_has_no_order_or_billing_logic(self):
        for relative in ANALYSIS_FILES:
            body = source(relative)
            for symbol in ORDER_SYMBOLS:
                self.assertNotIn(symbol, body, f"{relative} references {symbol}")
            self.assertNotIn("agents.orders", body, relative)

    def test_analysis_code_has_no_order_transport_client(self):
        for relative in ANALYSIS_FILES:
            body = source(relative)
            self.assertNotIn('boto3.client("sqs")', body, relative)
            self.assertNotIn("ORDER_RESULT_QUEUE_URL", body, relative)
            self.assertNotIn("ORDERS_BASE_URL", body, relative)
            self.assertNotIn("idToken", body, relative)

    def test_dedicated_role_policies_have_no_order_access(self):
        module = source("terraform/modules/analysis_runtime/main.tf")
        base = module.split('resource "aws_iam_role_policy" "analysis"', 1)[1]
        base = base.split('resource "', 1)[0]
        data = module.split(
            'resource "aws_iam_role_policy" "analysis_runtime_data"', 1)[1]
        data = data.split('resource "', 1)[0]
        for block in (base, data):
            for forbidden in ("sqs:", "secretsmanager:", "mays-orders",
                              "orders-agent", "ORDER_"):
                self.assertNotIn(forbidden, block)

    def test_analysis_lambda_env_has_no_order_transport(self):
        module = source("terraform/modules/analysis_runtime/main.tf")
        block = module.split('resource "aws_lambda_function" "analysis"', 1)[1]
        block = block.split('resource "', 1)[0]
        self.assertIn("RIS_PARSER_MODE            = \"lambda\"", block)
        for forbidden in ("ORDER_RESULT", "ORDER_DISPATCH", "ORDERS_",
                          "ORDERS_BASE_URL", "ID_TOKEN"):
            self.assertNotIn(forbidden, block)

    def test_orders_ownership_stays_outside_analysis(self):
        transport = source("agents/transport/order_transport.py")
        sender = source("agents/transport/order_result_sender.py")
        dispatch = source("lambda/dispatch_ingress.py")
        self.assertIn("does NOT own", transport)
        self.assertIn("order lifecycle (Mays-Orders)", transport)
        self.assertIn("ORDER_RESULT", sender)
        self.assertIn("SQS dispatch ingress", dispatch)
        # The analysis gateway never imports these modules.
        runner = source("lambda/analysis_runner.py")
        for module in ("order_transport", "order_result_sender",
                       "dispatch_ingress", "agents.orders"):
            self.assertNotIn(module, runner)


class RuntimeBoundaryTest(unittest.TestCase):
    def test_orders_work_is_rejected_without_order_side_effects(self):
        runtime, _ = build_runtime()
        order_work = {
            "workId": "order-canary", "type": "agent_orders",
            "capability": "orders.create", "agentId": "orders_function",
            "tenantId": "tenant-canary", "userId": "user-canary",
            "idempotencyKey": "order-key",
            "payload": {"customer": {"name": "Canary", "email": "c@example.invalid"}},
        }
        out = handler(order_work, runtime=runtime)
        self.assertEqual("REJECTED", out["results"][0]["status"])
        self.assertEqual("work_type_not_allowed", out["results"][0]["reason"])
        self.assertEqual({}, runtime["table"].items)

    def test_analysis_work_does_not_emit_order_delivery(self):
        runtime, _ = build_runtime()
        with mock.patch(
                "agents.runtime.pipeline._resolve_result_sender",
                side_effect=AssertionError("order transport must not resolve")):
            out = handler(work("work-boundary"), runtime=runtime)
        result = out["results"][0]
        self.assertEqual("COMPLETED", result["status"])
        self.assertEqual("NOT_ORDER", result.get("order_result_delivery"))
        stored = runtime["table"].items["work-boundary"]
        self.assertNotIn("orderResultDelivery", stored)
        self.assertEqual("", stored.get("orderId", ""))

    def test_analysis_workitem_persists_and_replays(self):
        runtime, session = build_runtime()
        first = handler(work("work-idem"), runtime=runtime)
        second = handler(work("work-idem"), runtime=runtime)
        self.assertEqual("COMPLETED", first["results"][0]["status"])
        self.assertTrue(second["results"][0]["duplicate"])
        self.assertEqual(1, session["parser"].job_calls)
        self.assertEqual("COMPLETED",
                         runtime["table"].items["work-idem"]["status"])
        self.assertEqual("work:work-idem:attempt:1",
                         runtime["table"].items["work-idem"]["result_reference"])


class ManifestBoundaryTest(unittest.TestCase):
    MANIFEST = ROOT / "docs" / "reports" / "analysis-order-boundary-12a-manifest.json"

    def test_plan_and_bundle_pins(self):
        import hashlib

        manifest = json.loads(self.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual("CORRECTION REQUIRED", manifest["verdict"])
        self.assertEqual(2, manifest["plan"]["adds"])
        self.assertEqual("NO_SHARED_DESTROY", manifest["plan"]["guard"])
        self.assertFalse(manifest["plan"]["applyApproved"])
        self.assertEqual(
            "b892d17a0168cac8df0278890323d1a1b10bbc7cc38dd14536239e776d4f700d",
            manifest["invalidatedPlan"]["sha256"])
        if manifest.get("supersededBy"):
            return
        bundle = ROOT / manifest["bundle"]["path"]
        if bundle.is_file():
            self.assertEqual(manifest["bundle"]["sha256"],
                             hashlib.sha256(bundle.read_bytes()).hexdigest())
        else:
            self.skipTest("analysis bundle not built on this host")

    def test_gate_rejects_every_non_analysis_work_type(self):
        from analysis_runner import _is_analysis_work

        self.assertTrue(_is_analysis_work({
            "type": "agent_analysis_agent", "capability": "analysis.run",
            "agentId": "analysis-agent"}))
        self.assertFalse(_is_analysis_work({
            "type": "agent_orders", "capability": "orders.create",
            "agentId": "orders_function"}))
        self.assertFalse(_is_analysis_work({
            "type": "agent_analysis_agent", "capability": "orders.create",
            "agentId": "analysis-agent"}))
        self.assertFalse(_is_analysis_work({
            "type": "agent_analysis_agent", "capability": "analysis.run",
            "agentId": "orders_function"}))


if __name__ == "__main__":
    unittest.main()
