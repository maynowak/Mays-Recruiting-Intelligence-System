"""L05 — Lambda-to-Lambda end-to-end: Orders -> dispatch ingress -> agent -> result consumer -> GET.

Skipped unless ``MO_ORDERS_SRC`` points at the Mays-Orders ``lambda/src``.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MO_SRC = os.environ.get("MO_ORDERS_SRC")
if MO_SRC and os.path.isdir(MO_SRC):
    sys.path.insert(0, MO_SRC)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lambda"))

RESULT_SECRET = "bridge-secret"
QUEUE_ARN = "arn:aws:sqs:eu-central-1:240571105849:ris-dev-dev-agent-dispatch"
ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_P"


class ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class Table:
    """One table double for both systems (separate instances in reality)."""

    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        key = Item.get("workId") or Item["orderId"]
        if ConditionExpression and "attribute_not_exists(workId)" in ConditionExpression:
            if key in self.items:
                raise ConditionalFailed()
        self.items[key] = dict(Item)

    def get_item(self, Key):
        if "workId" in Key:
            item = self.items.get(Key["workId"])
        else:
            order_id = Key["pk"][len("ord_"):]
            item = self.items.get(order_id)
        return {"Item": dict(item)} if item else {}

    def query(self, **kwargs):
        return {"Items": []}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, **kwargs):
        key = Key.get("workId") or Key["pk"][len("ord_"):]
        item = self.items[key]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        if ConditionExpression:
            if ("attribute_not_exists(#p)" in ConditionExpression
                    and "processing" in item):
                raise ConditionalFailed()
            if ("attribute_not_exists(expectedWorkId)" in ConditionExpression
                    and "expectedWorkId" in item):
                raise ConditionalFailed()
            if ("expectedWorkId = :w" in ConditionExpression
                    and item.get("expectedWorkId") != values.get(":w")):
                raise ConditionalFailed()
        set_part = UpdateExpression.split("REMOVE")[0].strip()
        if set_part.startswith("SET "):
            set_part = set_part[4:]
        for assignment in set_part.split(","):
            if "=" not in assignment:
                continue
            left, right = [s.strip() for s in assignment.split("=", 1)]
            item[names.get(left, left)] = values.get(right, right)
        return {"Attributes": dict(item)}


class ProfileStore:
    def get(self, profile_id):
        if profile_id != "ctx-partner-a":
            return None
        return {"apiProfileId": "ctx-partner-a", "status": "ACTIVE",
                "tenantId": "tenant-a", "userId": "partner-a-user"}


@unittest.skipUnless(MO_SRC and os.path.isdir(MO_SRC),
                     "MO_ORDERS_SRC not set")
class LambdaBridgeE2E(unittest.TestCase):
    def setUp(self):
        import identity as mo_identity
        import order_service as mo_orders
        import result_consumer
        import result_handler
        import index as mo_index
        import dispatch_ingress

        os.environ.update({
            "ORDERS_TABLE": "orders",
            "ORDERS_COGNITO_ISSUER": ISSUER,
            "ORDERS_COGNITO_CLIENT_ID": "client-a",
            "ORDER_RESULT_SECRET_ARN": "arn:aws:secretsmanager:eu-central-1:1:secret:x",
            "DISPATCH_QUEUE_ARN": QUEUE_ARN,
        })

        self.mo_index = mo_index
        self.mo_result_consumer = result_consumer
        self.dispatch_ingress = dispatch_ingress
        self.alice = mo_identity.OwnerIdentity(
            issuer=ISSUER, subject="partner-a-user", client_id="client-a")
        self.bob = mo_identity.OwnerIdentity(
            issuer=ISSUER, subject="partner-b-user", client_id="client-a")

        self.order_table = Table()
        self.work_table = Table()
        self.service = mo_orders.OrderService("orders", client=self.order_table)

        result_consumer.reset_cache()
        self.patches = [
            patch.object(mo_index, "create_order_service",
                         return_value=self.service),
            patch.object(result_handler, "create_order_service",
                         return_value=self.service),
            patch.object(result_consumer, "_fetch_secret",
                         return_value=[RESULT_SECRET]),
            patch.object(dispatch_ingress, "_dependencies", return_value={
                "profile_store": ProfileStore(),
                "registry": __import__("agents.ecosystem.registry",
                                       fromlist=["AgentRegistry"]).AgentRegistry(),
                "body": __import__("agents.agent_body",
                                   fromlist=["AgentBody"]).AgentBody(),
                "table": self.work_table,
                "entitlement_resolver": None,
            }),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.mo_result_consumer.reset_cache()
        for key in ("DISPATCH_QUEUE_ARN", "ORDER_RESULT_SECRET_ARN"):
            os.environ.pop(key, None)

    # -- helpers ---------------------------------------------------------
    def _event(self, identity, route, **kwargs):
        event = {"routeKey": route,
                 "requestContext": {"authorizer": {"jwt": {"claims": {
                     "iss": identity.issuer, "sub": identity.subject,
                     "client_id": identity.client_id,
                     "token_use": "access"}}}}}
        event.update(kwargs)
        return event

    def _create_order(self):
        body = {
            "orderType": "agent.execution",
            "agentOrder": {
                "schemaVersion": "1.0",
                "target": {"agentId": "addition_agent",
                           "capability": "math.add"},
                "input": {"data": {"left": 17, "right": 25}},
                "metadata": {"source": "ris", "requestId": "req-001",
                             "apiProfileRef": "ctx-partner-a",
                             "idempotencyKey": "idem-1"},
            },
        }
        response = self.mo_index.handler(
            self._event(self.alice, "POST /orders", body=json.dumps(body)), None)
        self.assertEqual(201, response["statusCode"])
        order_id = json.loads(response["body"])["orderId"]

        bound = self.service.prepare_dispatch(order_id, self.alice)
        envelope = self.service.dispatch_envelope(order_id, bound["workId"])
        return order_id, bound["workId"], envelope

    def _run_bridge(self):
        from agents.transport import result_from_work_item

        order_id, work_id, envelope = self._create_order()

        ingress_result = self.dispatch_ingress.handler(
            {"Records": [{"messageId": "msg-dispatch", "eventSourceARN": QUEUE_ARN,
                          "body": json.dumps(envelope)}]}, None)
        self.assertEqual([], ingress_result["batchItemFailures"])

        stored = self.work_table.items[work_id]
        self.assertEqual("COMPLETED", stored["status"])
        work_row = {
            "workId": work_id,
            "status": "COMPLETED",
            "attempt_no": stored.get("attempt_no", 1),
            "result": stored["result"]["data"],
        }
        result = result_from_work_item(envelope, work_row)

        response = self.mo_result_consumer.handler(
            {"Records": [self._result_record(result)]}, None)
        return order_id, work_id, result, response

    def _result_record(self, envelope, secret=RESULT_SECRET, message_id=None):
        from result_envelope import sign

        mid = message_id or envelope["messageId"]
        body = json.dumps(envelope)
        return {"messageId": mid, "body": body,
                "messageAttributes": {"serviceSignature": {
                    "stringValue": sign(secret, mid, body)}}}

    # -- tests -----------------------------------------------------------
    def test_full_bridge_returns_42_to_the_owner(self):
        order_id, _work_id, _result, response = self._run_bridge()
        self.assertEqual({"processed": 1, "rejected": 0},
                         json.loads(response["body"]))

        get = self.mo_index.handler(
            self._event(self.alice, "GET /orders/{orderId}",
                        pathParameters={"orderId": order_id}), None)
        self.assertEqual(200, get["statusCode"])
        body = json.loads(get["body"])
        self.assertEqual(42, body["processing"]["result"]["sum"])

    def test_foreign_partner_gets_404(self):
        order_id, _w, _r, _resp = self._run_bridge()
        get = self.mo_index.handler(
            self._event(self.bob, "GET /orders/{orderId}",
                        pathParameters={"orderId": order_id}), None)
        self.assertEqual(404, get["statusCode"])

    def test_duplicate_result_is_idempotent(self):
        _order_id, _w, result, _resp = self._run_bridge()
        again = self.mo_result_consumer.handler(
            {"Records": [self._result_record(result, message_id="m-dup")]}, None)
        self.assertEqual({"processed": 1, "rejected": 0},
                         json.loads(again["body"]))

    def test_tampered_result_is_rejected_by_the_consumer(self):
        _order_id, _w, result, _resp = self._run_bridge()
        record = self._result_record(result)
        record["body"] = json.dumps({**result, "payload": {"sum": 999}})
        response = self.mo_result_consumer.handler({"Records": [record]}, None)
        self.assertEqual(1, json.loads(response["body"])["rejected"])

    def test_no_secret_material_anywhere(self):
        order_id, _w, result, _resp = self._run_bridge()
        serialized = json.dumps({"order": self.order_table.items,
                                 "work": self.work_table.items,
                                 "result": result}, default=str)
        assert RESULT_SECRET not in serialized
        assert "ris_" not in serialized
        assert order_id


if __name__ == "__main__":
    unittest.main()
