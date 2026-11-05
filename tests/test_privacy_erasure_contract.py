"""R08-C0A contract tests; no AWS or erasure execution."""

import pytest

from agents.ecosystem.privacy_erasure_contract import (
    CHECKPOINT_IN_PROGRESS,
    ErasureCheckpointV1,
    ErasureContractError,
    ErasureProgressV1,
    OPERATION_SCOPE_CV,
    STATUS_COMPLETED,
    STATUS_PARTIAL,
    STATUS_RUNNING,
    ERASURE_CATEGORIES,
    new_operation,
)


NOW = "2026-11-01T00:00:00+00:00"
CTX = {
    "operation_id": "erase-op-1",
    "idempotency_key": "erase-key-1",
    "user_id": "user-1",
    "tenant_id": "tenant-1",
    "partner_application_id": "partner-1",
    "issuer": "issuer-1",
    "scope": "USER",
    "now": NOW,
}


def operation(**overrides):
    values = dict(CTX)
    values.update(overrides)
    return new_operation(**values)


def test_operation_is_versioned_scoped_and_dynamodb_projection_is_logical_only():
    item = operation().to_dynamodb_item()
    assert item["resourceType"] == "ErasureOperation"
    assert item["schemaVersion"] == 1
    assert item["scopeKey"] == "tenant-1#user-1#partner-1#issuer-1"
    assert item["idempotencyLookup"] == "tenant-1#erase-key-1"
    assert "s3Key" not in item
    assert "content" not in item
    assert operation(issuer="https://issuer.example/tenant-a").issuer.startswith("https://")


def test_idempotency_and_scope_are_required_and_cv_scope_needs_cv_id():
    with pytest.raises(ErasureContractError):
        operation(idempotency_key="")
    with pytest.raises(ErasureContractError):
        operation(scope=OPERATION_SCOPE_CV)
    with pytest.raises(ErasureContractError):
        operation(scope="OTHER")
    with pytest.raises(ErasureContractError):
        operation(tenant_id="tenant-1", user_id="user-1", issuer="issuer-1",
                  partner_application_id="partner-1", scope="USER",
                  operation_id="op", idempotency_key="key", now=NOW,
                  cv_id="cv-1")


def test_checkpoint_replay_uses_opaque_refs_and_rejects_storage_secrets():
    checkpoint = ErasureCheckpointV1(
        phase="cvDocuments", state=CHECKPOINT_IN_PROGRESS,
        cursor_ref="checkpoint-ref-1", last_resource_ref="cv-1",
        attempt=2, updated_at=NOW)
    assert checkpoint.to_dict()["cursorRef"] == "checkpoint-ref-1"
    with pytest.raises(ErasureContractError):
        ErasureCheckpointV1(phase="s3", cursor_ref="s3://bucket/key")


def test_status_transitions_are_monotonic_and_completion_requires_all_progress():
    running = operation().transition(STATUS_RUNNING, now=NOW)
    partial = running.transition(STATUS_PARTIAL, now=NOW,
                                 error_code="S3_UNAVAILABLE")
    resumed = partial.transition(STATUS_RUNNING, now=NOW)
    assert resumed.status == STATUS_RUNNING
    assert resumed.retry_count == 1
    with pytest.raises(ErasureContractError):
        resumed.transition(STATUS_COMPLETED, now=NOW)
    with pytest.raises(ErasureContractError):
        running.transition(STATUS_PARTIAL, now=NOW)
    with pytest.raises(ErasureContractError):
        operation().transition(STATUS_COMPLETED, now=NOW)


def test_completed_is_terminal_and_progress_errors_require_resume():
    completed_progress = {
        "userProfile": ErasureProgressV1(status="COMPLETED", affected=1),
    }
    current = operation(progress=completed_progress).transition(
        STATUS_RUNNING, now=NOW)
    with pytest.raises(ErasureContractError, match="every required category"):
        current.transition(STATUS_COMPLETED, now=NOW)
    complete_all = {category: ErasureProgressV1(status="COMPLETED")
                    for category in ERASURE_CATEGORIES}
    final = operation(progress=complete_all).transition(STATUS_RUNNING, now=NOW).transition(
        STATUS_COMPLETED, now=NOW)
    assert final.status == STATUS_COMPLETED
    with pytest.raises(ErasureContractError):
        final.transition(STATUS_RUNNING, now=NOW)
    with pytest.raises(ErasureContractError):
        ErasureProgressV1(status="PARTIAL")


def test_public_contract_rejects_sensitive_evidence_fields():
    with pytest.raises(ErasureContractError):
        ErasureProgressV1(status="FAILED", error_code="bad",
                          checkpoint=ErasureCheckpointV1(
                              phase="s3", cursor_ref="https://s3.example/key"))
