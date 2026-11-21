"""RIS-ANALYSIS-AGENT-RUNTIME-11 STEP B — internal-partner execution.

Uses the real runtime pipeline (WorkItem registration, entitlement re-check,
agent execution, result persistence) with in-memory tables and a fake parser.
No AWS and no real data.
"""

import base64
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "lambda"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from analysis_runner import handler  # noqa: E402
from agents.agent_body import AgentBody  # noqa: E402
from agents.analysis.contracts import (  # noqa: E402
    ANALYSIS_CONSENT_PURPOSE,
    ANALYSIS_NOTICE_VERSION,
)
from agents.analysis.cv_bridge import RequestCvResolver  # noqa: E402
from agents.analysis.job_store import InMemoryJobStore  # noqa: E402
from agents.analysis.orchestrator import AnalysisOrchestrator  # noqa: E402
from agents.analysis_agent.agent import AnalysisAgent  # noqa: E402
from agents.analysis_agent.registry import register_analysis_agent  # noqa: E402
from agents.ecosystem.registry import AgentRegistry  # noqa: E402
from agents.runtime.pipeline import process_record  # noqa: E402

PDF = b"%PDF-1.7\nsynthetic canary bytes\n%%EOF\n"
PDF_B64 = base64.b64encode(PDF).decode("ascii")
CAPS = ["parse.cv", "parse.job", "analyze.job", "compare.tags"]


class FakeTable:
    class ConditionalFailed(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "ConditionalCheckFailedException"}}

    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        if (ConditionExpression == "attribute_not_exists(workId)"
                and Item["workId"] in self.items):
            raise FakeTable.ConditionalFailed()
        self.items[Item["workId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, ConditionExpression=None):
        item = self.items[Key["workId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        expr = UpdateExpression.split("REMOVE")[0].strip()
        set_part = expr[len("SET "):] if expr.startswith("SET ") else expr
        for assign in set_part.split(","):
            left, right = [part.strip() for part in assign.split("=", 1)]
            item[names.get(left, left)] = values[right]


class FakeResolver:
    def __init__(self, rows):
        self.rows = rows

    def find_entitlements(self, user_id):
        return list(self.rows)


class Record:
    def __init__(self, tenant="tenant-canary", user="user-canary"):
        self.user_id = user
        self.tenant_id = tenant
        self.processing_status = "ready"
        self.document_id = "canary-doc"
        self.content_type = "application/pdf"
        self.status = "active"
        self.deleted_at = None
        self.erased_at = None


class Repo:
    def __init__(self, record=None):
        self.record = record or Record()

    def get(self, *args, **kwargs):
        return self.record


class Loader:
    def __init__(self):
        self.calls = 0

    def __call__(self, *args):
        self.calls += 1
        return PDF


class FakeParser:
    def __init__(self):
        self.cv_calls = 0
        self.job_calls = 0

    def parse_cv(self, pdf_base64):
        self.cv_calls += 1
        return {"stableId": "a" * 64, "cvTags": ["Python"],
                "skills": ["Python"], "parserVersion": "fake-1.0",
                "confidence": "confirmed"}

    def parse_job(self, job):
        self.job_calls += 1
        return {"stableId": "b" * 64, "jobTags": ["Python"],
                "requirements": [{"text": "Python", "category": "skill",
                                  "required": True, "weight": 1}],
                "parserVersion": "fake-1.0"}

    def parse_ats(self, job, profile):
        return {"stableId": "b" * 64, "atsTags": ["Python"],
                "parserVersion": "fake-1.0"}


def work(work_id="work-canary", results=None, cv=None, tenant="tenant-canary",
         user="user-canary"):
    request = {
        "schemaVersion": "1.0",
        "requestedResults": results or ["job.tags"],
        "input": {"job": {"text": "Synthetic canary job: Python required."}},
        "idempotencyKey": f"key-{work_id}",
    }
    if cv is not None:
        request["input"]["cv"] = cv
    return {
        "workId": work_id,
        "type": "agent_analysis_agent",
        "tenantId": tenant,
        "userId": user,
        "idempotencyKey": f"key-{work_id}",
        "capability": "analysis.run",
        "agentId": "analysis-agent",
        "apiProfileId": "profile-canary",
        "partnerApplicationId": "ris-internal-analysis",
        "issuer": "https://issuer.invalid/synthetic",
        "payload": request,
    }


def build_runtime(*, allowed=True, consent=True, record=None, table=None):
    config = {
        "entitlements": CAPS,
        "consent": consent,
        "consent_notice_approved": True,
        "caller_partner_id": "ris-internal",
        "consent_purpose": ANALYSIS_CONSENT_PURPOSE,
        "consent_notice_version": ANALYSIS_NOTICE_VERSION,
    }
    parser = FakeParser()
    session = {
        "parser": parser,
        "loader": Loader(),
    }
    agent = AnalysisAgent(config, orchestrator=AnalysisOrchestrator(
        parser=parser,
        cv_resolver=RequestCvResolver(
            document_loader=session["loader"],
            repository=Repo(record)),
        job_store=InMemoryJobStore(),
    ))
    registry = AgentRegistry()
    body = AgentBody()
    register_analysis_agent(registry, body, agent=agent)
    rows = ([{"agentId": "analysis-agent", "tenantId": "tenant-canary",
              "entitlementId": "ent-canary"}] if allowed else [])
    return {
        "process": process_record,
        "table": table or FakeTable(),
        "registry": registry,
        "body": body,
        "entitlement_resolver": FakeResolver(rows),
        "analysis_agent": agent,
    }, session


class InternalPartnerExecutionTest(unittest.TestCase):
    def test_authorized_work_completes_and_persists(self):
        runtime, session = build_runtime()
        out = handler(work(), runtime=runtime)
        self.assertEqual("COMPLETED", out["results"][0]["status"])
        stored = runtime["table"].items["work-canary"]
        self.assertEqual("COMPLETED", stored["status"])
        self.assertEqual("Python", stored["result"]["data"]["results"]
                         ["job.tags"]["jobTags"][0])
        self.assertEqual(0, session["parser"].cv_calls)

    def test_idempotent_replay_does_not_reexecute(self):
        runtime, session = build_runtime()
        first = handler(work(), runtime=runtime)
        second = handler(work(), runtime=runtime)
        self.assertFalse(first["results"][0]["duplicate"])
        self.assertTrue(second["results"][0]["duplicate"])
        self.assertEqual("COMPLETED", second["results"][0]["status"])
        self.assertEqual(1, session["parser"].job_calls)

    def test_cv_pdf_is_processed_and_not_persisted(self):
        runtime, session = build_runtime()
        out = handler(work(results=["cv.tags"], cv={"cvId": "canary-cv"}),
                      runtime=runtime)
        self.assertEqual("COMPLETED", out["results"][0]["status"])
        self.assertEqual(1, session["loader"].calls)
        stored = json.dumps(runtime["table"].items["work-canary"],
                            default=str)
        self.assertNotIn(PDF_B64, stored)
        self.assertNotIn("synthetic canary bytes", stored)

    def test_missing_entitlement_is_denied_without_execution(self):
        runtime, session = build_runtime(allowed=False)
        out = handler(work(), runtime=runtime)
        self.assertTrue(out["results"][0]["denied"])
        self.assertEqual("DEAD_LETTER", out["results"][0]["status"])
        self.assertEqual(0, session["parser"].cv_calls)
        self.assertEqual("DEAD_LETTER",
                         runtime["table"].items["work-canary"]["status"])

    def test_missing_consent_is_denied(self):
        runtime, _ = build_runtime(consent=False)
        out = handler(work(), runtime=runtime)
        self.assertEqual("DEAD_LETTER", out["results"][0]["status"])
        error = runtime["table"].items["work-canary"]["error"]
        self.assertIn("consent_required", str(error))

    def test_cross_tenant_cv_is_denied(self):
        runtime, session = build_runtime(record=Record(tenant="tenant-other"))
        out = handler(work(results=["cv.tags"], cv={"cvId": "canary-cv"}),
                      runtime=runtime)
        self.assertEqual("DEAD_LETTER", out["results"][0]["status"])
        self.assertEqual(0, session["loader"].calls)

    def test_sqs_event_shape_uses_the_same_pipeline(self):
        runtime, _ = build_runtime()
        event = {"Records": [{"messageId": "m-1",
                              "body": json.dumps(work("work-sqs"))}]}
        out = handler(event, runtime=runtime)
        self.assertEqual("COMPLETED", out["results"][0]["status"])
        self.assertEqual("COMPLETED", runtime["table"].items["work-sqs"]["status"])


class RemoteAndResultPathTest(unittest.TestCase):
    def test_remote_handler_runs_inside_the_existing_pipeline(self):
        from agents.runtime.remote_agent import LambdaAgentHandler
        import io

        class Client:
            def invoke(self, **kwargs):
                body = {"success": True,
                        "data": {"schemaVersion": "1.0",
                                 "results": {"job.tags": {"jobTags": ["Python"]}}}}
                return {"StatusCode": 200,
                        "Payload": io.BytesIO(json.dumps(body).encode())}

        runtime, _ = build_runtime()
        runtime["analysis_agent"] = LambdaAgentHandler(
            "ris-dev2-dev-analysis", client=Client())
        out = handler(work("work-remote"), runtime=runtime)
        self.assertEqual("COMPLETED", out["results"][0]["status"])
        self.assertEqual(["Python"], runtime["table"].items["work-remote"]
                         ["result"]["data"]["results"]["job.tags"]["jobTags"])

    def test_order_result_uses_the_existing_transport_and_stable_id(self):
        from agents.runtime.pipeline import process_record

        runtime, _ = build_runtime()
        sent = []
        item = work("work-order")
        item.update({"orderId": "ord_canary", "correlationId": "corr-1",
                     "apiProfileId": "profile-canary",
                     "payload": {"schemaVersion": "1.0",
                                 "requestedResults": ["job.tags"],
                                 "input": {"job": {"text": "Python"}},
                                 "idempotencyKey": "key-work-order"}})
        record = {"body": json.dumps(item)}
        first = process_record(
            record, table=runtime["table"], registry=runtime["registry"],
            body=runtime["body"],
            entitlement_resolver=runtime["entitlement_resolver"],
            analysis_agent=runtime["analysis_agent"],
            result_sender=sent.append)
        second = process_record(
            record, table=runtime["table"], registry=runtime["registry"],
            body=runtime["body"],
            entitlement_resolver=runtime["entitlement_resolver"],
            analysis_agent=runtime["analysis_agent"],
            result_sender=sent.append)
        self.assertEqual("COMPLETED", first["status"])
        self.assertEqual("SENT", first["order_result_delivery"])
        self.assertEqual("ORDER_RESULT", sent[0]["messageType"])
        self.assertEqual(sent[0]["messageId"], sent[1]["messageId"])
        self.assertTrue(second["duplicate"])
        # Stable idempotency key: Mays-Orders deduplicates the redelivery.
        self.assertEqual(sent[0]["idempotencyKey"], sent[1]["idempotencyKey"])

    def test_order_failed_uses_the_existing_transport(self):
        from agents.analysis.contracts import ContractError
        from agents.runtime.pipeline import process_record

        class Failing:
            def process_work(self, work_item):
                raise ContractError("consent_required", "not approved")

        runtime, _ = build_runtime()
        sent = []
        item = work("work-failed")
        item.update({"orderId": "ord_canary", "correlationId": "corr-2",
                     "apiProfileId": "profile-canary",
                     "payload": {"schemaVersion": "1.0",
                                 "requestedResults": ["job.tags"],
                                 "input": {"job": {"text": "Python"}},
                                 "idempotencyKey": "key-work-failed"}})
        # A raised agent error is a retryable failure, not ORDER_FAILED yet.
        with self.assertRaises(Exception):
            process_record(
                {"body": json.dumps(item)}, table=runtime["table"],
                registry=runtime["registry"], body=runtime["body"],
                entitlement_resolver=runtime["entitlement_resolver"],
                analysis_agent=Failing(), result_sender=sent.append)
        self.assertEqual([], sent)
        self.assertIn(runtime["table"].items["work-failed"]["status"],
                      ("FAILED", "DEAD_LETTER"))


if __name__ == "__main__":
    unittest.main()
