"""Static guards for the RC2 live-baseline reconciliation.

These tests deliberately protect the six live `ris-dev` functions that the
first RC1 plan would have removed. They are source/config guards only; they do
not make AWS calls and do not replace a reviewed Terraform plan.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "terraform"


def read(rel: str) -> str:
    return (TF / rel).read_text(encoding="utf-8")


def test_six_structured_cv_routes_remain_defined():
    api = read("modules/api/main.tf")
    expected = {
        "GET /v1/partner/me/cv-builder-profiles",
        "POST /v1/partner/me/cv-builder-profiles",
        "GET /v1/partner/me/cv-builder-profiles/{profileId}",
        "PATCH /v1/partner/me/cv-builder-profiles/{profileId}",
        "DELETE /v1/partner/me/cv-builder-profiles/{profileId}",
        "GET /v1/partner/me/cv-builder-profiles/{profileId}/export",
    }
    for route in expected:
        assert f'route_key          = "{route}"' in api


def test_structured_cv_owner_index_and_flag_remain_fail_closed():
    dynamodb = read("modules/dynamodb/main.tf")
    variables = read("variables.tf")
    lambda_tf = read("modules/lambda/main.tf")
    assert 'name            = "gsi-structured-owner"' in dynamodb
    assert 'variable "structured_cv_profile_enabled"' in variables
    assert "default     = false" in variables.split(
        'variable "structured_cv_profile_enabled"', 1)[1].split("}", 1)[0]
    assert ('STRUCTURED_CV_PROFILE_ENABLED = '
            'var.structured_cv_profile_enabled ? "true" : "false"') in lambda_tf


def test_partner_erasure_route_is_preserved():
    partner_edge = read("modules/partner_edge/main.tf")
    assert '"POST /v1/partner/me/erasure"' in partner_edge


def test_documents_cors_is_preserved_without_origin_wildcard():
    documents = read("modules/documents/main.tf")
    variables = read("modules/documents/variables.tf")
    assert 'resource "aws_s3_bucket_cors_configuration" "documents"' in documents
    assert "allowed_origins = var.browser_allowed_origins" in documents
    assert 'default     = ["https://www.mays-job-matcher.app"]' in variables
    assert 'allowed_origins = ["*"]' not in documents
    assert 'allowed_origins = ["*"]' not in variables


def test_consent_safety_flags_are_wired_and_not_hardcoded():
    lambda_tf = read("modules/lambda/main.tf")
    variables = read("variables.tf")
    for name in (
        "CONSENT_NOTICE_STATE_ENFORCED",
        "CONSENT_PILOT_ALLOWLIST",
        "CV_STORAGE_CONSENT_ENFORCED",
        "SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED",
    ):
        assert name in lambda_tf
        source_var = name.lower()
        assert f'variable "{source_var}"' in variables
    assert "CONSENT_PILOT_ALLOWLIST                 = var.consent_pilot_allowlist" in lambda_tf
    # The live allowlist is intentionally not committed; it must be supplied
    # from protected operator configuration at plan time.
    config = (ROOT / "installer/project-configs/ris-dev.json").read_text()
    assert "consent_pilot_allowlist" not in config


def test_partner_profile_condition_check_permission_is_preserved():
    lambda_tf = read("modules/lambda/main.tf")
    assert '"dynamodb:ConditionCheckItem"' in lambda_tf


def test_orders_worker_boundary_is_configured_explicitly():
    main = read("main.tf")
    variables = read("variables.tf")
    config = json.loads(
        (ROOT / "installer/project-configs/ris-dev.json").read_text())
    assert 'variable "mays_orders_lambda_execution_boundary"' in variables
    assert "lambda_execution_boundary = var.mays_orders_lambda_execution_boundary" in main
    assert config["terraform_vars"]["mays_orders_lambda_execution_boundary"] == (
        "arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary")


def test_health_publisher_schedule_keeps_the_live_interval():
    health = read("modules/health_plane/main.tf")
    assert 'schedule_expression = "rate(15 minutes)"' in health
    assert 'schedule_expression = "rate(5 minutes)"' not in health
