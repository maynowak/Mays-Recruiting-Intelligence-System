"""Separate cv-storage consent gate for durable CV writes."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

import handler  # noqa: E402
from jobsearch.consent_contract import (  # noqa: E402
    ConsentContractError,
    validate_consent_proof,
)

CTX = {
    "userId": "user-1",
    "tenantId": "tenant-1",
    "partnerApplicationId": "partner-1",
    "issuer": "https://issuer.example",
}


class _Repo:
    def __init__(self, allowed):
        self.allowed = allowed
        self.purposes = []

    def has_consent(self, ctx, purpose):
        self.purposes.append(purpose)
        return self.allowed


def test_cv_gate_is_inactive_until_rollout(monkeypatch):
    monkeypatch.delenv("CV_STORAGE_CONSENT_ENFORCED", raising=False)
    monkeypatch.setattr(handler, "_consent_repo", lambda: _Repo(False))
    assert handler._cv_storage_consent_error(CTX) is None


def test_cv_gate_denies_writes_without_consent(monkeypatch):
    monkeypatch.setenv("CV_STORAGE_CONSENT_ENFORCED", "true")
    repo = _Repo(False)
    monkeypatch.setattr(handler, "_consent_repo", lambda: repo)
    response = handler._cv_storage_consent_error(CTX)
    assert response is not None
    assert response["statusCode"] == 403
    assert "CV_STORAGE_CONSENT_REQUIRED" in response["body"]
    assert repo.purposes == ["cv-storage"]


def test_cv_gate_allows_writes_with_consent(monkeypatch):
    monkeypatch.setenv("CV_STORAGE_CONSENT_ENFORCED", "true")
    monkeypatch.setattr(handler, "_consent_repo", lambda: _Repo(True))
    assert handler._cv_storage_consent_error(CTX) is None


def test_cv_gate_fails_closed_when_store_is_unavailable(monkeypatch):
    monkeypatch.setenv("CV_STORAGE_CONSENT_ENFORCED", "true")

    def broken():
        raise RuntimeError("store down")

    monkeypatch.setattr(handler, "_consent_repo", broken)
    response = handler._cv_storage_consent_error(CTX)
    assert response is not None and response["statusCode"] == 403


def test_cv_gate_is_separate_from_application_consent():
    source = (ROOT / "lambda" / "handler.py").read_text(encoding="utf-8")
    assert "CV_STORAGE_CONSENT_ENFORCED" in source
    assert "has_consent(consent_ctx, 'cv-storage')" in source
    assert "APPLICATION_CONSENT_ENFORCED" in source
    assert "application-storage" in source


def test_cv_storage_art9_text_is_purpose_bound():
    version = "cv-storage-consent-2026-11-08-v1"
    digest = "2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036"
    consent, categories, proof_version, proof_hash = validate_consent_proof(
        "cv-storage",
        special_categories_consent=True,
        special_categories=["health", "sex_life"],
        external_text_version=version,
        external_text_sha256=digest,
    )
    assert consent is True
    assert categories == ["health", "sex_life"]
    assert proof_version == version
    assert proof_hash == digest


def test_cv_storage_rejects_application_art9_text():
    with __import__("pytest").raises(ConsentContractError):
        validate_consent_proof(
            "cv-storage",
            special_categories_consent=True,
            special_categories=["health"],
            external_text_version="application-storage-consent-2026-11-07-v4",
            external_text_sha256=(
                "8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7"
            ),
        )


def test_cv_consent_terraform_wiring_defaults_off():
    variables = (ROOT / "terraform" / "variables.tf").read_text(encoding="utf-8")
    module_variables = (ROOT / "terraform" / "modules" / "lambda" / "variables.tf").read_text(
        encoding="utf-8"
    )
    env = (ROOT / "terraform" / "modules" / "lambda" / "main.tf").read_text(encoding="utf-8")
    assert 'variable "cv_storage_consent_enforced"' in variables
    assert 'variable "cv_storage_consent_enforced"' in module_variables
    assert 'CV_STORAGE_CONSENT_ENFORCED' in env
    assert 'default     = false' in variables
