from pathlib import Path

from installer.bootstrap_preflight import EXPECTED, validate_bootstrap_config


ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_plan_contract_uses_external_identity_and_explicit_orders_modes():
    variables = text("terraform/variables.tf")
    main = text("terraform/main.tf")
    assert 'variable "identity_mode"' in variables
    assert 'variable "external_cognito_account_id"' in variables
    assert 'variable "orders_lifecycle"' in variables
    assert 'count  = local.identity_managed ? 1 : 0' in main
    assert 'count  = local.orders_enabled ? 1 : 0' in main
    assert 'count              = local.orders_managed ? 1 : 0' in main


def test_external_plan_has_no_protected_resource_declarations_in_root():
    main = text("terraform/main.tf")
    assert "aws_cognito_user_pool" not in main
    assert "aws_cloudfront_distribution" not in main
    assert "aws_route53_record" not in main
    assert "aws_acm_certificate" not in main


def test_external_mode_disables_cognito_module_and_uses_external_authorizer_inputs():
    main = text("terraform/main.tf")
    api = text("terraform/modules/api/main.tf")
    assert "count  = local.identity_managed ? 1 : 0" in main
    assert "var.external_cognito_issuer" in main
    assert "audience = [var.cognito_user_pool_client_id]" in api
    assert "audience = [var.cognito_user_pool_m2m_client_id]" in api
    assert "issuer   = var.cognito_issuer" in api


def test_protected_identity_is_reference_only_and_not_recreated():
    protected = text("docs/architecture/RIS-DEV2-PROTECTED-INFRASTRUCTURE.md")
    runbook = text("docs/runbooks/RIS-DEV2-CONTROLLED-UPGRADE.md")
    assert "PROTECTED / EXTERNALLY MANAGED" in protected
    assert "zero `ris-dev2` resource addresses" in protected
    assert "do not switch the AWS profile" in runbook


def test_external_identity_fails_closed_without_account_or_m2m_reference():
    config = {
        **EXPECTED,
        "identity_mode": "external",
        "orders_lifecycle": "disabled",
        "privacy_flags": {},
        "external_cognito_user_pool_id": "eu-central-1_ExamplePool",
        "external_cognito_user_pool_arn": "arn:aws:cognito-idp:eu-central-1:240571105849:userpool/eu-central-1_ExamplePool",
        "external_cognito_issuer": "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ExamplePool",
        "external_cognito_human_client_id": "humanClient123",
    }
    errors = validate_bootstrap_config(config)
    assert any("account ID" in error for error in errors)
    assert any("M2M" in error for error in errors)


def test_lambda_privacy_execution_flags_are_literal_false():
    main = text("terraform/modules/lambda/main.tf")
    for flag in (
        "ERASURE_OPERATION_REPOSITORY_ENABLED",
        "ERASURE_S3_PHASE_REPOSITORY_ENABLED",
        "ERASURE_S3_EXECUTION_ENABLED",
        "ERASURE_S3_QUIESCENCE_ENABLED",
        "ERASURE_WRITE_FREEZE_ENABLED",
        "ERASURE_UPLOAD_TICKET_LEDGER_ENABLED",
        "ERASURE_UPLOAD_CUTOVER_ENABLED",
    ):
        assert f'{flag} ' in main
        assert '"false"' in main[main.index(flag) : main.index(flag) + 100]


def test_foreign_state_contract_is_rejected_by_local_preflight():
    config = {
        **EXPECTED,
        "identity_mode": "managed",
        "orders_lifecycle": "disabled",
        "privacy_flags": {},
        "state_key": "env:/ris-dev/dev/terraform.tfstate",
    }
    errors = validate_bootstrap_config(config)
    assert any("state_key" in error for error in errors)
