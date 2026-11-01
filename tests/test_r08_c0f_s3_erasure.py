"""R08-C0F-1 fenced S3 phase tests; no real S3 calls."""

from datetime import datetime, timezone

import pytest

from agents.ecosystem.privacy_erasure_contract import (
    ErasureExecutionContextV1)
from agents.ecosystem.privacy_s3_erasure import (
    FencedS3Adapter, FencedS3ErasureOrchestrator, S3ErasureConflict,
    S3ErasurePhaseRepository, S3ErasureUnavailable, S3ErasureUnknownResult,
    S3VersionRef)


NOW = datetime.now(timezone.utc).isoformat()
CTX = ErasureExecutionContextV1(
    operation_id="op-1", user_id="user-1", tenant_id="tenant-1",
    partner_application_id="partner-1", issuer="https://issuer.example",
    scope="USER", operation_version=3, freeze_version=2)


class Client:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def transact_write_items(self, *, TransactItems):
        self.calls.append(TransactItems)
        if self.fail:
            raise Exception("ConditionalCheckFailedException")


class Adapter(FencedS3Adapter):
    supports_fencing = True

    def __init__(self, objects=None, fail_delete=False):
        self.objects = list(objects or [])
        self.deleted = []
        self.fail_delete = fail_delete
        self.inventories = 0

    def inventory(self, *, attempt_id, cursor_ref=None):
        self.inventories += 1
        if self.inventories == 1:
            return list(self.objects)
        return []

    def delete_version(self, *, attempt_id, object_ref):
        if self.fail_delete:
            raise TimeoutError("unknown S3 result")
        self.deleted.append((attempt_id, object_ref))


def repo(client, enabled=True):
    return S3ErasurePhaseRepository(
        client=client, phase_table_name="s3-phases",
        guard_table_name="profiles", operation_table_name="operations",
        enabled=enabled)


def test_fenced_run_handles_versions_delete_markers_and_reinventory():
    client = Client()
    adapter = Adapter([
        S3VersionRef("internal-key-1", "v1"),
        S3VersionRef("internal-key-1", "delete-marker", True),
    ])
    result = FencedS3ErasureOrchestrator(
        phases=repo(client), adapter=adapter, enabled=True).run(
            CTX, expected_version=0)
    assert result == {"complete": True, "phase": "COMPLETED", "remaining": 0}
    assert len(adapter.deleted) == 2
    assert all(len(items) == 3 for items in client.calls)
    assert all("ConditionCheck" in items[0] and "ConditionCheck" in items[1]
               for items in client.calls)


def test_stale_phase_or_guard_conflict_fails_closed():
    client = Client(fail=True)
    with pytest.raises(S3ErasureConflict):
        FencedS3ErasureOrchestrator(
            phases=repo(client), adapter=Adapter(), enabled=True).run(
                CTX, expected_version=0)


def test_fencing_capability_and_repository_are_disabled_by_default():
    with pytest.raises(S3ErasureUnavailable):
        FencedS3ErasureOrchestrator(
            phases=repo(Client(), enabled=False), adapter=Adapter()).run(
                CTX, expected_version=0)
    adapter = Adapter()
    adapter.supports_fencing = False
    with pytest.raises(S3ErasureUnavailable):
        FencedS3ErasureOrchestrator(
            phases=repo(Client()), adapter=adapter, enabled=True).run(
                CTX, expected_version=0)


def test_unknown_s3_result_never_becomes_completed():
    adapter = Adapter([S3VersionRef("internal-key", "v1")], fail_delete=True)
    with pytest.raises(S3ErasureUnknownResult):
        FencedS3ErasureOrchestrator(
            phases=repo(Client()), adapter=adapter, enabled=True).run(
                CTX, expected_version=0)


def test_inventory_pagination_is_fully_consumed():
    class Paged(Adapter):
        def inventory(self, *, attempt_id, cursor_ref=None):
            if self.inventories == 0:
                self.inventories += 1
                return ([S3VersionRef("internal-key", "v1")], "opaque-page-2")
            if self.inventories == 1:
                self.inventories += 1
                return ([S3VersionRef("internal-key", "v2", True)], None)
            return []

    adapter = Paged()
    result = FencedS3ErasureOrchestrator(
        phases=repo(Client()), adapter=adapter, enabled=True).run(
            CTX, expected_version=0)
    assert result["complete"] is True
    assert len(adapter.deleted) == 2


def test_public_checkpoint_has_no_s3_key_or_url():
    from agents.ecosystem.privacy_s3_erasure import S3ErasurePhaseV1
    phase = S3ErasurePhaseV1(
        operation_id="op-1", scope="USER", operation_version=3,
        freeze_version=2, attempt_id="attempt-1", phase="RETRY",
        cursor_ref="opaque-cursor", updated_at=NOW)
    rendered = str(phase.public_dict()).lower()
    assert "internal-key" not in rendered
    assert "presigned" not in rendered
    assert "version_id" not in rendered
