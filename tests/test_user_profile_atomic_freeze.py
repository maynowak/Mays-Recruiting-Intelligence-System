"""C0D atomic UserProfile/subject-guard transaction tests."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambda"))
import handler  # noqa: E402


CTX = {
    "userId": "user-1", "tenantId": "tenant-1",
    "partnerApplicationId": "partner-1", "issuer": "https://issuer.example",
    "email": "user@example.test",
}


class FakeClient:
    def __init__(self, *, fail_guard=False, fail_mutation=False):
        self.calls = []
        self.fail_guard = fail_guard
        self.fail_mutation = fail_mutation

    def transact_write_items(self, *, TransactItems):
        self.calls.append(TransactItems)
        if self.fail_guard or self.fail_mutation:
            reasons = [{"Code": "ConditionalCheckFailed" if self.fail_guard else "None"},
                       {"Code": "ConditionalCheckFailed" if self.fail_mutation else "None"}]
            exc = Exception("transaction cancelled")
            exc.response = {"CancellationReasons": reasons}
            raise exc


class FakeTable:
    name = "user-profile"

    def __init__(self, item=None):
        self.item = item or {
            "userId": "user-1", "tenantId": "tenant-1", "version": 1,
            "status": "active", "schemaVersion": 1,
        }

    def get_item(self, **_kwargs):
        return {"Item": dict(self.item)}


def _dynamodb(client):
    return SimpleNamespace(meta=SimpleNamespace(client=client))


def test_create_put_and_guard_are_one_transaction(monkeypatch):
    monkeypatch.setenv("ERASURE_WRITE_FREEZE_ENABLED", "true")
    monkeypatch.setenv("PARTNER_PROFILE_TABLE", "partner-profiles")
    client = FakeClient()
    table = FakeTable()
    monkeypatch.setattr(handler, "_get_dynamodb", lambda: _dynamodb(client))
    response = handler._provision_user_profile(
        table, CTX, {"firstName": "Ada"}, tenant_id="tenant-1",
        freeze_context=CTX)
    assert response["statusCode"] == 201
    assert len(client.calls) == 1
    assert "ConditionCheck" in client.calls[0][0]
    assert client.calls[0][0]["ConditionCheck"]["TableName"] == "partner-profiles"
    assert "Put" in client.calls[0][1]
    assert client.calls[0][1]["Put"]["TableName"] == "user-profile"


def test_patch_uses_same_guard_transaction_and_keeps_version_condition(monkeypatch):
    monkeypatch.setenv("ERASURE_WRITE_FREEZE_ENABLED", "true")
    monkeypatch.setenv("PARTNER_PROFILE_TABLE", "partner-profiles")
    client = FakeClient()
    table = FakeTable()
    monkeypatch.setattr(handler, "_get_dynamodb", lambda: _dynamodb(client))
    response = handler._update_user_profile(
        table, CTX, {"firstName": "Grace"}, expected_version=1,
        tenant_id="tenant-1", freeze_context=CTX)
    assert response["statusCode"] == 200
    action = client.calls[0][1]["Update"]
    assert action["TableName"] == "user-profile"
    assert ":expectedVersion" in action["ExpressionAttributeValues"]


def test_guard_conflict_fails_closed_and_does_not_fallback_to_plain_write(monkeypatch):
    monkeypatch.setenv("PARTNER_PROFILE_TABLE", "partner-profiles")
    client = FakeClient(fail_guard=True)
    monkeypatch.setattr(handler, "_get_dynamodb", lambda: _dynamodb(client))
    with pytest.raises(handler._WriteFreezeUnavailable):
        handler._user_profile_transact(
            "user-profile", CTX, {"Delete": {
                "Key": {"userId": {"S": "user-1"}},
                "ConditionExpression": "attribute_exists(userId)",
            }})
    assert len(client.calls) == 1


def test_context_mismatch_is_rejected_before_userprofile_mutation(monkeypatch):
    monkeypatch.setenv("ERASURE_WRITE_FREEZE_ENABLED", "true")
    monkeypatch.setattr(
        handler, "_partner_profile_context",
        lambda _event: ({**CTX, "tenantId": "other-tenant"}, None))
    with pytest.raises(handler._WriteFreezeUnavailable):
        handler._user_profile_freeze_context({}, CTX, "tenant-1")
