"""The ApplicationV1 storage consent gate must fail closed when enforced."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

import handler  # noqa: E402
from jobsearch.application_contract import ApplicationContext  # noqa: E402

CTX = ApplicationContext("u1", "t1", "p1", "https://issuer")


class _Repo:
    def __init__(self, allowed):
        self.allowed = allowed

    def has_consent(self, ctx, purpose):
        return self.allowed


def test_gate_denies_writes_without_consent(monkeypatch):
    monkeypatch.setenv("APPLICATION_CONSENT_ENFORCED", "true")
    monkeypatch.setattr(handler, "_consent_repo", lambda: _Repo(False))
    response = handler._application_consent_error(CTX)
    assert response is not None
    assert response["statusCode"] == 403
    assert "CONSENT_REQUIRED" in response["body"]


def test_gate_allows_writes_with_consent(monkeypatch):
    monkeypatch.setenv("APPLICATION_CONSENT_ENFORCED", "true")
    monkeypatch.setattr(handler, "_consent_repo", lambda: _Repo(True))
    assert handler._application_consent_error(CTX) is None


def test_gate_is_inactive_until_rollout(monkeypatch):
    monkeypatch.setenv("APPLICATION_CONSENT_ENFORCED", "false")
    monkeypatch.setattr(handler, "_consent_repo", lambda: _Repo(False))
    assert handler._application_consent_error(CTX) is None


def test_gate_fails_closed_when_store_is_unavailable(monkeypatch):
    monkeypatch.setenv("APPLICATION_CONSENT_ENFORCED", "true")

    def broken():
        raise RuntimeError("store down")

    monkeypatch.setattr(handler, "_consent_repo", broken)
    response = handler._application_consent_error(CTX)
    assert response is not None and response["statusCode"] == 403


def test_gate_covers_every_application_write_path():
    source = (ROOT / "lambda" / "handler.py").read_text(encoding="utf-8")
    assert source.count("denied = _application_consent_error(ctx)") == 5


def test_consent_routes_exist_on_both_apis():
    api = (ROOT / "terraform" / "modules" / "api" / "main.tf").read_text(encoding="utf-8")
    edge = (ROOT / "terraform" / "modules" / "partner_edge" / "main.tf").read_text(encoding="utf-8")
    for block in ("consents_get", "consents_grant", "consents_withdraw", "consents_history"):
        assert 'resource "aws_apigatewayv2_route" "%s"' % block in api
    for key in ("GET /v1/partner/me/consents", "POST /v1/partner/me/consents",
                "POST /v1/partner/me/consents/withdraw",
                "GET /v1/partner/me/consents/history"):
        assert '"%s"' % key in edge
    assert len(re.findall(r'route_key\s*=\s*"(?:GET|POST) /v1/partner/me/consents', api)) == 4


def test_consent_table_and_rollout_default():
    tf = (ROOT / "terraform" / "modules" / "lambda" / "main.tf").read_text(encoding="utf-8")
    variables = (ROOT / "terraform" / "variables.tf").read_text(encoding="utf-8")
    assert 'CONSENTS_TABLE' in tf
    assert 'APPLICATION_CONSENT_ENFORCED' in tf
    assert re.search(r'variable "application_consent_enforced"[\s\S]*?default\s*=\s*false',
                     variables)
