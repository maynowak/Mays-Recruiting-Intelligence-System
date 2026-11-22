"""RIS-ANALYSIS-ECOSYSTEM-CORRECTION-14 — persist/enqueue contract."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.runtime.work_queue import (  # noqa: E402
    WorkEnqueueError,
    enqueue_work_item,
)

QUEUE = "https://sqs.eu-central-1.amazonaws.com/1/work"
WORK = {"workId": "work-1", "type": "agent_addition_agent",
        "tenantId": "tenant-a", "userId": "user-a", "agentId": "addition_agent",
        "capability": "math.add", "idempotencyKey": "key-1",
        "payload": {"left": 1, "right": 2}}


class Table:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        if (ConditionExpression == "attribute_not_exists(workId)"
                and Item["workId"] in self.items):
            raise Conditional()
        self.items[Item["workId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues=None,
                    **kwargs):
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


if __name__ == "__main__":
    unittest.main()
