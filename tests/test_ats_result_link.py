"""Phase 4: local ATS result-link integration through the RIS orders facade.

The only fakes are infrastructure boundaries: an in-memory work table, an
in-memory order table, a captured result sender, and the ATS HTTP client.
The worker pipeline, the ATS body builder, the Transport V1 mapping and the
real orders_reader handler are exercised unmodified.
"""

import copy
import importlib.util
import json
import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from agents.agent_body import AgentBody
from agents.ats_agent.agent import ATSHttpClient
from agents.ecosystem.registry import AgentRegistry
from agents.runtime.pipeline import process_record

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST"
CLIENT = "client-test"
OWNER_SUB = "owner-1"

os.environ.setdefault("ORDERS_TABLE", "mays-orders")
os.environ.setdefault(
    "ORDERS_SQS_QUEUE_URL",
    "https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-orders-queue")
os.environ.setdefault("ORDERS_COGNITO_ISSUER", ISSUER)
os.environ.setdefault("ORDERS_COGNITO_CLIENT_ID", CLIENT)

_SPEC = importlib.util.spec_from_file_location(
    "orders_reader_link", os.path.join(_REPO_ROOT, "lambda", "orders_reader.py")
)
orders_reader = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(orders_reader)

OWNER_KEY = orders_reader._owner_key(ISSUER, OWNER_SUB)


class WorkTable:
    class ConditionalFailed(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "ConditionalCheckFailedException"}}

    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        if ConditionExpression == "attribute_not_exists(workId)" and Item["workId"] in self.items:
            raise WorkTable.ConditionalFailed()
        self.items[Item["workId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, ConditionExpression=None):
        item = self.items[Key["workId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        expr = UpdateExpression.split("REMOVE")[0].strip()
        set_part = expr[len("SET "):] if expr.startswith("SET ") else expr
        for assign in set_part.split(","):
            left, right = [part.strip() for part in assign.split("=", 1)]
            item[names.get(left, left)] = values[right]
        if "REMOVE" in UpdateExpression:
            item.pop("error", None)


class OrderTable:
    def __init__(self, item):
        self.item = item

    def get_item(self, Key):
        if Key["pk"] == self.item["pk"] and Key["sk"] == self.item["sk"]:
            return {"Item": copy.deepcopy(self.item)}
        return {}


def work_record(order_id="ord_link1", correlation_id="corr-link1"):
    return {
        "messageId": "msg-link-1",
        "body": json.dumps({
            "workId": "work-link1",
            "type": "ats_process",
            "tenantId": "tenant-a",
            "userId": "user-1",
            "requestedBy": "user-1",
            "idempotencyKey": "key-link1",
            "agentId": "ats-agent",
            "capability": "analyze.job",
            "apiProfileId": "profile-a",
            "partnerApplicationId": "app-a",
            "issuer": ISSUER,
            "orderId": order_id,
            "correlationId": correlation_id,
            "transportMessageId": "msg-dispatch-1",
            "payload": {
                "job": {"title": "Senior Python Engineer",
                        "tags": ["Python", "AWS"],
                        "descriptionPlain": "We need Python and AWS."},
                "profile": {"skills": "Python, AWS"},
            },
        }),
    }


def order_item(order_id="ord_link1", correlation_id="corr-link1"):
    return {
        "pk": f"ord_{order_id}",
        "sk": "#ORDER",
        "orderId": order_id,
        "orderType": "agent.execution",
        "status": "PROCESSING",
        "customer": {"name": "Partner A", "email": "partner@example.com"},
        "items": [{"sku": "AGENT", "quantity": 1, "unitPrice": 1,
                   "lineTotal": 1}],
        "currency": "EUR",
        "totalAmount": 1,
        "createdAt": "2026-11-17T10:00:00.000Z",
        "updatedAt": "2026-11-17T10:00:00.000Z",
        "version": 1,
        "ownerIssuer": ISSUER,
        "ownerSubject": OWNER_SUB,
        "ownerKey": OWNER_KEY,
        "ownerClientId": CLIENT,
        "actorType": "user",
        "actorId": OWNER_SUB,
        "gsi3pk": OWNER_KEY,
        "gsi3sk": f"2026-11-17T10:00:00.000Z#{order_id}",
        "agentOrder": {
            "schemaVersion": "1.0",
            "target": {"agentId": "ats-agent", "capability": "analyze.job",
                       "agentVersion": "1.0.0"},
            "input": {"schemaVersion": "1.0", "data": {"job": {"title": "Senior Python Engineer"}}},
            "metadata": {"source": "partner-a", "requestId": correlation_id},
            "resultContract": {"schemaVersion": "1.0", "format": "json",
                               "expectedCapability": "analyze.job",
                               "delivery": "order_result"},
        },
    }


def reader_event(order_id="ord_link1", sub=OWNER_SUB):
    return {
        "routeKey": "GET /orders/{orderId}",
        "pathParameters": {"orderId": order_id},
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "iss": ISSUER, "sub": sub, "token_use": "access",
            "client_id": CLIENT, "aud": CLIENT,
        }}}},
    }


class AtsResultLinkTest(unittest.TestCase):
    def setUp(self):
        fixture_path = os.path.join(
            _REPO_ROOT, "tests", "fixtures", "ats_result_body",
            "score-50-partial.json")
        with open(fixture_path, encoding="utf-8") as handle:
            self.api_response = json.load(handle)
        self.work_table = WorkTable()
        self.order = order_item()
        self.order_table = OrderTable(self.order)
        self.sent = []

    def test_full_sequence_and_authorized_read_back(self):
        original = ATSHttpClient.analyze
        response = copy.deepcopy(self.api_response)
        ATSHttpClient.analyze = lambda client, job, profile=None: copy.deepcopy(
            response)
        try:
            out = process_record(
                work_record(), table=self.work_table,
                registry=AgentRegistry(), body=AgentBody(),
                result_sender=self.sent.append)
        finally:
            ATSHttpClient.analyze = original

        self.assertEqual(out["status"], "COMPLETED")
        self.assertEqual(out["agent_id"], "ats-agent")
        self.assertEqual(len(self.sent), 1)
        envelope = self.sent[0]
        self.assertEqual(envelope["messageType"], "ORDER_RESULT")
        self.assertEqual(envelope["orderId"], "ord_link1")
        self.assertEqual(envelope["correlationId"], "corr-link1")
        self.assertEqual(envelope["execution"],
                         {"workId": "work-link1", "attempt": 1})
        self.assertEqual(envelope["payload"]["bodyType"],
                         "ATSAnalysisResultBody")
        self.assertEqual(envelope["payload"]["bodyVersion"], "2.0")

        # Orders-side application of the result (consumer boundary).
        self.order["status"] = "PROCESSING"
        self.order["processing"] = {
            "status": "COMPLETED", "attempt": 1,
            "completedAt": "2026-11-17T10:00:05.000Z",
            "result": envelope["payload"],
        }

        mine = orders_reader.handler(reader_event(), None, self.order_table)
        self.assertEqual(mine["statusCode"], 200)
        body = json.loads(mine["body"])
        self.assertEqual(body["orderType"], "agent.execution")
        self.assertEqual(body["processing"]["result"]["bodyType"],
                         "ATSAnalysisResultBody")
        self.assertEqual(body["processing"]["result"]["bodyVersion"], "2.0")
        self.assertEqual(body["processing"]["result"]["analysis"]["score"], 50)
        self.assertEqual(body["agentOrder"]["target"]["agentId"], "ats-agent")

        foreign = orders_reader.handler(
            reader_event(sub="owner-2"), None, self.order_table)
        self.assertEqual(foreign["statusCode"], 404)

    def test_work_row_keeps_correlation_but_no_secret(self):
        original = ATSHttpClient.analyze
        response = copy.deepcopy(self.api_response)
        ATSHttpClient.analyze = lambda client, job, profile=None: copy.deepcopy(
            response)
        try:
            process_record(work_record(), table=self.work_table,
                           registry=AgentRegistry(), body=AgentBody(),
                           result_sender=self.sent.append)
        finally:
            ATSHttpClient.analyze = original
        row = self.work_table.items["work-link1"]
        self.assertEqual(row["orderId"], "ord_link1")
        self.assertEqual(row["correlationId"], "corr-link1")
        self.assertEqual(row["apiProfileId"], "profile-a")
        self.assertNotIn("titleTokens", json.dumps(row["result"], default=str))

    # ----- negative cases (Phase 4 required matrix) -----------------------

    def test_foreign_owner_cannot_read_the_result(self):
        self.order["processing"] = {
            "status": "COMPLETED", "attempt": 1,
            "result": {"bodyType": "ATSAnalysisResultBody", "bodyVersion": "2.0"},
        }
        other = orders_reader.handler(
            reader_event(sub="owner-2"), None, self.order_table)
        self.assertEqual(other["statusCode"], 404)
        self.assertNotIn("ATSAnalysisResultBody", other["body"])

    def test_foreign_tenant_issuer_cannot_read_the_result(self):
        event = reader_event()
        event["requestContext"]["authorizer"]["jwt"]["claims"]["iss"] = (
            "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_OTHER")
        resp = orders_reader.handler(event, None, self.order_table)
        self.assertEqual(resp["statusCode"], 401)
        self.assertNotIn("ATSAnalysisResultBody", resp["body"])

    def test_invalid_correlation_is_not_forwarded(self):
        record = work_record()
        body = json.loads(record["body"])
        body.pop("correlationId")
        record["body"] = json.dumps(body)
        self._run(record)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.work_table.items["work-link1"]["status"],
                         "COMPLETED")

    def test_duplicate_delivery_reemits_the_same_result(self):
        self._run(work_record())
        self._run(work_record())
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.sent[0]["messageId"], self.sent[1]["messageId"])
        self.assertEqual(self.sent[0]["idempotencyKey"],
                         self.sent[1]["idempotencyKey"])

    def test_missing_transport_configuration_does_not_claim_delivery(self):
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "ORDER_RESULT_QUEUE_URL": "",
            "ORDER_RESULT_SECRET_ARN": "",
        }):
            self._run(work_record(), inject_sender=False)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.work_table.items["work-link1"]["status"],
                         "COMPLETED")

    def test_unknown_order_cannot_be_read(self):
        resp = orders_reader.handler(
            reader_event(order_id="ord_doesnotexist"), None, self.order_table)
        self.assertEqual(resp["statusCode"], 404)
        self.assertEqual(json.loads(resp["body"])["error"]["code"],
                         "ORDER_NOT_FOUND")

    def test_disallowed_result_fields_are_never_forwarded(self):
        from agents.runtime.pipeline import _forward_order_result

        item = {
            "workId": "work-link1", "orderId": "ord_link1",
            "correlationId": "corr-link1", "apiProfileId": "profile-a",
        }
        _forward_order_result(
            item=item, attempt=1,
            result={"success": True, "data": {"api_key": "ris_" + "A" * 47}},
            sender=self.sent.append)
        self.assertEqual(self.sent, [])

    def test_tampered_result_is_not_released_by_the_reader(self):
        self.order["processing"] = {
            "status": "COMPLETED", "attempt": 1,
            "result": {"api_key": "ris_" + "A" * 47},
        }
        resp = orders_reader.handler(reader_event(), None, self.order_table)
        self.assertEqual(resp["statusCode"], 500)
        self.assertNotIn("ris_", resp["body"])
        self.assertNotIn("api_key", resp["body"])

    def _run(self, record, inject_sender=True):
        original = ATSHttpClient.analyze
        response = copy.deepcopy(self.api_response)
        ATSHttpClient.analyze = lambda client, job, profile=None: copy.deepcopy(
            response)
        try:
            if not inject_sender:
                return process_record(
                    record, table=self.work_table,
                    registry=AgentRegistry(), body=AgentBody())
            return process_record(
                record, table=self.work_table,
                registry=AgentRegistry(), body=AgentBody(),
                result_sender=self.sent.append)
        finally:
            ATSHttpClient.analyze = original



if __name__ == "__main__":
    unittest.main()
