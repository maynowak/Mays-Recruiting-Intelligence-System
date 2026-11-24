"""Local product E2E: agent order -> dispatch -> ATS -> result -> read-back.

The RIS reader, the real dispatch ingress, the real pipeline, the ATS agent,
the Transport V1 forwarder, the pinned Orders result consumer and the RIS
reader are exercised without AWS. Only DynamoDB/SQS/HTTP boundaries are faked.
"""

import importlib.util
import json
import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "lambda"))

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_OYN9QiHc5"
CLIENT = "5jgjivk9k9rrjos62so1qhq8o3"
OWNER = "owner-e2e"
PROFILE_ID = "aprof-e2e"
QUEUE_ARN = "arn:aws:sqs:eu-central-1:262370457690:ris-dev2-dev-agent-dispatch"

os.environ.setdefault("ORDERS_TABLE", "ris-dev2-mays-orders")
os.environ.setdefault(
    "ORDERS_SQS_QUEUE_URL",
    "https://sqs.eu-central-1.amazonaws.com/262370457690/ris-dev2-mays-orders-orders-queue")

_SPEC = importlib.util.spec_from_file_location(
    "orders_reader_e2e", os.path.join(_REPO, "lambda", "orders_reader.py"))
orders_reader = importlib.util.module_from_spec(_SPEC)
sys.modules["orders_reader_e2e"] = orders_reader
_SPEC.loader.exec_module(orders_reader)

MO_SRC = os.environ.get("MO_ORDERS_SRC", "")
if MO_SRC:
    sys.path.insert(0, MO_SRC)

import dispatch_ingress  # noqa: E402
from agents.agent_body import AgentBody  # noqa: E402
from agents.ats_agent.agent import ATSHttpClient  # noqa: E402
from agents.ecosystem.registry import AgentRegistry  # noqa: E402
from agents.runtime import pipeline as pipeline_module  # noqa: E402


class ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class OrderTable:
    """Order table double for the reader, the consumer and the read-back."""

    def __init__(self):
        self.items = {}
        self.updates = 0

    def put_item(self, Item, ConditionExpression=None):
        if (ConditionExpression == "attribute_not_exists(pk)"
                and Item["pk"] in {i["pk"] for i in self.items.values()}):
            raise ConditionalFailed()
        self.items[Item["orderId"]] = dict(Item)

    def get_item(self, Key):
        for item in self.items.values():
            if item["pk"] == Key["pk"] and item["sk"] == Key["sk"]:
                return {"Item": dict(item)}
        return {}

    def query(self, **kwargs):
        values = kwargs.get("ExpressionAttributeValues") or {}
        items = [dict(i) for i in self.items.values()
                 if i.get("gsi3pk") == values.get(":owner")]
        return {"Items": items}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, **kwargs):
        item = next((i for i in self.items.values()
                     if i["pk"] == Key["pk"] and i["sk"] == Key["sk"]), None)
        if item is None:
            raise ConditionalFailed()
        values = ExpressionAttributeValues or {}
        names = ExpressionAttributeNames or {}
        if (ConditionExpression and "attribute_not_exists(#p)" in ConditionExpression
                and "processing" in item):
            raise ConditionalFailed()
        self.updates += 1
        set_part = UpdateExpression.split("REMOVE")[0].strip()
        if set_part.startswith("SET "):
            set_part = set_part[4:]
        for assignment in set_part.split(","):
            if "=" not in assignment:
                continue
            left, right = [p.strip() for p in assignment.split("=", 1)]
            field = names.get(left, left)
            if "+" in right and ":one" in values:
                item[field] = int(item.get(field, 0)) + int(values[":one"])
            else:
                item[field] = values[right]
        return {"Attributes": dict(item)}


class WorkTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        if (ConditionExpression == "attribute_not_exists(workId)"
                and Item["workId"] in self.items):
            raise ConditionalFailed()
        self.items[Item["workId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, ConditionExpression=None):
        item = self.items[Key["workId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        set_part = UpdateExpression.split("REMOVE")[0].strip()
        if set_part.startswith("SET "):
            set_part = set_part[4:]
        for assignment in set_part.split(","):
            left, right = [p.strip() for p in assignment.split("=", 1)]
            item[names.get(left, left)] = values[right]
        return {"Attributes": dict(item)}


class ProfileTable:
    def __init__(self, row):
        self.row = dict(row)

    def get_item(self, Key):
        return {"Item": dict(self.row)} if Key["apiProfileId"] == self.row["apiProfileId"] else {}


class ProfileStore:
    def __init__(self, row):
        self.row = dict(row)

    def get_profile(self, profile_id):
        return dict(self.row) if profile_id == self.row["apiProfileId"] else None


class Entitlements:
    def __init__(self, rows):
        self.rows = list(rows)

    def find_entitlements(self, user_id):
        return [dict(r) for r in self.rows if r.get("userId") == user_id]


def claims(sub=OWNER):
    return {"iss": ISSUER, "sub": sub, "token_use": "access",
            "client_id": CLIENT, "aud": CLIENT}


def event(route, body=None, order_id=None, sub=OWNER):
    ev = {"routeKey": route,
          "requestContext": {"authorizer": {"jwt": {"claims": claims(sub)}}}}
    if body is not None:
        ev["body"] = json.dumps(body)
    if order_id:
        ev["pathParameters"] = {"orderId": order_id}
    return ev


def agent_body(**overrides):
    from agents.orders.agent_order import serialize_agent_order_description

    document = {
        "schemaVersion": "1.0",
        "target": {"agentId": "ats-agent", "capability": "analyze.job"},
        "input": {"schemaVersion": "1.0",
                  "data": {"job": {"title": "Senior Python Engineer",
                                   "tags": ["Python", "AWS"],
                                   "descriptionPlain": "Python and AWS."},
                           "profile": {"skills": "Python, AWS"}}},
        "metadata": {"source": "e2e", "requestId": "corr-e2e",
                     "apiProfileRef": PROFILE_ID},
    }
    body = {
        "orderType": "agent.execution",
        "customer": {"name": "Mays", "email": "ops@example.com"},
        "items": [{"sku": "ATS", "quantity": 1, "unitPrice": 100}],
        "currency": "EUR",
        "orderDescription": serialize_agent_order_description(document),
    }
    body.update(overrides)
    return body


class FakeSQS:
    def __init__(self):
        self.sent = []

    def send_message(self, **kwargs):
        self.sent.append(kwargs)


@unittest.skipUnless(MO_SRC, "MO_ORDERS_SRC is required for the consumer")
class TestAgentOrderDispatchE2E(unittest.TestCase):
    def setUp(self):
        self.orders = OrderTable()
        self.work = WorkTable()
        self.profile_row = {"apiProfileId": PROFILE_ID, "status": "ACTIVE",
                            "ownerUserId": OWNER, "tenantId": "tenant-e2e"}
        self.profile_table = ProfileTable(self.profile_row)
        self.profile_store = ProfileStore(self.profile_row)
        self.entitlements = Entitlements([{
            "userId": OWNER, "tenantId": "tenant-e2e",
            "agentId": "ats-agent", "entitlementId": "ent-e2e"}])
        self.registry = AgentRegistry()
        self.body = AgentBody()
        self.dispatched = []
        self.results = []
        self.sqs = FakeSQS()
        self._patches = [
            patch.object(orders_reader, "_send_order_dispatch",
                         side_effect=self.dispatched.append),
            patch.object(dispatch_ingress, "_dependencies", return_value={
                "profile_store": self.profile_store,
                "table": self.work,
                "sqs_client": self.sqs,
                "work_queue_url": "https://sqs.eu-central-1.amazonaws.com/1/work",
            }),
            patch.object(pipeline_module, "_resolve_result_sender",
                         return_value=self.results.append),
        ]
        for p in self._patches:
            p.start()
        self._env = patch.dict(os.environ, {
            "DISPATCH_QUEUE_ARN": QUEUE_ARN,
            "ORDERS_COGNITO_ISSUER": ISSUER,
            "ORDERS_COGNITO_CLIENT_ID": CLIENT,
        })
        self._env.start()

    def tearDown(self):
        self._env.stop()
        for p in self._patches:
            p.stop()

    def _create_agent_order(self, body=None):
        return orders_reader.handler(
            event("POST /orders", body=body or agent_body()), None,
            self.orders, profile_table=self.profile_table,
            entitlement_resolver=self.entitlements)

    def _dispatch(self, envelope, message_id="sqs-dispatch-1"):
        result = dispatch_ingress.handler({"Records": [{
            "messageId": message_id,
            "eventSourceARN": QUEUE_ARN,
            "body": json.dumps(envelope),
        }]}, None)
        # The ingress persists + enqueues; the shared worker executes the
        # queued work item in this harness.
        for message in self.sqs.sent:
            pipeline_module.process_record(
                {"body": message["MessageBody"]},
                table=self.work, registry=self.registry, body=self.body,
                entitlement_resolver=self.entitlements,
                result_sender=self.results.append)
        self.sqs.sent.clear()
        return result

    def test_agent_order_round_trip_and_authorized_read_back(self):
        from result_envelope import sign
        from result_handler import process_records
        from order_service import OrderService

        response = self._create_agent_order()
        self.assertEqual(201, response["statusCode"], response["body"])
        created = json.loads(response["body"])
        order_id = created["orderId"]
        self.assertEqual(1, len(self.dispatched))
        envelope = self.dispatched[0]
        self.assertEqual(order_id, envelope["orderId"])

        with open(os.path.join(_REPO, "tests", "fixtures", "ats_result_body",
                               "score-50-partial.json"), encoding="utf-8") as fh:
            ats_body = json.load(fh)
        with patch.object(ATSHttpClient, "analyze",
                          return_value=ats_body):
            out = self._dispatch(envelope)
        self.assertEqual([], out["batchItemFailures"])
        work = self.work.items[envelope["execution"]["workId"]]
        self.assertEqual("COMPLETED", work["status"])
        self.assertEqual(order_id, work["orderId"])
        self.assertEqual("corr-e2e", work["correlationId"])
        self.assertEqual(PROFILE_ID, work["apiProfileId"])
        self.assertEqual("SENT", work["orderResultDelivery"]["status"])
        self.assertEqual(1, len(self.results))
        result = self.results[0]
        self.assertEqual("ORDER_RESULT", result["messageType"])

        body = json.dumps(result, separators=(",", ":"))
        signature = sign("test-secret", result["messageId"], body)
        record = {"messageId": "11111111-2222-3333-4444-555555555555",
                  "body": body,
                  "messageAttributes": {"serviceSignature": {
                      "stringValue": signature}}}
        service = OrderService("orders", client=self.orders)
        consumer = process_records([record], ["test-secret"], service=service)
        self.assertEqual({"processed": 1, "rejected": 0},
                         json.loads(consumer["body"]))

        stored = self.orders.items[order_id]
        self.assertEqual("PENDING", stored["status"])
        self.assertEqual("COMPLETED", stored["processing"]["status"])
        self.assertEqual("ATSAnalysisResultBody",
                         stored["processing"]["result"]["bodyType"])
        self.assertEqual("2.0", stored["processing"]["result"]["bodyVersion"])
        self.assertEqual(50, stored["processing"]["result"]["analysis"]["score"])

        read = orders_reader.handler(
            event("GET /orders/{orderId}", order_id=order_id), None, self.orders)
        self.assertEqual(200, read["statusCode"])
        public = json.loads(read["body"])
        self.assertEqual("agent.execution", public["orderType"])
        self.assertEqual("2.0", public["processing"]["result"]["bodyVersion"])
        self.assertEqual(50, public["processing"]["result"]["analysis"]["score"])

        foreign = orders_reader.handler(
            event("GET /orders/{orderId}", order_id=order_id, sub="owner-other"),
            None, self.orders)
        self.assertEqual(404, foreign["statusCode"])

    def test_duplicate_result_does_not_write_twice(self):
        from result_envelope import sign
        from result_handler import process_records
        from order_service import OrderService

        order_id = json.loads(self._create_agent_order()["body"])["orderId"]
        with open(os.path.join(_REPO, "tests", "fixtures", "ats_result_body",
                               "score-50-partial.json"), encoding="utf-8") as fh:
            ats_body = json.load(fh)
        with patch.object(ATSHttpClient, "analyze", return_value=ats_body):
            self._dispatch(self.dispatched[0])
        result = self.results[0]
        body = json.dumps(result, separators=(",", ":"))
        record = {"messageId": "11111111-2222-3333-4444-555555555555",
                  "body": body,
                  "messageAttributes": {"serviceSignature": {
                      "stringValue": sign("test-secret", result["messageId"], body)}}}
        service = OrderService("orders", client=self.orders)
        process_records([record], ["test-secret"], service=service)
        before = dict(self.orders.items[order_id]["processing"])
        writes = self.orders.updates
        process_records([record], ["test-secret"], service=service)
        self.assertEqual(before, self.orders.items[order_id]["processing"])
        self.assertEqual(writes, self.orders.updates)

    def test_invalid_signature_is_rejected_without_persistence(self):
        from result_handler import process_records
        from order_service import OrderService

        order_id = json.loads(self._create_agent_order()["body"])["orderId"]
        with open(os.path.join(_REPO, "tests", "fixtures", "ats_result_body",
                               "score-50-partial.json"), encoding="utf-8") as fh:
            ats_body = json.load(fh)
        with patch.object(ATSHttpClient, "analyze", return_value=ats_body):
            self._dispatch(self.dispatched[0])
        result = self.results[0]
        body = json.dumps(result, separators=(",", ":"))
        record = {"messageId": "11111111-2222-3333-4444-555555555555",
                  "body": body,
                  "messageAttributes": {"serviceSignature": {
                      "stringValue": "forged"}}}
        out = process_records([record], ["test-secret"],
                              service=OrderService("orders", client=self.orders))
        self.assertEqual(1, json.loads(out["body"])["rejected"])
        self.assertNotIn("processing", self.orders.items[order_id])

    def test_missing_entitlement_produces_no_result(self):
        self.entitlements.rows = []
        self._create_agent_order()
        with patch.object(ATSHttpClient, "analyze",
                          side_effect=AssertionError("must not execute")):
            if self.dispatched:
                self._dispatch(self.dispatched[0])
        self.assertEqual([], self.results)
        self.assertTrue(all(
            item.get("status") != "COMPLETED" for item in self.work.items.values()))

    def test_retail_order_is_never_dispatched(self):
        body = {"customer": {"name": "Retail", "email": "r@example.com"},
                "items": [{"sku": "S", "quantity": 1, "unitPrice": 10}]}
        with patch.object(orders_reader, "_send_order_created", return_value=None):
            response = orders_reader.handler(
                event("POST /orders", body=body), None, self.orders)
        self.assertEqual(201, response["statusCode"])
        self.assertEqual([], self.dispatched)
        order_id = json.loads(response["body"])["orderId"]
        self.assertNotIn("agentOrder", self.orders.items[order_id])

    def test_foreign_profile_is_rejected_before_persistence(self):
        self.profile_table.row["ownerUserId"] = "owner-other"
        response = self._create_agent_order()
        self.assertEqual(403, response["statusCode"])
        self.assertEqual({}, self.orders.items)
        self.assertEqual([], self.dispatched)


if __name__ == "__main__":
    unittest.main()
