"""Static guards for the RIS-DEV plan reconciliation.

Guards the minimal, state-compatible fixes:
- health/reader absolute artifact paths are ignored while source hashes remain;
- Mays-Orders worker boundary is passed explicitly from root;
- no global ignore or boundary weakening is introduced.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "terraform"


def read(rel: str) -> str:
    return (TF / rel).read_text(encoding="utf-8")


def test_health_and_reader_only_ignore_filename():
    health = read("modules/health_plane/main.tf")
    reader = read("modules/orders_reader/main.tf")
    assert health.count("lifecycle { ignore_changes = [filename] }") == 2
    assert "lifecycle { ignore_changes = [filename] }" in reader
    # Real code changes must still be detected for the reader.
    assert "source_code_hash = filebase64sha256(var.filename)" in reader
    # No broad ignore of source code or all attributes.
    assert "ignore_changes = all" not in health + reader


def test_orders_boundary_is_explicit_and_optional():
    root = read("variables.tf")
    main = read("main.tf")
    assert "variable \"mays_orders_lambda_execution_boundary\"" in root
    assert "default     = null" in root
    assert "lambda_execution_boundary = var.mays_orders_lambda_execution_boundary" in main
    # Must not hardcode the account-specific boundary in the repository.
    assert "Mays-Orders-Lambda-Execution-Boundary" not in root
    assert "Mays-Orders-Lambda-Execution-Boundary" not in main


def test_no_global_gate_changes_in_reconciliation():
    main = read("modules/lambda/main.tf")
    assert 'APPLICATION_CONSENT_ENFORCED  = var.application_consent_enforced ? "true" : "false"' in main
    assert 'CONSENT_NOTICE_STATE_ENFORCED = var.consent_notice_state_enforced ? "true" : "false"' in main
