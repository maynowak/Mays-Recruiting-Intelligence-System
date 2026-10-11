"""Real tests for atomic Partner Registry uniqueness.

The fake DynamoDB client below models DynamoDB semantics faithfully enough to
prove concurrency safety:

  * primary key uniqueness per item
  * TransactWriteItems atomicity (all writes applied or none)
  * ConditionExpression attribute_not_exists(<pk>) evaluated against the
    existing item with that primary key
  * TransactionCancelledException on any failed condition
"""

import threading
import unittest

from agents.ecosystem.partner_registry import (
    CLIENT_RESERVATION_PREFIX,
    PartnerRegistryError,
    create_partner_application,
    deactivate_partner_application,
    list_partner_applications,
    resolve_partner_application,
)

TBL = "test-partner-applications"


class TransactionCancelled(Exception):
    """Mirrors botocore ClientError for TransactionCancelledException."""


class ConditionalCheckFailed(Exception):
    """Mirrors ConditionalCheckFailedException raised by a single Put."""


class FakeDynamoDB:
    """Minimal in-memory DynamoDB model with GSI gsi-client."""

    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()

    # -- helpers ---------------------------------------------------------
    def _pk(self, item):
        return item["applicationId"]["S"]

    def _get(self, pk):
        return self.items.get(pk)

    # -- API surface -----------------------------------------------------
    def transact_write_items(self, TransactItems):
        with self.lock:
            # Evaluate every condition first (DynamoDB validates the whole
            # transaction before applying anything).
            for entry in TransactItems:
                put = entry["Put"]
                pk = self._pk(put["Item"])
                cond = put.get("ConditionExpression")
                if cond == "attribute_not_exists(applicationId)":
                    if self._get(pk) is not None:
                        raise TransactionCancelled(
                            "Transaction cancelled: conditional check failed")
            # All conditions hold -> apply atomically under the same lock.
            for entry in TransactItems:
                put = entry["Put"]
                self.items[self._pk(put["Item"])] = dict(put["Item"])

    def put_item(self, TableName, Item, ConditionExpression=None):
        with self.lock:
            pk = self._pk(Item)
            if ConditionExpression == "attribute_not_exists(applicationId)":
                if self._get(pk) is not None:
                    raise ConditionalCheckFailed("conditional check failed")
            self.items[pk] = dict(Item)

    def query(self, TableName, IndexName, KeyConditionExpression,
              ExpressionAttributeValues, Limit=1, ConsistentRead=None):
        if ConsistentRead is None:
            raise AssertionError(
                "resolve_partner_application must request a strongly "
                "consistent read; revocation lag on the authorization hot "
                "path is not acceptable")
        with self.lock:
            cid = ExpressionAttributeValues[":cid"]["S"]
            hits = [it for it in self.items.values()
                    if it.get("cognitoClientId", {}).get("S") == cid]
        return {"Items": hits[:Limit]}

    def update_item(self, TableName, Key, UpdateExpression,
                    ExpressionAttributeNames, ExpressionAttributeValues,
                    ConditionExpression=None, ReturnValues="ALL_NEW"):
        with self.lock:
            pk = Key["applicationId"]["S"]
            if ConditionExpression == "attribute_exists(applicationId)" and pk not in self.items:
                raise ConditionalCheckFailed("condition failed")
            if pk not in self.items:
                raise ConditionalCheckFailed("item not found")
            self.items[pk]["status"] = dict(ExpressionAttributeValues[":s"])
            return {"Attributes": dict(self.items[pk])}

    def scan(self, TableName, ExclusiveStartKey=None):
        with self.lock:
            return {"Items": [dict(v) for v in self.items.values()]}


class TestRegistryUniqueness(unittest.TestCase):
    def setUp(self):
        self.db = FakeDynamoDB()

    def create(self, app_id, client_id, profile="prof-1", tenant="tenant-1"):
        return create_partner_application(
            application_id=app_id,
            cognito_client_id=client_id,
            api_profile_id=profile,
            tenant_id=tenant,
            table_name=TBL,
            dynamodb_client=self.db,
        )

    # --- successful registration ---------------------------------------
    def test_first_registration_succeeds(self):
        res = self.create("app-1", "client-1")
        self.assertEqual(res["status"], "ACTIVE")
        self.assertIn("app-1", self.db.items)
        self.assertIn(CLIENT_RESERVATION_PREFIX + "client-1", self.db.items)

    def test_uses_transact_write_items_not_put_item(self):
        # Evidence the atomic path is exercised.
        seen = []
        original = self.db.transact_write_items

        def spy(**kwargs):
            seen.append(kwargs)
            return original(**kwargs)

        self.db.transact_write_items = spy
        self.create("app-1", "client-1")
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(seen[0]["TransactItems"]), 2)

    # --- uniqueness -----------------------------------------------------
    def test_duplicate_application_id_rejected(self):
        self.create("app-1", "client-1")
        with self.assertRaises(PartnerRegistryError):
            self.create("app-1", "client-2")
        # No partial write: client-2 reservation must not exist.
        self.assertNotIn(CLIENT_RESERVATION_PREFIX + "client-2", self.db.items)

    def test_duplicate_cognito_client_id_rejected(self):
        self.create("app-1", "client-1")
        with self.assertRaises(PartnerRegistryError):
            self.create("app-2", "client-1")
        # Rollback: app-2 record must not have been created.
        self.assertNotIn("app-2", self.db.items)

    def test_transaction_rollback_on_client_conflict(self):
        self.create("app-1", "client-1")
        before = dict(self.db.items)
        with self.assertRaises(PartnerRegistryError):
            self.create("app-2", "client-1")
        self.assertEqual(set(before), set(self.db.items))

    def test_concurrent_registration_same_client_only_one_wins(self):
        results = []
        errors = []
        barrier = threading.Barrier(8)

        def worker(i):
            barrier.wait()
            try:
                results.append(self.create(f"app-{i}", "client-shared"))
            except PartnerRegistryError as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 1, "exactly one registration must win")
        self.assertEqual(len(errors), 7)
        # Only one application record exists.
        apps = [k for k in self.db.items if not k.startswith(CLIENT_RESERVATION_PREFIX)]
        self.assertEqual(len(apps), 1)

    def test_concurrent_distinct_clients_all_succeed(self):
        successes = []
        failures = []
        barrier = threading.Barrier(6)

        def worker(i):
            barrier.wait()
            try:
                self.create(f"app-{i}", f"client-{i}")
                successes.append(i)
            except PartnerRegistryError as exc:
                failures.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 6)
        self.assertEqual(len(failures), 0)

    # --- lookup compatibility ------------------------------------------
    def test_resolve_returns_application_not_reservation(self):
        self.create("app-1", "client-1")
        rec = resolve_partner_application("client-1", table_name=TBL,
                                          dynamodb_client=self.db)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["applicationId"], "app-1")
        self.assertEqual(rec["status"], "ACTIVE")
        self.assertNotIn("reservedForApplicationId", rec)

    def test_resolve_unknown_client_returns_none(self):
        self.create("app-1", "client-1")
        self.assertIsNone(resolve_partner_application("client-x",
                                                      table_name=TBL,
                                                      dynamodb_client=self.db))

    def test_resolve_missing_client_returns_none(self):
        self.assertIsNone(resolve_partner_application(None, table_name=TBL,
                                                      dynamodb_client=self.db))

    def test_resolve_fails_closed_on_error(self):
        class Broken:
            def query(self, **kwargs):
                raise RuntimeError("network")

        self.assertIsNone(resolve_partner_application("c", table_name=TBL,
                                                      dynamodb_client=Broken()))

    # --- deactivation ---------------------------------------------------
    def test_deactivation_preserves_reservation(self):
        self.create("app-1", "client-1")
        res = deactivate_partner_application("app-1", table_name=TBL,
                                             dynamodb_client=self.db)
        self.assertEqual(res["status"], "INACTIVE")
        rec = resolve_partner_application("client-1", table_name=TBL,
                                          dynamodb_client=self.db)
        self.assertEqual(rec["status"], "INACTIVE")
        # Reservation still blocks reuse of the same client ID.
        with self.assertRaises(PartnerRegistryError):
            self.create("app-2", "client-1")

    def test_deactivate_unknown_application_raises(self):
        with self.assertRaises(PartnerRegistryError):
            deactivate_partner_application("nope", table_name=TBL,
                                           dynamodb_client=self.db)

    def test_deactivate_requires_application_id(self):
        with self.assertRaises(PartnerRegistryError):
            deactivate_partner_application("", table_name=TBL,
                                           dynamodb_client=self.db)

    # --- listing -------------------------------------------------------
    def test_list_excludes_reservation_items(self):
        self.create("app-1", "client-1")
        self.create("app-2", "client-2")
        rows = list_partner_applications(table_name=TBL,
                                         dynamodb_client=self.db)
        self.assertEqual(len(rows), 2)
        ids = sorted(r["applicationId"] for r in rows)
        self.assertEqual(ids, ["app-1", "app-2"])
        for row in rows:
            self.assertNotIn("reservedForApplicationId", row)
            self.assertFalse(row["applicationId"].startswith(
                CLIENT_RESERVATION_PREFIX))

    def test_list_fails_closed(self):
        class Broken:
            def scan(self, **kwargs):
                raise RuntimeError("network")

        self.assertEqual(list_partner_applications(table_name=TBL,
                                                   dynamodb_client=Broken()),
                         [])

    # --- validation -----------------------------------------------------
    def test_missing_identifiers_rejected(self):
        with self.assertRaises(PartnerRegistryError):
            create_partner_application("", "c", "p", "t", TBL, self.db)
        with self.assertRaises(PartnerRegistryError):
            create_partner_application("a", "", "p", "t", TBL, self.db)

    def test_reservation_prefix_constant(self):
        self.assertEqual(CLIENT_RESERVATION_PREFIX, "CLIENT#")

    # --- strong consistency on the authorization hot path ---------------
    def test_resolve_uses_consistent_read(self):
        """Revocation must not lag: deactivate writes the base table, the
        lookup reads the GSI, so the read must be strongly consistent."""
        seen = []
        original = self.db.query

        def spy(**kwargs):
            seen.append(kwargs)
            return original(**kwargs)

        self.create("app-1", "client-1")
        self.db.query = spy
        resolve_partner_application("client-1", table_name=TBL,
                                    dynamodb_client=self.db)
        self.assertTrue(seen, "query was never called")
        for call in seen:
            self.assertIs(call.get("ConsistentRead"), True)

    def test_deactivation_is_immediately_visible_to_resolve(self):
        self.create("app-1", "client-1")
        deactivate_partner_application("app-1", table_name=TBL,
                                       dynamodb_client=self.db)
        rec = resolve_partner_application("client-1", table_name=TBL,
                                          dynamodb_client=self.db)
        self.assertEqual(rec["status"], "INACTIVE")

    # --- reserved namespace protection (independent-tester findings) ---
    def test_application_id_may_not_use_reserved_prefix(self):
        with self.assertRaises(PartnerRegistryError):
            self.create("CLIENT#victim", "victim")
        # The real client must still be registrable afterwards.
        self.create("app-ok", "victim")
        rec = resolve_partner_application("victim", table_name=TBL,
                                          dynamodb_client=self.db)
        self.assertEqual(rec["applicationId"], "app-ok")

    def test_deactivate_refuses_reservation_item(self):
        self.create("app-1", "client-1")
        with self.assertRaises(PartnerRegistryError):
            deactivate_partner_application(
                CLIENT_RESERVATION_PREFIX + "client-1",
                table_name=TBL, dynamodb_client=self.db)
        # Reservation untouched, client ID still reserved.
        with self.assertRaises(PartnerRegistryError):
            self.create("app-2", "client-1")

    def test_reserved_prefix_application_not_listed_as_reservation(self):
        # Nothing should be creatable in the reserved namespace at all.
        with self.assertRaises(PartnerRegistryError):
            self.create("CLIENT#x", "other-client")
        rows = list_partner_applications(table_name=TBL,
                                         dynamodb_client=self.db)
        self.assertEqual(len(rows), 0)


if __name__ == "__main__":
    unittest.main()