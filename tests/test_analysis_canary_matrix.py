"""RIS-ANALYSIS-CANARY-10A STEP C — synthetic canary matrix.

Runs the real Node parser CLI (skipped when it is not configured) against the
synthetic CV PDF and job ad. No real personal data, no live consent, no
entitlement bypass: every case uses explicit synthetic claims.
"""

import base64
import io
import json
import os
import shutil
import sys
import unittest
from dataclasses import replace
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
from agents.analysis.job_store import (  # noqa: E402
    InMemoryJobStore,
    JobAccessDenied,
    JobExpired,
    JobNotFound,
    JobTooLarge,
    MAX_JOB_BYTES,
    MAX_TTL_SECONDS,
    S3JobStore,
    STANDARD_TTL_SECONDS,
)
from agents.analysis.orchestrator import (  # noqa: E402
    AnalysisOrchestrator,
    NodeParser,
)

FIXTURES = ROOT / "tests" / "fixtures" / "analysis"
PDF = FIXTURES / "synthetic-canary-cv.pdf"
JOB = json.loads((FIXTURES / "synthetic-job.json").read_text(encoding="utf-8"))
ALL = frozenset({"parse.cv", "parse.job", "analyze.job", "compare.tags"})


def node_available() -> bool:
    cli = os.environ.get("RIS_PARSER_CLI", "")
    node = os.environ.get("RIS_PARSER_NODE") or shutil.which("node")
    return bool(cli and Path(cli).is_file() and node)


def identity(entitlements=ALL, tenant="tenant-canary", user="user-canary"):
    return Identity(
        tenant_id=tenant, user_id=user, entitlements=frozenset(entitlements),
        consent=True,
        partner_application_id="ris-internal-analysis",
        issuer="https://issuer.invalid/synthetic",
        caller_partner_id="ris-internal",
        consent_purpose=ANALYSIS_CONSENT_PURPOSE,
        consent_notice_version=ANALYSIS_NOTICE_VERSION,
        consent_notice_approved=True,
    )


class PdfLoader:
    def __init__(self):
        self.calls = []

    def __call__(self, tenant_id, user_id, doc_id):
        self.calls.append((tenant_id, user_id, doc_id))
        return PDF.read_bytes()


class CanaryRecord:
    user_id = "user-canary"
    tenant_id = "tenant-canary"
    processing_status = "ready"
    document_id = "canary-doc"
    content_type = "application/pdf"
    status = "active"
    deleted_at = None
    erased_at = None


class CanaryRepo:
    def __init__(self, record=None):
        self.record = record or CanaryRecord()

    def get(self, resource_id, user_id, tenant_id, partner_app_id=None,
            issuer=None):
        return self.record


def structured_cv():
    return {"structured": {
        "skills": ["Python", "AWS", "Terraform", "Docker", "Linux", "SQL"],
        "languages": ["German", "English"],
        "education": [{"degree": "MSc Computer Science"}],
        "location": "Berlin",
    }}


def request(results, cv=None, job=None, key="canary", profile=None):
    body = {
        "schemaVersion": "1.0",
        "requestedResults": results,
        "input": {},
        "idempotencyKey": key,
    }
    if cv is not None:
        body["input"]["cv"] = cv
    if job is not None:
        body["input"]["job"] = job
    if profile is not None:
        body["input"]["profile"] = profile
    return body


@unittest.skipUnless(node_available(),
                     "RIS_PARSER_CLI/RIS_PARSER_NODE not configured")
class SyntheticCanaryMatrixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = NodeParser(mode="cli")

    def build(self, record=None):
        self.loader = PdfLoader()
        return AnalysisOrchestrator(
            parser=self.parser,
            cv_resolver=RequestCvResolver(document_loader=self.loader,
                                          repository=CanaryRepo(record)),
            job_store=InMemoryJobStore(),
        )

    def run_case(self, results, cv=None, job=None, key="canary", ident=None,
                 record=None, profile=None):
        orchestrator = self.build(record)
        body = request(results, cv=cv, job=job, key=key, profile=profile)
        return orchestrator, orchestrator.run(body, ident or identity())

    def test_cv_only_parses_the_synthetic_pdf(self):
        _, out = self.run_case(["cv.tags"], cv={"cvId": "canary-cv"})
        self.assertEqual(["cv.tags"], sorted(out["results"]))
        tags = out["results"]["cv.tags"]["cvTags"]
        self.assertIn("Python", tags)
        self.assertIn("AWS", tags)
        self.assertEqual(1, len(self.loader.calls))
        self.assertNotIn("synthetic-canary-cv", json.dumps(out))
        self.assertNotIn(base64.b64encode(PDF.read_bytes()).decode(), json.dumps(out))

    def test_job_only_parses_the_synthetic_ad(self):
        _, out = self.run_case(["job.tags"], job={"text": JOB["descriptionPlain"]})
        self.assertEqual(["job.tags"], sorted(out["results"]))
        self.assertGreaterEqual(len(out["results"]["job.tags"]["jobTags"]), 3)

    def test_ats_only_uses_the_job_and_profile(self):
        _, out = self.run_case(
            ["ats.tags"], job={"text": JOB["descriptionPlain"]},
            key="ats", profile={"skills": ["Python", "AWS"]})
        self.assertEqual(["ats.tags"], sorted(out["results"]))
        self.assertGreaterEqual(len(out["results"]["ats.tags"]["atsTags"]), 1)

    def test_comparison_with_structured_cv(self):
        _, out = self.run_case(
            ["comparison"], cv=structured_cv(),
            job={"text": JOB["descriptionPlain"]}, key="comparison")
        coverage = out["results"]["comparison"]["coverage"]
        for key in ("required", "preferred", "overall"):
            self.assertGreaterEqual(coverage[key], 0)
            self.assertLessEqual(coverage[key], 100)

    def test_full_pipeline_and_idempotent_replay(self):
        orchestrator = self.build()
        body = request(["cv.tags", "job.tags", "ats.tags", "comparison"],
                       cv=structured_cv(),
                       job={"text": JOB["descriptionPlain"]}, key="full")
        first = orchestrator.run(body, identity())
        second = orchestrator.run(body, identity())
        self.assertEqual(
            ["ats.tags", "comparison", "cv.tags", "job.tags"],
            sorted(first["results"]))
        self.assertFalse(first.get("idempotent", False))
        self.assertTrue(second["idempotent"])
        replay = dict(second)
        replay.pop("idempotent")
        original = dict(first)
        original.pop("idempotent", None)
        self.assertEqual(original, replay)

    def test_cv_pdf_full_pipeline_matches_structured_shape(self):
        _, out = self.run_case(
            ["cv.tags", "job.tags", "comparison"],
            cv={"cvId": "canary-cv"},
            job={"text": JOB["descriptionPlain"]}, key="pdf-full")
        self.assertEqual(["comparison", "cv.tags", "job.tags"],
                         sorted(out["results"]))
        self.assertIn("Python", out["results"]["cv.tags"]["skills"])

    def test_missing_entitlement_is_denied(self):
        limited = identity(entitlements={"parse.job"})
        with self.assertRaises(ContractError) as ctx:
            self.run_case(["cv.tags"], cv={"cvId": "canary-cv"}, ident=limited)
        self.assertEqual("entitlement_denied", ctx.exception.code)

    def test_cross_tenant_cv_is_denied_before_parsing(self):
        record = CanaryRecord()
        record.tenant_id = "tenant-other"
        with self.assertRaises(ContractError) as ctx:
            self.run_case(["cv.tags"], cv={"cvId": "canary-cv"}, record=record)
        self.assertEqual("cv_access_denied", ctx.exception.code)

    def test_consent_and_notice_gates_are_not_bypassed(self):
        with self.assertRaises(ContractError) as ctx:
            self.run_case(["job.tags"], job={"text": JOB["descriptionPlain"]},
                          ident=replace(identity(), consent=False))
        self.assertEqual("consent_required", ctx.exception.code)

        with self.assertRaises(ContractError) as ctx:
            self.run_case(["job.tags"], job={"text": JOB["descriptionPlain"]},
                          ident=replace(identity(), consent_notice_approved=False))
        self.assertEqual("consent_notice_not_approved", ctx.exception.code)

    def test_foreign_partner_is_denied(self):
        with self.assertRaises(ContractError) as ctx:
            self.run_case(["job.tags"], job={"text": JOB["descriptionPlain"]},
                          ident=replace(identity(),
                                        caller_partner_id="external-partner"))
        self.assertEqual("partner_mismatch", ctx.exception.code)

    def test_bad_input_and_missing_job_ref(self):
        with self.assertRaises(ContractError) as ctx:
            self.run_case(["job.tags"], job={"text": "x" * 40000})
        self.assertEqual("job_text_too_large", ctx.exception.code)

        with self.assertRaises(ContractError) as ctx:
            self.run_case(["job.tags"], job={"jobRef": "job_missing"})
        self.assertEqual("job_not_found", ctx.exception.code)

        with self.assertRaises(ContractError) as ctx:
            self.run_case(["everything"], job={"text": "x"})
        self.assertEqual("invalid_requested_results", ctx.exception.code)


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = (
            kwargs["Body"], dict(kwargs.get("Metadata") or {}))

    def get_object(self, Bucket, Key):
        body, metadata = self.objects[(Bucket, Key)]
        return {"Body": io.BytesIO(body), "Metadata": dict(metadata)}

    def copy_object(self, Bucket, Key, Metadata, **kwargs):
        self.objects[(Bucket, Key)] = (
            self.objects[(Bucket, Key)][0], dict(Metadata))

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)

    def head_object(self, Bucket, Key):
        return {"Metadata": dict(self.objects[(Bucket, Key)][1])}

    def get_paginator(self, name):
        store = self

        class Paginator:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": key}
                                    for (bucket, key) in list(store.objects)
                                    if bucket == Bucket and key.startswith(Prefix)]}
        return Paginator()


class TemporaryJobStoreTest(unittest.TestCase):
    def setUp(self):
        self.now = 1_700_000_000.0
        self.client = FakeS3()
        self.store = S3JobStore("canary-jobs", client=self.client,
                                clock=lambda: self.now)

    def test_standard_ttl_and_hard_maximum(self):
        record = self.store.put("Synthetic job text", "tenant-canary",
                                "user-canary")
        self.assertEqual(STANDARD_TTL_SECONDS, record.expires_at - record.created_at)
        self.assertEqual(MAX_TTL_SECONDS, record.max_expires_at - record.created_at)
        put = self.client.puts[0]
        self.assertEqual("AES256", put["ServerSideEncryption"])
        self.assertEqual("tenant-canary", put["Metadata"]["tenant"])
        self.assertEqual("user-canary", put["Metadata"]["user"])

        extended = self.store.extend(record.ref, "tenant-canary", "user-canary")
        capped = self.store.extend(record.ref, "tenant-canary", "user-canary")
        self.assertLessEqual(capped.expires_at,
                             record.created_at + MAX_TTL_SECONDS)
        self.assertGreaterEqual(capped.expires_at, extended.expires_at)

    def test_access_after_two_hours_and_after_four_hours(self):
        record = self.store.put("Synthetic job text", "tenant-canary",
                                "user-canary")
        self.now += STANDARD_TTL_SECONDS + 1
        with self.assertRaises(JobExpired):
            self.store.get(record.ref, "tenant-canary", "user-canary")

        self.now = record.created_at + MAX_TTL_SECONDS + 1
        with self.assertRaises(JobExpired):
            self.store.get(record.ref, "tenant-canary", "user-canary")
        self.assertEqual(1, self.store.cleanup_expired())
        with self.assertRaises(Exception):
            self.store.get(record.ref, "tenant-canary", "user-canary")

    def test_cross_tenant_and_oversize_are_rejected(self):
        record = self.store.put("Synthetic job text", "tenant-canary",
                                "user-canary")
        with self.assertRaises(JobNotFound):
            self.store.get(record.ref, "tenant-other", "user-canary")
        with self.assertRaises(JobTooLarge):
            self.store.put("x" * (MAX_JOB_BYTES + 1), "tenant-canary",
                           "user-canary")
        with self.assertRaises(JobNotFound):
            self.store.get("job_missing", "tenant-canary", "user-canary")

    def test_in_memory_store_matches_ttl_semantics(self):
        clock = [self.now]
        store = InMemoryJobStore(clock=lambda: clock[0])
        record = store.put("Synthetic job text", "tenant-canary", "user-canary")
        self.assertEqual(STANDARD_TTL_SECONDS, record.expires_at - record.created_at)
        clock[0] += MAX_TTL_SECONDS + 1
        with self.assertRaises(JobExpired):
            store.get(record.ref, "tenant-canary", "user-canary")
        self.assertEqual(1, store.cleanup_expired())


if __name__ == "__main__":
    unittest.main()
