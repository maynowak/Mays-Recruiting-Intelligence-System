"""L01/L03 — dispatch ingress Lambda entrypoint tests.

Calls the real ``handler``; only DynamoDB/registry wiring is replaced.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lambda"))

import dispatch_ingress  # noqa: E402
from agents.addition_agent.agent import AdditionAgent  # noqa: E402
from agents.agent_body import AgentBody  # noqa: E402
from agents.ecosystem.registry import AgentRegistry  # noqa: E402

QUEUE_ARN = "arn:aws:sqs:eu-central-1:240571105849:ris-dev-dev-agent-dispatch"
PROFILE_ID = "profile-a"


class ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class Table:
    def __init__(self, fail_put=False):
        self.items = {}
        self.fail_put = fail_put

    def put_item(self, Item, ConditionExpression=None):
        if self.fail_put:
            raise RuntimeError("table unavailable")
        if (ConditionExpression == "attribute_not_exists(workId)"
                and Item["workId"] in self.items):
            raise ConditionalFailed()
        self.items[Item["workId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None,
                    ConditionExpression=None):
        item = self.items[Key["workId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        set_part = UpdateExpression.split("REMOVE")[0].strip()
        if set_part.startswith("SET "):
            set_part = set_part[4:]
        for assignment in set_part.split(","):
            left, right = [s.strip() for s in assignment.split("=", 1)]
            item[names.get(left, left)] = values[right]


class ProfileStore:
    def __init__(self, status="ACTIVE", tenant="tenant-a", user="partner-a-user"):
        self.row = {"apiProfileId": PROFILE_ID, "status": status,
                    "tenantId": tenant, "userId": user}

    def get(self, profile_id):
        return dict(self.row) if profile_id == PROFILE_ID else None


def dispatch_envelope(**overrides):
    envelope = {
        "schemaVersion": "1",
        "messageId": "msg-1",
        "messageType": "ORDER_DISPATCH",
        "orderId": "ord_abc123",
        "correlationId": "req-001",
        "idempotencyKey": "idem-1",
        "sender": {"system": "mays-orders", "reference": "orders-api"},
        "recipient": {"system": "ris", "agentId": "addition_agent",
                      "capability": "math.add"},
        "identity": {"contextRef": PROFILE_ID},
        "payload": {"left": 17, "right": 25},
        "createdAt": "2026-11-13T00:00:00+00:00",
        "execution": {"workId": "work-1"},
    }
    envelope.update(overrides)
    return envelope


class IngressHarness(unittest.TestCase):
    def setUp(self):
        self.table = Table()
        self.deps = {
            "profile_store": ProfileStore(),
            "registry": AgentRegistry(),
            "body": AgentBody(),
            "table": self.table,
            "entitlement_resolver": None,
        }
        self.patch = patch.object(dispatch_ingress, "_dependencies",
                                  return_value=self.deps)
        self.patch.start()
        self._arn = os.environ.pop("DISPATCH_QUEUE_ARN", None)

    def tearDown(self):
        self.patch.stop()
        if self._arn is None:
            os.environ.pop("DISPATCH_QUEUE_ARN", None)
        else:
            os.environ["DISPATCH_QUEUE_ARN"] = self._arn

    def record(self, envelope=None, message_id="msg-1",
               source_arn=QUEUE_ARN):
        return {"messageId": message_id,
                "eventSourceARN": source_arn,
                "body": json.dumps(envelope or dispatch_envelope())}

    def run_handler(self, *records):
        return dispatch_ingress.handler({"Records": list(records)}, None)


class TestValidDispatch(IngressHarness):
    def test_valid_dispatch_executes_the_addition_agent(self):
        result = self.run_handler(self.record())
        self.assertEqual([], result["batchItemFailures"])
        stored = self.table.items["work-1"]
        self.assertEqual("COMPLETED", stored["status"])
        self.assertEqual(42, stored["result"]["data"]["sum"])

    def test_bound_work_id_is_preserved(self):
        self.run_handler(self.record())
        self.assertIn("work-1", self.table.items)

    def test_duplicate_dispatch_does_not_execute_twice(self):
        calls = []
        real = AdditionAgent.process_work

        def spy(agent_self, work_item):
            calls.append(work_item["workId"])
            return real(agent_self, work_item)

        with patch.object(AdditionAgent, "process_work", spy):
            self.run_handler(self.record())
            self.run_handler(self.record(message_id="msg-2"))
        self.assertEqual(["work-1"], calls)


class TestRejectedDispatch(IngressHarness):
    def _assert_rejected(self, record):
        result = self.run_handler(record)
        self.assertEqual([], result["batchItemFailures"])
        self.assertEqual({}, self.table.items)

    def test_unsupported_schema_version(self):
        self._assert_rejected(self.record(dispatch_envelope(schemaVersion="2")))

    def test_unknown_message_type(self):
        self._assert_rejected(self.record(dispatch_envelope(
            messageType="ORDER_RESULT")))

    def test_manipulated_sender_system(self):
        self._assert_rejected(self.record(dispatch_envelope(
            sender={"system": "evil", "reference": "x"})))

    def test_foreign_tenant_claim(self):
        envelope = dispatch_envelope()
        envelope["identity"]["tenantId"] = "tenant-other"
        self._assert_rejected(self.record(envelope))

    def test_foreign_api_profile_reference(self):
        self._assert_rejected(self.record(dispatch_envelope(
            identity={"contextRef": "profile-other"})))

    def test_unsupported_capability(self):
        envelope = dispatch_envelope()
        envelope["recipient"]["capability"] = "math.divide"
        self._assert_rejected(self.record(envelope))

    def test_missing_work_id(self):
        envelope = dispatch_envelope()
        envelope.pop("execution")
        self._assert_rejected(self.record(envelope))

    def test_unexpected_queue_binding(self):
        os.environ["DISPATCH_QUEUE_ARN"] = QUEUE_ARN
        self._assert_rejected(self.record(
            source_arn="arn:aws:sqs:eu-central-1:240571105849:other-queue"))

    def test_inactive_profile_is_rejected(self):
        self.deps["profile_store"] = ProfileStore(status="SUSPENDED")
        self._assert_rejected(self.record())


class TestBatchBehaviour(IngressHarness):
    def test_partial_batch_keeps_good_record_and_rejects_bad(self):
        good = self.record()
        bad = self.record(dispatch_envelope(schemaVersion="9"),
                          message_id="msg-bad")
        result = self.run_handler(bad, good)
        self.assertEqual([], result["batchItemFailures"])
        self.assertIn("work-1", self.table.items)

    def test_transient_failure_requests_retry(self):
        self.table.fail_put = True
        result = self.run_handler(self.record())
        self.assertEqual([{"itemIdentifier": "msg-1"}],
                         result["batchItemFailures"])

    def test_no_secret_material_in_work_item(self):
        self.run_handler(self.record())
        serialized = json.dumps(self.table.items, default=str)
        self.assertNotIn("ris_", serialized)
        self.assertNotIn("Bearer", serialized)


if __name__ == "__main__":
    unittest.main()
