"""RIS-ANALYSIS-OFFER-E2E-15 STEP E1 — synthetic identity isolation."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

from agents.analysis.contracts import (  # noqa: E402
    ANALYSIS_CONSENT_PURPOSE,
    ANALYSIS_NOTICE_VERSION,
    ContractError,
    Identity,
    require_capabilities,
)
from agents.analysis.cv_bridge import RequestCvResolver  # noqa: E402
from agents.analysis.orchestrator import AnalysisOrchestrator  # noqa: E402
from agents.analysis_agent.agent import AnalysisAgent  # noqa: E402
from analysis_runner import (  # noqa: E402
    analysis_config_from_env,
    handler,
)

TENANT = "tenant-synthetic-canary"
USER = "user-synthetic-canary"
PARTNER = "ris-internal-analysis"
ISSUER = "https://issuer.invalid/synthetic"
FUTURE = "2099-01-01T00:00:00+00:00"
ALL = "parse.cv,parse.job,analyze.job,compare.tags"

JOB = {
    "stableId": "b" * 64,
    "jobTags": ["Python", "AWS", "Docker"],
    "requiredSkills": ["Python", "AWS"],
    "preferredSkills": ["Docker"],
    "experienceRequirements": [{"text": "5+ years"}],
    "workMode": "remote",
    "location": ["Berlin"],
    "confidence": "confirmed",
    "analysisStatus": "complete",
    "parserVersion": "fake-1.0",
}
ATS = {
    "stableId": "b" * 64,
    "atsTags": ["Python", "AWS"],
    "requirements": [{"id": "r1", "text": "Python", "category": "skill"}],
    "matches": [{"requirementId": "r1", "status": "MATCHED"}],
    "criticalGaps": [],
    "score": 80.0,
    "analysisStatus": "complete",
    "parserVersion": "fake-1.0",
}


class Parser:
    def parse_cv(self, pdf_base64):  # pragma: no cover - structured path
        raise AssertionError("structured CV must not be parsed")

    def parse_job(self, job):
        return dict(JOB)

    def parse_ats(self, job, profile):
        return dict(ATS)


class Loader:
    def __call__(self, *args):
        raise AssertionError("synthetic structured CV must not load S3")


def env(**overrides):
    base = {
        "ANALYSIS_SYNTHETIC_MODE": "true",
        "ANALYSIS_SYNTHETIC_TENANT_ID": TENANT,
        "ANALYSIS_SYNTHETIC_USER_ID": USER,
        "ANALYSIS_SYNTHETIC_PARTNER_APPLICATION_ID": PARTNER,
        "ANALYSIS_SYNTHETIC_ISSUER": ISSUER,
        "ANALYSIS_SYNTHETIC_ENTITLEMENTS": ALL,
        "ANALYSIS_SYNTHETIC_EXPIRES_AT": FUTURE,
    }
    base.update(overrides)
    return base


def request(results, cv=None, job=None, profile=None, key=None):
    body = {"schemaVersion": "1.0", "requestedResults": results,
            "input": {}, "idempotencyKey": key or f"synthetic-{id(results)}-{results}"}
    if cv is not None:
        body["input"]["cv"] = cv
    if job is not None:
        body["input"]["job"] = job
    if profile is not None:
        body["input"]["profile"] = profile
    return body


def structured(skills=None):
    return {"structured": {"skills": skills or ["Python", "AWS", "Docker"]}}


def work(payload, tenant=TENANT, user=USER, partner=PARTNER, issuer=ISSUER):
    return {
        "workId": "work-synthetic", "type": "agent_analysis_agent",
        "tenantId": tenant, "userId": user,
        "idempotencyKey": "synthetic-key", "capability": "analysis.run",
        "agentId": "analysis-agent",
        "partnerApplicationId": partner, "issuer": issuer,
        "payload": payload,
    }


def agent(environment):
    return AnalysisAgent(
        analysis_config_from_env(environment),
        orchestrator=AnalysisOrchestrator(
            parser=Parser(),
            cv_resolver=RequestCvResolver(document_loader=Loader(),
                                          repository=None)))


def is_denied(result, code):
    return (not result.get("success")
            and code in str((result.get("error") or {}).get("message")))


class SyntheticConfigTest(unittest.TestCase):
    def test_default_disabled(self):
        config = analysis_config_from_env({})
        self.assertFalse(config["synthetic"]["enabled"])

    def test_complete_profile_enabled(self):
        profile = analysis_config_from_env(env())["synthetic"]
        self.assertTrue(profile["enabled"])
        self.assertEqual(TENANT, profile["tenant_id"])

    def test_incomplete_expired_or_invalid_profile_disables(self):
        for overrides in (
                {"ANALYSIS_SYNTHETIC_TENANT_ID": ""},
                {"ANALYSIS_SYNTHETIC_USER_ID": ""},
                {"ANALYSIS_SYNTHETIC_PARTNER_APPLICATION_ID": ""},
                {"ANALYSIS_SYNTHETIC_ISSUER": ""},
                {"ANALYSIS_SYNTHETIC_ENTITLEMENTS": ""},
                {"ANALYSIS_SYNTHETIC_EXPIRES_AT": ""},
                {"ANALYSIS_SYNTHETIC_EXPIRES_AT": "2020-01-01T00:00:00Z"},
                {"ANALYSIS_SYNTHETIC_EXPIRES_AT": "not-a-date"}):
            self.assertFalse(
                analysis_config_from_env(env(**overrides))["synthetic"]["enabled"],
                overrides)

    def test_profile_is_not_enabled_by_payload_fields(self):
        config = analysis_config_from_env({})
        self.assertFalse(config["synthetic"]["enabled"])
        out = agent({}).process_work(work(
            request(["cv.tags"], cv=structured()),
            tenant=TENANT))
        self.assertFalse(out["success"])
        self.assertIn("analysis_identity_not_configured",
                      out["error"]["message"])


class SyntheticIdentityTest(unittest.TestCase):
    def test_exact_identity_gets_a_synthetic_identity(self):
        ident = agent(env())._identity(work(
            request(["cv.tags"], cv=structured())))
        self.assertTrue(ident.synthetic)
        self.assertFalse(ident.consent_notice_approved)
        self.assertEqual(TENANT, ident.tenant_id)
        self.assertIn("parse.cv", ident.entitlements)

    def test_every_mismatch_is_denied(self):
        cases = (
            {"tenant": "tenant-other"},
            {"user": "user-other"},
            {"partner": "external-partner"},
            {"issuer": "https://issuer.invalid/other"},
        )
        for case in cases:
            out = agent(env()).process_work(work(
                request(["cv.tags"], cv=structured()), **case))
            self.assertTrue(is_denied(out, "consent_required"), case)

    def test_manipulated_nested_workitem_is_denied(self):
        nested = work(request(["cv.tags"], cv=structured()),
                      tenant="tenant-other", user="user-other")
        top = work(nested)
        out = agent(env()).process_work(top)
        self.assertTrue(is_denied(out, "consent_required"))

    def test_real_identity_with_mode_active_is_denied(self):
        out = agent(env()).process_work(work(
            request(["job.tags"], job={"text": "Python"}),
            tenant="tenant-real", user="user-real",
            partner="real-partner", issuer="https://issuer.real"))
        self.assertTrue(is_denied(out, "consent_required"))

    def test_missing_capability_is_entitlement_denied(self):
        out = agent(env(
            ANALYSIS_SYNTHETIC_ENTITLEMENTS="parse.job")).process_work(work(
                request(["cv.tags"], cv=structured())))
        self.assertTrue(is_denied(out, "entitlement_denied"))

    def test_direct_invoke_without_allowlist_context_is_denied(self):
        out = handler({"executionMode": "agent", "workItem": {
            "workId": "direct", "type": "agent_analysis_agent",
            "tenantId": TENANT, "userId": USER,
            "capability": "analysis.run", "agentId": "analysis-agent",
            "payload": request(["cv.tags"], cv=structured())}})
        self.assertFalse(out["success"])
        self.assertTrue("consent_required" in out["error"]["message"]
                        or "analysis_identity_not_configured"
                        in out["error"]["message"])

    def test_synthetic_identity_requires_real_consent_for_normal_path(self):
        synthetic = Identity(
            tenant_id=TENANT, user_id=USER, entitlements=frozenset({"parse.cv"}),
            consent=True, consent_purpose=ANALYSIS_CONSENT_PURPOSE,
            consent_notice_version=ANALYSIS_NOTICE_VERSION,
            consent_notice_approved=False, synthetic=True)
        require_capabilities(["cv.tags"], synthetic)

        real = Identity(
            tenant_id=TENANT, user_id=USER, entitlements=frozenset({"parse.cv"}),
            consent=True, consent_purpose=ANALYSIS_CONSENT_PURPOSE,
            consent_notice_version=ANALYSIS_NOTICE_VERSION,
            consent_notice_approved=False)
        with self.assertRaises(ContractError) as ctx:
            require_capabilities(["cv.tags"], real)
        self.assertEqual("consent_notice_not_approved", ctx.exception.code)


class SyntheticPositivesTest(unittest.TestCase):
    def setUp(self):
        self.agent = agent(env())

    def test_cv_job_comparison_and_ats(self):
        cv = self.agent.process_work(work(
            request(["cv.tags"], cv=structured())))
        self.assertTrue(cv["success"])
        self.assertEqual("CVParserResultBody",
                         cv["data"]["results"]["cv.tags"]["bodyType"])

        job = self.agent.process_work(work(
            request(["job.tags"], job={"text": "Senior Python Engineer"})))
        self.assertTrue(job["success"])
        self.assertEqual("JobParserResultBody",
                         job["data"]["results"]["job.tags"]["bodyType"])

        match = self.agent.process_work(work(request(
            ["comparison", "ats.tags"], cv=structured(),
            job={"text": "Senior Python Engineer"})))
        self.assertTrue(match["success"])
        self.assertEqual("ComparisonResultBody",
                         match["data"]["results"]["comparison"]["bodyType"])
        self.assertEqual("ATSAnalysisResultBody",
                         match["data"]["results"]["ats.tags"]["bodyType"])
        self.assertEqual(100.0, match["data"]["results"]["comparison"]
                         ["coverage"]["required"])
        self.assertEqual(80.0, match["data"]["results"]["comparison"]
                         ["provenance"]["atsScore"])


if __name__ == "__main__":
    unittest.main()
