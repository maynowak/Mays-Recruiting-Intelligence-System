"""ApplicationV1 dispatch and dual-auth boundary regression tests."""

import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler  # noqa: E402


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
