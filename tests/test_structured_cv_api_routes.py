"""Static contract tests for the Structured-CV partner API routes.

These tests do not call AWS. They pin the Terraform route surface, authorizer,
absence of wildcard/proxy routes, default-off Lambda flag and the single fixed
upstream handler dispatch.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "terraform" / "modules" / "api" / "main.tf").read_text(encoding="utf-8")
HANDLER = (ROOT / "lambda" / "handler.py").read_text(encoding="utf-8")

ROUTES = (
    "GET /v1/partner/me/cv-builder-profiles",
    "POST /v1/partner/me/cv-builder-profiles",
    "GET /v1/partner/me/cv-builder-profiles/{profileId}",
    "PATCH /v1/partner/me/cv-builder-profiles/{profileId}",
    "DELETE /v1/partner/me/cv-builder-profiles/{profileId}",
    "GET /v1/partner/me/cv-builder-profiles/{profileId}/export",
)


def test_all_six_structured_cv_routes_are_explicit():
    for route in ROUTES:
        assert f'route_key          = "{route}"' in API


def test_each_structured_route_uses_jwt_authorizer():
    blocks = API.split('resource "aws_apigatewayv2_route" "partner_cv_builder_profiles_')[1:]
    assert len(blocks) == 6
    for block in blocks:
        assert 'authorization_type = "JWT"' in block
        assert "authorizer_id      = aws_apigatewayv2_authorizer.jwt.id" in block
        assert "integrations/${aws_apigatewayv2_integration.lambda.id}" in block


def test_no_wildcard_or_proxy_structured_route():
    assert "cv-builder-profiles/{proxy+}" not in API
    assert "ANY /v1/partner/me/cv-builder-profiles" not in API
    assert "{proxy+}" not in API


def test_feature_flag_defaults_off_in_lambda_and_terraform():
    assert 'STRUCTURED_CV_PROFILE_ENABLED", "false"' in HANDLER
    lambda_tf = (ROOT / "terraform" / "modules" / "lambda" / "main.tf").read_text(encoding="utf-8")
    assert 'STRUCTURED_CV_PROFILE_ENABLED = var.structured_cv_profile_enabled ? "true" : "false"' in lambda_tf
    variables = (ROOT / "terraform" / "modules" / "lambda" / "variables.tf").read_text(encoding="utf-8")
    assert 'variable "structured_cv_profile_enabled"' in variables
    assert "default     = false" in variables.split('variable "structured_cv_profile_enabled"')[1].split("}")[0]


def test_handler_has_one_fixed_dispatch_and_no_client_route_parameter():
    assert HANDLER.count("return _handle_structured_cv_routes(event, context, method, path)") == 1
    assert "path.startswith('/v1/partner/me/cv-builder-profiles/')" in HANDLER
    assert "cv-builder-profiles/{profileId}" not in HANDLER


def test_existing_partner_routes_are_not_removed():
    for route in (
        "GET /v1/partner/me/cvs",
        "POST /v1/partner/me/cvs",
        "GET /v1/partner/me/manual-search-profiles",
        "GET /v1/partner/me/privacy/inspect",
        "GET /v1/partner/me/consents",
    ):
        assert f'route_key          = "{route}"' in API
