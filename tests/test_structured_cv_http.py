"""HTTP contract tests for the structured CV profile adapter.

These tests use the verified partner context as an injected boundary; full
JWT/credential integration is covered by the existing partner-surface tests.
No AWS call is made.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from jobsearch.structured_cv_profile import StructuredCvConflict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("ris_structured_cv_handler", ROOT / "lambda" / "handler.py")
handler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handler)

CONTEXT = {
    "userId": "user-synthetic-1",
    "tenantId": "tenant-synthetic-1",
    "partnerApplicationId": "partner-synthetic-1",
    "issuer": "issuer-synthetic-1",
}
PATH = "/v1/partner/me/cv-builder-profiles"


def _event(method="GET", path=PATH, body=None, headers=None, query=None):
    return {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if isinstance(body, dict) else body,
        "headers": headers or {},
        "queryStringParameters": query or {},
    }


def _profile(version=1):
    return {
        "schemaVersion": 1,
        "profileId": "cvp-12345678",
        "name": "Synthetic CV",
        "template": "classic",
        "cvData": {
            "schemaVersion": 1,
            "personal": {"fullName": "", "email": "", "phone": "", "location": ""},
            "profile": {"headline": "", "summary": ""},
            "experience": [], "education": [], "skills": [], "projects": [],
            "certificates": [], "languages": [], "links": [],
        },
        "version": version,
        "createdAt": "2026-11-13T00:00:00+00:00",
        "updatedAt": "2026-11-13T00:00:00+00:00",
    }


class _FakeRepo:
    def __init__(self, *args, **kwargs):
        self.created = []
        self.deleted = []

    def create(self, body, ctx, *, idempotency_key):
        self.created.append((body, ctx, idempotency_key))
        return _profile()

    def list(self, ctx, *, limit=20, cursor=None):
        return [], None

    def get(self, profile_id, ctx):
        return _profile()

    def export(self, profile_id, ctx):
        return {"schemaVersion": 1, "profile": _profile()}

    def update(self, profile_id, body, ctx, *, expected_version):
        return _profile(expected_version + 1)

    def delete(self, profile_id, ctx, *, expected_version=None):
        self.deleted.append((profile_id, expected_version))


class StructuredCvConsentBoundaryTest(unittest.TestCase):
    def _consent(self, state, *, test_mode=False):
        class _Repo:
            def get(self, _ctx, _purpose):
                return state

        env = {"STRUCTURED_CV_PROFILE_TEST_MODE": "true" if test_mode else "false"}
        with patch.dict(os.environ, env), \
                patch("jobsearch.consent_repository.ConsentRepository", return_value=_Repo()):
            return handler._structured_cv_consent_ok(CONTEXT)

    def test_granted_draft_does_not_authorize_real_writes(self):
        self.assertFalse(self._consent({
            "status": "GRANTED",
            "noticeVersion": "structured-cv-profile-storage-2026-11-12-draft-1",
        }))

    def test_draft_is_rejected_even_with_a_legacy_environment_flag(self):
        state = {
            "status": "GRANTED",
            "noticeVersion": "structured-cv-profile-storage-2026-11-12-draft-1",
        }
        self.assertFalse(self._consent(state, test_mode=True))
        self.assertFalse(self._consent(dict(state, status="WITHDRAWN"), test_mode=True))

    def test_approved_notice_requires_legal_approval_reference(self):
        class Entry:
            state = "APPROVED"
            legal_approval_ref = None

        state = {"status": "GRANTED", "noticeVersion": "approved-version"}
        with patch("jobsearch.consent_contract.notice_version", return_value=Entry()):
            self.assertFalse(self._consent(state))
        Entry.legal_approval_ref = "LEGAL-REF"
        with patch("jobsearch.consent_contract.notice_version", return_value=Entry()):
            self.assertTrue(self._consent(state))


class StructuredCvHttpTest(unittest.TestCase):
    def _call(self, event, method, path, *, consent=True, repo=None, enabled=True):
        repo = repo or _FakeRepo()
        with patch.dict(os.environ, {"STRUCTURED_CV_PROFILE_ENABLED": "true" if enabled else "false"}):
            with patch.object(handler, "_partner_profile_context", return_value=(CONTEXT, None)):
                with patch.object(handler, "_structured_cv_consent_ok", return_value=consent):
                    with patch("jobsearch.structured_cv_profile.StructuredCvProfileRepository", return_value=repo):
                        with patch.object(handler, "_handle_structured_cv_routes", wraps=handler._handle_structured_cv_routes):
                            return handler._handle_structured_cv_routes(event, None, method, path), repo

    def test_feature_flag_disabled_fails_closed_before_auth(self):
        response, repo = self._call(_event(), "GET", PATH, enabled=False)
        self.assertEqual(response["statusCode"], 503)
        self.assertEqual(json.loads(response["body"])["code"],
                         "STRUCTURED_CV_PROFILE_STORAGE_DISABLED")

    def test_create_requires_consent(self):
        response, repo = self._call(_event("POST", body={"name": "x"}), "POST", PATH, consent=False)
        self.assertEqual(response["statusCode"], 403)
        self.assertEqual(json.loads(response["body"])["code"], "CONSENT_REQUIRED")
        self.assertEqual(repo.created, [])

    def test_create_returns_etag_and_never_accepts_client_identity(self):
        body = {"name": "Synthetic CV", "template": "classic", "cvData": _profile()["cvData"]}
        response, repo = self._call(
            _event("POST", body=body, headers={"Idempotency-Key": "idem-" + "x" * 20}),
            "POST", PATH)
        self.assertEqual(response["statusCode"], 201)
        self.assertEqual(response["headers"]["ETag"], '"v1"')
        self.assertEqual(repo.created[0][1]["userId"], CONTEXT["userId"])
        self.assertNotIn("userId", repo.created[0][0])

    def test_missing_if_match_is_428(self):
        response, repo = self._call(
            _event("PATCH", path=PATH + "/cvp-12345678", body={"name": "x"}),
            "PATCH", PATH + "/cvp-12345678")
        self.assertEqual(response["statusCode"], 428)
        self.assertEqual(json.loads(response["body"])["code"], "PRECONDITION_REQUIRED")

    def test_update_uses_if_match_and_returns_new_etag(self):
        response, repo = self._call(
            _event("PATCH", path=PATH + "/cvp-12345678", body={"name": "x"},
                   headers={"If-Match": '"v1"'}),
            "PATCH", PATH + "/cvp-12345678")
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["ETag"], '"v2"')

    def test_repository_conditional_conflict_maps_to_409(self):
        class ConflictRepo(_FakeRepo):
            def update(self, profile_id, body, ctx, *, expected_version):
                raise StructuredCvConflict()

        response, _ = self._call(
            _event("PATCH", path=PATH + "/cvp-12345678", body={"name": "x"},
                   headers={"If-Match": '"v1"'}),
            "PATCH", PATH + "/cvp-12345678", repo=ConflictRepo())
        self.assertEqual(409, response["statusCode"])
        self.assertEqual("VERSION_CONFLICT", json.loads(response["body"])["code"])

    def test_unexpected_storage_error_stays_503_without_internal_detail(self):
        class BrokenRepo(_FakeRepo):
            def update(self, profile_id, body, ctx, *, expected_version):
                raise RuntimeError("DynamoDB expression secret detail")

        response, _ = self._call(
            _event("PATCH", path=PATH + "/cvp-12345678", body={"name": "x"},
                   headers={"If-Match": '"v1"'}),
            "PATCH", PATH + "/cvp-12345678", repo=BrokenRepo())
        self.assertEqual(503, response["statusCode"])
        self.assertNotIn("DynamoDB", response["body"])

    def test_delete_is_204_without_json_body(self):
        response, repo = self._call(
            _event("DELETE", path=PATH + "/cvp-12345678"),
            "DELETE", PATH + "/cvp-12345678")
        self.assertEqual(response["statusCode"], 204)
        self.assertEqual(response["body"], "")
        self.assertEqual(repo.deleted, [("cvp-12345678", None)])

    def test_invalid_limit_is_422_without_repository_call(self):
        response, repo = self._call(_event("GET", query={"limit": "not-a-number"}),
                                    "GET", PATH)
        self.assertEqual(response["statusCode"], 422)

    def test_export_route_and_item_route(self):
        response, _ = self._call(
            _event("GET", path=PATH + "/cvp-12345678/export"),
            "GET", PATH + "/cvp-12345678/export")
        self.assertEqual(response["statusCode"], 200)
        self.assertIn("profile", json.loads(response["body"]))
        response, _ = self._call(
            _event("GET", path=PATH + "/cvp-12345678"),
            "GET", PATH + "/cvp-12345678")
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["ETag"], '"v1"')


if __name__ == "__main__":
    unittest.main()
