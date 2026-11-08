"""Separate search-profile-storage consent gate.

Covers the three Option-A profile domains:
* manual search profiles (no CV parent),
* CV search profiles (durable CV parent),
* ATS profiles (durable CV-search-profile parent).

Writes require consent when the rollout switch is on; list/get/delete remain
available. The notice itself is a DRAFT technical candidate with no invented
legal approval.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lambda"))

import handler  # noqa: E402
from jobsearch.consent_contract import (  # noqa: E402
    EXTERNAL_NOTICE_REFS,
    NOTICE_DRAFT,
    NOTICE_REGISTRY,
)
from tests.test_partner_ats_profiles_api import AtsHarness  # noqa: E402
from tests.test_partner_cv_search_profiles_api import CvSpHarness  # noqa: E402
from tests.test_partner_manual_profiles_api import Harness  # noqa: E402

TEXT_VERSION = "search-profile-storage-consent-2026-11-08-v1"
TEXT_SHA256 = "926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8"


class _Consent:
    def __init__(self, allowed):
        self.allowed = allowed
        self.purposes = []

    def has_consent(self, ctx, purpose):
        self.purposes.append(purpose)
        return self.allowed


class TestNoticeCandidate:
    def test_notice_is_draft_and_has_no_invented_legal_approval(self):
        notice = NOTICE_REGISTRY["search-profile-storage"]["1.0"]
        assert notice.state == NOTICE_DRAFT
        assert notice.legal_approval_ref is None
        assert notice.approved is False

    def test_partner_text_is_known_but_not_mapped_to_the_ris_version(self):
        ref = EXTERNAL_NOTICE_REFS["search-profile-storage"][TEXT_VERSION]
        assert ref["source"] == "mays-jobsearch"
        assert ref["noticeState"] == NOTICE_DRAFT
        assert ref["noticeVersion"] is None
        assert ref["textSha256"] == TEXT_SHA256


class TestManualGate(Harness):
    def test_gate_is_off_by_default(self):
        with patch.object(handler, "_consent_repo", lambda: _Consent(False)):
            created = self.create()
        assert created["statusCode"] == 201

    def test_enforced_gate_blocks_create_but_allows_list_and_delete(self):
        existing = self.body(self.create())["manualSearchProfileId"]
        with patch.dict(os.environ, {"SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED": "true"}), \
                patch.object(handler, "_consent_repo", lambda: _Consent(False)):
            blocked = self.create(name="blocked")
            listed = self.call("GET", "/v1/partner/me/manual-search-profiles")
            deleted = self.call(
                "DELETE", f"/v1/partner/me/manual-search-profiles/{existing}")
        assert blocked["statusCode"] == 403
        assert "SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED" in self.body(blocked)["code"]
        assert listed["statusCode"] == 200
        assert deleted["statusCode"] == 204

    def test_enforced_gate_allows_create_with_consent(self):
        repo = _Consent(True)
        with patch.dict(os.environ, {"SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED": "true"}), \
                patch.object(handler, "_consent_repo", lambda: repo):
            created = self.create(name="allowed")
        assert created["statusCode"] == 201
        assert repo.purposes == ["search-profile-storage"]


class TestCvSearchProfileGate(CvSpHarness):
    def test_enforced_gate_blocks_cv_search_profile_create(self):
        cv_id = self.cv()
        with patch.dict(os.environ, {"SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED": "true"}), \
                patch.object(handler, "_consent_repo", lambda: _Consent(False)):
            blocked = self.create_sp(cv_id)
            listed = self.call("GET", self.url(cv_id))
        assert blocked["statusCode"] == 403
        assert "SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED" in self.body(blocked)["code"]
        assert listed["statusCode"] == 200


class TestAtsProfileGate(AtsHarness):
    def test_enforced_gate_blocks_ats_create(self):
        cv_id, sp_id = self.parent()
        with patch.dict(os.environ, {"SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED": "true"}), \
                patch.object(handler, "_consent_repo", lambda: _Consent(False)):
            blocked = self.create_ats(sp_id)
            listed = self.call("GET", self.ats_url(sp_id))
        assert blocked["statusCode"] == 403
        assert "SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED" in self.body(blocked)["code"]
        assert listed["statusCode"] == 200


class TestTerraformWiring:
    def test_search_gate_defaults_off_and_is_wired_to_the_lambda(self):
        root_vars = (ROOT / "terraform" / "variables.tf").read_text(encoding="utf-8")
        module_vars = (ROOT / "terraform" / "modules" / "lambda" / "variables.tf").read_text(
            encoding="utf-8"
        )
        module = (ROOT / "terraform" / "modules" / "lambda" / "main.tf").read_text(
            encoding="utf-8"
        )
        root = (ROOT / "terraform" / "main.tf").read_text(encoding="utf-8")
        for source in (root_vars, module_vars):
            assert 'variable "search_profile_storage_consent_enforced"' in source
            assert "default     = false" in source
        assert "SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED" in module
        assert "search_profile_storage_consent_enforced" in root
