"""R08-C0E: scoped G5 authorization and fail-closed legacy boundary."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from agents.ecosystem.privacy_erasure import (
    ErasureExecutionUnavailable, PrivacyErasure)
from agents.ecosystem.privacy_erasure_contract import (
    ErasureOperationV1, STATUS_RUNNING)
from agents.ecosystem.privacy_erasure_repository import (
    ErasureOperationConflict, WriteFreezeRepository)


CTX = {
    "user_id": "user-1", "tenant_id": "tenant-1",
    "partner_application_id": "partner-1", "issuer": "https://issuer.example",
}
NOW = datetime.now(timezone.utc).isoformat()


def _operation(**overrides):
    values = dict(
        operation_id="op-1", idempotency_key="idem-1",
        user_id="user-1", tenant_id="tenant-1",
        partner_application_id="partner-1", issuer="https://issuer.example",
        scope="USER", status=STATUS_RUNNING, version=3,
        created_at=NOW, updated_at=NOW, started_at=NOW)
    values.update(overrides)
    return ErasureOperationV1(**values)


class _Client:
    def __init__(self, failure=False):
        self.calls = []
        self.failure = failure

    def transact_write_items(self, *, TransactItems):
        self.calls.append(TransactItems)
        if self.failure:
            exc = Exception("ConditionalCheckFailedException")
            raise exc


def _table(client):
    return SimpleNamespace(meta=SimpleNamespace(client=client))


def test_authorization_checks_operation_and_active_freeze_atomically():
    client = _Client()
    repo = WriteFreezeRepository(table=_table(client), table_name="profiles",
                                 enabled=True)
    context = repo.authorize_execution(
        _operation(), expected_operation_version=3,
        expected_freeze_version=2, context=CTX,
        operation_table=_table(client), operation_table_name="operations")
    assert context.operation_id == "op-1"
    assert context.operation_version == 3
    assert len(client.calls) == 1
    assert len(client.calls[0]) == 2
    assert all("ConditionCheck" in item for item in client.calls[0])


def test_foreign_or_stale_execution_fails_closed_before_transaction():
    client = _Client()
    repo = WriteFreezeRepository(table=_table(client), table_name="profiles",
                                 enabled=True)
    with pytest.raises(ErasureOperationConflict):
        repo.authorize_execution(
            _operation(), expected_operation_version=2,
            expected_freeze_version=2, context={**CTX, "tenant_id": "other"},
            operation_table=_table(client), operation_table_name="operations")
    assert client.calls == []


def test_authorization_condition_conflict_is_not_a_bypass():
    client = _Client(failure=True)
    repo = WriteFreezeRepository(table=_table(client), table_name="profiles",
                                 enabled=True)
    with pytest.raises(ErasureOperationConflict):
        repo.authorize_execution(
            _operation(), expected_operation_version=3,
            expected_freeze_version=2, context=CTX,
            operation_table=_table(client), operation_table_name="operations")
    assert len(client.calls) == 1


def test_legacy_g5_engine_refuses_mutations_while_freeze_is_enabled(monkeypatch):
    monkeypatch.setenv("ERASURE_WRITE_FREEZE_ENABLED", "true")
    calls = []
    erasure = PrivacyErasure(document_deleter=lambda _user: calls.append("s3"))
    with pytest.raises(ErasureExecutionUnavailable):
        erasure.erase("user-1", "tenant-1")
    assert calls == []
