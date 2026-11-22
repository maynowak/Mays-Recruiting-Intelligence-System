"""Pipeline tests for CV / job / ATS / comparison (synthetic, no AWS)."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.analysis.contracts import (  # noqa: E402
    ANALYSIS_CONSENT_PURPOSE,
    ANALYSIS_NOTICE_VERSION,
    ContractError,
    Identity,
)
from agents.analysis.job_store import (  # noqa: E402
    MAX_JOB_BYTES,
    MAX_TTL_SECONDS,
    STANDARD_TTL_SECONDS,
    InMemoryJobStore,
    JobAccessDenied,
    JobExpired,
    JobTooLarge,
)
from agents.analysis.orchestrator import (  # noqa: E402
    AnalysisOrchestrator,
    job_from_text,
)
from agents.analysis.tags import compare_tags  # noqa: E402
from agents.parsers.node_adapter import ParserUnavailable  # noqa: E402

CV_DATA = {
    "stableId": "a" * 64,
    "cvTags": ["Python", "AWS", "Kubernetes", "German", "MSc"],
    "skills": ["Python", "AWS", "Kubernetes"],
    "experience": [{"title": "Engineer", "company": "X"}],
    "education": [{"degree": "MSc"}],
    "languages": ["German"],
    "location": "Berlin",
    "confidence": "confirmed",
    "parserVersion": "1.0.0",
}
JOB_DATA = {
    "stableId": "b" * 64,
    "jobTags": ["Python", "AWS", "Docker", "Kubernetes"],
    "requiredSkills": ["Python", "AWS"],
    "preferredSkills": ["Docker", "Kubernetes"],
    "experienceRequirements": [{"text": "5+ years"}],
    "workMode": "remote",
    "location": ["Berlin"],
    "confidence": "confirmed",
    "parserVersion": "1.0.0",
    "analysisStatus": "complete",
}
ATS_DATA = {
    "stableId": "b" * 64,
    "atsTags": ["Python", "AWS"],
    "requirements": [{"id": "r1", "text": "Python", "category": "skill"}],
    "matches": [{"requirementId": "r1", "status": "match"}],
    "criticalGaps": [],
    "score": 77.5,
    "analysisStatus": "complete",
}
ALL = frozenset({"parse.cv", "parse.job", "analyze.job", "compare.tags"})


class FakeParser:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def _maybe_fail(self):
        if self.fail:
            raise self.fail

    def parse_cv(self, pdf_base64):
        self.calls.append("parse.cv")
        self._maybe_fail()
        return dict(CV_DATA)

    def parse_job(self, job):
        self.calls.append("parse.job")
        self._maybe_fail()
        return dict(JOB_DATA)

    def parse_ats(self, job, profile):
        self.calls.append("parse.ats")
        self._maybe_fail()
        return dict(ATS_DATA)


def identity(entitlements=ALL, consent=True, tenant="tenant-a", user="user-1"):
    return Identity(
        tenant_id=tenant, user_id=user, entitlements=entitlements,
        consent=consent,
        consent_purpose=ANALYSIS_CONSENT_PURPOSE,
        consent_notice_version=ANALYSIS_NOTICE_VERSION,
        consent_notice_approved=True,
    )


def payload(results, cv=None, job=None, profile=None, idem=None):
    body = {
        "schemaVersion": "1.0",
        "requestedResults": results,
        "input": {"cv": cv, "job": job},
    }
    if profile is not None:
        body["input"]["profile"] = profile
    if idem:
        body["idempotencyKey"] = idem
    return body


def structured_cv():
    return {"structured": {"skills": ["Python", "AWS", "Kubernetes"],
                           "languages": ["German"],
                           "education": [{"degree": "MSc"}],
                           "location": "Berlin"}}


class AnalysisPipelineTest(unittest.TestCase):
    def setUp(self):
        self.parser = FakeParser()
        self.store = InMemoryJobStore(clock=lambda: 1000.0)
        self.orch = AnalysisOrchestrator(parser=self.parser,
                                         job_store=self.store)

    def run_request(self, body, ident=None):
        return self.orch.run(body, ident or identity())

    def test_cv_only_structured_does_not_call_parser(self):
        out = self.run_request(payload(["cv.tags"], cv=structured_cv()))
        self.assertIn("cv.tags", out["results"])
        self.assertEqual([], self.parser.calls)
        self.assertEqual("CVParserResultBody",
                         out["results"]["cv.tags"]["bodyType"])

    def test_job_only_inline_calls_only_job_parser(self):
        out = self.run_request(payload(
            ["job.tags"], job={"text": "Senior Python Engineer\nRequired: Python"}))
        self.assertEqual(["parse.job"], self.parser.calls)
        self.assertEqual("JobParserResultBody",
                         out["results"]["job.tags"]["bodyType"])

    def test_ats_only_uses_cv_skills(self):
        out = self.run_request(payload(
            ["ats.tags"], cv=structured_cv(),
            job={"text": "Senior Python Engineer"}))
        self.assertEqual(["parse.ats"], self.parser.calls)
        body = out["results"]["ats.tags"]
        self.assertEqual("ATSAnalysisResultBody", body["bodyType"])
        self.assertEqual("2.0", body["bodyVersion"])
        self.assertEqual(77.5, body["analysis"]["score"])
        self.assertIn("atsTags", body)

    def test_comparison_only(self):
        out = self.run_request(payload(
            ["comparison"], cv=structured_cv(),
            job={"text": "Senior Python Engineer"}))
        body = out["results"]["comparison"]
        self.assertEqual("ComparisonResultBody", body["bodyType"])
        self.assertEqual(["aws", "python", "kubernetes"], body["matched"])
        self.assertEqual(["docker"], body["missingInCv"])
        self.assertEqual(83.3, body["weightedScore"])
        self.assertEqual(100.0, body["coverage"]["required"])
        self.assertEqual(50.0, body["coverage"]["preferred"])

    def test_full_analysis_runs_each_needed_step_once(self):
        out = self.run_request(payload(
            ["cv.tags", "job.tags", "ats.tags", "comparison"],
            cv=structured_cv(), job={"text": "Senior Python Engineer"}))
        self.assertEqual(["parse.job", "parse.ats"], self.parser.calls)
        self.assertEqual({"cv.tags", "job.tags", "ats.tags", "comparison"},
                         set(out["results"]))

    def test_invalid_result_choice(self):
        with self.assertRaises(ContractError) as ctx:
            self.run_request(payload(["cv.tags", "unknown"]))
        self.assertEqual("invalid_requested_results", ctx.exception.code)

    def test_missing_inputs(self):
        with self.assertRaises(ContractError) as ctx:
            self.run_request(payload(["cv.tags"]))
        self.assertEqual("missing_cv", ctx.exception.code)
        with self.assertRaises(ContractError) as ctx:
            self.run_request(payload(["job.tags"]))
        self.assertEqual("missing_job", ctx.exception.code)

    def test_consent_required(self):
        with self.assertRaises(ContractError) as ctx:
            self.run_request(payload(["cv.tags"], cv=structured_cv()),
                             identity(consent=False))
        self.assertEqual("consent_required", ctx.exception.code)

    def test_entitlement_denied(self):
        with self.assertRaises(ContractError) as ctx:
            self.run_request(payload(["cv.tags"], cv=structured_cv()),
                             identity(entitlements=frozenset({"parse.job"})))
        self.assertEqual("entitlement_denied", ctx.exception.code)

    def test_idempotency_returns_same_result(self):
        body = payload(["job.tags"], job={"text": "Python"}, idem="idem-1")
        first = self.run_request(body)
        second = self.run_request(body)
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["results"], second["results"])
        self.assertEqual(["parse.job"], self.parser.calls)

    def test_cross_tenant_jobref_is_denied(self):
        record = self.store.put("Secret job text", "tenant-a", "user-1")
        with self.assertRaises(ContractError) as ctx:
            self.run_request(
                payload(["job.tags"], job={"jobRef": record.ref}),
                identity(tenant="tenant-b"))
        self.assertEqual("job_access_denied", ctx.exception.code)

    def test_jobref_expired(self):
        record = self.store.put("text", "tenant-a", "user-1")
        self.store._clock = lambda: 1000.0 + STANDARD_TTL_SECONDS + 1
        with self.assertRaises(ContractError) as ctx:
            self.run_request(
                payload(["job.tags"], job={"jobRef": record.ref}),
                identity())
        self.assertEqual("job_ref_expired", ctx.exception.code)

    def test_ttl_standard_and_maximum(self):
        store = InMemoryJobStore(clock=lambda: 0.0)
        record = store.put("text", "tenant-a", "user-1")
        self.assertEqual(STANDARD_TTL_SECONDS, record.expires_at)
        extended = store.extend(record.ref, "tenant-a", "user-1",
                                extend_seconds=4 * 60 * 60)
        self.assertEqual(MAX_TTL_SECONDS, extended.expires_at)
        store._clock = lambda: MAX_TTL_SECONDS + 1
        with self.assertRaises(JobExpired):
            store.get(record.ref, "tenant-a", "user-1")

    def test_size_limit(self):
        store = InMemoryJobStore()
        with self.assertRaises(JobTooLarge):
            store.put("x" * (MAX_JOB_BYTES + 1), "tenant-a", "user-1")

    def test_inline_text_above_32k_requires_jobref(self):
        huge = "x" * (32 * 1024 + 1)
        with self.assertRaises(ContractError) as ctx:
            self.run_request(payload(["job.tags"], job={"text": huge}))
        self.assertEqual("job_text_too_large", ctx.exception.code)

    def test_workitem_result_contains_no_document_content(self):
        out = self.run_request(payload(["job.tags"],
                                       job={"text": "Synthetic job text"}))
        serialized = json.dumps(out)
        self.assertNotIn("pdfBase64", serialized)
        self.assertNotIn("Synthetic job text", serialized)

    def test_parser_unavailable_propagates(self):
        parser = FakeParser(fail=ParserUnavailable("node missing"))
        orch = AnalysisOrchestrator(parser=parser)
        with self.assertRaises(ParserUnavailable):
            orch.run(payload(["job.tags"], job={"text": "Python"}),
                     identity())

    def test_cleanup_delete_is_idempotent(self):
        store = InMemoryJobStore()
        record = store.put("text", "tenant-a", "user-1")
        self.assertTrue(store.delete(record.ref))
        self.assertFalse(store.delete(record.ref))
        with self.assertRaises(Exception):
            store.get(record.ref, "tenant-a", "user-1")

    def test_comparison_is_deterministic_and_alias_aware(self):
        cv = {"skills": ["k8s", "nodejs"]}
        job = {"requiredSkills": ["Kubernetes"], "preferredSkills": ["Node.js"]}
        first = compare_tags(cv, job)
        second = compare_tags(cv, job)
        self.assertEqual(first, second)
        self.assertEqual(["kubernetes", "node.js"], first["matched"])
        self.assertEqual(100.0, first["weightedScore"])
        self.assertEqual([], first["extraInCv"])

    def test_comparison_without_job_tags_is_unknown(self):
        result = compare_tags({"skills": ["Python"]}, {})
        self.assertTrue(result["unknown"])
        self.assertIsNone(result["weightedScore"])

    def test_structured_cv_tags_include_education_and_languages(self):
        out = self.run_request(payload(["cv.tags"], cv=structured_cv()))
        tags = out["results"]["cv.tags"]["cvTags"]
        for expected in ("Python", "AWS", "German", "MSc"):
            self.assertIn(expected, tags)


    def test_analysis_agent_fails_closed_without_entitlements(self):
        from agents.analysis_agent.agent import AnalysisAgent

        agent = AnalysisAgent()
        out = agent.process_work({
            "workId": "w1", "type": "agent_analysis_agent",
            "tenantId": "tenant-a", "idempotencyKey": "i1",
            "capability": "analysis.run",
            "payload": {"schemaVersion": "1.0", "requestedResults": ["cv.tags"],
                        "input": {"cv": structured_cv()}},
        })
        self.assertFalse(out["success"])
        self.assertEqual("ValidationError", out["error"]["type"])

    def test_analysis_agent_runs_requested_pipeline(self):
        from agents.analysis_agent.agent import AnalysisAgent

        agent = AnalysisAgent(config={
            "entitlements": sorted(ALL), "consent": True,
                                      "consent_notice_approved": True},
            orchestrator=AnalysisOrchestrator(parser=self.parser,
                                              job_store=self.store))
        out = agent.process_work({
            "workId": "w2", "type": "agent_analysis_agent",
            "tenantId": "tenant-a", "userId": "user-1",
            "idempotencyKey": "i2", "capability": "analysis.run",
            "payload": {"schemaVersion": "1.0", "requestedResults": ["job.tags"],
                        "input": {"job": {"text": "Senior Python Engineer"}}},
        })
        self.assertTrue(out["success"])
        self.assertIn("job.tags", out["data"]["results"])
        self.assertTrue(agent.validate_work({
            "workId": "w2", "type": "agent_analysis_agent",
            "tenantId": "tenant-a", "idempotencyKey": "i2",
            "capability": "analysis.run", "payload": {}}))

    def test_analysis_agent_propagates_parser_failure(self):
        from agents.analysis_agent.agent import AnalysisAgent

        parser = FakeParser(fail=ParserUnavailable("node missing"))
        agent = AnalysisAgent(config={"entitlements": sorted(ALL),
                                      "consent": True,
                                      "consent_notice_approved": True},
                              orchestrator=AnalysisOrchestrator(parser=parser))
        with self.assertRaises(ParserUnavailable):
            agent.process_work({
                "workId": "w3", "type": "agent_analysis_agent",
                "tenantId": "tenant-a", "userId": "user-1",
                "idempotencyKey": "i3", "capability": "analysis.run",
                "payload": {"schemaVersion": "1.0", "requestedResults": ["job.tags"],
                            "input": {"job": {"text": "Python"}}},
            })

    def test_pipeline_registers_analysis_agent(self):
        from agents.runtime.pipeline import ensure_reference_agent

        registry, _ = ensure_reference_agent()
        self.assertTrue(registry.is_registered("analysis-agent"))


    def test_wrong_consent_purpose_denied(self):
        from dataclasses import replace

        with self.assertRaises(ContractError) as ctx:
            self.run_request(
                payload(["cv.tags"], cv=structured_cv()),
                replace(identity(), consent_purpose="application-storage"))
        self.assertEqual("consent_purpose_mismatch", ctx.exception.code)

    def test_draft_notice_not_approved_denied(self):
        from dataclasses import replace

        with self.assertRaises(ContractError) as ctx:
            self.run_request(
                payload(["cv.tags"], cv=structured_cv()),
                replace(identity(), consent_notice_approved=False))
        self.assertEqual("consent_notice_not_approved", ctx.exception.code)

    def test_claimed_external_partner_denied(self):
        body = payload(["cv.tags"], cv=structured_cv())
        body["partnerId"] = "external-partner"
        with self.assertRaises(ContractError) as ctx:
            self.run_request(body)
        self.assertEqual("partner_mismatch", ctx.exception.code)

    def test_caller_partner_mismatch_denied(self):
        from dataclasses import replace

        with self.assertRaises(ContractError) as ctx:
            self.run_request(
                payload(["cv.tags"], cv=structured_cv()),
                replace(identity(), caller_partner_id="external-partner"))
        self.assertEqual("partner_mismatch", ctx.exception.code)

    def test_cv_owner_and_tenant_are_owner_only(self):
        from agents.analysis.partner import assert_cv_owner

        assert_cv_owner(identity(), "user-1", "tenant-a")
        with self.assertRaises(ContractError) as ctx:
            assert_cv_owner(identity(), "user-2", "tenant-a")
        self.assertEqual("cv_owner_mismatch", ctx.exception.code)
        with self.assertRaises(ContractError) as ctx:
            assert_cv_owner(identity(), "user-1", "tenant-b")
        self.assertEqual("cv_tenant_mismatch", ctx.exception.code)


    def test_analysis_consent_purpose_is_draft_and_separate(self):
        from jobsearch.consent_contract import (
            CONSENT_PURPOSES,
            NOTICE_DRAFT,
            NOTICE_REGISTRY,
        )

        self.assertIn("analysis-processing", CONSENT_PURPOSES)
        self.assertEqual({"1.0"}, set(CONSENT_PURPOSES["analysis-processing"]))
        entry = NOTICE_REGISTRY["analysis-processing"]["1.0"]
        self.assertEqual(NOTICE_DRAFT, entry.state)
        # Existing purposes are not extended by the analysis notice.
        self.assertNotIn("analysis-processing",
                         CONSENT_PURPOSES["application-storage"])


if __name__ == "__main__":
    unittest.main()
