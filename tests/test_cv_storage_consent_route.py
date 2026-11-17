"""Route-level cv-storage consent gate: writes blocked, reads/delete allowed."""

import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lambda"))

import handler as h  # noqa: E402
from tests.test_partner_cv_document_api import CVS, CvHarness  # noqa: E402


class _Consent:
    def __init__(self, allowed):
        self.allowed = allowed

    def has_consent(self, ctx, purpose):
        assert purpose == "cv-storage"
        return self.allowed


class CvStorageConsentRouteTests(CvHarness):
    def test_gate_blocks_create_but_keeps_list_and_delete_available(self):
        existing = self.body(self.create_cv(name="existing.pdf"))
        with patch.dict(os.environ, {"CV_STORAGE_CONSENT_ENFORCED": "true"}), \
                patch.object(h, "_consent_repo", lambda: _Consent(False)):
            blocked = self.create_cv(name="blocked.pdf")
            listed = self.call("GET", CVS)
            deleted = self.call("DELETE", f"{CVS}/{existing['cvId']}")
        self.assertEqual(blocked["statusCode"], 403)
        self.assertIn("CV_STORAGE_CONSENT_REQUIRED", self.body(blocked)["code"])
        self.assertEqual(listed["statusCode"], 200)
        self.assertEqual(deleted["statusCode"], 200)

    def test_gate_blocks_upload_and_patch_but_allows_read(self):
        created = self.body(self.create_cv(name="cv.pdf"))
        cv_id = created["cvId"]
        with patch.dict(os.environ, {"CV_STORAGE_CONSENT_ENFORCED": "true"}), \
                patch.object(h, "_consent_repo", lambda: _Consent(False)):
            upload = self.ticket(cv_id)
            patch_response = self.call(
                "PATCH", f"{CVS}/{cv_id}",
                body={"filename": "renamed.pdf", "version": 1})
            read = self.call("GET", f"{CVS}/{cv_id}")
        self.assertEqual(upload["statusCode"], 403)
        self.assertEqual(patch_response["statusCode"], 403)
        self.assertEqual(read["statusCode"], 200)

    def test_gate_allows_write_after_explicit_consent(self):
        with patch.dict(os.environ, {"CV_STORAGE_CONSENT_ENFORCED": "true"}), \
                patch.object(h, "_consent_repo", lambda: _Consent(True)):
            created = self.create_cv(name="allowed.pdf")
        self.assertEqual(created["statusCode"], 201)
