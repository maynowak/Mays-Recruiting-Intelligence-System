#!/usr/bin/env python3
"""RIS Orders-Reader — eigene Order-Fassade in unserem Bereich.

Liest/schreibt Auftraege aus der Mays-Orders-Tabelle (gleiches Konto,
eigene IAM-Rolle, keine Aenderung am fremden Projekt) und liefert
HTTP-JSON ohne Decimal-Fehler (Gate-3-Befund: "Decimal is not JSON
serializable" in fremdem Handler).

Provenienz: Lesepfad + Statusregeln 1:1 aus dokumentiertem
Mays-Orders-Verhalten (Gate-2/3 verifiziert: PENDING->CONFIRMED->
PROCESSING->SHIPPED->DELIVERED, CANCELLED aus PENDING/CONFIRMED;
Fehlercodes 400/404/409/500). Eigene Implementierung, eigene Tests,
eigene Terraform-Ressourcen (terraform/modules/orders_reader).
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any, Dict, Optional

ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "mays-orders")
ORDER_ID_PREFIX = "ord_"
ORDER_SK = "#ORDER"
GSI1_PK = "LIST"
TABLE_INDEX_NAME = "gsi1"

INTERNAL_FIELDS = {"pk", "sk", "gsi1pk", "gsi1sk", "version", "isTestData"}

VALID_STATUSES = {
    "PENDING",
    "CONFIRMED",
    "PROCESSING",
    "SHIPPED",
    "DELIVERED",
    "CANCELLED",
}

# Zulaessige Uebergaenge (Gate-2/3-belegter Stand, keine Erweiterung).
TRANSITIONS = {
    "PENDING": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"SHIPPED"},
    "SHIPPED": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}

JSON_HEADERS = {"Content-Type": "application/json"}

_dynamodb_table = None


def _get_table():
    """Boto3-Tabelle lazy (Lambda-Runtime stellt boto3 bereit)."""
    global _dynamodb_table
    if _dynamodb_table is None:  # pragma: no cover - live Pfad, Tests injizieren Fake
        import boto3

        _dynamodb_table = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")
        ).Table(ORDERS_TABLE)
    return _dynamodb_table


def _json_default(value: Any) -> Any:
    """Ganzzahlige Decimals -> JSON-Integer, restliche Decimals -> Float."""
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _ok(status_code: int, payload: Any) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": json.dumps(payload, separators=(",", ":"), default=_json_default),
    }


def _err(status_code: int, code: str, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return {"statusCode": status_code, "headers": JSON_HEADERS, "body": json.dumps(body)}


def _public(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in item.items() if k not in INTERNAL_FIELDS}


def _list_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "orderId": item["orderId"],
        "status": item["status"],
        "customer": {"name": item["customer"]["name"]},
        "totalAmount": item["totalAmount"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
    }


def _list_orders(table: Any, limit: int) -> Dict[str, Any]:
    result = table.query(
        IndexName=TABLE_INDEX_NAME,
        KeyConditionExpression="gsi1pk = :pk",
        ExpressionAttributeValues={":pk": GSI1_PK},
        ScanIndexForward=False,
        Limit=limit,
    )
    orders = [_list_item(item) for item in result.get("Items", [])]
    return {"orders": orders, "count": len(orders)}


def _get_order(table: Any, order_id: str) -> Optional[Dict[str, Any]]:
    result = table.get_item(Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK})
    item = result.get("Item")
    return _public(item) if item else None


def _update_status(table: Any, order_id: str, new_status: str) -> Dict[str, Any]:
    """Gibt (http_code, payload) zurueck; 409 bei ungueltigem Uebergang/Race."""
    current = _get_order(table, order_id)
    if current is None:
        return 404, {"code": "ORDER_NOT_FOUND", "message": f"Order {order_id} not found"}
    if new_status not in TRANSITIONS.get(current["status"], set()):
        return 409, {
            "code": "INVALID_TRANSITION",
            "message": f"Transition from {current['status']} to {new_status} is not allowed",
            "details": {"currentStatus": current["status"], "requestedStatus": new_status},
        }
    try:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        result = table.update_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
            UpdateExpression="SET #status = :newStatus, updatedAt = :now, #version = #version + :one",
            ConditionExpression="attribute_exists(pk) AND #status = :currentStatus",
            ExpressionAttributeNames={"#status": "status", "#version": "version"},
            ExpressionAttributeValues={
                ":newStatus": new_status,
                ":currentStatus": current["status"],
                ":now": now,
                ":one": 1,
            },
            ReturnValues="ALL_NEW",
        )
        return 200, _public(result["Attributes"])
    except Exception as exc:
        if hasattr(exc, "response") and exc.response.get("Error", {}).get("Code") in (
            "ConditionalCheckFailedException",
        ):
            return 409, {"code": "CONFLICT", "message": "Order was modified concurrently"}
        raise


def _valid_order_id(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.startswith(ORDER_ID_PREFIX) and len(value) > len(ORDER_ID_PREFIX):
        return value
    return None


def handler(event: Dict[str, Any], context: Any, table: Any = None) -> Dict[str, Any]:
    """HTTP-API-v2-Einstieg (routeKey). `table` nur fuer Unit-Tests injizierbar."""
    tbl = table if table is not None else _get_table()
    try:
        route = event.get("routeKey", "")
        if route == "GET /orders":
            params = event.get("queryStringParameters") or {}
            try:
                limit = int(params.get("limit", "20"))
            except (TypeError, ValueError):
                return _err(400, "VALIDATION_ERROR", "Query parameter 'limit' must be an integer")
            if limit < 1 or limit > 100:
                return _err(400, "VALIDATION_ERROR", "Query parameter 'limit' must be 1..100")
            return _ok(200, _list_orders(tbl, limit))
        if route == "GET /orders/{orderId}":
            order_id = _valid_order_id((event.get("pathParameters") or {}).get("orderId"))
            if not order_id:
                return _err(400, "VALIDATION_ERROR", "Invalid orderId")
            order = _get_order(tbl, order_id)
            if order is None:
                return _err(404, "ORDER_NOT_FOUND", f"Order {order_id} not found")
            return _ok(200, order)
        if route == "PATCH /orders/{orderId}/status":
            order_id = _valid_order_id((event.get("pathParameters") or {}).get("orderId"))
            if not order_id:
                return _err(400, "VALIDATION_ERROR", "Invalid orderId")
            try:
                body = json.loads(event.get("body") or "{}")
            except (ValueError, TypeError):
                return _err(400, "VALIDATION_ERROR", "Request body must be valid JSON")
            status = body.get("status")
            if status not in VALID_STATUSES:
                return _err(400, "VALIDATION_ERROR", "Field 'status' must be a valid status value")
            code, payload = _update_status(tbl, order_id, status)
            if code != 200:
                return {"statusCode": code, "headers": JSON_HEADERS, "body": json.dumps({"error": payload})}
            return _ok(200, payload)
        return _err(400, "VALIDATION_ERROR", f"Unsupported route: {route}")
    except Exception as exc:  # pragma: no cover - letzte Sicherung, Tests pruefen Pfade gezielt
        import sys

        print(f"Unexpected error: {exc}", file=sys.stderr)
        return _err(500, "INTERNAL_ERROR", "Internal error")
