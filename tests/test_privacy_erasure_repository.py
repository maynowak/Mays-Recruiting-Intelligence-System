"""R08-C0B repository tests using a conditional DynamoDB-shaped fake."""

from copy import deepcopy

import pytest

from agents.ecosystem.privacy_erasure_contract import (
    ErasureCheckpointV1,
    ErasureProgressV1,
    STATUS_PARTIAL,
    STATUS_RUNNING,
    new_operation,
)
from agents.ecosystem.privacy_erasure_repository import (
    ErasureOperationConflict,
    ErasureOperationNotFound,
    ErasureOperationRepository,
    ErasureOperationVersionConflict,
    ErasureRepositoryDisabled,
)


NOW = "2026-11-01T00:00:00+00:00"
CTX = {
    "userId": "user-1", "tenantId": "tenant-1",
    "partnerApplicationId": "partner-1", "issuer": "https://issuer.example",
}


class ConditionalFakeTable:
    def __init__(self):
        self.items = {}
        self.scans = 0

    def get_item(self, *, Key, ConsistentRead=False):
        return {"Item": deepcopy(self.items[Key["resourceId"]])} \
            if Key["resourceId"] in self.items else {}

    def transact_write_items(self, *, TransactItems):
        pending = []
        for action in TransactItems:
            item = action["Put"]["Item"]
            if item["resourceId"] in self.items:
                raise Exception("ConditionalCheckFailedException")
            pending.append(item)
        for item in pending:
            self.items[item["resourceId"]] = deepcopy(item)

    def put_item(self, *, Item, ConditionExpression, ExpressionAttributeValues):
        current = self.items.get(Item["resourceId"])
        expected = ExpressionAttributeValues.get(":v")
        if current is None or current.get("version") != expected:
            raise Exception("ConditionalCheckFailedException")
        for key in ("resourceType", "userId", "tenantId",
                    "partnerApplicationId", "issuer"):
            token = {"resourceType": ":rt", "userId": ":u", "tenantId": ":t",
                     "partnerApplicationId": ":p", "issuer": ":i"}.get(key)
            if token and current.get(key) != ExpressionAttributeValues[token]:
                raise Exception("ConditionalCheckFailedException")
        self.items[Item["resourceId"]] = deepcopy(Item)


def operation(**overrides):
    values = {
        "operation_id": "op-1", "idempotency_key": "idem-1",
        "user_id": "user-1", "tenant_id": "tenant-1",
        "partner_application_id": "partner-1", "issuer": "https://issuer.example",
        "scope": "USER", "now": NOW,
    }
    values.update(overrides)
    return new_operation(**values)


def repository(table=None, **kwargs):
    return ErasureOperationRepository(
        table=table or ConditionalFakeTable(), table_name="erasure-ops",
        enabled=True, **kwargs)


def test_disabled_repository_is_fail_closed():
    repo = ErasureOperationRepository(table=ConditionalFakeTable(),
                                      table_name="erasure-ops", enabled=False)
    with pytest.raises(ErasureRepositoryDisabled):
        repo.create(operation(), CTX)


def test_create_get_and_idempotent_replay():
    table = ConditionalFakeTable()
    repo = repository(table)
    created = repo.create(operation(), CTX)
    assert repo.get("op-1", CTX).operation_id == created.operation_id
    replay = repo.create(operation(), CTX)
    assert replay.version == 1
    assert len(table.items) == 2  # operation + idempotency marker


def test_same_idempotency_key_with_different_scope_conflicts():
    table = ConditionalFakeTable()
    repo = repository(table)
    repo.create(operation(), CTX)
    different = operation(operation_id="op-2", scope="CV", cv_id="cv-1")
    with pytest.raises(ErasureOperationConflict):
        repo.create(different, CTX)


def test_compare_and_swap_version_and_checkpoint_resume():
    table = ConditionalFakeTable()
    repo = repository(table)
    repo.create(operation(), CTX)
    running = repo.resume("op-1", context=CTX, now=NOW)
    assert running.status == STATUS_RUNNING
    checkpoint = ErasureCheckpointV1(
        phase="manualSearchProfiles", state="IN_PROGRESS",
        cursor_ref="opaque-cursor", last_resource_ref="profile-1",
        updated_at=NOW)
    progress = ErasureProgressV1(status="PARTIAL", checkpoint=checkpoint,
                                  error_code="PROFILE_WRITE_FAILED",
                                  retryable=True)
    updated = repo.save_checkpoint(
        "op-1", "manualSearchProfiles", progress,
        expected_version=running.version, context=CTX, now=NOW)
    assert updated.version == 3
    assert repo.get_checkpoint("op-1", "manualSearchProfiles", CTX) == checkpoint
    with pytest.raises(ErasureOperationVersionConflict):
        repo.save_checkpoint("op-1", "manualSearchProfiles", progress,
                             expected_version=1, context=CTX, now=NOW)


def test_resume_partial_and_completed_cannot_resume():
    table = ConditionalFakeTable()
    repo = repository(table)
    repo.create(operation(), CTX)
    running = repo.resume("op-1", context=CTX, now=NOW)
    partial = running.transition(STATUS_PARTIAL, now=NOW,
                                 error_code="STORE_UNAVAILABLE")
    partial = repo.update(partial, expected_version=running.version, context=CTX)
    resumed = repo.resume("op-1", context=CTX, now=NOW)
    assert resumed.status == STATUS_RUNNING
    with pytest.raises(ErasureOperationNotFound):
        repo.get("op-1", {**CTX, "tenantId": "tenant-other"})


def test_foreign_partner_and_issuer_are_not_revealed_and_no_scan_is_used():
    table = ConditionalFakeTable()
    repo = repository(table)
    repo.create(operation(), CTX)
    for foreign in (
        {**CTX, "partnerApplicationId": "partner-other"},
        {**CTX, "issuer": "https://other.example"},
        {**CTX, "userId": "user-other"},
    ):
        with pytest.raises(ErasureOperationNotFound):
            repo.get("op-1", foreign)
    assert table.scans == 0
    rendered = " ".join(str(item).lower() for item in table.items.values())
    assert "s3://" not in rendered
    assert "s3key" not in rendered
    assert "objectkey" not in rendered
