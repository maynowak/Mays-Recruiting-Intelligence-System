from installer.bootstrap_preflight import EXPECTED, validate_bootstrap_config


def valid_external_config():
    return {
        **EXPECTED,
        "identity_mode": "external",
        "external_cognito_user_pool_id": "eu-central-1_ExamplePool",
        "external_cognito_user_pool_arn": (
            "arn:aws:cognito-idp:eu-central-1:262370457690:"
            "userpool/eu-central-1_ExamplePool"
        ),
        "external_cognito_issuer": (
            "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ExamplePool"
        ),
        "external_cognito_human_client_id": "humanClient123",
        "external_cognito_m2m_client_id": "m2mClient123",
        "orders_lifecycle": "external",
        "external_orders_table_name": "ris-dev2-orders",
        "external_orders_table_arn": (
            "arn:aws:dynamodb:eu-central-1:262370457690:table/ris-dev2-orders"
        ),
        "external_orders_queue_url": (
            "https://sqs.eu-central-1.amazonaws.com/262370457690/ris-dev2-orders-queue"
        ),
        "external_orders_queue_arn": (
            "arn:aws:sqs:eu-central-1:262370457690:ris-dev2-orders-queue"
        ),
        "privacy_flags": {},
    }


def test_external_bootstrap_contract_passes_without_aws():
    assert validate_bootstrap_config(valid_external_config()) == []


def test_missing_identity_and_orders_modes_fail_closed():
    config = {**EXPECTED, "privacy_flags": {}}
    errors = validate_bootstrap_config(config)
    assert any("identity_mode" in error for error in errors)
    assert any("orders_lifecycle" in error for error in errors)


def test_foreign_project_profile_backend_and_state_fail_closed():
    config = valid_external_config()
    config.update(
        project_name="mays-ris",
        aws_profile="other",
        backend_bucket="other-state",
        state_key="env:/other/dev/terraform.tfstate",
    )
    errors = validate_bootstrap_config(config)
    assert any("project_name" in error for error in errors)
    assert any("aws_profile" in error for error in errors)
    assert any("backend_bucket" in error for error in errors)
    assert any("state_key" in error for error in errors)


def test_privacy_execution_flags_fail_closed():
    config = valid_external_config()
    config["privacy_flags"] = {"ERASURE_S3_EXECUTION_ENABLED": True}
    errors = validate_bootstrap_config(config)
    assert any("ERASURE_S3_EXECUTION_ENABLED" in error for error in errors)


def test_disabled_orders_requires_no_dummy_references():
    config = {**EXPECTED, "identity_mode": "managed", "orders_lifecycle": "disabled"}
    config["privacy_flags"] = {}
    assert validate_bootstrap_config(config) == []
