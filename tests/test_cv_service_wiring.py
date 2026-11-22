"""RIS-ANALYSIS-READINESS-09 STEP B — CV service wiring.

RequestCvResolver is connected to the existing PartnerProfileRepository and a
documents loader. These tests use fakes: no S3, no DynamoDB, no CV bytes in
WorkItems, logs or errors.
"""

import base64
import hashlib
import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.analysis.contracts import (  # noqa: E402
    ANALYSIS_CONSENT_PURPOSE,
    ANALYSIS_NOTICE_VERSION,
    ContractError,
    Identity,
)
from agents.analysis.cv_bridge import (  # noqa: E402
    RequestCvResolver,
    build_cv_resolver,
)
from agents.analysis.orchestrator import (  # noqa: E402
    AnalysisOrchestrator,
    ParserPort,
)
from agents.analysis_agent.agent import AnalysisAgent  # noqa: E402

PDF = b"%PDF-1.7\nsynthetic-cv-bytes\n%%EOF\n"
PDF_B64 = base64.b64encode(PDF).decode("ascii")
ALL = frozenset({"parse.cv", "parse.job", "analyze.job", "compare.tags"})


@dataclass
class Record:
    user_id: str = "user-1"
    tenant_id: str = "tenant-a"
    processing_status: str = "ready"
    document_id: str = "doc-1"
    content_type: str = "application/pdf"
    status: str = "active"
    deleted_at: Optional[str] = None
    erased_at: Optional[str] = None


class FakeRepo:
    def __init__(self, record=None, error=None):
        self.record = record
        self.error = error
        self.calls = []

    def get(self, resource_id, user_id, tenant_id, partner_app_id=None,
            issuer=None):
        self.calls.append((resource_id, user_id, tenant_id,
                           partner_app_id, issuer))
        if self.error:
            raise self.error
        return self.record


class FakeLoader:
    def __init__(self, payload=PDF, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def __call__(self, tenant_id, user_id, doc_id):
        self.calls.append((tenant_id, user_id, doc_id))
        if self.error:
            raise self.error
        return self.payload


def identity(tenant="tenant-a", user="user-1"):
    return Identity(
        tenant_id=tenant, user_id=user, entitlements=ALL, consent=True,
        partner_application_id="ris-internal-analysis",
        issuer="https://issuer",
        caller_partner_id="ris-internal",
        consent_purpose=ANALYSIS_CONSENT_PURPOSE,
        consent_notice_version=ANALYSIS_NOTICE_VERSION,
        consent_notice_approved=True,
    )


class FakeParser(ParserPort):
    def __init__(self):
        self.cv_calls = []
        self.job_calls = []

    def parse_cv(self, pdf_base64):
        self.cv_calls.append(pdf_base64)
        return {"stableId": hashlib.sha256(pdf_base64.encode()).hexdigest(),
                "cvTags": ["Python", "AWS"], "skills": ["Python", "AWS"],
                "experience": [], "education": [], "languages": [],
                "location": "", "confidence": "confirmed",
                "parserVersion": "fake-1.0",
                "provenance": {"source": "fake"}}

    def parse_job(self, job):
        self.job_calls.append(job)
        return {"stableId": "b" * 64, "jobTags": ["Python"],
                "requirements": [{"text": "Python", "category": "skill",
                                  "required": True, "weight": 1}],
                "parserVersion": "fake-1.0"}

    def parse_ats(self, job, profile):
        return {"atsTags": [], "parserVersion": "fake-1.0"}


def request(cv, job=None):
    return {
        "schemaVersion": "1.0",
        "requestedResults": ["cv.tags", "job.tags", "comparison"],
        "input": {
            "cv": cv,
            "job": job or {"text": "Senior Python Engineer\nRequired: Python"},
        },
        "idempotencyKey": "cv-wiring",
    }


class StoredCvWiringTest(unittest.TestCase):
    def make(self, record=None, **kwargs):
        repo = FakeRepo(record or Record())
        loader = FakeLoader(**kwargs)
        return RequestCvResolver(document_loader=loader, repository=repo), repo, loader

    def test_happy_path_reads_the_owner_document(self):
        resolver, repo, loader = self.make()
        result = resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("ris-cv", result.source)
        self.assertEqual(PDF_B64, result.pdf_base64)
        self.assertEqual(hashlib.sha256(PDF).hexdigest(), result.sha256)
        self.assertEqual("cv-1", repo.calls[0][0])
        self.assertEqual(("tenant-a", "user-1", "doc-1"), loader.calls[0])

    def test_structured_cv_skips_repository_and_loader(self):
        resolver, repo, loader = self.make()
        result = resolver.resolve(
            {"structured": {"skills": ["Python"], "languages": ["German"]}},
            identity())
        self.assertTrue(result.is_structured)
        self.assertIsNone(result.pdf_base64)
        self.assertEqual([], repo.calls)
        self.assertEqual([], loader.calls)

    def test_structured_cv_requires_skills(self):
        resolver, _, _ = self.make()
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"structured": {"location": "Berlin"}},
                             identity())
        self.assertEqual("invalid_cv", ctx.exception.code)

    def test_foreign_owner_is_denied(self):
        resolver, repo, loader = self.make(Record(user_id="user-2"))
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_access_denied", ctx.exception.code)
        self.assertEqual([], loader.calls)
        self.assertNotIn("cv-1", ctx.exception.message)
        self.assertNotIn("user-2", ctx.exception.message)

    def test_foreign_tenant_is_denied(self):
        resolver, _, loader = self.make(Record(tenant_id="tenant-b"))
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_access_denied", ctx.exception.code)
        self.assertEqual([], loader.calls)

    def test_not_ready_and_missing_document(self):
        resolver, _, _ = self.make(Record(processing_status="pending"))
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_not_ready", ctx.exception.code)

        resolver, _, _ = self.make(Record(document_id=None))
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_not_ready", ctx.exception.code)

    def test_deleted_or_erased_cv_is_not_available(self):
        resolver, _, loader = self.make(Record(deleted_at="2026-11-20"))
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_not_available", ctx.exception.code)

        resolver, _, loader = self.make(Record(status="erased"))
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_not_available", ctx.exception.code)
        self.assertEqual([], loader.calls)

    def test_unknown_or_unreadable_cv_fails_closed(self):
        resolver, _, _ = self.make(record=None)
        resolver._repository.record = None
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_not_found", ctx.exception.code)

        repo = FakeRepo(error=RuntimeError("throttled"))
        resolver = RequestCvResolver(document_loader=FakeLoader(), repository=repo)
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_not_accessible", ctx.exception.code)

        resolver, _, _ = self.make(Record(), error=RuntimeError("denied"))
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_not_accessible", ctx.exception.code)

    def test_non_pdf_and_empty_document_are_rejected(self):
        resolver, _, _ = self.make(Record(content_type="image/png"))
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_unsupported", ctx.exception.code)

        resolver, _, _ = self.make(payload=b"")
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({"cvId": "cv-1"}, identity())
        self.assertEqual("cv_not_ready", ctx.exception.code)

    def test_missing_reference_is_rejected(self):
        resolver, _, _ = self.make()
        with self.assertRaises(ContractError) as ctx:
            resolver.resolve({}, identity())
        self.assertEqual("missing_cv", ctx.exception.code)


class CvPipelineTest(unittest.TestCase):
    def test_pdf_is_forwarded_to_the_parser_and_never_returned(self):
        parser = FakeParser()
        orchestrator = AnalysisOrchestrator(
            parser=parser,
            cv_resolver=RequestCvResolver(
                document_loader=FakeLoader(), repository=FakeRepo(Record())),
        )
        result = orchestrator.run(request({"cvId": "cv-1"}), identity())
        self.assertEqual([PDF_B64], parser.cv_calls)
        self.assertIn("cv.tags", result["results"])
        self.assertIn("comparison", result["results"])
        serialized = json.dumps(result)
        self.assertNotIn(PDF_B64, serialized)
        self.assertNotIn("synthetic-cv-bytes", serialized)

    def test_structured_cv_is_not_reparsed(self):
        parser = FakeParser()
        orchestrator = AnalysisOrchestrator(
            parser=parser,
            cv_resolver=RequestCvResolver(
                document_loader=FakeLoader(), repository=FakeRepo(Record())),
        )
        result = orchestrator.run(
            request({"structured": {"skills": ["Python", "AWS"],
                                    "languages": ["German"]}}),
            identity())
        self.assertEqual([], parser.cv_calls)
        self.assertEqual(["Python", "AWS", "German"],
                         result["results"]["cv.tags"]["cvTags"])

    def test_foreign_owner_fails_before_parsing(self):
        parser = FakeParser()
        orchestrator = AnalysisOrchestrator(
            parser=parser,
            cv_resolver=RequestCvResolver(
                document_loader=FakeLoader(),
                repository=FakeRepo(Record(user_id="user-2"))),
        )
        with self.assertRaises(ContractError) as ctx:
            orchestrator.run(request({"cvId": "cv-1"}), identity())
        self.assertEqual("cv_access_denied", ctx.exception.code)
        self.assertEqual([], parser.cv_calls)

    def test_agent_uses_the_configured_repository_and_loader(self):
        repo = FakeRepo(Record())
        loader = FakeLoader()
        parser = FakeParser()
        agent = AnalysisAgent(
            config={"entitlements": sorted(ALL), "consent": True,
                    "consent_notice_approved": True,
                    "cv_repository": repo, "cv_document_loader": loader},
            orchestrator=AnalysisOrchestrator(
                parser=parser, cv_resolver=build_cv_resolver({
                    "cv_repository": repo,
                    "cv_document_loader": loader})),
        )
        work = {
            "workId": "w-cv", "type": "agent_analysis_agent",
            "tenantId": "tenant-a", "userId": "user-1",
            "idempotencyKey": "w-cv", "capability": "analysis.run",
            "payload": request({"cvId": "cv-1"}),
        }
        self.assertTrue(agent.validate_work(work))
        result = agent.process_work(work)
        self.assertTrue(result["success"])
        self.assertEqual(1, len(loader.calls))
        self.assertEqual(1, len(repo.calls))
        self.assertNotIn("synthetic-cv-bytes", json.dumps(result))

    def test_build_cv_resolver_defaults_without_injection(self):
        resolver = build_cv_resolver({})
        self.assertIsInstance(resolver, RequestCvResolver)
        self.assertIsNone(resolver._repository)
        self.assertIsNone(resolver._document_loader)


if __name__ == "__main__":
    unittest.main()
