"""The new partner/personal API surface must stay closed until approved.

Deploying routes and tables is an infrastructure change, not a data-protection
approval (RG-09). These tests pin the fail-closed default and the fact that
existing RIS routes are unaffected.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

import handler  # noqa: E402


def _event(path: str) -> dict:
    return {
        "httpMethod": "GET",
        "path": path,
        "headers": {},
        "requestContext": {"http": {"method": "GET", "path": path}},
    }


def test_partner_surface_is_closed_by_default(monkeypatch):
    monkeypatch.delenv("PARTNER_SURFACE_ENABLED", raising=False)
    response = handler.lambda_handler(_event("/v1/partner/me/applications"), None)
    assert response["statusCode"] == 503
    assert "not activated" in response["body"]


def test_partner_surface_closed_for_every_partner_path(monkeypatch):
    monkeypatch.setenv("PARTNER_SURFACE_ENABLED", "false")
    for path in (
        "/v1/partner/me/applications",
        "/v1/partner/me/applications/metrics",
        "/v1/partner/me/cvs",
        "/v1/partner/me/privacy/inspect",
        "/v1/partner/me/search-profiles/s1/ats-profiles",
    ):
        assert handler.lambda_handler(_event(path), None)["statusCode"] == 503


def test_partner_surface_opens_only_with_explicit_true(monkeypatch):
    monkeypatch.setenv("PARTNER_SURFACE_ENABLED", "true")
    response = handler.lambda_handler(_event("/v1/partner/me/applications"), None)
    # Reaches the real handler: without a JWT it is rejected, not gated.
    assert response["statusCode"] != 503


def test_existing_ris_routes_are_not_gated(monkeypatch):
    monkeypatch.delenv("PARTNER_SURFACE_ENABLED", raising=False)
    for path in ("/me", "/agents", "/platform"):
        assert handler.lambda_handler(_event(path), None)["statusCode"] != 503
