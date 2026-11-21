"""RIS-ANALYSIS-OFFER-E2E-15 — product contract tests for the three offers."""

import base64
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.analysis.contracts import (  # noqa: E402
    ANALYSIS_CONSENT_PURPOSE,
    ANALYSIS_NOTICE_VERSION,
    ContractError,
    Identity,
)
from agents.analysis.cv_bridge import RequestCvResolver  # noqa: E402
from agents.analysis.orchestrator import AnalysisOrchestrator  # noqa: E402

ALL = frozenset({"parse.cv", "parse.job", "analyze.job", "compare.tags"})
CV_DATA = {
    "stableId": "a" * 64,
    "cvTags": ["Python", "AWS", "German", "MSc"],
    "skills": ["Python", "AWS"],
    "experience": [{"title": "Engineer", "company": "Example"}],
    "education": [{"degree": "MSc"}],
    "languages": ["German"],
    "location": "Berlin",
    "confidence": "confirmed",
    "parserVersion": "fake-1.0",
}
JOB_DATA = {
    "stableId": "b" * 64,
    "jobTags": ["Python", "AWS", "Docker", "Kubernetes"],
    "requiredSkills": ["Python", "AWS"],
    "preferredSkills": ["Docker", "Kubernetes"],
    "experienceRequirements": [{"text": "5+ years", "category": "experience"}],
    "workMode": "remote",
    "location": ["Berlin"],
    "confidence": "confirmed",
    "analysisStatus": "complete",
    "parserVersion": "fake-1.0",
}
ATS_DATA = {
    "stableId": "b" * 64,
    "atsTags": ["Python", "AWS", "Docker"],
    "requirements": [{"id": "r1", "text": "Python", "category": "skill"}],
    "matches": [{"requirementId": "r1", "status": "MATCHED"}],
    "criticalGaps": [],
    "score": 77.5,
    "analysisStatus": "complete",
    "parserVersion": "fake-1.0",
}


class Parser:
    def __init__(self, job=None, cv=None, ats=None):
        self.job = job or JOB_DATA
        self.cv = cv or CV_DATA
        self.ats = ats or ATS_DATA
        self.calls = []

    def parse_cv(self, pdf_base64):
        self.calls.append("parse.cv")
        return dict(self.cv)

    def parse_job(self, job):
        self.calls.append("parse.job")
        return dict(self.job)

    def parse_ats(self, job, profile):
        self.calls.append("parse.ats")
        return dict(self.ats)


class Repo:
    def __init__(self, record=None):
        self.record = record

    def get(self, *args, **kwargs):
        return self.record


class Record:
    user_id = "user-1"
    tenant_id = "tenant-a"
    processing_status = "ready"
    document_id = "doc-1"
    content_type = "application/pdf"
    status = "active"
    deleted_at = None
    erased_at = None


def identity(entitlements=ALL):
    return Identity(
        tenant_id="tenant-a", user_id="user-1",
        entitlements=frozenset(entitlements), consent=True,
        caller_partner_id="ris-internal",
        consent_purpose=ANALYSIS_CONSENT_PURPOSE,
        consent_notice_version=ANALYSIS_NOTICE_VERSION,
        consent_notice_approved=True,
    )


def request(results, cv=None, job=None, profile=None):
    body = {"schemaVersion": "1.0", "requestedResults": results,
            "input": {}, "idempotencyKey": "offer-test"}
    if cv is not None:
        body["input"]["cv"] = cv
    if job is not None:
        body["input"]["job"] = job
    if profile is not None:
        body["input"]["profile"] = profile
    return body


def structured(skills=None, languages=None, education=None, experience=None):
    data = {"skills": skills if skills is not None else ["Python", "AWS"]}
    if languages is not None:
        data["languages"] = languages
    if education is not None:
        data["education"] = education
    if experience is not None:
        data["experience"] = experience
    return {"structured": data}


def orchestrator(parser=None, record=None):
    return AnalysisOrchestrator(
        parser=parser or Parser(),
        cv_resolver=RequestCvResolver(
            document_loader=lambda *a: b"%PDF-1.7\nsynthetic\n",
            repository=Repo(record or Record())))


class CvOfferTest(unittest.TestCase):
    def test_structured_cv_full_body(self):
        out = orchestrator().run(request(
            ["cv.tags"], cv=structured(
                languages=["German"], education=[{"degree": "MSc"}],
                experience=[{"title": "Engineer"}])), identity())
        body = out["results"]["cv.tags"]
        self.assertEqual("CVParserResultBody", body["bodyType"])
        self.assertEqual("1.0", body["bodyVersion"])
        self.assertEqual(["German"], body["languages"])
        self.assertEqual([{"degree": "MSc"}], body["education"])
        self.assertEqual([{"title": "Engineer"}], body["experience"])

    def test_pdf_path(self):
        parser = Parser()
        out = orchestrator(parser).run(request(
            ["cv.tags"], cv={"cvId": "cv-1"}), identity())
        self.assertIn("parse.cv", parser.calls)
        self.assertEqual(["Python", "AWS"], out["results"]["cv.tags"]["skills"])

    def test_missing_information_is_not_invented(self):
        out = orchestrator().run(request(
            ["cv.tags"], cv=structured(skills=["Python"])), identity())
        body = out["results"]["cv.tags"]
        self.assertEqual([], body["experience"])
        self.assertEqual([], body["education"])
        self.assertEqual([], body["languages"])
        self.assertEqual("", body["location"])

    def test_invalid_structured_cv(self):
        with self.assertRaises(ContractError) as ctx:
            orchestrator().run(request(
                ["cv.tags"], cv={"structured": {"languages": ["German"]}}),
                identity())
        self.assertEqual("invalid_cv", ctx.exception.code)

    def test_unknown_and_foreign_cv_references(self):
        missing = AnalysisOrchestrator(
            parser=Parser(),
            cv_resolver=RequestCvResolver(
                document_loader=lambda *a: b"", repository=Repo(None)))
        with self.assertRaises(ContractError) as ctx:
            missing.run(request(["cv.tags"], cv={"cvId": "missing"}),
                        identity())
        self.assertEqual("cv_not_found", ctx.exception.code)

        foreign = Record()
        foreign.tenant_id = "tenant-b"
        with self.assertRaises(ContractError) as ctx:
            orchestrator(record=foreign).run(request(
                ["cv.tags"], cv={"cvId": "cv-1"}), identity())
        self.assertEqual("cv_access_denied", ctx.exception.code)


class JobOfferTest(unittest.TestCase):
    def test_job_fields(self):
        out = orchestrator().run(request(
            ["job.tags"], job={"text": "Senior Python Engineer"}), identity())
        body = out["results"]["job.tags"]
        self.assertEqual("JobParserResultBody", body["bodyType"])
        self.assertEqual(["Python", "AWS"], body["requiredSkills"])
        self.assertEqual(["Docker", "Kubernetes"], body["preferredSkills"])
        self.assertEqual("remote", body["workMode"])
        self.assertEqual(["Berlin"], body["location"])
        self.assertTrue(body["experienceRequirements"])
        # The parser contract has no dedicated education requirement field;
        # absence must not be invented as a requirement.
        self.assertNotIn("educationRequirements", body)

    def test_missing_job_information(self):
        parser = Parser(job={
            "stableId": "b" * 64, "jobTags": [], "requiredSkills": [],
            "preferredSkills": [], "experienceRequirements": [],
            "workMode": "unknown", "location": [], "confidence": "uncertain",
            "analysisStatus": "partial", "parserVersion": "fake-1.0"})
        out = orchestrator(parser).run(request(
            ["job.tags"], job={"text": "Short ad"}), identity())
        body = out["results"]["job.tags"]
        self.assertEqual([], body["requiredSkills"])
        self.assertEqual([], body["preferredSkills"])
        self.assertEqual("unknown", body["workMode"])
        self.assertEqual("partial", body["analysisStatus"])

    def test_invalid_and_foreign_jobref(self):
        with self.assertRaises(ContractError) as ctx:
            orchestrator().run(request(["job.tags"], job={}), identity())
        self.assertEqual("missing_job", ctx.exception.code)


class MatchOfferTest(unittest.TestCase):
    def match(self, skills, job=None, ats=False):
        results = ["comparison"] + (["ats.tags"] if ats else [])
        parser = Parser(job=job) if job else Parser()
        return orchestrator(parser).run(request(
            results, cv=structured(skills=skills),
            job={"text": "Senior Engineer"}), identity())

    def test_full_match(self):
        out = self.match(["Python", "AWS", "Docker", "Kubernetes"])
        body = out["results"]["comparison"]
        self.assertEqual(100.0, body["coverage"]["required"])
        self.assertEqual(100.0, body["coverage"]["preferred"])
        self.assertEqual(100.0, body["weightedScore"])

    def test_partial_and_missing_must(self):
        out = self.match(["Python"])
        body = out["results"]["comparison"]
        self.assertEqual(50.0, body["coverage"]["required"])
        self.assertEqual(0.0, body["coverage"]["preferred"])
        self.assertIn("aws", body["missingInCv"])
        self.assertIn("python", body["matched"])

        out = self.match(["Linux"])
        body = out["results"]["comparison"]
        self.assertEqual(0.0, body["coverage"]["required"])
        self.assertIn("aws", body["missingInCv"])

    def test_aliases_are_mapped(self):
        out = self.match(["k8s", "Amazon Web Services", "postgres"])
        body = out["results"]["comparison"]
        self.assertEqual("1.0.0", body["aliasMapVersion"])
        self.assertIn("kubernetes", body["matched"])
        self.assertIn("aws", body["matched"])
        self.assertIn("postgresql", body["extraInCv"])

    def test_unknown_criteria_are_marked(self):
        job = {"stableId": "b" * 64, "jobTags": [], "requiredSkills": [],
               "preferredSkills": [], "experienceRequirements": [],
               "workMode": "unknown", "location": [], "confidence": "uncertain",
               "analysisStatus": "partial", "parserVersion": "fake-1.0"}
        out = self.match(["Python"], job=job)
        body = out["results"]["comparison"]
        self.assertTrue(body["unknown"])
        self.assertIsNone(body["weightedScore"])

    def test_ats_is_separate_from_deterministic_coverage(self):
        without = self.match(["Python", "AWS"])["results"]["comparison"]
        with_ats = self.match(["Python", "AWS"], ats=True)
        body = with_ats["results"]["comparison"]
        self.assertEqual(without["coverage"], body["coverage"])
        self.assertEqual(without["weightedScore"], body["weightedScore"])
        self.assertEqual(77.5, body["provenance"]["atsScore"])
        self.assertIn("atsTags", body)
        self.assertEqual("ATSAnalysisResultBody",
                         with_ats["results"]["ats.tags"]["bodyType"])


class OfferCatalogDraftTest(unittest.TestCase):
    def test_three_offers_are_draft_and_priced_by_mays_orders(self):
        import yaml

        path = ROOT / "agent-installations" / "analysis-agent" / "offers.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual("DRAFT", data["status"])
        self.assertFalse(data["activation"])
        self.assertEqual("mays-orders", data["pricing"]["owner"])
        self.assertFalse(data["pricing"]["definedHere"])
        self.assertEqual("ABSENT", data["catalog"]["visibility"])
        ids = {offer["id"] for offer in data["offers"]}
        self.assertEqual({"analysis.cv", "analysis.job", "analysis.match"}, ids)
        for offer in data["offers"]:
            self.assertEqual("DRAFT", offer["status"])
            self.assertNotIn("price", offer)
            self.assertEqual("analysis-processing", offer["consentPurpose"])
        self.assertIn("ats-agent", data["notOffer"])


if __name__ == "__main__":
    unittest.main()
