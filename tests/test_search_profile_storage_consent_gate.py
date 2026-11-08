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
    NOTICE_APPROVED,
    NOTICE_REGISTRY,
)
try:
    import boto3
    from moto import mock_aws
    from jobsearch.consent_contract import ConsentContext
    from jobsearch.consent_repository import ConsentRepository
except ImportError:  # pragma: no cover
    boto3 = None
    mock_aws = lambda fn: fn

from tests.test_partner_ats_profiles_api import AtsHarness  # noqa: E402
from tests.test_partner_cv_search_profiles_api import CvSpHarness  # noqa: E402
from tests.test_partner_manual_profiles_api import Harness  # noqa: E402

TEXT_VERSION = "search-profile-storage-consent-2026-11-08-v2"
TEXT_SHA256 = "75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6"


class _Consent:
    def __init__(self, allowed):
        self.allowed = allowed
        self.purposes = []

    def has_consent(self, ctx, purpose):
        self.purposes.append(purpose)
        return self.allowed


class TestNoticeCandidate:
    def test_notice_is_approved_for_the_limited_pilot(self):
        notice = NOTICE_REGISTRY["search-profile-storage"]["1.0"]
        assert notice.state == NOTICE_APPROVED
        assert notice.legal_approval_ref == "JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08"
        assert notice.approved is True

    def test_partner_text_is_mapped_to_the_ris_version(self):
        ref = EXTERNAL_NOTICE_REFS["search-profile-storage"][TEXT_VERSION]
        assert ref["source"] == "mays-jobsearch"
        assert ref["noticeState"] == NOTICE_APPROVED
        assert ref["noticeVersion"] == "1.0"
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


class _LifecycleRepo:
    """Synthetic grant/withdraw/regrant state for the gate test."""

    def __init__(self):
        self.status = "NOT_GRANTED"

    def grant(self):
        self.status = "GRANTED"

    def withdraw(self):
        self.status = "WITHDRAWN"

    def has_consent(self, ctx, purpose):
        assert purpose == "search-profile-storage"
        return self.status == "GRANTED"


class TestGrantWithdrawRegrant:
    def test_writes_are_blocked_after_withdrawal_and_allowed_again_after_regrant(self, monkeypatch):
        monkeypatch.setenv("SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED", "true")
        repo = _LifecycleRepo()
        monkeypatch.setattr(handler, "_consent_repo", lambda: repo)

        repo.grant()
        assert handler._search_profile_storage_consent_error(
            {"userId": "u1", "tenantId": "t1", "partnerApplicationId": "p1",
             "issuer": "https://issuer"}
        ) is None

        repo.withdraw()
        denied = handler._search_profile_storage_consent_error(
            {"userId": "u1", "tenantId": "t1", "partnerApplicationId": "p1",
             "issuer": "https://issuer"}
        )
        assert denied is not None and denied["statusCode"] == 403
        assert "SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED" in denied["body"]

        repo.grant()
        assert handler._search_profile_storage_consent_error(
            {"userId": "u1", "tenantId": "t1", "partnerApplicationId": "p1",
             "issuer": "https://issuer"}
        ) is None


class TestDraftConsentLifecycle:
    def test_grant_withdraw_regrant_with_the_draft_notice(self):
        if not boto3:
            import pytest
            pytest.skip("boto3/moto unavailable")
        with mock_aws():
            db = boto3.resource("dynamodb", region_name="eu-central-1")
            db.create_table(
                TableName="consents",
                KeySchema=[{"AttributeName": "scopeKey", "KeyType": "HASH"},
                           {"AttributeName": "entityKey", "KeyType": "RANGE"}],
                AttributeDefinitions=[
                    {"AttributeName": "scopeKey", "AttributeType": "S"},
                    {"AttributeName": "entityKey", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            repo = ConsentRepository("consents", db)
            ctx = ConsentContext("u1", "t1", "p1", "https://issuer")
            with patch.dict(os.environ, {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
                granted = repo.grant(ctx, "search-profile-storage", "1.0")
                assert granted["status"] == "GRANTED"
                assert granted["noticeState"] == NOTICE_APPROVED
                assert repo.has_consent(ctx, "search-profile-storage") is True
                withdrawn = repo.withdraw(ctx, "search-profile-storage")
                assert withdrawn["status"] == "WITHDRAWN"
                assert repo.has_consent(ctx, "search-profile-storage") is False
                regranted = repo.grant(ctx, "search-profile-storage", "1.0")
                assert regranted["status"] == "GRANTED"
                assert repo.has_consent(ctx, "search-profile-storage") is True


class TestApiGatewayV2Gate:
    def test_v2_event_method_is_detected(self, monkeypatch):
        monkeypatch.setenv("SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED", "true")
        monkeypatch.setattr(handler, "_consent_repo", lambda: _Consent(False))
        ctx = {"userId": "u1", "tenantId": "t1",
               "partnerApplicationId": "p1", "issuer": "https://issuer"}
        monkeypatch.setattr(handler, "_partner_profile_context", lambda event: (ctx, None))

        def call(*args):
            raise AssertionError("handler must not run when the gate denies")

        response = handler._search_profile_storage_guard(
            call, {"requestContext": {"http": {"method": "POST"}}}, None, "POST")
        assert response is not None and response["statusCode"] == 403
        assert "SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED" in response["body"]
