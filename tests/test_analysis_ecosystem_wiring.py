"""RIS-ANALYSIS-ECOSYSTEM-INTEGRATION-13 — worker/ecosystem wiring."""

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "tests", ROOT / "lambda"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agents.runtime.pipeline import process_record  # noqa: E402
from agents.runtime.remote_agent import LambdaAgentHandler  # noqa: E402
from test_analysis_runner_pipeline import (  # noqa: E402
    FakeResolver,
    FakeTable,
    build_runtime,
    work,
)


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class StaticWiringTest(unittest.TestCase):
    def test_worker_uses_remote_adapter_and_ingress_enqueues(self):
        worker = source("lambda/handler.py")
        ingress = source("lambda/dispatch_ingress.py")
        self.assertIn("build_analysis_executor", worker)
        self.assertIn("analysis_agent=", worker)
        self.assertIn("enqueue_work_item", ingress)
        self.assertNotIn("process_record", ingress)
        self.assertNotIn("build_analysis_executor", ingress)
        self.assertIn("executionMode", source("agents/runtime/remote_agent.py"))

    def test_no_new_queue_or_transport(self):
        analysis = source("terraform/modules/analysis_runtime/main.tf")
        self.assertNotIn("aws_sqs_queue", analysis)
        self.assertNotIn("aws_sqs_queue_policy", analysis)
        self.assertNotIn("ORDER_RESULT", analysis)
        remote = source("agents/runtime/remote_agent.py")
        self.assertNotIn("sqs", remote.lower())
        self.assertNotIn("_forward_order_result", remote)
        self.assertNotIn("send_message", remote)

    def test_worker_and_ingress_get_the_analysis_function(self):
        worker = source("terraform/modules/lambda/main.tf")
        ingress = source("terraform/modules/agent_transport/lambda.tf")
        for body in (worker, ingress):
            self.assertIn("ANALYSIS_FUNCTION_NAME", body)
            self.assertIn("ANALYSIS_REMOTE_TIMEOUT_SECONDS", body)
        root = source("terraform/main.tf")
        self.assertIn("analysis_function_name", root)
        self.assertIn("module.analysis_runtime.analysis_function_name", root)
        self.assertIn("AllowRisWorkerInvokeAnalysis", root)
        self.assertIn("AllowRisIngressInvokeAnalysis", root)
        self.assertIn("principal     = module.lambda.lambda_role_arn", root)
        self.assertIn("principal     = module.agent_transport[0].dispatch_ingress_role_arn",
                      root)

    def test_analysis_runner_keeps_the_work_type_gate(self):
        runner = source("lambda/analysis_runner.py")
        self.assertIn("_is_analysis_work", runner)
        self.assertIn('executionMode") == "agent"', runner)
        self.assertIn("build_analysis_executor", source("lambda/handler.py"))


class SharedPipelineTest(unittest.TestCase):
    class RemoteClient:
        def __init__(self):
            self.calls = 0

        def invoke(self, **kwargs):
            self.calls += 1
            body = {"success": True,
                    "data": {"schemaVersion": "1.0",
                             "results": {"job.tags": {"jobTags": ["Python"]}}}}
            return {"StatusCode": 200,
                    "Payload": io.BytesIO(json.dumps(body).encode())}

    def resolver(self):
        return FakeResolver([
            {"agentId": "analysis-agent", "tenantId": "tenant-canary",
             "entitlementId": "ent-analysis"},
            {"agentId": "addition_agent", "tenantId": "tenant-canary",
             "entitlementId": "ent-addition"},
        ])

    def addition_work(self, work_id="work-add"):
        return {
            "workId": work_id, "type": "agent_addition_agent",
            "tenantId": "tenant-canary", "userId": "user-canary",
            "idempotencyKey": f"key-{work_id}", "capability": "math.add",
            "agentId": "addition_agent", "apiProfileId": "profile-canary",
            "partnerApplicationId": "ris-internal-analysis",
            "payload": {"left": 2, "right": 3},
        }

    def test_two_agents_share_the_queue_and_registry(self):
        runtime, _ = build_runtime()
        runtime["analysis_agent"] = LambdaAgentHandler(
            "ris-dev2-dev-analysis", client=self.RemoteClient())
        runtime["entitlement_resolver"] = self.resolver()
        table = FakeTable()
        addition = process_record(
            {"body": json.dumps(self.addition_work())}, table=table,
            registry=runtime["registry"], body=runtime["body"],
            entitlement_resolver=runtime["entitlement_resolver"],
            analysis_agent=runtime["analysis_agent"])
        analysis = process_record(
            {"body": json.dumps(work("work-ana"))}, table=table,
            registry=runtime["registry"], body=runtime["body"],
            entitlement_resolver=runtime["entitlement_resolver"],
            analysis_agent=runtime["analysis_agent"])
        self.assertEqual("COMPLETED", addition["status"])
        self.assertEqual("addition_agent", addition["agent_id"])
        self.assertEqual("COMPLETED", analysis["status"])
        self.assertEqual("analysis-agent", analysis["agent_id"])
        self.assertNotEqual(addition["workId"], analysis["workId"])

    def test_entitlement_revoke_after_enqueue_blocks_execution(self):
        runtime, session = build_runtime()
        runtime["analysis_agent"] = LambdaAgentHandler(
            "ris-dev2-dev-analysis", client=self.RemoteClient())
        runtime["entitlement_resolver"] = FakeResolver([])
        out = process_record(
            {"body": json.dumps(work("work-revoked"))},
            table=runtime["table"], registry=runtime["registry"],
            body=runtime["body"],
            entitlement_resolver=runtime["entitlement_resolver"],
            analysis_agent=runtime["analysis_agent"])
        self.assertTrue(out["denied"])
        self.assertEqual("DEAD_LETTER", out["status"])
        self.assertEqual(0, session["parser"].job_calls)

    def test_analysis_duplicate_does_not_reexecute(self):
        runtime, _ = build_runtime()
        client = self.RemoteClient()
        runtime["analysis_agent"] = LambdaAgentHandler(
            "ris-dev2-dev-analysis", client=client)
        first = process_record(
            {"body": json.dumps(work("work-dup"))}, table=runtime["table"],
            registry=runtime["registry"], body=runtime["body"],
            entitlement_resolver=runtime["entitlement_resolver"],
            analysis_agent=runtime["analysis_agent"])
        second = process_record(
            {"body": json.dumps(work("work-dup"))}, table=runtime["table"],
            registry=runtime["registry"], body=runtime["body"],
            entitlement_resolver=runtime["entitlement_resolver"],
            analysis_agent=runtime["analysis_agent"])
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(1, client.calls)


class ManifestPinTest(unittest.TestCase):
    RemoteClient = SharedPipelineTest.RemoteClient
    resolver = SharedPipelineTest.resolver

    def test_plan_and_bundle_manifest(self):
        import hashlib

        path = ROOT / "docs" / "reports" / "analysis-final-canary-gate-15b-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(4, manifest["plan"]["adds"])
        self.assertEqual(3, manifest["plan"]["changes"])
        self.assertEqual(0, manifest["plan"]["destroys"])
        self.assertEqual("NO_SHARED_DESTROY", manifest["plan"]["guard"])
        self.assertFalse(manifest["plan"]["applyApproved"])
        for relative, key in (("terraform/lambda.zip", "worker"),
                              ("terraform/analysis-lambda.zip", "analysis")):
            artifact = ROOT / relative
            if not artifact.is_file():
                continue
            self.assertEqual(
                manifest["bundles"][key]["sha256"],
                hashlib.sha256(artifact.read_bytes()).hexdigest(),
                relative)


    def test_dispatch_queue_to_work_queue_to_worker_for_both_agents(self):
        import json
        from unittest.mock import patch

        import dispatch_ingress
        from test_dispatch_ingress_lambda import (
            FakeSQS,
            ProfileStore,
            dispatch_envelope,
            QUEUE_ARN,
        )

        runtime, _ = build_runtime()
        client = self.RemoteClient()
        runtime["analysis_agent"] = LambdaAgentHandler(
            "ris-dev2-dev-analysis", client=client)
        runtime["entitlement_resolver"] = self.resolver()
        table = FakeTable()
        sqs = FakeSQS()
        deps = {"profile_store": ProfileStore(tenant="tenant-canary",
                                               user="user-canary"),
                "table": table, "sqs_client": sqs,
                "work_queue_url": "https://sqs.eu-central-1.amazonaws.com/1/work"}

        def record(envelope, message_id):
            return {"messageId": message_id, "eventSourceARN": QUEUE_ARN,
                    "body": json.dumps(envelope)}

        addition = dispatch_envelope()
        analysis = dispatch_envelope(
            messageId="msg-2", idempotencyKey="idem-2",
            recipient={"system": "ris", "agentId": "analysis-agent",
                       "capability": "analysis.run"},
            payload={"schemaVersion": "1.0",
                     "requestedResults": ["job.tags"],
                     "input": {"job": {"text": "Synthetic Python"}},
                     "idempotencyKey": "analysis-key"},
            execution={"workId": "work-analysis"})
        with patch.object(dispatch_ingress, "_dependencies", return_value=deps):
            out = dispatch_ingress.handler(
                {"Records": [record(addition, "msg-1"),
                             record(analysis, "msg-2")]}, None)
        self.assertEqual([], out["batchItemFailures"])
        self.assertEqual(2, len(sqs.sent))
        self.assertEqual("QUEUED", table.items["work-1"]["status"])
        self.assertEqual("QUEUED", table.items["work-analysis"]["status"])

        for message in sqs.sent:
            body = json.loads(message["MessageBody"])
            result = process_record(
                {"body": json.dumps(body)}, table=table,
                registry=runtime["registry"], body=runtime["body"],
                entitlement_resolver=runtime["entitlement_resolver"],
                analysis_agent=runtime["analysis_agent"])
            self.assertEqual("COMPLETED", result["status"])
            if body["agentId"] == "addition_agent":
                self.assertEqual("addition_agent", result["agent_id"])
                self.assertEqual(42, table.items[body["workId"]]["result"]
                                 ["data"]["sum"])
            else:
                self.assertEqual("analysis-agent", result["agent_id"])
                self.assertTrue(client.calls >= 1)


if __name__ == "__main__":
    unittest.main()
