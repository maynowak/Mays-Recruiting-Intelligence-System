"""A05/D05 — cross-repository dispatch handoff (Orders -> RIS -> Orders).

Local only. Skipped unless ``MO_ORDERS_SRC`` points at the Mays-Orders
``lambda/src`` directory, so the RIS suite stays green without that checkout.

Run with:
    MO_ORDERS_SRC=/path/to/mays-order-aws/lambda/src python -m pytest \
        tests/test_mo_dispatch_handoff.py -q
"""

import os
import sys
import unittest
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MO_SRC = os.environ.get("MO_ORDERS_SRC")

if MO_SRC and os.path.isdir(MO_SRC):
    sys.path.insert(0, MO_SRC)

sys.path.insert(0, ROOT)


@unittest.skipUnless(MO_SRC and os.path.isdir(MO_SRC),
                     "MO_ORDERS_SRC not set")
class TestDispatchHandoff(unittest.TestCase):
    def setUp(self):
        import dispatch as mo_dispatch
        import identity as mo_identity
        import order_service as mo_order_service
        import result_envelope as mo_result
        import result_handler as mo_result_handler

        self.mo_dispatch = mo_dispatch
        self.mo_result = mo_result
        self.mo_result_handler = mo_result_handler
        self.service = mo_order_service.OrderService("t", client=Table())
        self.alice = mo_identity.OwnerIdentity(
            issuer="https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_P",
            subject="alice", client_id="client-a")
        self.bob = mo_identity.OwnerIdentity(
            issuer=self.alice.issuer, subject="bob", client_id="client-a")

        self.order_id = self.service.create_order({
            "orderType": "agent.execution",
            "agentOrder": {
                "schemaVersion": "1.0",
                "target": {"agentId": "addition_agent",
                           "capability": "math.add"},
                "input": {"data": {"left": 17, "right": 25}},
                "metadata": {"source": "ris-agent-ecosystem",
                             "requestId": "req-001",
                             "apiProfileRef": "ctx-a"},
            },
        }, self.alice)["orderId"]

    # -- helpers ---------------------------------------------------------
    def _dispatch(self):
        bound = self.service.prepare_dispatch(self.order_id, self.alice)
        envelope = self.service.dispatch_envelope(self.order_id, bound["workId"])
        return bound, envelope

    def _ris_work_item(self, envelope):
        from agents.transport import VerifiedContext, dispatch_to_work_item
        from agents.transport import validate_envelope

        validated = validate_envelope(envelope, expected_type="ORDER_DISPATCH")
        context = VerifiedContext(
            context_ref="ctx-a", tenant_id="tenant-a", owner_id="alice",
            api_profile_id="profile-a", partner_application_id="partner-a",
            issuer="https://cognito.internal")
        return validated, dispatch_to_work_item(validated, context)

    def _execute(self, work_item):
        from agents.addition_agent import AdditionAgent
        return AdditionAgent().process_work(work_item)

    def _result_envelope(self, envelope, work_item, result):
        from agents.transport import result_from_work_item
        row = {"workId": work_item["workId"], "status": "COMPLETED",
               "attempt_no": 1,
               "result": {"left": 17, "right": 25, "sum": result["data"]["sum"]}}
        return result_from_work_item(envelope, row)

    # -- tests -----------------------------------------------------------
    def test_full_round_trip_returns_42_to_the_same_order(self):
        bound, envelope = self._dispatch()
        self.assertFalse(bound["reused"])

        validated, work_item = self._ris_work_item(envelope)
        # A05-1: the work item reuses the id bound on the order.
        self.assertEqual(bound["workId"], work_item["workId"])

        agent_result = self._execute(work_item)
        self.assertEqual(42, agent_result["data"]["sum"])

        result = self._result_envelope(validated, work_item, agent_result)
        applied = self.service.apply_result(
            self.mo_result.validate_result_envelope(result))
        self.assertEqual(42, applied["result"]["sum"])

        owner_view = self.service.get_order(self.order_id, self.alice)
        self.assertEqual("COMPLETED", owner_view["processing"]["status"])
        self.assertEqual(42, owner_view["processing"]["result"]["sum"])

    def test_work_id_is_stable_across_repeated_dispatch_attempts(self):
        first, _ = self._dispatch()
        second = self.service.prepare_dispatch(self.order_id, self.alice)
        self.assertTrue(second["reused"])
        self.assertEqual(first["workId"], second["workId"])

    def test_send_state_is_recorded_and_repeatable(self):
        bound, envelope = self._dispatch()
        record = self.service.mark_dispatch_sent(
            self.order_id, bound["workId"], envelope["messageId"])
        self.assertEqual("SENT", record["status"])
        again = self.service.mark_dispatch_sent(
            self.order_id, bound["workId"], envelope["messageId"])
        self.assertEqual(record["messageId"], again["messageId"])

    def test_foreign_owner_cannot_dispatch(self):
        from errors import OrderError
        with self.assertRaises(OrderError):
            self.service.prepare_dispatch(self.order_id, self.bob)

    def test_cancelled_order_is_not_dispatched(self):
        self.service._table.items[self.order_id]["status"] = "CANCELLED"
        with self.assertRaises(self.mo_dispatch.DispatchRejected) as ctx:
            self.service.prepare_dispatch(self.order_id, self.alice)
        self.assertEqual("order_cancelled", ctx.exception.code)

    def test_tampered_fingerprint_blocks_dispatch(self):
        self.service._table.items[self.order_id]["agentOrder"]["input"]["data"][
            "right"] = 999
        with self.assertRaises(self.mo_dispatch.DispatchRejected) as ctx:
            self.service.prepare_dispatch(self.order_id, self.alice)
        self.assertEqual("fingerprint_mismatch", ctx.exception.code)

    def test_wrong_work_id_result_is_rejected(self):
        bound, envelope = self._dispatch()
        validated, work_item = self._ris_work_item(envelope)
        result = self._result_envelope(
            validated, {**work_item, "workId": "work-other"},
            {"data": {"sum": 42}})
        with self.assertRaises(self.mo_result.ResultRejected) as ctx:
            self.service.apply_result(
                self.mo_result.validate_result_envelope(result))
        self.assertEqual("work_mismatch", ctx.exception.code)

    def test_duplicate_result_is_idempotent(self):
        bound, envelope = self._dispatch()
        validated, work_item = self._ris_work_item(envelope)
        result = self._result_envelope(validated, work_item,
                                       {"data": {"sum": 42}})
        parsed = self.mo_result.validate_result_envelope(result)
        first = self.service.apply_result(parsed)
        second = self.service.apply_result(parsed)
        self.assertEqual(first["idempotencyKey"], second["idempotencyKey"])
        self.assertEqual(1, len(self.service._table.items))

    def test_stale_attempt_is_rejected(self):
        bound, envelope = self._dispatch()
        validated, work_item = self._ris_work_item(envelope)
        self.service._table.items[self.order_id]["processing"] = {
            "schemaVersion": "1.0", "status": "RUNNING", "attempt": 5}
        result = self._result_envelope(validated, work_item,
                                       {"data": {"sum": 42}})
        result["execution"]["attempt"] = 3
        with self.assertRaises(self.mo_result.ResultRejected) as ctx:
            self.service.apply_result(
                self.mo_result.validate_result_envelope(result))
        self.assertEqual("stale_attempt", ctx.exception.code)

    def test_consumer_rejects_unsigned_result(self):
        bound, envelope = self._dispatch()
        validated, work_item = self._ris_work_item(envelope)
        result = self._result_envelope(validated, work_item,
                                       {"data": {"sum": 42}})
        import json
        os.environ["ORDERS_TABLE"] = "t"
        os.environ["ORDER_RESULT_SERVICE_SECRET"] = "s3cret"
        record = {"messageId": "m1", "body": json.dumps(result),
                  "messageAttributes": {}}
        try:
            response = self.mo_result_handler.handler({"Records": [record]}, None)
        finally:
            os.environ.pop("ORDER_RESULT_SERVICE_SECRET", None)
        self.assertEqual(1, json.loads(response["body"])["rejected"])


class ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class Table:
    """Minimal conditional table for the cross-repo flow."""

    def __init__(self):
        self.items = {}

    def put_item(self, **kwargs):
        self.items[kwargs["Item"]["orderId"]] = dict(kwargs["Item"])
        return {}

    def get_item(self, Key):
        order_id = Key["pk"][len("ord_"):]
        item = self.items.get(order_id)
        return {"Item": dict(item)} if item else {}

    def query(self, **kwargs):
        return {"Items": []}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, **kwargs):
        order_id = Key["pk"][len("ord_"):]
        item = self.items[order_id]
        values = ExpressionAttributeValues or {}
        if ConditionExpression:
            if ("attribute_not_exists(expectedWorkId)" in ConditionExpression
                    and "expectedWorkId" in item):
                raise ConditionalFailed()
            if ("attribute_not_exists(#p)" in ConditionExpression
                    and "processing" in item):
                raise ConditionalFailed()
            if ("expectedWorkId = :w" in ConditionExpression
                    and item.get("expectedWorkId") != values.get(":w")):
                raise ConditionalFailed()
        if ":w" in values:
            item["expectedWorkId"] = values[":w"]
        if ":p" in values:
            item["processing"] = values[":p"]
        if ":d" in values:
            item["dispatch"] = values[":d"]
        return {"Attributes": dict(item)}


if __name__ == "__main__":
    unittest.main()
