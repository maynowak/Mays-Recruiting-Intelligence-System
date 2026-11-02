"""Offline, fail-closed RIS-DEV2 bootstrap contract.

This module validates only declared configuration. It intentionally performs no
AWS, Terraform backend, state, or filesystem mutation. Live resource ownership
must be verified separately before any remote plan.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping


EXPECTED = {
    "project_name": "ris-dev2",
    "environment": "dev",
    "account_id": "262370457690",
    "region": "eu-central-1",
    "aws_profile": "default",
    "backend_bucket": "ris-dev2-tf-state-dev",
    "backend_lock_table": "ris-dev2-tf-lock",
    "workspace": "ris-dev2",
    "state_key": "env:/ris-dev2/dev/terraform.tfstate",
}

PRIVACY_FLAGS = (
    "PRIVACY_RECEIPT_JOURNAL_ENABLED",
    "ERASURE_OPERATION_REPOSITORY_ENABLED",
    "ERASURE_WRITE_FREEZE_ENABLED",
    "ERASURE_UPLOAD_TICKET_LEDGER_ENABLED",
    "ERASURE_UPLOAD_CUTOVER_ENABLED",
    "ERASURE_S3_QUIESCENCE_ENABLED",
    "ERASURE_S3_PHASE_REPOSITORY_ENABLED",
    "ERASURE_S3_EXECUTION_ENABLED",
)


def _required_equal(config: Mapping[str, Any], key: str, errors: list[str]) -> None:
    expected = EXPECTED[key]
    actual = config.get(key)
    if actual != expected:
        errors.append(f"{key} must be exactly {expected!r}, got {actual!r}")


def validate_bootstrap_config(config: Mapping[str, Any]) -> list[str]:
    """Return contract violations; an empty list means the config is valid."""
    errors: list[str] = []
    for key in EXPECTED:
        _required_equal(config, key, errors)

    identity_mode = config.get("identity_mode")
    if identity_mode not in {"managed", "external"}:
        errors.append("identity_mode must be explicitly managed or external")
    elif identity_mode == "external":
        pool_id = str(config.get("external_cognito_user_pool_id", ""))
        identity_account = str(config.get("external_cognito_account_id", ""))
        pool_arn = str(config.get("external_cognito_user_pool_arn", ""))
        issuer = str(config.get("external_cognito_issuer", ""))
        human = str(config.get("external_cognito_human_client_id", ""))
        m2m = str(config.get("external_cognito_m2m_client_id", ""))
        if not re.fullmatch(r"eu-central-1_[A-Za-z0-9]+", pool_id):
            errors.append("external Cognito pool ID is missing or malformed")
        if not re.fullmatch(r"[0-9]{12}", identity_account):
            errors.append("external Cognito account ID is missing or malformed")
        if not re.fullmatch(
            rf"arn:aws:cognito-idp:eu-central-1:{re.escape(identity_account)}:userpool/{re.escape(pool_id)}",
            pool_arn,
        ):
            errors.append("external Cognito pool ARN does not match pool/account/region")
        if issuer != f"https://cognito-idp.eu-central-1.amazonaws.com/{pool_id}":
            errors.append("external Cognito issuer does not match pool/region")
        if not re.fullmatch(r"[A-Za-z0-9]+", human):
            errors.append("external human Cognito client ID is missing or malformed")
        if not re.fullmatch(r"[A-Za-z0-9]+", m2m):
            errors.append("external M2M Cognito client ID is missing or malformed")

    orders_lifecycle = config.get("orders_lifecycle")
    if orders_lifecycle not in {"managed", "external", "disabled"}:
        errors.append("orders_lifecycle must be explicitly managed, external, or disabled")
    elif orders_lifecycle == "external":
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(config.get("external_orders_table_name", ""))):
            errors.append("external Orders table name is missing or malformed")
        if not re.fullmatch(
            rf"arn:aws:dynamodb:eu-central-1:{EXPECTED['account_id']}:table/[A-Za-z0-9_.-]+",
            str(config.get("external_orders_table_arn", "")),
        ):
            errors.append("external Orders table ARN is missing or malformed")
        if not re.fullmatch(
            rf"https://sqs\.eu-central-1\.amazonaws\.com/{EXPECTED['account_id']}/[A-Za-z0-9_.-]+",
            str(config.get("external_orders_queue_url", "")),
        ):
            errors.append("external Orders queue URL is missing or malformed")
        if not re.fullmatch(
            rf"arn:aws:sqs:eu-central-1:{EXPECTED['account_id']}:[A-Za-z0-9_.-]+",
            str(config.get("external_orders_queue_arn", "")),
        ):
            errors.append("external Orders queue ARN is missing or malformed")

    privacy_flags = config.get("privacy_flags", {})
    if not isinstance(privacy_flags, Mapping):
        errors.append("privacy_flags must be an object")
    else:
        for flag in PRIVACY_FLAGS:
            value = privacy_flags.get(flag, False)
            if value is True or str(value).strip().lower() == "true":
                errors.append(f"privacy execution flag must remain false: {flag}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RIS-DEV2 bootstrap config offline")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"BOOTSTRAP PREFLIGHT BLOCKED: {exc}")
        return 2
    errors = validate_bootstrap_config(config)
    if errors:
        print("BOOTSTRAP PREFLIGHT BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("BOOTSTRAP PREFLIGHT PASS: configuration contract only; AWS not queried")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
