"""RIS-ANALYSIS-AGENT-RUNTIME-11 STEP B — dedicated analysis runner wiring."""

import json
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

from analysis_runner import (  # noqa: E402
    analysis_config_from_env,
    build_runtime,
    handler,
)


class ConfigTest(unittest.TestCase):
    def test_defaults_deny(self):
        config = analysis_config_from_env({})
        self.assertEqual([], config["entitlements"])
        self.assertFalse(config["consent"])
        self.assertFalse(config["consent_notice_approved"])
        self.assertEqual("ris-internal", config["caller_partner_id"])
        self.assertEqual("analysis-processing", config["consent_purpose"])
        self.assertEqual("1.0", config["consent_notice_version"])

    def test_explicit_operator_values(self):
        config = analysis_config_from_env({
            "ANALYSIS_ENTITLEMENTS": "parse.cv, parse.job,analyze.job,",
            "ANALYSIS_CONSENT": "TRUE",
            "ANALYSIS_NOTICE_APPROVED": "1",
            "ANALYSIS_CALLER_PARTNER_ID": "ris-internal",
        })
        self.assertEqual(["parse.cv", "parse.job", "analyze.job"],
                         config["entitlements"])
        self.assertTrue(config["consent"])
        self.assertTrue(config["consent_notice_approved"])


class EventParsingTest(unittest.TestCase):
    def test_direct_wrapped_and_sqs_events(self):
        work = {"workId": "w1", "type": "agent_analysis_agent",
                "capability": "analysis.run", "agentId": "analysis-agent"}
        calls = []

        def process(record, **kwargs):
            calls.append((record, kwargs))
            return {"workId": json.loads(record["body"])["workId"],
                    "status": "COMPLETED"}

        runtime = {"process": process}
        self.assertEqual(1, handler(dict(work), runtime=runtime)["processed"])
        self.assertEqual(1, handler({"workItem": work, "messageId": "m2"},
                                    runtime=runtime)["processed"])
        sqs = {"Records": [{"messageId": "m3",
                            "body": json.dumps(work)}]}
        self.assertEqual(1, handler(sqs, runtime=runtime)["processed"])
        self.assertEqual("m3", calls[-1][0]["messageId"])

    def test_orders_work_is_rejected_before_the_pipeline(self):
        calls = []

        def process(record, **kwargs):  # pragma: no cover - must not run
            calls.append(record)
            return {"status": "COMPLETED"}

        order_work = {"workId": "order-1", "type": "agent_orders",
                      "capability": "orders.create",
                      "agentId": "orders_function",
                      "payload": {"customer": {"name": "x", "email": "x@y"}}}
        out = handler(order_work, runtime={"process": process})
        self.assertEqual("REJECTED", out["results"][0]["status"])
        self.assertEqual("work_type_not_allowed", out["results"][0]["reason"])
        self.assertEqual([], calls)

    def test_invalid_event_fails_closed(self):
        with self.assertRaises(ValueError):
            handler({"nothing": True}, runtime={"process": lambda *a, **k: {}})
        with self.assertRaises(ValueError):
            handler(["not", "an", "object"],
                    runtime={"process": lambda *a, **k: {}})

    def test_handler_passes_runtime_objects(self):
        seen = {}

        def process(record, **kwargs):
            seen.update(kwargs)
            return {"status": "COMPLETED"}

        marker = object()
        handler({"workId": "w1", "type": "agent_analysis_agent",
                 "capability": "analysis.run", "agentId": "analysis-agent"},
                runtime={"process": process, "table": marker, "registry": marker,
                         "body": marker, "entitlement_resolver": marker,
                         "analysis_agent": marker})
        self.assertIs(marker, seen["table"])
        self.assertIs(marker, seen["analysis_agent"])

    def test_permanent_rejection_is_controlled_and_not_logged_with_body(self):
        sentinel = "SYNTHETIC-BODY-MUST-NOT-APPEAR"

        def process(record, **kwargs):
            raise ValueError(sentinel)

        with self.assertLogs("analysis_runner", level="WARNING") as logs:
            out = handler({"workId": "w1", "type": "agent_analysis_agent",
                           "capability": "analysis.run",
                           "agentId": "analysis-agent", "payload": sentinel},
                          runtime={"process": process})
        self.assertEqual("REJECTED", out["results"][0]["status"])
        self.assertNotIn(sentinel, "\n".join(logs.output))

    def test_unexpected_failure_propagates_for_retry(self):
        def process(record, **kwargs):
            raise RuntimeError("transient")

        with self.assertRaises(RuntimeError):
            handler({"workId": "w1", "type": "agent_analysis_agent",
                     "capability": "analysis.run", "agentId": "analysis-agent"},
                    runtime={"process": process})


class BuildRuntimeTest(unittest.TestCase):
    def test_only_analysis_agent_is_registered_and_configured(self):
        env = {
            "RIS_PARSER_MODE": "lambda",
            "RIS_PARSER_FUNCTION": "ris-dev2-dev-analysis-parser",
            "ANALYSIS_ENTITLEMENTS": "parse.cv,parse.job,analyze.job,compare.tags",
            "ANALYSIS_CONSENT": "true",
            "ANALYSIS_NOTICE_APPROVED": "true",
        }
        runtime = build_runtime(env)
        self.assertTrue(runtime["registry"].is_registered("analysis-agent"))
        self.assertEqual("parse.cv",
                         runtime["analysis_agent"].config["entitlements"][0])
        self.assertEqual("lambda", runtime["analysis_agent"]._orchestrator
                         .parser.mode)
        self.assertIsNone(runtime["entitlement_resolver"])
        self.assertTrue(callable(runtime["process"]))

    def test_missing_entitlement_table_disables_recheck_only_for_harness(self):
        runtime = build_runtime({})
        self.assertIsNone(runtime["entitlement_resolver"])
        self.assertEqual([], runtime["analysis_agent"].config["entitlements"])


class ExecutionModeTest(unittest.TestCase):
    class Parser:
        def parse_cv(self, pdf_base64):  # pragma: no cover - not used
            return {}

        def parse_job(self, job):
            return {"stableId": "b" * 64, "jobTags": ["Python"],
                    "parserVersion": "fake-1.0"}

        def parse_ats(self, job, profile):  # pragma: no cover - not used
            return {}

    def test_execution_mode_runs_only_the_agent(self):
        from agents.analysis.orchestrator import AnalysisOrchestrator

        orchestrator = AnalysisOrchestrator(parser=self.Parser())
        work = {
            "workId": "w-exec", "type": "agent_analysis_agent",
            "tenantId": "tenant-canary", "userId": "user-canary",
            "idempotencyKey": "key", "capability": "analysis.run",
            "agentId": "analysis-agent",
            "payload": {"schemaVersion": "1.0",
                        "requestedResults": ["job.tags"],
                        "input": {"job": {"text": "Synthetic: Python"}}},
        }
        env = {
            "ANALYSIS_ENTITLEMENTS": "parse.job",
            "ANALYSIS_CONSENT": "true",
            "ANALYSIS_NOTICE_APPROVED": "true",
        }
        with mock.patch.dict("os.environ", env, clear=False), \
                mock.patch(
                    "analysis_runner.build_orchestrator",
                    return_value=orchestrator):
            result = handler({"executionMode": "agent", "workItem": work},
                             runtime={"process": self.fail})
        self.assertTrue(result["success"])
        self.assertIn("job.tags", result["data"]["results"])

    def test_execution_mode_rejects_order_work(self):
        result = handler({
            "executionMode": "agent",
            "workItem": {"type": "agent_orders", "capability": "orders.create",
                         "agentId": "orders_function", "workId": "o1"}})
        self.assertFalse(result["success"])
        self.assertEqual("ValidationError", result["error"]["type"])

    def test_execution_mode_rejects_invalid_event(self):
        result = handler({"executionMode": "agent", "workItem": "x"})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
