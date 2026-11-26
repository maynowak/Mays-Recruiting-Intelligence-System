"""RIS-ANALYSIS-ECOSYSTEM-CORRECTION-14 — persist/enqueue contract."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.runtime import work_queue  # noqa: E402
from agents.runtime.work_queue import (  # noqa: E402
    WorkEnqueueError,
    enqueue_work_item,
)

QUEUE = "https://sqs.eu-central-1.amazonaws.com/1/work"
WORK = {
    "workId": "work-1", "type": "agent_addition_agent",
    "tenantId": "tenant-a", "userId": "user-a", "agentId": "addition_agent",
    "capability": "math.add", "idempotencyKey": "key-1",
    "partnerApplicationId": "", "issuer": "",
    "status": "QUEUED", "payload": {"left": 1, "right": 2},
}


class Table:
    def __init__(self):
        self.items = {}
        self.updates = []

    def put_item(self, Item, ConditionExpression=None):
        if (ConditionExpression == "attribute_not_exists(workId)"
                and Item["workId"] in self.items):
            raise Conditional()
        self.items[Item["workId"]] = dict(Item)

    def get_item(self, Key, ConsistentRead=False):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues=None,
                    ConditionExpression=None, **kwargs):
        self.updates.append({"key": Key, "expr": UpdateExpression,
                             "condition": ConditionExpression,
                             "values": ExpressionAttributeValues})
        for assignment in UpdateExpression.split(","):
            left, right = [part.strip() for part in assignment.split("=", 1)]
            field = left.replace("SET ", "").strip()
            self.items[Key["workId"]][field] = \
                (ExpressionAttributeValues or {})[right]


class Conditional(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeSQS:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def send_message(self, **kwargs):
        if self.fail:
            raise RuntimeError("sqs down")
        self.sent.append(kwargs)


class EnqueueTest(unittest.TestCase):
    def setUp(self):
        self.table = Table()
        self.sqs = FakeSQS()

    def test_persist_then_enqueue(self):
        out = enqueue_work_item(dict(WORK), table=self.table, queue_url=QUEUE,
                                sqs_client=self.sqs)
        self.assertEqual("QUEUED", out["status"])
        self.assertEqual("work-1", self.table.items["work-1"]["workId"])
        self.assertIn("enqueuedAt", self.table.items["work-1"])
        self.assertEqual(1, len(self.sqs.sent))
        self.assertEqual("work-1",
                         json.loads(self.sqs.sent[0]["MessageBody"])["workId"])
        self.assertEqual("attribute_exists(workId)",
                         self.table.updates[0]["condition"])

    def test_redelivery_does_not_enqueue_twice(self):
        enqueue_work_item(dict(WORK), table=self.table, queue_url=QUEUE,
                          sqs_client=self.sqs)
        second = enqueue_work_item(dict(WORK), table=self.table,
                                   queue_url=QUEUE, sqs_client=self.sqs)
        self.assertTrue(second["duplicate"])
        self.assertFalse(second["enqueued"])
        self.assertEqual(1, len(self.sqs.sent))

    def test_terminal_duplicate_is_not_requeued(self):
        self.table.items["work-1"] = {**WORK, "status": "COMPLETED"}
        out = enqueue_work_item(dict(WORK), table=self.table, queue_url=QUEUE,
                                sqs_client=self.sqs)
        self.assertFalse(out["enqueued"])
        self.assertEqual([], self.sqs.sent)

    def test_send_failure_is_recoverable(self):
        with self.assertRaises(WorkEnqueueError):
            enqueue_work_item(dict(WORK), table=self.table, queue_url=QUEUE,
                              sqs_client=FakeSQS(fail=True))
        self.assertIn("work-1", self.table.items)
        self.assertNotIn("enqueuedAt", self.table.items["work-1"])
        sqs = FakeSQS()
        enqueue_work_item(dict(WORK), table=self.table, queue_url=QUEUE,
                          sqs_client=sqs)
        self.assertEqual(1, len(sqs.sent))

    def test_missing_queue_or_item_fails_closed(self):
        with self.assertRaises(WorkEnqueueError):
            enqueue_work_item(dict(WORK), table=self.table, queue_url="")
        with self.assertRaises(WorkEnqueueError):
            enqueue_work_item({}, table=self.table, queue_url=QUEUE)


class TransactCancelled(Exception):
    def __init__(self, reasons=None):
        self.response = {
            "Error": {"Code": "TransactionCanceledException",
                      "Message": "Transaction cancelled, please refer to "
                                 "CancellationReasons"},
            "CancellationReasons": reasons or [],
        }


class _TransactClient:
    def __init__(self, owner, error):
        self.owner = owner
        self.error = error

    def transact_write_items(self, **kwargs):
        self.owner.transact_calls.append(kwargs)
        if self.error is not None:
            raise self.error


class TransactTable:
    name = "work-items"

    def __init__(self, item=None, error=None):
        self.item = dict(item) if item else None
        self.transact_calls = []
        self.updates = []
        self.meta = SimpleNamespace(
            client=_TransactClient(self, error))

    def get_item(self, Key, ConsistentRead=False):
        return {"Item": dict(self.item)} if self.item else {}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)


class CancellationFailClosedTest(unittest.TestCase):
    def _call(self, table, sqs=None):
        return enqueue_work_item(dict(WORK), table=table, queue_url=QUEUE,
                                 sqs_client=sqs or FakeSQS())

    def test_cancelled_without_existing_row_fails_closed(self):
        table = TransactTable(error=TransactCancelled([
            {"Code": "ConditionalCheckFailed"}, {"Code": "None"}]))
        sqs = FakeSQS()
        with self.assertRaises(WorkEnqueueError):
            self._call(table, sqs)
        self.assertEqual([], sqs.sent)
        self.assertEqual([], table.updates)

    def test_cancelled_with_incomplete_item_fails_closed(self):
        table = TransactTable(item={"workId": "work-1"},
                              error=TransactCancelled())
        sqs = FakeSQS()
        with self.assertRaises(WorkEnqueueError):
            self._call(table, sqs)
        self.assertEqual([], sqs.sent)
        self.assertEqual([], table.updates)

    def test_cancelled_with_identity_mismatch_fails_closed(self):
        for field, bad in (("tenantId", "tenant-b"), ("userId", "user-b"),
                           ("partnerApplicationId", "other"),
                           ("issuer", "https://other"), ("agentId", "ats-agent"),
                           ("capability", "analyze.job"),
                           ("apiProfileId", "aprof_other"),
                           ("type", "agent_ats-agent")):
            table = TransactTable(item={**WORK, field: bad},
                                  error=TransactCancelled())
            sqs = FakeSQS()
            with self.assertRaises(WorkEnqueueError):
                self._call(table, sqs)
            self.assertEqual([], sqs.sent, field)
            self.assertEqual([], table.updates, field)

    def test_cancelled_with_payload_mismatch_fails_closed(self):
        table = TransactTable(
            item={**WORK, "payload": {"left": 9, "right": 9}},
            error=TransactCancelled())
        sqs = FakeSQS()
        with self.assertRaises(WorkEnqueueError):
            self._call(table, sqs)
        self.assertEqual([], sqs.sent)
        self.assertEqual([], table.updates)

    def test_cancelled_with_idempotency_mismatch_fails_closed(self):
        table = TransactTable(item={**WORK, "idempotencyKey": "other-key"},
                              error=TransactCancelled())
        sqs = FakeSQS()
        with self.assertRaises(WorkEnqueueError):
            self._call(table, sqs)
        self.assertEqual([], sqs.sent)
        self.assertEqual([], table.updates)

    def test_identical_nested_payload_and_key_is_idempotent(self):
        payload = {"left": 1, "right": {"nested": [1, 2, 3]}}
        requested = {**WORK, "payload": payload}
        table = TransactTable(
            item={**requested, "enqueuedAt": "2026-01-01T00:00:00+00:00"},
            error=TransactCancelled())
        sqs = FakeSQS()
        out = enqueue_work_item(dict(requested), table=table, queue_url=QUEUE,
                                sqs_client=sqs)
        self.assertTrue(out["duplicate"])
        self.assertEqual([], sqs.sent)
        self.assertEqual([], table.updates)

    def test_cancelled_with_valid_enqueued_duplicate(self):
        table = TransactTable(
            item={**WORK, "enqueuedAt": "2026-01-01T00:00:00+00:00"},
            error=TransactCancelled())
        sqs = FakeSQS()
        out = self._call(table, sqs)
        self.assertTrue(out["duplicate"])
        self.assertFalse(out["enqueued"])
        self.assertEqual([], sqs.sent)
        self.assertEqual([], table.updates)

    def test_cancelled_with_terminal_duplicate(self):
        table = TransactTable(item={**WORK, "status": "COMPLETED"},
                              error=TransactCancelled())
        sqs = FakeSQS()
        out = self._call(table, sqs)
        self.assertTrue(out["duplicate"])
        self.assertEqual([], sqs.sent)

    def test_cancelled_with_valid_queued_row_sends_once(self):
        table = TransactTable(item=dict(WORK), error=TransactCancelled())
        sqs = FakeSQS()
        out = self._call(table, sqs)
        self.assertEqual(1, len(sqs.sent))
        self.assertTrue(out["enqueued"])
        self.assertEqual(1, len(table.updates))
        self.assertEqual("attribute_exists(workId)",
                         table.updates[0]["ConditionExpression"])

    def test_non_conditional_error_propagates_without_send(self):
        table = TransactTable(error=RuntimeError("store down"))
        sqs = FakeSQS()
        with self.assertRaises(RuntimeError):
            self._call(table, sqs)
        self.assertEqual([], sqs.sent)
        self.assertEqual([], table.updates)

    def test_cancellation_reasons_are_logged_without_values(self):
        reasons = [{"Code": "ConditionalCheckFailed"},
                   {"Code": "TransactionConflict"}]
        table = TransactTable(error=TransactCancelled(reasons))
        with patch.object(work_queue.logger, "warning") as log:
            with self.assertRaises(WorkEnqueueError):
                self._call(table)
        text = " ".join(str(call) for call in log.call_args_list)
        self.assertIn("ConditionalCheckFailed", text)
        self.assertIn("TransactionConflict", text)
        self.assertNotIn("payload", text)
        self.assertNotIn("user-a", text)


if __name__ == "__main__":
    unittest.main()
