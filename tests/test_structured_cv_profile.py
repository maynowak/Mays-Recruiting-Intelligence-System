"""Local contract/repository tests for structured CV profiles.

No AWS account is used. DynamoDB is provided by moto for the GSI/query
behaviour; the transaction call is simulated explicitly because the installed
moto version cannot execute DynamoDB transactions with this table shape.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import boto3
    from boto3.dynamodb.types import TypeDeserializer
    from moto import mock_aws
except ImportError:  # pragma: no cover
    boto3 = None
    TypeDeserializer = None
    mock_aws = None

from jobsearch.structured_cv_profile import (
    MAX_PROFILES_PER_OWNER,
    StructuredCvCapacity,
    StructuredCvConflict,
    StructuredCvError,
    StructuredCvNotFound,
    StructuredCvProfileRepository,
    owner_key,
    validate_create_body,
)

CONTEXT = {
    "userId": "user-synthetic-1",
    "tenantId": "tenant-synthetic-1",
    "partnerApplicationId": "partner-synthetic-1",
    "issuer": "issuer-synthetic-1",
}


def _body(name: str = "Synthetic CV", **extra):
    body = {
        "name": name,
        "template": "classic",
        "cvData": {
            "schemaVersion": 1,
            "personal": {"fullName": "Synthetic Person", "email": "", "phone": "", "location": ""},
            "profile": {"headline": "", "summary": ""},
            "experience": [],
            "education": [],
            "skills": [],
            "projects": [],
            "certificates": [],
            "languages": [],
            "links": [],
        },
    }
    body.update(extra)
    return body


def _review(count: int = 44):
    items = []
    for index in range(count):
        items.append({
            "id": f"item-{index}",
            "index": index,
            "text": f"synthetic {index}",
            "original": f"synthetic {index}",
            "edited": False,
            "target": "skills",
            "status": "accepted" if index % 2 else "pending",
            "applied": bool(index % 2),
            "page": 1,
            "sectionHeading": "Kenntnisse",
            "reason": "ambiguous",
            "suggestedTarget": "skills",
        })
    return {
        "schemaVersion": 1,
        "sourceName": "synthetic.pdf",
        "pageCount": 1,
        "pendingAcknowledged": True,
        "selectedSections": ["skills"],
        "skills": {"total": count, "selected": 0, "unselected": count, "limited": False},
        "items": items,
        "total": count,
        "pending": sum(1 for item in items if item["status"] == "pending"),
        "accepted": sum(1 for item in items if item["status"] == "accepted"),
        "ignored": 0,
    }


class _TransactionCanceledException(Exception):
    pass


_TransactionCanceledException.__name__ = "TransactionCanceledException"


class _FakeTransactions:
    """Apply the small transaction subset used by the repository."""

    def __init__(self, client):
        self.client = client
        self.calls = 0
        self.deserializer = TypeDeserializer()

    def _raw(self, value):
        if isinstance(value, dict) and any(k in value for k in ("S", "N", "BOOL", "M", "L", "NULL", "B")):
            return self.deserializer.deserialize(value)
        return value

    def _get(self, resource_id):
        return self.client.get_item(TableName="partner-profiles-test",
                                    Key={"resourceId": resource_id},
                                    ConsistentRead=True).get("Item")

    def _fail(self, index=0, count=None, kind="condition"):
        reasons = [{"Code": "None"} for _ in range(count or index + 1)]
        reasons[index] = {"Code": "ConditionalCheckFailed", "Message": kind}
        exc = _TransactionCanceledException("TransactionCanceled: simulated condition failure")
        exc.response = {"CancellationReasons": reasons}
        raise exc

    def _check_condition(self, condition, existing, values=None, names=None, index=0, count=None):
        if not condition:
            return
        if not existing:
            self._fail(index, count, "missing")
        values = values or {}
        names = names or {}
        expression = condition
        for alias, real in names.items():
            expression = expression.replace(alias, real)
        if "ownerKey = :owner" in expression and existing.get("ownerKey") != self._raw(values.get(":owner")):
            self._fail(index, count, "owner")
        if "#version = :expected" in expression or "version = :expected" in expression:
            expected = self._raw(values.get(":expected"))
            if existing.get("version") != expected:
                self._fail(index, count, "version")

    def transact_write_items(self, TransactItems):
        self.calls += 1
        count = len(TransactItems)
        for index, action in enumerate(TransactItems):
            if "Put" in action:
                raw = action["Put"]["Item"]
                resource_id = self._raw(raw["resourceId"])
                existing = self._get(resource_id)
                condition = action["Put"].get("ConditionExpression", "")
                if condition and existing:
                    values = action["Put"].get("ExpressionAttributeValues", {})
                    now = self._raw(values.get(":now")) if values.get(":now") else None
                    expires = existing.get("expiresAt")
                    if not (now and expires and int(expires) < int(now)):
                        self._fail(index, count, "idempotency")
            elif "Update" in action:
                update = action["Update"]
                resource_id = self._raw(update["Key"]["resourceId"])
                existing = self._get(resource_id)
                current = int((existing or {}).get("count") or 0)
                expression = update.get("UpdateExpression", "")
                if "if_not_exists" in expression and current >= MAX_PROFILES_PER_OWNER:
                    self._fail(index, count, "capacity")
                if " - :one" in expression and current <= 0:
                    self._fail(index, count, "capacity-counter")
            elif "Delete" in action:
                delete = action["Delete"]
                resource_id = self._raw(delete["Key"]["resourceId"])
                existing = self._get(resource_id)
                self._check_condition(
                    delete.get("ConditionExpression", ""), existing,
                    delete.get("ExpressionAttributeValues", {}),
                    delete.get("ExpressionAttributeNames", {}), index, count)
        for action in TransactItems:
            if "Put" in action:
                item = {key: self._raw(value) for key, value in action["Put"]["Item"].items()}
                self.client.put_item(TableName="partner-profiles-test", Item=item)
            elif "Update" in action:
                update = action["Update"]
                resource_id = self._raw(update["Key"]["resourceId"])
                existing = self._get(resource_id)
                current = int((existing or {}).get("count") or 0)
                values = update["ExpressionAttributeValues"]
                delta = -1 if " - :one" in update.get("UpdateExpression", "") else 1
                self.client.put_item(TableName="partner-profiles-test", Item={
                    "resourceId": resource_id,
                    "count": current + delta,
                    "updatedAt": self._raw(values[":now"]),
                })
            elif "Delete" in action:
                resource_id = self._raw(action["Delete"]["Key"]["resourceId"])
                self.client.delete_item(TableName="partner-profiles-test",
                                        Key={"resourceId": resource_id})
        return {}


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class StructuredCvRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.aws = mock_aws()
        self.aws.start()
        self.dynamodb = boto3.resource("dynamodb", region_name="eu-central-1")
        self.dynamodb.create_table(
            TableName="partner-profiles-test",
            KeySchema=[{"AttributeName": "resourceId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "resourceId", "AttributeType": "S"},
                {"AttributeName": "ownerKey", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "resourceType", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "gsi-structured-owner",
                    "KeySchema": [
                        {"AttributeName": "ownerKey", "KeyType": "HASH"},
                        {"AttributeName": "resourceId", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "gsi-user",
                    "KeySchema": [
                        {"AttributeName": "userId", "KeyType": "HASH"},
                        {"AttributeName": "resourceType", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        )
        self.repo = StructuredCvProfileRepository("partner-profiles-test", self.dynamodb)
        self.repo.client.transact_write_items = _FakeTransactions(self.repo.client).transact_write_items

    def tearDown(self):
        self.aws.stop()

    def test_create_get_update_export_delete(self):
        profile = self.repo.create(_body(), CONTEXT, idempotency_key="idem-" + "a" * 20)
        self.assertTrue(profile["profileId"].startswith("cvp-"))
        self.assertEqual(profile["version"], 1)
        self.assertEqual(self.repo.get(profile["profileId"], CONTEXT)["name"], "Synthetic CV")

        updated = self.repo.update(profile["profileId"], {"name": "Updated"}, CONTEXT, expected_version=1)
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["name"], "Updated")
        self.assertEqual(self.repo.export(profile["profileId"], CONTEXT)["profile"]["version"], 2)

        self.repo.delete(profile["profileId"], CONTEXT, expected_version=2)
        with self.assertRaises(StructuredCvNotFound):
            self.repo.get(profile["profileId"], CONTEXT)

    def test_idempotency_replay_and_conflict(self):
        key = "idem-" + "b" * 20
        first = self.repo.create(_body("One"), CONTEXT, idempotency_key=key)
        replay = self.repo.create(_body("One"), CONTEXT, idempotency_key=key)
        self.assertEqual(first["profileId"], replay["profileId"])
        with self.assertRaises(StructuredCvConflict):
            self.repo.create(_body("Different"), CONTEXT, idempotency_key=key)

    def test_version_conflict_and_missing_precondition(self):
        profile = self.repo.create(_body(), CONTEXT, idempotency_key="idem-" + "c" * 20)
        with self.assertRaises(StructuredCvError) as missing:
            self.repo.update(profile["profileId"], {"name": "X"}, CONTEXT, expected_version=None)
        self.assertEqual(missing.exception.status, 428)
        self.repo.update(profile["profileId"], {"name": "X"}, CONTEXT, expected_version=1)
        with self.assertRaises(StructuredCvConflict):
            self.repo.update(profile["profileId"], {"name": "Y"}, CONTEXT, expected_version=1)

    def test_owner_isolation_across_all_identity_fields(self):
        profile = self.repo.create(_body(), CONTEXT, idempotency_key="idem-" + "d" * 20)
        for field in ("userId", "tenantId", "partnerApplicationId", "issuer"):
            foreign = dict(CONTEXT)
            foreign[field] = "foreign"
            with self.assertRaises(StructuredCvNotFound):
                self.repo.get(profile["profileId"], foreign)
            self.assertEqual(self.repo.list(foreign)[0], [])

    def test_list_uses_dedicated_owner_index_and_paginates(self):
        for index in range(3):
            self.repo.create(_body(f"CV {index}"), CONTEXT,
                             idempotency_key=f"idem-{index}-" + "e" * 20)
        items, cursor = self.repo.list(CONTEXT, limit=2)
        self.assertEqual(len(items), 2)
        self.assertIsNotNone(cursor)
        second, next_cursor = self.repo.list(CONTEXT, limit=2, cursor=cursor)
        self.assertEqual(len(second), 1)
        self.assertIsNone(next_cursor)
        self.assertEqual({item["name"] for item in items + second},
                         {"CV 0", "CV 1", "CV 2"})

    def test_capacity_fails_closed_after_twenty(self):
        for index in range(MAX_PROFILES_PER_OWNER):
            self.repo.create(_body(f"CV {index}"), CONTEXT,
                             idempotency_key=f"cap-{index}-" + "f" * 20)
        with self.assertRaises(StructuredCvCapacity):
            self.repo.create(_body("Over"), CONTEXT, idempotency_key="cap-over-" + "f" * 20)

    def test_delete_releases_capacity(self):
        profiles = []
        for index in range(MAX_PROFILES_PER_OWNER):
            profiles.append(self.repo.create(
                _body(f"CV {index}"), CONTEXT,
                idempotency_key=f"release-{index}-" + "j" * 20))
        self.repo.delete(profiles[0]["profileId"], CONTEXT)
        replacement = self.repo.create(_body("Replacement"), CONTEXT,
                                       idempotency_key="release-new-" + "j" * 20)
        self.assertTrue(replacement["profileId"].startswith("cvp-"))

    def test_account_erasure_across_partner_scopes(self):
        other = dict(CONTEXT, partnerApplicationId="partner-synthetic-2")
        first = self.repo.create(_body("One"), CONTEXT,
                                 idempotency_key="user-erase-1-" + "k" * 20)
        second = self.repo.create(_body("Two"), other,
                                  idempotency_key="user-erase-2-" + "k" * 20)
        self.assertEqual(self.repo.erase_for_user(CONTEXT["userId"], CONTEXT["tenantId"]), 2)
        with self.assertRaises(StructuredCvNotFound):
            self.repo.get(first["profileId"], CONTEXT)
        with self.assertRaises(StructuredCvNotFound):
            self.repo.get(second["profileId"], other)

    def test_injected_conditional_failure_maps_to_version_conflict(self):
        profile = self.repo.create(_body(), CONTEXT, idempotency_key="idem-" + "m" * 20)

        def conditional_failure(**_kwargs):
            raise RuntimeError("ConditionalCheckFailedException")

        self.repo.table.update_item = conditional_failure
        with self.assertRaises(StructuredCvConflict):
            self.repo.update(profile["profileId"], {"name": "Race"}, CONTEXT,
                             expected_version=1)

    def test_race_after_precheck_detects_newer_version(self):
        profile = self.repo.create(_body(), CONTEXT, idempotency_key="idem-" + "n" * 20)
        original = self.repo.table.update_item

        def raced_update(**kwargs):
            self.repo.table.update_item = original
            original(Key={"resourceId": profile["profileId"]},
                     UpdateExpression="SET #v = :v",
                     ExpressionAttributeNames={"#v": "version"},
                     ExpressionAttributeValues={":v": 2})
            raise RuntimeError("ConditionalCheckFailedException")

        self.repo.table.update_item = raced_update
        with self.assertRaises(StructuredCvConflict):
            self.repo.update(profile["profileId"], {"name": "Race"}, CONTEXT,
                             expected_version=1)

    def test_delete_race_returns_not_found_not_storage_unavailable(self):
        profile = self.repo.create(_body(), CONTEXT, idempotency_key="idem-" + "o" * 20)
        original = self.repo.client.transact_write_items

        def raced_transaction(TransactItems):
            self.repo.table.delete_item(Key={"resourceId": profile["profileId"]})
            return original(TransactItems)

        self.repo.client.transact_write_items = raced_transaction
        with self.assertRaises(StructuredCvNotFound):
            self.repo.delete(profile["profileId"], CONTEXT)

    def test_missing_counter_is_repaired_by_atomic_delete_retry(self):
        first = self.repo.create(_body("First"), CONTEXT,
                                 idempotency_key="idem-" + "p" * 20)
        self.repo.create(_body("Second"), CONTEXT,
                         idempotency_key="idem-" + "q" * 20)
        self.repo.table.delete_item(Key={
            "resourceId": "capacity#SCVP#" + owner_key(CONTEXT)})
        self.repo.delete(first["profileId"], CONTEXT)
        remaining = self.repo.list(CONTEXT)[0]
        self.assertEqual([item["name"] for item in remaining], ["Second"])
        counter = self.repo.table.get_item(Key={
            "resourceId": "capacity#SCVP#" + owner_key(CONTEXT)},
            ConsistentRead=True)["Item"]
        self.assertEqual(1, int(counter["count"]))

    def test_reconcile_capacity_repairs_stale_counter(self):
        self.repo.create(_body("Only"), CONTEXT, idempotency_key="idem-" + "t" * 20)
        counter_key = "capacity#SCVP#" + owner_key(CONTEXT)
        self.repo.table.put_item(Item={
            "resourceId": counter_key, "count": MAX_PROFILES_PER_OWNER,
            "updatedAt": "2026-11-13T00:00:00+00:00"})
        with self.assertRaises(StructuredCvCapacity):
            self.repo.create(_body("Blocked"), CONTEXT,
                             idempotency_key="idem-" + "u" * 20)
        self.assertEqual(1, self.repo.reconcile_capacity(CONTEXT))
        self.repo.create(_body("Allowed"), CONTEXT,
                         idempotency_key="idem-" + "v" * 20)
        self.assertEqual(2, len(self.repo.list(CONTEXT)[0]))

    def test_repeated_delete_is_not_found_without_ownership_leak(self):
        profile = self.repo.create(_body(), CONTEXT, idempotency_key="idem-" + "r" * 20)
        self.repo.delete(profile["profileId"], CONTEXT)
        with self.assertRaises(StructuredCvNotFound):
            self.repo.delete(profile["profileId"], CONTEXT)
        foreign = dict(CONTEXT, userId="foreign")
        with self.assertRaises(StructuredCvNotFound):
            self.repo.delete("cvp-does-not-exist", foreign)

    def test_account_erasure_resumes_after_partial_failure(self):
        for index in range(2):
            self.repo.create(_body(f"Resume {index}"), CONTEXT,
                             idempotency_key=f"resume-{index}-" + "s" * 20)
        original = self.repo.delete
        failed = []

        def flaky(profile_id, ctx, *, expected_version=None):
            if not failed:
                failed.append(profile_id)
                raise StructuredCvError("STORAGE_UNAVAILABLE", "synthetic", 503)
            return original(profile_id, ctx, expected_version=expected_version)

        self.repo.delete = flaky
        with self.assertRaises(StructuredCvError):
            self.repo.erase_for_user(CONTEXT["userId"], CONTEXT["tenantId"])
        self.repo.delete = original
        self.assertEqual(2, self.repo.erase_for_user(
            CONTEXT["userId"], CONTEXT["tenantId"]))
        self.assertEqual([], self.repo.list(CONTEXT)[0])

    def test_durable_review_preserves_applied_and_44_items(self):
        review = _review(44)
        profile = self.repo.create(_body(importReview=review), CONTEXT,
                                   idempotency_key="idem-" + "g" * 20)
        stored = self.repo.get(profile["profileId"], CONTEXT)
        self.assertEqual(len(stored["importReview"]["items"]), 44)
        self.assertFalse(stored["importReview"]["items"][0]["applied"])
        self.assertTrue(stored["importReview"]["items"][1]["applied"])

    def test_count_only_or_pending_review_is_rejected(self):
        bad = _review(2)
        bad["items"] = []
        bad["total"] = 2
        bad["pending"] = 0
        bad["accepted"] = 2
        with self.assertRaises(StructuredCvError):
            validate_create_body(_body(importReview=bad))

    def test_unknown_schema_version_and_unknown_fields_are_rejected(self):
        body = _body()
        body["cvData"]["schemaVersion"] = 2
        with self.assertRaises(StructuredCvError):
            validate_create_body(body)
        body = _body()
        body["unexpected"] = True
        with self.assertRaises(StructuredCvError):
            validate_create_body(body)

    def test_101_skills_are_rejected(self):
        body = _body()
        body["cvData"]["skills"] = [f"skill-{index}" for index in range(101)]
        with self.assertRaises(StructuredCvError):
            validate_create_body(body)

    def test_invalid_template_and_oversized_payload_are_rejected(self):
        with self.assertRaises(StructuredCvError):
            validate_create_body({**_body(), "template": "unknown"})
        body = _body()
        body["cvData"]["profile"]["summary"] = "x" * 300001
        with self.assertRaises(StructuredCvError):
            validate_create_body(body)

    def test_delete_then_export_is_not_found(self):
        profile = self.repo.create(_body(), CONTEXT, idempotency_key="idem-" + "h" * 20)
        self.repo.delete(profile["profileId"], CONTEXT)
        with self.assertRaises(StructuredCvNotFound):
            self.repo.export(profile["profileId"], CONTEXT)

    def test_erase_all_is_owner_scoped_and_idempotent(self):
        for index in range(2):
            self.repo.create(_body(f"Erase {index}"), CONTEXT,
                             idempotency_key=f"erase-{index}-" + "i" * 20)
        self.assertEqual(self.repo.erase_all(CONTEXT), 2)
        self.assertEqual(self.repo.erase_all(CONTEXT), 0)
        self.assertEqual(self.repo.list(CONTEXT)[0], [])


if __name__ == "__main__":
    unittest.main()
