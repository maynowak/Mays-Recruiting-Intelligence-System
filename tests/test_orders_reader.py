"""Tests fuer RIS Orders-Reader (eigene Lambda, Gate 4).

Belegt: Decimal-sichere Responses (Gate-3-Befund), Statusregeln,
Fehlercodes — gegen Fake-Tabelle mit Boto3-typischen Decimals.
"""

import importlib.util
import json
import os
import sys
import unittest
from decimal import Decimal

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "orders_reader", os.path.join(_REPO_ROOT, "lambda", "orders_reader.py")
)
orders_reader = importlib.util.module_from_spec(_SPEC)
sys.modules["orders_reader"] = orders_reader
_SPEC.loader.exec_module(orders_reader)


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
    }


class FakeTable:
    def __init__(self, items):
        self._items = {i["orderId"]: dict(i) for i in items}
        self.updated = []

    def get_item(self, Key):
        for item in self._items.values():
            if item["pk"] == Key["pk"] and item["sk"] == Key["sk"]:
                return {"Item": dict(item)}
        return {}

    def query(self, **kwargs):
        items = sorted(self._items.values(), key=lambda i: i["gsi1sk"], reverse=True)
        return {"Items": [dict(i) for i in items[: kwargs.get("Limit", 20)]]}

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


def event(route, order_id=None, body=None, params=None):
    ev = {"routeKey": route}
    if order_id:
        ev["pathParameters"] = {"orderId": order_id}
    if body is not None:
        ev["body"] = json.dumps(body)
    if params is not None:
        ev["queryStringParameters"] = params
    return ev


class TestOrdersReaderDecimal(unittest.TestCase):
    def test_get_returns_200_with_integer_amounts(self):
        table = FakeTable([ddb_like_order()])
        resp = orders_reader.handler(event("GET /orders/{orderId}", "ord_test1"), None, table)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["status"], "CONFIRMED")
        self.assertEqual(body["totalAmount"], 300)
        self.assertNotIn("pk", body)
        self.assertNotIn("version", body)

    def test_decimals_never_leak_as_strings(self):
        table = FakeTable([ddb_like_order()])
        resp = orders_reader.handler(event("GET /orders/{orderId}", "ord_test1"), None, table)
        self.assertNotIn('"totalAmount":"300"', resp["body"])
        self.assertIn('"totalAmount":300', resp["body"])

    def test_list_returns_200(self):
        table = FakeTable([ddb_like_order("ord_a"), ddb_like_order("ord_b", "PENDING")])
        resp = orders_reader.handler(event("GET /orders", params={"limit": "10"}), None, table)
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["count"], 2)

    def test_patch_valid_transition_returns_200(self):
        table = FakeTable([ddb_like_order(status="CONFIRMED")])
        resp = orders_reader.handler(
            event("PATCH /orders/{orderId}/status", "ord_test1", {"status": "CANCELLED"}),
            None, table,
        )
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["status"], "CANCELLED")
        self.assertEqual(body["totalAmount"], 300)

    def test_patch_invalid_transition_returns_409(self):
        table = FakeTable([ddb_like_order(status="CANCELLED")])
        resp = orders_reader.handler(
            event("PATCH /orders/{orderId}/status", "ord_test1", {"status": "SHIPPED"}),
            None, table,
        )
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(json.loads(resp["body"])["error"]["code"], "INVALID_TRANSITION")

    def test_patch_invalid_status_returns_400(self):
        table = FakeTable([ddb_like_order()])
        resp = orders_reader.handler(
            event("PATCH /orders/{orderId}/status", "ord_test1", {"status": "NOPE"}),
            None, table,
        )
        self.assertEqual(resp["statusCode"], 400)

    def test_get_missing_returns_404(self):
        table = FakeTable([])
        resp = orders_reader.handler(event("GET /orders/{orderId}", "ord_nope"), None, table)
        self.assertEqual(resp["statusCode"], 404)

    def test_get_invalid_id_returns_400(self):
        table = FakeTable([])
        resp = orders_reader.handler(event("GET /orders/{orderId}", "bad-id"), None, table)
        self.assertEqual(resp["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
