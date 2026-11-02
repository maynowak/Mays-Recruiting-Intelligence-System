"""R08-C0F-2C durable upload-ticket ledger tests."""

from datetime import datetime, timezone

import pytest

from agents.ecosystem.privacy_upload_ticket import (
    STATUS_COMPLETED, STATUS_ISSUED, UploadTicketConflict,
    UploadTicketLedgerRepository, UploadTicketLedgerV1)


NOW = datetime.now(timezone.utc).isoformat()


def ticket(**changes):
    values = dict(
        ticket_id="ticket-doc-1", cv_id="cv-1", document_id="doc-1",
        user_id="user-1", tenant_id="tenant-1",
        partner_application_id="partner-1", issuer="https://issuer.example",
        issued_at=NOW, expires_at="2099-01-01T00:00:00+00:00")
    values.update(changes)
    return UploadTicketLedgerV1(**values)


class Client:
    def __init__(self, fail=False):
        self.calls = []
        self.items = {}
        self.fail = fail

    def transact_write_items(self, *, TransactItems):
        self.calls.append(TransactItems)
        if self.fail:
            raise Exception("ConditionalCheckFailedException")
        for action in TransactItems:
            if "Put" in action:
                put = action["Put"]
                resource = put["Item"]["resourceId"]["S"]
                if (put.get("ConditionExpression") ==
                        "attribute_not_exists(resourceId)") \
                        and resource in self.items:
                    raise Exception("ConditionalCheckFailedException")
                self.items[resource] = put["Item"]
            if "Update" in action:
                update = action["Update"]
                resource = update["Key"]["resourceId"]["S"]
                item = self.items.setdefault(resource, {})
                expected = update["ExpressionAttributeValues"][":oldv"]["N"]
                if item.get("version", {}).get("N") not in (None, expected):
                    raise Exception("ConditionalCheckFailedException")
                item["resourceType"] = {"S": "UploadTicketLedgerV1"}
                item["ticketId"] = {"S": resource}
                item["cvId"] = {"S": "cv-1"}
                item["documentId"] = {"S": "doc-1"}
                item["userId"] = {"S": "user-1"}
                item["tenantId"] = {"S": "tenant-1"}
                item["partnerApplicationId"] = {"S": "partner-1"}
                item["issuer"] = {"S": "https://issuer.example"}
                item["issuedAt"] = {"S": NOW}
                item["expiresAt"] = {"S": "2099-01-01T00:00:00+00:00"}
                item["status"] = {"S": "COMPLETED"}
                item["version"] = {"N": "2"}

    def get_item(self, *, TableName, Key, ConsistentRead):
        return {"Item": self.items.get(Key["resourceId"]["S"])}


def repo(client, enabled=True):
    return UploadTicketLedgerRepository(
        client=client, table_name="ticket-ledger",
        guard_table_name="profiles", enabled=enabled)


def test_registration_is_atomic_and_stores_no_secret_material():
    client = Client()
    stored = repo(client).register(ticket())
    assert stored.status == STATUS_ISSUED
    assert len(client.calls) == 1
    actions = client.calls[0]
    assert sum("ConditionCheck" in action for action in actions) == 2
    assert sum("Put" in action for action in actions) == 2
    rendered = str(client.items).lower()
    assert "presigned" not in rendered
    assert "uploadurl" not in rendered
    assert "s3://" not in rendered
    assert "credential" not in rendered


def test_duplicate_registration_replays_same_ticket():
    client = Client()
    ledger = repo(client)
    first = ledger.register(ticket())
    replay = ledger.register(ticket())
    assert replay.ticket_id == first.ticket_id
    assert len(client.calls) == 2


def test_guard_or_registration_conflict_fails_closed():
    with pytest.raises(Exception):
        repo(Client(fail=True)).register(ticket())
    ledger = repo(Client())
    conflict_client = Client()
    conflict_ledger = repo(conflict_client)
    conflict_ledger.register(ticket())
    with pytest.raises(UploadTicketConflict):
        conflict_ledger.register(ticket(ticket_id="ticket-other"))


def test_completion_is_versioned_and_rechecks_guards():
    client = Client()
    ledger = repo(client)
    current = ledger.register(ticket())
    completed = ledger.transition(current, status=STATUS_COMPLETED,
                                  expected_version=1)
    assert completed.status == STATUS_COMPLETED
    assert completed.version == 2
    assert len(client.calls[-1]) == 3
    with pytest.raises(UploadTicketConflict):
        ledger.transition(current, status=STATUS_COMPLETED, expected_version=1)
