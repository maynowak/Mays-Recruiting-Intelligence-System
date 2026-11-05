from dataclasses import replace

import pytest

from agents.ecosystem.privacy_deletion_ledger import (
    EXPECTED_ABSENT, DeletionLedgerError, LedgerScope, LocalDeletionLedger,
)
from agents.ecosystem.privacy_recovery_contract import (
    PHASES, RecoveryCheckpointV1, RecoveryContractError, RecoveryPlanV1,
)
from agents.ecosystem.privacy_recovery_repository import LocalRecoveryRepository


NOW = "2026-11-04T00:00:00+00:00"
SCOPE = LedgerScope("user-a", "tenant-a", "partner-a", "issuer-a")


def plan():
    return RecoveryPlanV1(
        recovery_id="recovery-1", source_snapshot_ref="snapshot-1",
        restore_point=NOW, deletion_ledger_ref="ledger-1",
        created_at=NOW, updated_at=NOW)


def test_ledger_is_idempotent_and_does_not_store_raw_reference():
    ledger = LocalDeletionLedger()
    first = ledger.capture(operation_id="op-1", scope=SCOPE,
                           resource_type="CV_DOCUMENT", resource_ref="opaque-cv-1")
    second = ledger.capture(operation_id="op-1", scope=SCOPE,
                            resource_type="CV_DOCUMENT", resource_ref="opaque-cv-1")
    assert first == second
    snapshot = ledger.snapshot()
    assert "opaque-cv-1" not in repr(snapshot)
    assert len(snapshot) == 1


def test_ledger_rejects_foreign_scope_and_unknown_resource():
    ledger = LocalDeletionLedger()
    foreign = replace(SCOPE, tenant_id="tenant-b")
    ledger.capture(operation_id="op-1", scope=SCOPE,
                   resource_type="USER_PROFILE", resource_ref="profile-1")
    result = ledger.reconcile_restore(
        operation_id="op-1", scope=foreign, restored_resources=[])
    assert result.status == "BLOCKED"
    assert result.error_code == "MISSING_LEDGER_EVIDENCE"
    with pytest.raises(DeletionLedgerError, match="UNKNOWN_RESOURCE_TYPE"):
        ledger.capture(operation_id="op-1", scope=SCOPE,
                       resource_type="SECRET", resource_ref="x")
    with pytest.raises(DeletionLedgerError, match="LEDGER_CONFLICT"):
        ledger.capture(operation_id="op-1", scope=SCOPE,
                       resource_type="USER_PROFILE", resource_ref="different-profile")


def test_restore_of_erased_resource_requires_reconciliation_without_mutation():
    ledger = LocalDeletionLedger()
    entry = ledger.mark_erasure_result(
        operation_id="op-1", scope=SCOPE, resource_type="USER_PROFILE",
        resource_ref="profile-1", complete=True)
    assert entry.state == EXPECTED_ABSENT
    result = ledger.reconcile_restore(
        operation_id="op-1", scope=SCOPE,
        restored_resources=[{"tenantId": "tenant-a", "userId": "user-a",
                            "partnerApplicationId": "partner-a", "issuer": "issuer-a",
                            "resourceType": "USER_PROFILE", "resourceRef": "profile-1"}])
    assert result.status == "RECONCILIATION_REQUIRED"
    assert result.error_code == "RESTORED_ERASED_RESOURCE"
    assert ledger.snapshot()[0]["state"] == EXPECTED_ABSENT


def test_recovery_checkpoint_is_conditional_and_promotion_is_fail_closed():
    repo = LocalRecoveryRepository()
    current = repo.create(plan())
    current = repo.complete_phase("recovery-1", "RESTORE_STAGING",
                                  now=NOW, expected_version=current.version)
    with pytest.raises(RecoveryContractError, match="STALE_RECOVERY_VERSION"):
        repo.complete_phase("recovery-1", "REPLAY_DELETIONS",
                            now=NOW, expected_version=1)
    assert not current.promotion_eligible
    with pytest.raises(RecoveryContractError, match="INVALID_PHASE_ORDER"):
        repo.complete_phase("recovery-1", "PROMOTION_GATE",
                            now=NOW, expected_version=current.version)
    with pytest.raises(RecoveryContractError, match="PROMOTION_REQUIRES_COMPLETED_PHASES"):
        RecoveryPlanV1(**{**plan().__dict__, "promotion_eligible": True})


def test_recovery_rejects_sensitive_snapshot_reference():
    with pytest.raises(RecoveryContractError, match="SENSITIVE_SOURCE_SNAPSHOT_REF"):
        RecoveryPlanV1(recovery_id="recovery-1", source_snapshot_ref="s3://bucket",
                       restore_point=NOW, deletion_ledger_ref="ledger-1",
                       created_at=NOW, updated_at=NOW)


def test_recovery_rejects_unknown_schema_version():
    with pytest.raises(RecoveryContractError, match="UNSUPPORTED_SCHEMA_VERSION"):
        RecoveryPlanV1(recovery_id="recovery-1", source_snapshot_ref="snapshot-1",
                       restore_point=NOW, deletion_ledger_ref="ledger-1",
                       created_at=NOW, updated_at=NOW, schema_version=2)


def test_recovery_rejects_non_utc_restore_point_and_enforces_phase_order():
    with pytest.raises(RecoveryContractError, match="INVALID_RESTORE_POINT"):
        RecoveryPlanV1(recovery_id="recovery-1", source_snapshot_ref="snapshot-1",
                       restore_point="not-a-time", deletion_ledger_ref="ledger-1",
                       created_at=NOW, updated_at=NOW)
