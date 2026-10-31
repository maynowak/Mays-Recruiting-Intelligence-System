"""R08-A1 tests: durable privacy receipt journal (unit + storage semantics).

DynamoDB Local integration is in tests/integration.
"""

import copy
import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.privacy_receipt import (  # noqa: E402
    PrivacyContextV1, PrivacyReceiptError, PrivacyReceiptV1,
)
from agents.ecosystem.privacy_receipt_journal import (  # noqa: E402
    PrivacyReceiptConflict, PrivacyReceiptIntegrityError,
    PrivacyReceiptInvalidCursor, PrivacyReceiptJournal,
    PrivacyReceiptJournalDisabled, PrivacyReceiptJournalError,
    PrivacyReceiptNotFound, PrivacyReceiptStorageError,
    receipt_content_hash, scope_key,
)
from tests.test_partner_manual_profiles_api import FakeDynamo  # noqa: E402
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileRepository,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64
CTX = PrivacyContextV1(
    user_id="sub_synthetic_123",
    tenant_id="tenant-synthetic",
    partner_application_id="app-synthetic",
    issuer="https://issuer.example/pool")


def make_receipt(receipt_id="rcpt_0123456789abcdef", **overrides):
    data = dict(
        receipt_id=receipt_id,
        subject_ref=CTX.user_id,
        tenant_ref=CTX.tenant_id,
        partner_application_ref=CTX.partner_application_id,
        issuer_ref=CTX.issuer,
        event_type="PROFILE_CREATED",
        purpose="profile_management",
        legal_basis_ref="REVIEW_REQUIRED",
        privacy_notice_version=None,
        privacy_notice_digest=None,
        data_categories=("cv_metadata",),
        processing_domain="ris",
        operation_ref="op_0123456789abcdef",
        recorded_at=NOW.isoformat(),
        status="completed",
        retention_policy_ref="REVIEW_REQUIRED",
        evidence_level="server_verified",
        schema_version=1,
    )
    data.update(overrides)
    return PrivacyReceiptV1(**data)


class FakeReceiptTable:
    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()
        self.put_error = None
        self.get_error = None
        self.query_error = None
        self.put_calls = 0

    def put_item(self, Item, ConditionExpression=None):
        self.put_calls += 1
        if self.put_error:
            raise self.put_error
        rid = Item["receiptId"]
        with self.lock:
            if ConditionExpression == "attribute_not_exists(receiptId)" \
                    and rid in self.items:
                raise Exception("ConditionalCheckFailedException")
            self.items[rid] = copy.deepcopy(Item)

    def get_item(self, Key, ConsistentRead=False):
        if self.get_error:
            raise self.get_error
        item = self.items.get(Key["receiptId"])
        return {"Item": copy.deepcopy(item)} if item else {}

    def query(self, **kwargs):
        if self.query_error:
            raise self.query_error
        vals = kwargs.get("ExpressionAttributeValues", {})
        scope = vals.get(":s")
        results = [copy.deepcopy(v) for v in self.items.values()
                   if v.get("scopeKey") == scope]
        results.sort(key=lambda v: v.get("scopeSort", ""),
                     reverse=not kwargs.get("ScanIndexForward", True))
        start = kwargs.get("ExclusiveStartKey")
        if start:
            ids = [v["receiptId"] for v in results]
            if start.get("receiptId") in ids:
                results = results[ids.index(start["receiptId"]) + 1:]
        limit = kwargs.get("Limit", 50)
        page = results[:limit]
        cursor = ({"receiptId": page[-1]["receiptId"],
                   "scopeKey": page[-1]["scopeKey"],
                   "scopeSort": page[-1]["scopeSort"]}
                  if len(results) > limit else None)
        return {"Items": page, "LastEvaluatedKey": cursor}


class JournalHarness(unittest.TestCase):
    def setUp(self):
        self.receipts = FakeReceiptTable()
        self.cursor_dynamo = FakeDynamo()
        self.cursor_repo = PartnerProfileRepository(table_name="partner-profiles")
        self.cursor_repo._table = self.cursor_dynamo
        self.cursor_repo._client = self.cursor_dynamo
        self.journal = PrivacyReceiptJournal(
            table_name="privacy-receipts", table=self.receipts,
            enabled=True, cursor_repo=self.cursor_repo,
            clock=lambda: NOW)

    def append(self, receipt=None, context=CTX):
        return self.journal.append_receipt(receipt or make_receipt(), context)


class TestAppendGet(JournalHarness):
    def test_append_and_get_roundtrip(self):
        receipt = self.append()
        self.assertEqual(receipt, self.journal.get_receipt(
            receipt.receipt_id, CTX))
        self.assertEqual(1, len(self.receipts.items))
        item = self.receipts.items[receipt.receipt_id]
        self.assertEqual(scope_key(CTX), item["scopeKey"])
        self.assertEqual(receipt_content_hash(receipt),
                         item["contentHash"])
        self.assertEqual(NOW.isoformat(), item["recordedAt"])

    def test_idempotent_replay_same_payload(self):
        first = self.append()
        second = self.append(make_receipt(recorded_at="2025-01-01T00:00:00+00:00"))
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual(1, len(self.receipts.items))
        self.assertEqual(first.recorded_at, second.recorded_at)

    def test_same_id_different_payload_conflicts(self):
        self.append()
        with self.assertRaises(PrivacyReceiptConflict):
            self.append(make_receipt(event_type="PROFILE_UPDATED"))

    def test_invalid_receipt_rejected(self):
        with self.assertRaises(PrivacyReceiptError):
            self.append(make_receipt(event_type="UNKNOWN_EVENT"))
        self.assertEqual(0, len(self.receipts.items))

    def test_context_mismatch_rejected(self):
        other = PrivacyContextV1(
            user_id="sub_other", tenant_id=CTX.tenant_id,
            partner_application_id=CTX.partner_application_id,
            issuer=CTX.issuer)
        with self.assertRaises(PrivacyReceiptJournalError):
            self.append(context=other)
        self.assertEqual(0, len(self.receipts.items))

    def test_missing_context_is_rejected(self):
        with self.assertRaises(PrivacyReceiptError):
            PrivacyContextV1(
                user_id="", tenant_id=CTX.tenant_id,
                partner_application_id=CTX.partner_application_id,
                issuer=CTX.issuer)

    def test_no_update_or_delete_api(self):
        self.assertFalse(hasattr(self.journal, "update_receipt"))
        self.assertFalse(hasattr(self.journal, "delete_receipt"))

    def test_replay_does_not_mutate_stored_receipt(self):
        first = self.append()
        before = copy.deepcopy(self.receipts.items[first.receipt_id])
        self.append(make_receipt(recorded_at="2025-01-01T00:00:00+00:00"))
        self.assertEqual(before, self.receipts.items[first.receipt_id])


class TestIsolation(JournalHarness):
    def test_cross_user_tenant_partner_issuer(self):
        receipt = self.append()
        for field, value in (
            ("user_id", "sub_other"),
            ("tenant_id", "tenant-other"),
            ("partner_application_id", "app-other"),
            ("issuer", "https://other/pool"),
        ):
            other = PrivacyContextV1(
                user_id=value if field == "user_id" else CTX.user_id,
                tenant_id=value if field == "tenant_id" else CTX.tenant_id,
                partner_application_id=(value if field == "partner_application_id"
                                        else CTX.partner_application_id),
                issuer=value if field == "issuer" else CTX.issuer)
            with self.assertRaises(PrivacyReceiptNotFound):
                self.journal.get_receipt(receipt.receipt_id, other)

    def test_list_does_not_leak_other_scope(self):
        self.append()
        other = PrivacyContextV1(
            user_id="sub_other", tenant_id=CTX.tenant_id,
            partner_application_id=CTX.partner_application_id,
            issuer=CTX.issuer)
        receipts, cursor = self.journal.list_receipts(other)
        self.assertEqual([], receipts)
        self.assertIsNone(cursor)

    def test_scope_key_is_stable_and_distinct(self):
        self.assertEqual(scope_key(CTX), scope_key(CTX))
        other = PrivacyContextV1(
            user_id="sub_other", tenant_id=CTX.tenant_id,
            partner_application_id=CTX.partner_application_id,
            issuer=CTX.issuer)
        self.assertNotEqual(scope_key(CTX), scope_key(other))


class TestPagination(JournalHarness):
    def _three(self):
        ids = []
        for i in range(3):
            receipt = make_receipt(receipt_id=f"rcpt_{i:016d}")
            ids.append(self.append(receipt).receipt_id)
        return ids

    def test_pagination_across_pages(self):
        self._three()
        first, cursor = self.journal.list_receipts(CTX, limit=2)
        self.assertEqual(2, len(first))
        self.assertIsNotNone(cursor)
        second, cursor2 = self.journal.list_receipts(
            CTX, cursor=cursor, limit=2)
        self.assertEqual(1, len(second))
        self.assertIsNone(cursor2)
        self.assertEqual(3, len({r.receipt_id for r in first + second}))

    def test_invalid_cursor(self):
        with self.assertRaises(PrivacyReceiptInvalidCursor):
            self.journal.list_receipts(CTX, cursor="not-a-cursor")

    def test_cursor_from_other_scope_is_rejected(self):
        self._three()
        _, cursor = self.journal.list_receipts(CTX, limit=1)
        other = PrivacyContextV1(
            user_id="sub_other", tenant_id=CTX.tenant_id,
            partner_application_id=CTX.partner_application_id,
            issuer=CTX.issuer)
        with self.assertRaises(PrivacyReceiptInvalidCursor):
            self.journal.list_receipts(other, cursor=cursor)

    def test_limit_is_bounded(self):
        self._three()
        receipts, _ = self.journal.list_receipts(CTX, limit=999)
        self.assertLessEqual(len(receipts), 50)


class TestFailClosed(JournalHarness):
    def test_disabled_journal_rejects_all_operations(self):
        journal = PrivacyReceiptJournal(
            table_name="privacy-receipts", table=self.receipts,
            enabled=False, cursor_repo=self.cursor_repo)
        for action in (
            lambda: journal.append_receipt(make_receipt(), CTX),
            lambda: journal.get_receipt("rcpt_x", CTX),
            lambda: journal.list_receipts(CTX),
        ):
            with self.assertRaises(PrivacyReceiptJournalDisabled):
                action()

    def test_write_error_is_not_success(self):
        self.receipts.put_error = RuntimeError("write down")
        with self.assertRaises(PrivacyReceiptStorageError):
            self.append()
        self.assertEqual(0, len(self.receipts.items))

    def test_read_error_is_not_not_found(self):
        self.receipts.get_error = RuntimeError("read down")
        with self.assertRaises(PrivacyReceiptStorageError):
            self.journal.get_receipt("rcpt_0123456789abcdef", CTX)

    def test_query_error_is_not_empty_page(self):
        self.receipts.query_error = RuntimeError("query down")
        with self.assertRaises(PrivacyReceiptStorageError):
            self.journal.list_receipts(CTX)

    def test_integrity_mismatch_is_detected(self):
        receipt = self.append()
        item = self.receipts.items[receipt.receipt_id]
        item["payload"]["eventType"] = "PROFILE_UPDATED"
        with self.assertRaises(PrivacyReceiptIntegrityError):
            self.journal.get_receipt(receipt.receipt_id, CTX)

    def test_no_scan_in_normal_repository(self):
        source = open(
            os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
                "agents", "ecosystem", "privacy_receipt_journal.py"),
            encoding="utf-8").read()
        self.assertNotIn(".scan(", source)


class TestConcurrentAppend(JournalHarness):
    def test_parallel_same_receipt_has_one_item(self):
        outcome = []
        barrier = threading.Barrier(2)

        def attempt():
            barrier.wait()
            try:
                outcome.append(self.append().receipt_id)
            except Exception as exc:  # noqa: BLE001
                outcome.append(type(exc).__name__)

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(1, len(set(outcome)), outcome)
        self.assertEqual(1, len(self.receipts.items))


class TestDataMinimisation(JournalHarness):
    def test_stored_item_has_no_raw_or_hierarchy_fields(self):
        receipt = self.append()
        item = self.receipts.items[receipt.receipt_id]
        serialized = str(item)
        for forbidden in ("cvText", "cvContent", "filename", "user@example",
                          "prompt", "Authorization", "presignedUrl",
                          "accessToken", "secret"):
            self.assertNotIn(forbidden, serialized)
        for system in ("capacity#", "lifecycle#", "idem#", "parentId"):
            self.assertNotIn(system, serialized)


class TestTerraformJournalConfig(unittest.TestCase):
    def _read(self, *parts):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return open(os.path.join(root, *parts), encoding="utf-8").read()

    def test_table_is_separate_and_subject_scoped(self):
        src = self._read("terraform", "modules", "dynamodb", "main.tf")
        block = src.split(
            'resource "aws_dynamodb_table" "privacy_receipts"')[1]
        block = block.split('\nresource "')[0]
        self.assertIn('${var.project_name}-${var.environment}-privacy-receipts',
                      block)
        self.assertIn('hash_key     = "receiptId"', block)
        self.assertIn('name            = "gsi-subject"', block)
        self.assertIn('hash_key        = "scopeKey"', block)
        self.assertIn('range_key       = "scopeSort"', block)
        self.assertNotIn("ttl {", block)

    def test_iam_is_minimal_and_has_no_scan_update_delete(self):
        src = self._read("terraform", "modules", "lambda", "main.tf")
        block = src.split(
            'resource "aws_iam_role_policy" "lambda_privacy_receipts"')[1]
        block = block.split('\nresource "')[0]
        for action in ("PutItem", "GetItem", "Query"):
            self.assertIn(f'"dynamodb:{action}"', block)
        for forbidden in ("Scan", "UpdateItem", "DeleteItem"):
            self.assertNotIn(f'"dynamodb:{forbidden}"', block)

    def test_journal_is_fail_closed_in_lambda_env(self):
        src = self._read("terraform", "modules", "lambda", "main.tf")
        self.assertIn('PRIVACY_RECEIPTS_TABLE         = var.privacy_receipts_table_name',
                      src)
        self.assertIn('PRIVACY_RECEIPT_JOURNAL_ENABLED = "false"', src)


if __name__ == "__main__":
    unittest.main()
