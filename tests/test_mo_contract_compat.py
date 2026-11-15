"""I03 — contract compatibility between RIS transport V1 and the Orders consumer.

Fails when the two deployments drift apart. Skipped unless ``MO_ORDERS_SRC``
points at the Mays-Orders ``lambda/src``.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MO_SRC = os.environ.get("MO_ORDERS_SRC")
if MO_SRC and os.path.isdir(MO_SRC):
    sys.path.insert(0, MO_SRC)
sys.path.insert(0, ROOT)

# Fields the Orders consumer requires from a result message. Changing either
# side must change this list deliberately.
RESULT_REQUIRED_FIELDS = {
    "schemaVersion", "messageId", "messageType", "orderId", "correlationId",
    "idempotencyKey", "sender", "recipient", "execution", "payload", "createdAt",
}
DISPATCH_REQUIRED_FIELDS = {
    "schemaVersion", "messageId", "messageType", "orderId", "correlationId",
    "idempotencyKey", "sender", "recipient", "identity", "payload", "createdAt",
}


@unittest.skipUnless(MO_SRC and os.path.isdir(MO_SRC),
                     "MO_ORDERS_SRC not set")
class TransportContractCompatibility(unittest.TestCase):
    def setUp(self):
        from agents.transport import order_transport as ris
        import result_envelope as mo_result
        import dispatch as mo_dispatch

        self.ris = ris
        self.mo_result = mo_result
        self.mo_dispatch = mo_dispatch

    # -- versions and types ---------------------------------------------
    def test_ris_schema_version_is_accepted_by_orders(self):
        self.assertIn(self.ris.SCHEMA_VERSION,
                      self.mo_result.ACCEPTED_SCHEMA_VERSIONS)

    def test_result_message_types_match(self):
        self.assertEqual({self.ris.ORDER_RESULT, self.ris.ORDER_FAILED},
                         set(self.mo_result.SUPPORTED_TYPES))

    def test_result_direction_is_ris_to_orders(self):
        self.assertEqual(("ris", "mays-orders"),
                         self.ris.DIRECTION[self.ris.ORDER_RESULT])
        self.assertEqual(("ris", "mays-orders"),
                         self.ris.DIRECTION[self.ris.ORDER_FAILED])

    def test_required_result_fields_are_pinned(self):
        self.assertEqual(RESULT_REQUIRED_FIELDS,
                         set(self.mo_result.REQUIRED_KEYS))

    def test_required_dispatch_fields_are_pinned(self):
        self.assertTrue(DISPATCH_REQUIRED_FIELDS.issubset(
            self.ris.TOP_LEVEL_KEYS))

    # -- round trips -----------------------------------------------------
    def test_orders_dispatch_is_accepted_by_ris(self):
        order = {
            "orderId": "ord_abc123",
            "agentOrder": {
                "schemaVersion": "1.0",
                "target": {"agentId": "addition_agent",
                           "capability": "math.add"},
                "input": {"data": {"left": 17, "right": 25}},
                "metadata": {"requestId": "req-1",
                             "apiProfileRef": "ctx-a",
                             "idempotencyKey": "idem-1"},
            },
        }
        envelope = self.mo_dispatch.build_dispatch_envelope(order, "work-1")
        parsed = self.ris.validate_envelope(envelope,
                                            expected_type="ORDER_DISPATCH")
        self.assertEqual("work-1", parsed["execution"]["workId"])

    def test_ris_result_is_accepted_by_orders(self):
        dispatch = {
            "schemaVersion": "1",
            "messageId": "m1",
            "messageType": "ORDER_DISPATCH",
            "orderId": "ord_abc123",
            "correlationId": "req-1",
            "idempotencyKey": "idem-1",
            "sender": {"system": "mays-orders"},
            "recipient": {"system": "ris", "agentId": "addition_agent",
                          "capability": "math.add"},
            "identity": {"contextRef": "ctx-a"},
            "payload": {"left": 17, "right": 25},
            "createdAt": "2026-11-13T00:00:00+00:00",
            "execution": {"workId": "work-1"},
        }
        parsed_dispatch = self.ris.validate_envelope(dispatch)
        result = self.ris.result_from_work_item(
            parsed_dispatch,
            {"workId": "work-1", "status": "COMPLETED", "attempt_no": 1,
             "result": {"left": 17, "right": 25, "sum": 42}})
        accepted = self.mo_result.validate_result_envelope(result)
        self.assertEqual(42, accepted["payload"]["sum"])
        self.assertEqual("work-1", accepted["execution"]["workId"])

    # -- strictness ------------------------------------------------------
    def test_orders_rejects_unknown_result_field(self):
        from agents.transport import order_transport as ris

        dispatch = {
            "schemaVersion": "1", "messageId": "m1",
            "messageType": "ORDER_DISPATCH", "orderId": "ord_abc123",
            "correlationId": "req-1", "idempotencyKey": "idem-1",
            "sender": {"system": "mays-orders"},
            "recipient": {"system": "ris", "agentId": "addition_agent"},
            "identity": {"contextRef": "ctx-a"},
            "payload": {"left": 17, "right": 25},
            "createdAt": "2026-11-13T00:00:00+00:00",
        }
        parsed = ris.validate_envelope(dispatch)
        result = ris.result_from_work_item(
            parsed, {"workId": "w", "status": "COMPLETED", "attempt_no": 1,
                     "result": {"sum": 42}})
        result["newField"] = "drift"
        with self.assertRaises(self.mo_result.ResultEnvelopeError) as ctx:
            self.mo_result.validate_result_envelope(result)
        self.assertEqual("unknown_field", ctx.exception.code)

    def test_orders_rejects_an_unsupported_ris_version(self):
        envelope = {
            "schemaVersion": "2", "messageId": "m1",
            "messageType": "ORDER_RESULT", "orderId": "ord_abc123",
            "correlationId": "req-1", "idempotencyKey": "k",
            "sender": {"system": "ris"}, "recipient": {"system": "mays-orders"},
            "payload": {"sum": 42}, "createdAt": "2026-11-13T00:00:00+00:00",
            "execution": {"workId": "w", "attempt": 1},
        }
        with self.assertRaises(self.mo_result.ResultEnvelopeError) as ctx:
            self.mo_result.validate_result_envelope(envelope)
        self.assertEqual("unsupported_schema_version", ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
