"""R08-B1 read-only, scoped privacy data inspection tests."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambda"))

import handler  # noqa: E402


CTX = {
    "userId": "user-inspect",
    "tenantId": "tenant-inspect",
    "partnerApplicationId": "partner-inspect",
    "issuer": "https://issuer-inspect.example",
}


def _cv(index):
    return SimpleNamespace(
        cv_id=f"cv-{index}", name=f"cv-{index}.pdf", content_type="application/pdf",
        document_id=f"doc-{index}", processing_status="pending", size=0,
        version=1, created_at="2026-11-01T00:00:00+00:00",
        updated_at="2026-11-01T00:00:00+00:00", metadata={},
    )


def _manual(index):
    return SimpleNamespace(
        version=1,
        to_dict=lambda: {
            "manualProfileId": f"manual-{index}", "name": f"Manual {index}",
            "description": "", "origin": "manual", "searchConfig": {},
            "matchingPreferences": {}, "createdAt": "2026-11-01T00:00:00+00:00",
            "updatedAt": "2026-11-01T00:00:00+00:00",
        },
    )


def _cv_search(index):
    return SimpleNamespace(
        version=1,
        to_dict=lambda: {
            "searchProfileId": f"cvsp-{index}", "cvId": "cv-1",
            "name": f"CV Search {index}", "description": "", "origin": "cv",
            "searchConfig": {}, "createdAt": "2026-11-01T00:00:00+00:00",
            "updatedAt": "2026-11-01T00:00:00+00:00",
        },
    )


def _ats(index):
    return SimpleNamespace(
        version=1,
        to_dict=lambda: {
            "atsProfileId": f"ats-{index}", "searchProfileId": "cvsp-1",
            "name": f"ATS {index}", "targetRoles": [], "skills": [],
            "createdAt": "2026-11-01T00:00:00+00:00",
            "updatedAt": "2026-11-01T00:00:00+00:00",
        },
    )


class FakeRepo:
    table_name = "partner-profiles-test"
    table = object()

    def __init__(self, *, fail=False, empty=False):
        self.fail = fail
        self.items = {} if empty else {
            "CVDocument": [_cv(1), _cv(2)],
            "ManualSearchProfile": [_manual(1), _manual(2)],
            "CVSearchProfile": [_cv_search(1), _cv_search(2)],
            "ATSSearchProfile": [_ats(1), _ats(2)],
        }

    def resolve_cursor(self, token, **_kwargs):
        if token is None:
            return None
        if not str(token).startswith("offset:"):
            from jobsearch.partner_profile_cursor import CursorError
            raise CursorError("invalid")
        return int(str(token).split(":", 1)[1])

    def issue_cursor(self, cursor, **_kwargs):
        return f"offset:{cursor}"

    def list_by_user(self, _user, _tenant, *, resource_type, limit, cursor,
                     **_kwargs):
        if self.fail:
            raise RuntimeError("storage unavailable")
        rows = self.items.get(resource_type, [])
        start = int(cursor or 0)
        page = rows[start:start + limit]
        next_cursor = start + limit if start + limit < len(rows) else None
        return page, next_cursor


def _event(*, query=None):
    return {
        "httpMethod": "GET",
        "path": "/v1/partner/me/privacy/inspect",
        "queryStringParameters": query or {},
    }


def _body(response):
    return json.loads(response["body"])


def test_inspection_lists_all_domains_with_independent_pagination():
    repo = FakeRepo()
    with patch("handler._partner_profile_context", return_value=(CTX, None)), \
            patch("handler._manual_profile_repo", return_value=repo), \
            patch("handler._privacy_read_user_profile", return_value={"userId": CTX["userId"]}):
        first = _body(handler._handle_api_event(_event(query={"limit": "1"}), None))
        assert first["status"] == "PARTIAL"  # receipt journal is disabled
        for key in ("cvDocuments", "manualSearchProfiles", "cvSearchProfiles", "atsSearchProfiles"):
            assert len(first["categories"][key]["items"]) == 1
            assert first["categories"][key]["nextCursor"] == "offset:1"
            assert first["categories"][key]["status"] == "COMPLETE"

        second = _body(handler._handle_api_event(_event(query={
            "limit": "1", "cvCursor": "offset:1", "manualCursor": "offset:1",
            "cvSearchCursor": "offset:1", "atsCursor": "offset:1",
        }), None))
        for key in ("cvDocuments", "manualSearchProfiles", "cvSearchProfiles", "atsSearchProfiles"):
            assert len(second["categories"][key]["items"]) == 1
            assert second["categories"][key]["nextCursor"] is None


def test_inspection_reports_user_without_data_without_false_unavailable():
    repo = FakeRepo(empty=True)
    with patch("handler._partner_profile_context", return_value=(CTX, None)), \
            patch("handler._manual_profile_repo", return_value=repo), \
            patch("handler._privacy_read_user_profile", return_value=None):
        result = _body(handler._handle_api_event(_event(), None))
    assert result["categories"]["userProfile"]["storageStatus"] == "no_data"
    assert result["categories"]["cvDocuments"]["storageStatus"] == "no_data"
    assert result["categories"]["cvDocuments"]["status"] == "COMPLETE"


def test_inspection_marks_unreachable_profile_storage_partial():
    with patch("handler._partner_profile_context", return_value=(CTX, None)), \
            patch("handler._manual_profile_repo", return_value=FakeRepo(fail=True)), \
            patch("handler._privacy_read_user_profile", return_value={"userId": CTX["userId"]}):
        result = _body(handler._handle_api_event(_event(), None))
    assert result["status"] == "PARTIAL"
    assert result["categories"]["cvDocuments"]["status"] == "UNAVAILABLE"
    assert result["categories"]["cvDocuments"]["code"] == "unavailable"


def test_inspection_propagates_missing_auth_and_excludes_secrets():
    response = handler._handle_api_event(_event(), None)
    assert response["statusCode"] == 401

    repo = FakeRepo()
    with patch("handler._partner_profile_context", return_value=(CTX, None)), \
            patch("handler._manual_profile_repo", return_value=repo), \
            patch("handler._privacy_read_user_profile", return_value={"userId": CTX["userId"]}):
        payload = json.dumps(handler._handle_api_event(_event(), None))
    for secret in ("Authorization", "X-Api-Credential", "presigned", "s3://", "secret-key"):
        assert secret.lower() not in payload.lower()


def test_export_exhausts_all_profile_pages_and_separates_file_status():
    repo = FakeRepo()
    ready = _cv(3)
    ready.processing_status = "ready"
    ready.document_id = "doc-ready"
    repo.items["CVDocument"].append(ready)
    with patch("handler._partner_profile_context", return_value=(CTX, None)), \
            patch("handler._manual_profile_repo", return_value=repo), \
            patch("handler._privacy_read_user_profile", return_value={"userId": CTX["userId"]}):
        result = _body(handler._handle_api_event({
            "httpMethod": "GET",
            "path": "/v1/partner/me/privacy/export",
            "queryStringParameters": {"limit": "1"},
        }, None))
    assert result["exportType"] == "RIS_USER_PRIVACY_EXPORT"
    assert result["status"] == "PARTIAL"  # disabled receipt journal
    assert result["metadataExport"]["categories"]["cvDocuments"]["status"] == "COMPLETE"
    assert len(result["metadataExport"]["categories"]["cvDocuments"]["items"]) == 3
    assert result["fileExport"]["status"] == "NOT_INCLUDED"
    assert result["fileExport"]["complete"] is False
    assert result["fileExport"]["items"][0]["downloadEndpoint"].endswith(
        "/v1/partner/me/cvs/cv-3/document")
    encoded = json.dumps(result).lower()
    assert "s3://" not in encoded
    assert "presigned" not in encoded
    assert "downloadurl" not in encoded


def test_export_reports_empty_authorized_categories_as_no_data():
    repo = FakeRepo(empty=True)
    with patch("handler._partner_profile_context", return_value=(CTX, None)), \
            patch("handler._manual_profile_repo", return_value=repo), \
            patch("handler._privacy_read_user_profile", return_value=None):
        result = _body(handler._handle_api_event({
            "httpMethod": "GET",
            "path": "/v1/partner/me/privacy/export",
            "queryStringParameters": {},
        }, None))
    assert result["metadataExport"]["categories"]["userProfile"]["storageStatus"] == "no_data"
    assert result["metadataExport"]["categories"]["manualSearchProfiles"]["storageStatus"] == "no_data"
    assert result["metadataExport"]["categories"]["manualSearchProfiles"]["items"] == []


def test_export_marks_unreachable_categories_unavailable():
    with patch("handler._partner_profile_context", return_value=(CTX, None)), \
            patch("handler._manual_profile_repo", return_value=FakeRepo(fail=True)), \
            patch("handler._privacy_read_user_profile", return_value={"userId": CTX["userId"]}):
        result = _body(handler._handle_api_event({
            "httpMethod": "GET",
            "path": "/v1/partner/me/privacy/export",
            "queryStringParameters": {},
        }, None))
    category = result["metadataExport"]["categories"]["cvDocuments"]
    assert result["status"] == "PARTIAL"
    assert category["status"] == "UNAVAILABLE"
    assert category["storageStatus"] == "unavailable"
    assert category["code"] == "unavailable"


def test_export_requires_verified_context():
    response = handler._handle_api_event({
        "httpMethod": "GET",
        "path": "/v1/partner/me/privacy/export",
        "queryStringParameters": {},
    }, None)
    assert response["statusCode"] == 401
