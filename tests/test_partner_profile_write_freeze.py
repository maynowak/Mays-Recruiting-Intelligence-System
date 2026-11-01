"""C0C transaction guard construction tests."""

import os

import pytest

from jobsearch.partner_profile_contract import CVDocument
from jobsearch.partner_profile_repository import PartnerProfileReadError, PartnerProfileRepository


CTX = {
    "user_id": "user-1", "tenant_id": "tenant-1",
    "partner_app_id": "partner-1", "issuer": "https://issuer.example",
}


def test_freeze_disabled_keeps_normal_crud_guard_free():
    repo = PartnerProfileRepository(table_name="profiles")
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv("ERASURE_WRITE_FREEZE_ENABLED", raising=False)
        assert repo._freeze_checks(**CTX, resource=object()) == []


def test_cv_mutation_gets_user_and_cv_atomic_condition_checks(monkeypatch):
    monkeypatch.setenv("ERASURE_WRITE_FREEZE_ENABLED", "true")
    repo = PartnerProfileRepository(table_name="profiles")
    cv = CVDocument(cv_id="cv-1", user_id="user-1", tenant_id="tenant-1",
                    name="cv.pdf")
    checks = repo._freeze_checks(**CTX, resource=cv)
    assert len(checks) == 2
    assert all("ConditionCheck" in item for item in checks)
    assert all("attribute_not_exists(resourceId)" in item["ConditionCheck"][
        "ConditionExpression"] for item in checks)


def test_enabled_freeze_without_verified_partner_scope_fails_closed(monkeypatch):
    monkeypatch.setenv("ERASURE_WRITE_FREEZE_ENABLED", "true")
    repo = PartnerProfileRepository(table_name="profiles")
    with pytest.raises(PartnerProfileReadError):
        repo._freeze_checks(user_id="user-1", tenant_id="tenant-1",
                            partner_app_id=None, issuer=None, resource=object())


def test_legacy_user_profile_boundary_blocks_when_freeze_enabled(monkeypatch):
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))
    import handler

    monkeypatch.setenv("ERASURE_WRITE_FREEZE_ENABLED", "true")
    monkeypatch.setattr(
        handler, "_partner_profile_context",
        lambda _event: (None, {"statusCode": 401}))
    with pytest.raises(handler._WriteFreezeUnavailable):
        handler._user_profile_freeze_context(
            {}, {"userId": "user-1"}, "tenant-1")
