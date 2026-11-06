"""ApplicationV1 dispatch and dual-auth boundary regression tests."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler  # noqa: E402

# These tests exercise the partner boundary itself, not the surface rollout gate.
os.environ.setdefault("PARTNER_SURFACE_ENABLED", "true")


def _event(path="/v1/partner/me/applications", headers=None):
    return {
        "httpMethod": "GET",
        "path": path,
        "headers": headers or {},
        "requestContext": {
            "http": {"method": "GET", "path": path},
            "authorizer": {"jwt": {"claims": {
                "sub": "synthetic-user",
                "iss": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ",
                "token_use": "access",
                "client_id": "synthetic-client",
            }}},
        },
    }


def test_application_dispatch_reaches_dual_auth_boundary_without_500():
    response = handler.handler(_event(), None)

    assert response["statusCode"] == 401
    assert json.loads(response["body"]) == {
        "error": "Unauthorized",
        "code": "unauthorized",
    }


def test_application_dispatch_rejects_malformed_credential_without_500():
    response = handler.handler(
        _event(headers={"X-Api-Credential": "invalid-test-credential"}),
        None,
    )

    assert response["statusCode"] == 401
    assert json.loads(response["body"]) == {
        "error": "Unauthorized",
        "code": "unauthorized",
    }


VALID_SHAPED_CREDENTIAL = "ris_" + "A" * 40


class _CredentialStore:
    def __init__(self, metadata=None):
        self.metadata = metadata

    def get_by_digest(self, _digest):
        return self.metadata


class _ProfileStore:
    def __init__(self, profile=None):
        self.profile = profile

    def get_profile(self, _profile_id):
        return self.profile


def _sources(tenant="tenant-a"):
    expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    return {
        "credential_store": _CredentialStore({
            "credentialId": "credential-1",
            "apiProfileId": "profile-1",
            "tenantId": tenant,
            "ownerUserId": "synthetic-user",
            "status": "ACTIVE",
            "expiresAt": expires,
        }),
        "profile_store": _ProfileStore({
            "apiProfileId": "profile-1",
            "tenantId": tenant,
            "ownerUserId": "synthetic-user",
            "status": "ACTIVE",
            "expiresAt": expires,
        }),
    }


def _authorized_event(credential=VALID_SHAPED_CREDENTIAL):
    return _event(headers={"X-Api-Credential": credential})


def _registry(status="ACTIVE", tenant="tenant-a"):
    return {
        "applicationId": "partner-1",
        "apiProfileId": "profile-1",
        "tenantId": tenant,
        "status": status,
    }


def test_unknown_well_formed_credential_is_401_when_stores_are_configured():
    sources = _sources()
    sources["credential_store"] = _CredentialStore(None)
    with patch.object(handler, "_build_introspection_sources", return_value=sources):
        response = handler.handler(_authorized_event(), None)
    assert response["statusCode"] == 401
    assert json.loads(response["body"])["code"] == "unauthorized"


def test_inactive_partner_is_403_without_entering_application_repository():
    with patch.object(handler, "_build_introspection_sources", return_value=_sources()), \
            patch("agents.ecosystem.partner_registry.resolve_partner_application",
                  return_value=_registry(status="DISABLED")):
        response = handler.handler(_authorized_event(), None)
    assert response["statusCode"] == 403
    assert json.loads(response["body"])["code"] == "forbidden"


def test_tenant_conflict_is_403_without_fallback_tenant():
    event = _authorized_event()
    event["requestContext"]["authorizer"]["jwt"]["claims"]["custom:tenant_id"] = "tenant-b"
    with patch.object(handler, "_build_introspection_sources", return_value=_sources()), \
            patch("agents.ecosystem.partner_registry.resolve_partner_application",
                  return_value=_registry()):
        response = handler.handler(event, None)
    assert response["statusCode"] == 403
    assert json.loads(response["body"])["code"] == "forbidden"


def test_configured_backend_failure_is_controlled_503():
    with patch.object(handler, "_build_introspection_sources",
                      side_effect=RuntimeError("backend unavailable")):
        response = handler.handler(_authorized_event(), None)
    assert response["statusCode"] == 503
    assert json.loads(response["body"]) == {
        "error": "Service unavailable",
        "code": "unavailable",
    }
