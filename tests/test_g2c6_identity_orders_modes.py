"""Static, offline guards for the G2C-6 ownership boundaries."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "terraform"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_managed_identity_remains_the_default_and_external_is_explicit():
    variables = read("terraform/variables.tf")
    main = read("terraform/main.tf")

    assert 'variable "identity_mode"' in variables
    assert 'default     = "managed"' in variables
    assert 'contains(["managed", "external"], var.identity_mode)' in variables
    assert 'count  = local.identity_managed ? 1 : 0' in main
    assert 'var.external_cognito_user_pool_id' in main
    assert 'var.external_cognito_human_client_id' in main
    assert 'var.external_cognito_m2m_client_id' in main


def test_external_identity_is_fail_closed_and_never_falls_back():
    variables = read("terraform/variables.tf")
    main = read("terraform/main.tf")

    for name in (
        "external_cognito_user_pool_id",
        "external_cognito_user_pool_arn",
        "external_cognito_issuer",
        "external_cognito_human_client_id",
        "external_cognito_m2m_client_id",
    ):
        assert f'variable "{name}"' in variables
    assert 'var.identity_mode == "managed" ||' in variables
    assert 'var.external_cognito_user_pool_id' in main
    assert 'var.external_cognito_human_client_id' in main
    assert 'var.external_cognito_m2m_client_id' in main
    assert 'module.cognito[0]' in main
    assert 'module.cognito.user_pool' not in main


def test_authorizers_use_the_explicit_complete_issuer():
    api = read("terraform/modules/api/main.tf")
    variables = read("terraform/modules/api/variables.tf")

    assert 'variable "cognito_issuer"' in variables
    assert 'issuer   = var.cognito_issuer' in api
    assert 'issuer   = "https://${var.cognito_user_pool_endpoint}"' not in api


def test_orders_modes_are_explicit_and_disabled_has_no_reader_or_orders_monitoring():
    variables = read("terraform/variables.tf")
    main = read("terraform/main.tf")

    assert 'variable "orders_lifecycle"' in variables
    assert 'contains(["managed", "external", "disabled"], var.orders_lifecycle)' in variables
    assert 'local.orders_managed ? 1 : 0' in main
    assert 'count  = local.orders_enabled ? 1 : 0' in main
    assert 'orders_lifecycle' in main
    assert 'var.external_orders_table_arn' in main
    assert 'var.external_orders_queue_arn' in main


def test_external_and_disabled_orders_do_not_trigger_installer_managed_component():
    installer = read("installer/ris.py")

    assert "def configured_orders_lifecycle" in installer
    assert 'configured_orders_lifecycle(ctx) == "managed"' in installer
    assert 'if ctx.composite and orders_lifecycle == "managed":' in installer


def test_protected_resource_classes_are_not_declared_by_external_identity_inputs():
    main = read("terraform/main.tf")
    variables = read("terraform/variables.tf")

    assert "aws_cloudfront_distribution" not in main
    assert "aws_route53_record" not in main
    assert "aws_acm_certificate" not in main
    assert "external_cognito_domain" in variables
    assert "aws_cognito_user_pool" not in main
