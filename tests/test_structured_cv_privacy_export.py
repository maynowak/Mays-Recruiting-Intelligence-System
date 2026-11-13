"""Privacy-export integration for owner-scoped structured CV profiles."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "ris_structured_cv_hardening_handler", ROOT / "lambda" / "handler.py")
handler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handler)

CONTEXT = {
    "userId": "user-synthetic-1",
    "tenantId": "tenant-synthetic-1",
    "partnerApplicationId": "partner-synthetic-1",
    "issuer": "issuer-synthetic-1",
}


def _review_item(index: int) -> dict:
    return {
        "id": f"item-{index}",
        "index": index,
        "text": f"original synthetic {index}",
        "original": f"original synthetic {index}",
        "edited": index == 1,
        "target": "skills",
        "status": "accepted" if index % 2 else "pending",
        "applied": bool(index % 2),
        "page": 1,
        "sectionHeading": "Kenntnisse",
        "reason": "ambiguous",
        "suggestedTarget": "skills",
    }


def _profile(profile_id: str = "cvp-12345678") -> dict:
    items = [_review_item(index) for index in range(44)]
    return {
        "schemaVersion": 1,
        "profileId": profile_id,
        "name": "Synthetic CV",
        "template": "classic",
        "cvData": {
            "schemaVersion": 1,
            "personal": {"fullName": "", "email": "", "phone": "", "location": ""},
            "profile": {"headline": "", "summary": ""},
            "experience": [], "education": [], "skills": [], "projects": [],
            "certificates": [], "languages": [], "links": [],
        },
        "importReview": {
            "schemaVersion": 1,
            "sourceName": "synthetic.pdf",
            "pageCount": 1,
            "pendingAcknowledged": True,
            "selectedSections": ["skills"],
            "skills": {"total": 44, "selected": 0, "unselected": 44, "limited": False},
            "items": items,
            "total": 44,
            "pending": 22,
            "accepted": 22,
            "ignored": 0,
        },
        "version": 1,
        "createdAt": "2026-11-13T00:00:00+00:00",
        "updatedAt": "2026-11-13T00:00:00+00:00",
    }


class _FakeStructuredRepo:
    pages = None
    fail = False

    def __init__(self, *args, **kwargs):
        self.calls = []

    def list(self, ctx, *, limit=20, cursor=None):
        self.calls.append((ctx, limit, cursor))
        if self.fail:
            raise RuntimeError("storage unavailable")
        pages = self.pages or [([_profile()], None)]
        index = int(cursor) if cursor is not None else 0
        return pages[index]


class _FakeManualRepo:
    table_name = "test"
    table = object()

    def resolve_cursor(self, token, **_kwargs):
        return token

    def issue_cursor(self, cursor, **_kwargs):
        return cursor

    def list_by_user(self, *_args, **_kwargs):
        return [], None


class _FakeApplicationRepo:
    def __init__(self, *args, **kwargs):
        pass

    def list(self, *_args, **_kwargs):
        return [], None


class _FakeApplicationModule:
    ApplicationRepository = _FakeApplicationRepo


class StructuredCvPrivacyExportTest(unittest.TestCase):
    def _call(self, repo_cls):
        event = {"queryStringParameters": {"limit": "2"}}
        with patch.object(handler, "_partner_profile_context", return_value=(CONTEXT, None)), \
                patch.object(handler, "_manual_profile_repo", return_value=_FakeManualRepo()), \
                patch.object(handler, "_privacy_read_user_profile", return_value=None), \
                patch.object(handler, "_privacy_export_receipts", return_value=[]), \
                patch("jobsearch.structured_cv_profile.StructuredCvProfileRepository", repo_cls), \
                patch.dict(sys.modules, {"jobsearch.application_repository": _FakeApplicationModule()}):
            response = handler._handle_privacy_export(event, None)
        return response, json.loads(response["body"])

    def test_export_collects_full_review_and_all_pages(self):
        seen = []

        class PagedRepo(_FakeStructuredRepo):
            pages = [([_profile("cvp-11111111")], "1"),
                     ([_profile("cvp-22222222")], None)]

            def list(self, ctx, *, limit=20, cursor=None):
                seen.append(ctx)
                return super().list(ctx, limit=limit, cursor=cursor)

        response, body = self._call(PagedRepo)
        self.assertEqual(200, response["statusCode"])
        category = body["metadataExport"]["categories"]["structuredCvProfiles"]
        self.assertEqual("COMPLETE", category["status"])
        self.assertEqual(2, len(category["items"]))
        self.assertEqual(44, len(category["items"][0]["importReview"]["items"]))
        self.assertEqual("original synthetic 1",
                         category["items"][0]["importReview"]["items"][1]["original"])
        self.assertTrue(category["items"][0]["importReview"]["items"][1]["applied"])
        self.assertTrue(category["items"][0]["importReview"]["items"][1]["edited"])
        self.assertEqual("pending", category["items"][0]["importReview"]["items"][0]["status"])
        self.assertEqual(CONTEXT, seen[0])

    def test_unavailable_structured_storage_marks_whole_export_partial(self):
        class FailingRepo(_FakeStructuredRepo):
            fail = True

        _response, body = self._call(FailingRepo)
        self.assertEqual("PARTIAL", body["status"])
        category = body["metadataExport"]["categories"]["structuredCvProfiles"]
        self.assertEqual("UNAVAILABLE", category["status"])
        self.assertEqual("unavailable", category["code"])
        self.assertEqual([], category["items"])


if __name__ == "__main__":
    unittest.main()
