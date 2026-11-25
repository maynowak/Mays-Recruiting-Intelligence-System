"""RIS-ERASURE-PARTNER-ROUTE-ALIGNMENT-01: partner-edge erasure route.

The Jobsearch BFF contract is ``POST /api/ris/erasure`` -> RIS
``POST /v1/partner/me/erasure``. These tests pin the alignment without
running AWS, Terraform or a real erasure:

* the route exists in the partner gateway module and has Terraform
  provenance on the kernel API,
* ``POST`` dispatches to the **existing** ``_handle_me_erasure`` lifecycle,
* a denied partner boundary never reaches the lifecycle,
* a non-POST method does not reach it either,
* ``POST /me/erasure`` keeps working unchanged,
* no second deletion engine was introduced.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

import handler as h  # noqa: E402

PARTNER_PATH = "/v1/partner/me/erasure"


def _event(method="POST", path=PARTNER_PATH):
    return {
        "httpMethod": method,
        "path": path,
        "headers": {},
        "requestContext": {
            "http": {"method": method, "path": path},
            "authorizer": {"jwt": {"claims": {}}},
        },
    }


def _source(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. Route declaration (Terraform is the source of truth)
# --------------------------------------------------------------------------- #

def test_partner_edge_declares_the_erasure_route():
    edge = _source("terraform", "modules", "partner_edge", "main.tf")
    assert '"POST %s"' % PARTNER_PATH in edge
    # It must be inside the routes set, not a wildcard/ANY route.
    assert "ANY /v1/partner" not in edge
    assert "{proxy+}" not in edge


def test_kernel_api_declares_the_same_route_for_provenance():
    api = _source("terraform", "modules", "api", "main.tf")
    assert 'route_key          = "POST %s"' % PARTNER_PATH in api
    block = api.split('resource "aws_apigatewayv2_route" "partner_erasure"')[1]
    block = block.split("\nresource ")[0]
    assert 'authorization_type = "JWT"' in block
    assert "aws_apigatewayv2_authorizer.jwt.id" in block
    # No new resource families are introduced by this route.
    for forbidden in ("aws_dynamodb_table", "aws_s3_bucket",
                      "aws_iam_role_policy", "aws_sqs_queue"):
        assert forbidden not in block


# --------------------------------------------------------------------------- #
# 2. Dispatch: POST reaches the existing lifecycle
# --------------------------------------------------------------------------- #

def test_post_dispatches_to_the_existing_erasure_lifecycle(monkeypatch):
    calls = {"context": 0, "erasure": 0}

    def partner_context(event):
        calls["context"] += 1
        return {"userId": "user-1", "tenantId": "tenant-1"}, None

    def erasure(event, context):
        calls["erasure"] += 1
        return {"statusCode": 207, "body": json.dumps({"complete": False})}

    monkeypatch.setattr(h, "_partner_profile_context", partner_context)
    monkeypatch.setattr(h, "_handle_me_erasure", erasure)

    response = h._handle_api_event(_event(), None)

    assert response["statusCode"] == 207
    assert calls == {"context": 1, "erasure": 1}


def test_denied_partner_context_never_invokes_the_lifecycle(monkeypatch):
    calls = {"erasure": 0}

    monkeypatch.setattr(
        h, "_partner_profile_context",
        lambda event: (None, {"statusCode": 403,
                              "body": json.dumps({"error": "Forbidden"})}),
    )

    def erasure(event, context):  # pragma: no cover - must not run
        calls["erasure"] += 1
        return {"statusCode": 200}

    monkeypatch.setattr(h, "_handle_me_erasure", erasure)

    response = h._handle_api_event(_event(), None)

    assert response["statusCode"] == 403
    assert calls["erasure"] == 0


def test_non_post_method_does_not_reach_the_lifecycle(monkeypatch):
    calls = {"context": 0, "erasure": 0}

    def partner_context(event):  # pragma: no cover - must not run
        calls["context"] += 1
        return {"userId": "user-1"}, None

    def erasure(event, context):  # pragma: no cover - must not run
        calls["erasure"] += 1
        return {"statusCode": 200}

    monkeypatch.setattr(h, "_partner_profile_context", partner_context)
    monkeypatch.setattr(h, "_handle_me_erasure", erasure)

    for method in ("GET", "PUT", "DELETE", "PATCH"):
        response = h._handle_api_event(_event(method), None)
        assert response["statusCode"] == 404, method

    assert calls == {"context": 0, "erasure": 0}


# --------------------------------------------------------------------------- #
# 3. The kernel route must not regress
# --------------------------------------------------------------------------- #

def test_kernel_me_erasure_still_dispatches_to_the_lifecycle(monkeypatch):
    calls = {"partnerContext": 0, "erasure": 0}

    def partner_context(event):  # pragma: no cover - must not run
        calls["partnerContext"] += 1
        return {"userId": "user-1"}, None

    def erasure(event, context):
        calls["erasure"] += 1
        return {"statusCode": 200, "body": json.dumps({"complete": True})}

    monkeypatch.setattr(h, "_partner_profile_context", partner_context)
    monkeypatch.setattr(h, "_handle_me_erasure", erasure)

    response = h._handle_api_event(_event(path="/me/erasure"), None)

    assert response["statusCode"] == 200
    # /me/erasure must not start requiring the partner credential boundary.
    assert calls == {"partnerContext": 0, "erasure": 1}


def test_kernel_erasure_route_still_declared_in_api_terraform():
    api = _source("terraform", "modules", "api", "main.tf")
    assert 'route_key          = "POST /me/erasure"' in api
    # The partner route is additive: the kernel route declaration count is
    # unchanged (one resource block each).
    assert api.count('resource "aws_apigatewayv2_route" "erasure"') == 1
    assert api.count('resource "aws_apigatewayv2_route" "partner_erasure"') == 1


# --------------------------------------------------------------------------- #
# 4. One deletion engine, no client-supplied identity
# --------------------------------------------------------------------------- #

def test_there_is_exactly_one_erasure_engine():
    handler_source = _source("lambda", "handler.py")
    assert handler_source.count("PrivacyErasure(") == 1
    assert handler_source.count("def _handle_me_erasure(") == 1
    # Both routes dispatch into that single function.
    assert handler_source.count("return _handle_me_erasure(event, context)") == 2


def test_partner_route_reads_no_identity_from_the_request():
    source = _source("lambda", "handler.py")
    branch = source.split("elif method == 'POST' and path == '/v1/partner/me/erasure':")[1]
    branch = branch.split("elif path == '/v1/partner/me/consents'")[0]
    for forbidden in ("event.get('body')", 'event.get("body")',
                      "queryStringParameters", "pathParameters"):
        assert forbidden not in branch
    # Identity comes from the partner boundary + verified JWT claims only.
    assert "_partner_profile_context(event)" in branch
    assert "_extract_user_context(event)" in source.split("def _handle_me_erasure")[1]


def test_erasure_lifecycle_derives_identity_from_jwt_only():
    source = _source("lambda", "handler.py")
    body = source.split("def _handle_me_erasure")[1].split("def _documents_context")[0]
    assert "user_context = _extract_user_context(event)" in body
    for forbidden in ("event.get('body')", 'event.get("body")',
                      "queryStringParameters"):
        assert forbidden not in body


# --------------------------------------------------------------------------- #
# 4b. Real partner boundary (no monkeypatched context): fail closed
# --------------------------------------------------------------------------- #

def _authenticated_event(credential=None):
    event = _event()
    event["requestContext"]["authorizer"]["jwt"]["claims"] = {
        "sub": "user-1",
        "token_use": "access",
        "client_id": "client-1",
        "iss": "https://issuer.example",
    }
    if credential is not None:
        event["headers"] = {"X-Api-Credential": credential}
    return event


def test_real_boundary_denies_a_missing_partner_credential(monkeypatch):
    calls = {"erasure": 0}
    monkeypatch.setattr(
        h, "_handle_me_erasure",
        lambda event, context: calls.update(erasure=calls["erasure"] + 1)
        or {"statusCode": 200},
    )

    response = h._handle_api_event(_authenticated_event(), None)

    assert response["statusCode"] == 401
    assert calls["erasure"] == 0


def test_real_boundary_denies_a_malformed_partner_credential(monkeypatch):
    calls = {"erasure": 0}
    monkeypatch.setattr(
        h, "_handle_me_erasure",
        lambda event, context: calls.update(erasure=calls["erasure"] + 1)
        or {"statusCode": 200},
    )

    response = h._handle_api_event(
        _authenticated_event("a-cognito-jwt-looking.value.here"), None)

    assert response["statusCode"] == 401
    assert calls["erasure"] == 0


def test_real_boundary_denies_an_unauthenticated_caller(monkeypatch):
    calls = {"erasure": 0}
    monkeypatch.setattr(
        h, "_handle_me_erasure",
        lambda event, context: calls.update(erasure=calls["erasure"] + 1)
        or {"statusCode": 200},
    )

    response = h._handle_api_event(_event(), None)

    assert response["statusCode"] == 401
    assert calls["erasure"] == 0


# --------------------------------------------------------------------------- #
# 5. The partner surface gate covers the new path (fail closed until approved)
# --------------------------------------------------------------------------- #

def test_partner_erasure_is_closed_while_the_surface_is_disabled(monkeypatch):
    monkeypatch.setenv("PARTNER_SURFACE_ENABLED", "false")
    response = h.lambda_handler(_event(), None)
    assert response["statusCode"] == 503
    assert "not activated" in response["body"]


def test_partner_erasure_gate_is_prefix_based_not_route_specific():
    source = _source("lambda", "handler.py")
    assert 'path.startswith("/v1/partner/me/")' in source


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([os.path.abspath(__file__)]))
