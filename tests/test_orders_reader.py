"""Tests fuer RIS Orders-Reader (eigene Lambda, Gate 4 + Owner-Isolation).

Belegt: Decimal-sichere Responses, Statusregeln, Fehlercodes und die
serverseitige Owner-Bindung gegen Fake-Tabelle.
"""

import importlib.util
import json
import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST"
CLIENT = "client-test"
OWNER_SUB = "owner-1"

# Required at import (fail-closed binding validation).
os.environ.setdefault("ORDERS_TABLE", "mays-orders")
os.environ.setdefault(
    "ORDERS_SQS_QUEUE_URL",
    "https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-orders-queue")
os.environ.setdefault("ORDERS_COGNITO_ISSUER", ISSUER)
os.environ.setdefault("ORDERS_COGNITO_CLIENT_ID", CLIENT)

_SPEC = importlib.util.spec_from_file_location(
    "orders_reader", os.path.join(_REPO_ROOT, "lambda", "orders_reader.py")
)
orders_reader = importlib.util.module_from_spec(_SPEC)
sys.modules["orders_reader"] = orders_reader
_SPEC.loader.exec_module(orders_reader)

OWNER_KEY = orders_reader._owner_key(ISSUER, OWNER_SUB)

DEFAULT_CLAIMS = {
    "iss": ISSUER,
    "sub": OWNER_SUB,
    "token_use": "access",
    "client_id": CLIENT,
    "aud": CLIENT,
    "custom:tenant_id": "tenant-a",
}


def ddb_like_order(order_id="ord_test1", status="CONFIRMED"):
    return {
        "pk": f"ord_{order_id}",
        "sk": "#ORDER",
        "orderId": order_id,
        "status": status,
        "customer": {"name": "Reader Test", "email": "reader@example.com"},
        "items": [
            {"sku": "SKU-R", "quantity": Decimal(2), "unitPrice": Decimal(150),
             "lineTotal": Decimal(300)}
        ],
        "currency": "EUR",
        "totalAmount": Decimal(300),
        "createdAt": "2026-10-01T12:00:00.000Z",
        "updatedAt": "2026-10-01T12:00:05.000Z",
        "version": Decimal(1),
        "gsi1pk": "LIST",
        "gsi1sk": "2026-10-01T12:00:00.000Z",
        "ownerIssuer": ISSUER,
        "ownerSubject": OWNER_SUB,
        "ownerKey": OWNER_KEY,
        "ownerClientId": CLIENT,
        "actorType": "user",
        "actorId": OWNER_SUB,
        "gsi3pk": OWNER_KEY,
        "gsi3sk": f"2026-10-01T12:00:00.000Z#{order_id}",
    }


class FakeTable:
    def __init__(self, items):
        self._items = {i["orderId"]: dict(i) for i in items}
        self.updated = []
        self.last_query = None

    def get_item(self, Key):
        for item in self._items.values():
            if item["pk"] == Key["pk"] and item["sk"] == Key["sk"]:
                return {"Item": dict(item)}
        return {}

    def query(self, **kwargs):
        self.last_query = kwargs
        index = kwargs.get("IndexName")
        values = kwargs.get("ExpressionAttributeValues") or {}
        items = list(self._items.values())
        if index == "gsi3":
            items = [i for i in items if i.get("gsi3pk") == values.get(":owner")]
            sort_key = "gsi3sk"
        else:
            items = [i for i in items if i.get("gsi1pk") == values.get(":pk")]
            sort_key = "gsi1sk"
        items.sort(key=lambda i: i.get(sort_key, ""), reverse=True)
        return {"Items": [dict(i) for i in items[: kwargs.get("Limit", 20)]]}

    def put_item(self, Item, ConditionExpression=None):
        if ConditionExpression == "attribute_not_exists(pk)":
            if any(i["pk"] == Item["pk"] for i in self._items.values()):
                raise _ConditionalFail()
        self._items[Item["orderId"]] = dict(Item)

    def update_item(self, Key, UpdateExpression, ConditionExpression,
                    ExpressionAttributeNames, ExpressionAttributeValues,
                    ReturnValues):
        for item in self._items.values():
            if item["pk"] == Key["pk"] and item["sk"] == Key["sk"]:
                if item["status"] != ExpressionAttributeValues[":currentStatus"]:
                    raise _ConditionalFail()
                item["status"] = ExpressionAttributeValues[":newStatus"]
                item["updatedAt"] = ExpressionAttributeValues[":now"]
                item["version"] = item.get("version", Decimal(0)) + 1
                self.updated.append(item["orderId"])
                return {"Attributes": dict(item)}
        raise _ConditionalFail()


class _ConditionalFail(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


def event(route, order_id=None, body=None, params=None, claims="default"):
    ev = {"routeKey": route}
    if claims is not None:
        if claims == "default":
            claims = dict(DEFAULT_CLAIMS)
        ev["requestContext"] = {
            "authorizer": {"jwt": {"claims": claims}}
        }
    if order_id:
        ev["pathParameters"] = {"orderId": order_id}
    if body is not None:
        ev["body"] = json.dumps(body)
    if params is not None:
        ev["queryStringParameters"] = params
    return ev


class TestOrdersReaderAuthorization(unittest.TestCase):
    def test_get_without_identity_returns_401(self):
        table = FakeTable([ddb_like_order()])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1", claims=None), None, table)
        self.assertEqual(resp["statusCode"], 401)

    def test_get_with_missing_sub_returns_401(self):
        table = FakeTable([ddb_like_order()])
        claims = dict(DEFAULT_CLAIMS)
        claims.pop("sub")
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1", claims=claims), None, table)
        self.assertEqual(resp["statusCode"], 401)

    def test_get_with_wrong_issuer_returns_401(self):
        table = FakeTable([ddb_like_order()])
        claims = dict(DEFAULT_CLAIMS, iss="https://cognito-idp.eu-central-1.amazonaws.com/other")
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1", claims=claims), None, table)
        self.assertEqual(resp["statusCode"], 401)

    def test_get_with_wrong_client_returns_401(self):
        table = FakeTable([ddb_like_order()])
        claims = dict(DEFAULT_CLAIMS, client_id="other", aud="other")
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1", claims=claims), None, table)
        self.assertEqual(resp["statusCode"], 401)

    def test_get_with_invalid_token_use_returns_401(self):
        table = FakeTable([ddb_like_order()])
        claims = dict(DEFAULT_CLAIMS, token_use="refresh")
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1", claims=claims), None, table)
        self.assertEqual(resp["statusCode"], 401)

    def test_missing_identity_config_returns_503(self):
        table = FakeTable([ddb_like_order()])
        with patch.dict(os.environ, {
            "ORDERS_COGNITO_ISSUER": "",
            "ORDERS_COGNITO_CLIENT_ID": "",
        }):
            resp = orders_reader.handler(
                event("GET /orders/{orderId}", "ord_test1"), None, table)
        self.assertEqual(resp["statusCode"], 503)

    def test_foreign_owner_returns_404(self):
        table = FakeTable([ddb_like_order()])
        claims = dict(DEFAULT_CLAIMS, sub="owner-2")
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1", claims=claims), None, table)
        self.assertEqual(resp["statusCode"], 404)
        self.assertEqual(json.loads(resp["body"])["error"]["code"],
                         "ORDER_NOT_FOUND")

    def test_legacy_unbound_order_returns_404(self):
        item = ddb_like_order()
        for key in ("ownerIssuer", "ownerSubject", "ownerKey", "gsi3pk", "gsi3sk"):
            item.pop(key, None)
        table = FakeTable([item])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1"), None, table)
        self.assertEqual(resp["statusCode"], 404)

    def test_list_uses_owner_index_and_isolates_owners(self):
        mine = ddb_like_order("ord_mine")
        foreign = ddb_like_order("ord_foreign")
        foreign.update({
            "ownerKey": orders_reader._owner_key(ISSUER, "owner-2"),
            "gsi3pk": orders_reader._owner_key(ISSUER, "owner-2"),
            "gsi3sk": "2026-10-01T12:00:00.000Z#ord_foreign",
        })
        table = FakeTable([mine, foreign])
        resp = orders_reader.handler(
            event("GET /orders", params={"limit": "10"}), None, table)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["orders"][0]["orderId"], "ord_mine")
        self.assertEqual(table.last_query["IndexName"], "gsi3")
        self.assertEqual(table.last_query["ExpressionAttributeValues"][":owner"],
                         OWNER_KEY)

    def test_patch_foreign_owner_returns_404_and_does_not_change(self):
        table = FakeTable([ddb_like_order(status="CONFIRMED")])
        claims = dict(DEFAULT_CLAIMS, sub="owner-2")
        resp = orders_reader.handler(
            event("PATCH /orders/{orderId}/status", "ord_test1",
                  {"status": "CANCELLED"}, claims=claims), None, table)
        self.assertEqual(resp["statusCode"], 404)
        self.assertEqual(table._items["ord_test1"]["status"], "CONFIRMED")


class TestOrdersReaderProjection(unittest.TestCase):
    def _agent_order(self):
        item = ddb_like_order("ord_agent", "PROCESSING")
        item.update({
            "orderType": "agent.execution",
            "agentOrder": {
                "schemaVersion": "1.0",
                "target": {"agentId": "ats-agent", "capability": "analyze.job",
                           "agentVersion": "1.0.0"},
                "input": {"schemaVersion": "1.0",
                          "data": {"job": {"title": "QA Engineer"}}},
                "metadata": {
                    "source": "test", "requestId": "corr-1",
                    "apiProfileRef": "profile-a",
                    "partnerApplicationRef": "app-a",
                    "idempotencyKey": "idem-1",
                },
                "resultContract": {"schemaVersion": "1.0", "format": "json",
                                   "expectedCapability": "analyze.job",
                                   "delivery": "order_result"},
                "processing": {"status": "RUNNING"},
            },
            "agentOrderFingerprint": "fp",
            "expectedWorkId": "work-1",
            "dispatch": {"status": "PENDING"},
            "processing": {
                "status": "COMPLETED", "attempt": 1,
                "completedAt": "2026-10-01T12:00:05.000Z",
                "workId": "work-1", "messageId": "m-1",
                "idempotencyKey": "idem-1", "executionId": "exec-1",
                "result": {"bodyType": "ATSAnalysisResultBody",
                           "bodyVersion": "2.0",
                           "analysis": {"score": 50}},
            },
            "subjectId": "subject-1",
            "gsi2pk": "gsi2", "gsi2sk": "x",
        })
        return item

    def test_agent_projection_is_whitelisted(self):
        table = FakeTable([self._agent_order()])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_agent"), None, table)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["orderType"], "agent.execution")
        self.assertEqual(body["agentOrder"]["target"]["agentId"], "ats-agent")
        self.assertEqual(body["agentOrder"]["metadata"],
                         {"source": "test", "requestId": "corr-1"})
        self.assertEqual(body["processing"]["result"]["bodyVersion"], "2.0")
        serialized = json.dumps(body)
        for forbidden in (
            "ownerKey", "ownerIssuer", "ownerSubject", "gsi3pk", "gsi3sk",
            "gsi2pk", "subjectId", "agentOrderFingerprint", "expectedWorkId",
            "dispatch", "apiProfileRef", "partnerApplicationRef",
            "idempotencyKey", "workId", "messageId", "executionId",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_secret_shaped_result_returns_500_without_leak(self):
        item = ddb_like_order()
        item["processing"] = {
            "status": "COMPLETED", "attempt": 1,
            "result": {"api_key": "ris_" + "A" * 47},
        }
        table = FakeTable([item])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1"), None, table)
        self.assertEqual(resp["statusCode"], 500)
        self.assertNotIn("ris_", resp["body"])
        self.assertNotIn("api_key", resp["body"])

    def test_create_binds_owner_and_is_readable_only_by_owner(self):
        table = FakeTable([])
        body = {
            "customer": {"name": "Reader Test", "email": "reader@example.com"},
            "items": [{"sku": "SKU-R", "quantity": 2, "unitPrice": 150}],
            "currency": "EUR",
        }
        with patch.object(orders_reader, "_send_order_created", return_value=None):
            resp = orders_reader.handler(event("POST /orders", body=body), None, table)
        self.assertEqual(resp["statusCode"], 201)
        created = json.loads(resp["body"])
        order_id = created["orderId"]
        stored = table._items[order_id]
        self.assertEqual(stored["ownerKey"], OWNER_KEY)
        self.assertEqual(stored["ownerSubject"], OWNER_SUB)
        self.assertEqual(stored["gsi3pk"], OWNER_KEY)

        mine = orders_reader.handler(
            event("GET /orders/{orderId}", order_id), None, table)
        self.assertEqual(mine["statusCode"], 200)
        foreign = orders_reader.handler(
            event("GET /orders/{orderId}", order_id,
                  claims=dict(DEFAULT_CLAIMS, sub="owner-2")), None, table)
        self.assertEqual(foreign["statusCode"], 404)


class TestOrdersReaderDecimal(unittest.TestCase):
    def test_get_returns_200_with_integer_amounts(self):
        table = FakeTable([ddb_like_order()])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1"), None, table)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["status"], "CONFIRMED")
        self.assertEqual(body["totalAmount"], 300)
        self.assertNotIn("pk", body)
        self.assertNotIn("version", body)

    def test_decimals_never_leak_as_strings(self):
        table = FakeTable([ddb_like_order()])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_test1"), None, table)
        self.assertNotIn('"totalAmount":"300"', resp["body"])
        self.assertIn('"totalAmount":300', resp["body"])

    def test_list_returns_200(self):
        table = FakeTable([ddb_like_order("ord_a"), ddb_like_order("ord_b", "PENDING")])
        resp = orders_reader.handler(
            event("GET /orders", params={"limit": "10"}), None, table)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 2)

    def test_patch_valid_transition_returns_200(self):
        table = FakeTable([ddb_like_order(status="CONFIRMED")])
        resp = orders_reader.handler(
            event("PATCH /orders/{orderId}/status", "ord_test1",
                  {"status": "CANCELLED"}), None, table)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["status"], "CANCELLED")
        self.assertEqual(body["totalAmount"], 300)

    def test_patch_invalid_transition_returns_409(self):
        table = FakeTable([ddb_like_order(status="CANCELLED")])
        resp = orders_reader.handler(
            event("PATCH /orders/{orderId}/status", "ord_test1",
                  {"status": "SHIPPED"}), None, table)
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(json.loads(resp["body"])["error"]["code"],
                         "INVALID_TRANSITION")

    def test_patch_invalid_status_returns_400(self):
        table = FakeTable([ddb_like_order()])
        resp = orders_reader.handler(
            event("PATCH /orders/{orderId}/status", "ord_test1",
                  {"status": "NOPE"}), None, table)
        self.assertEqual(resp["statusCode"], 400)

    def test_get_missing_returns_404(self):
        table = FakeTable([])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_nope"), None, table)
        self.assertEqual(resp["statusCode"], 404)

    def test_get_invalid_id_returns_400(self):
        table = FakeTable([])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "bad-id"), None, table)
        self.assertEqual(resp["statusCode"], 400)

    def test_get_id_with_separator_returns_400(self):
        table = FakeTable([])
        resp = orders_reader.handler(
            event("GET /orders/{orderId}", "ord_../x"), None, table)
        self.assertEqual(resp["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
