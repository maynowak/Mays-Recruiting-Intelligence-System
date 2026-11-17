#!/usr/bin/env python3
"""RIS Orders-Reader — eigene Order-Fassade in unserem Bereich.

Liest/schreibt Auftraege aus der Mays-Orders-Tabelle (gleiches Konto,
eigene IAM-Rolle, keine Aenderung am fremden Projekt) und liefert
HTTP-JSON ohne Decimal-Fehler (Gate-3-Befund: "Decimal is not JSON
serializable" in fremdem Handler).

Owner-Bindung: Die Identitaet kommt ausschliesslich aus den vom API-Gateway
verifizierten JWT-Claims (iss + sub). Der Owner-Key wird identisch zum
Orders-Modul gebildet (sha256(iss + NUL + sub)). Ein fremder, fehlender oder
legacy-ungebundener Owner liefert 404; ein gueltiges JWT allein genuegt nicht.
Die Orders-Items tragen keinen Tenant; die Tenant-Grenze ist der gepinnte
Issuer/Client plus die Owner-Bindung.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from decimal import Decimal
from typing import Any, Dict, Optional

try:  # repository layout / tests (package takes precedence)
    from agents.orders.agent_order import (
        AgentOrderError,
        fingerprint as agent_order_fingerprint,
        validate_order_document,
    )
    from agents.transport.order_transport import (
        ORDER_DISPATCH,
        TransportError,
        build_dispatch_envelope,
    )
except ImportError:  # Lambda reader bundle (flat contract modules)
    from agent_order import (
        AgentOrderError,
        fingerprint as agent_order_fingerprint,
        validate_order_document,
    )
    from order_transport import (
        ORDER_DISPATCH,
        TransportError,
        build_dispatch_envelope,
    )

ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "")
ORDERS_SQS_QUEUE_URL = os.environ.get("ORDERS_SQS_QUEUE_URL", "")
RIS_DISPATCH_QUEUE_URL = os.environ.get("RIS_DISPATCH_QUEUE_URL", "")
API_PROFILES_TABLE = os.environ.get("API_PROFILES_TABLE", "")
# Validate non-empty binding (fail-closed: reject missing binding at runtime)
if not ORDERS_TABLE:
    raise RuntimeError("ORDERS_TABLE environment variable must be set")
if not ORDERS_SQS_QUEUE_URL:
    raise RuntimeError("ORDERS_SQS_QUEUE_URL environment variable must be set")
if "mays-orders-orders-queue" in ORDERS_SQS_QUEUE_URL and "-mays-orders" not in ORDERS_TABLE:
    # Detect fallback attempt to standalone mays-orders when project != mays-orders
    if ORDERS_TABLE != "mays-orders":
        raise RuntimeError(
            f"ORDERS_SQS_QUEUE_URL appears to bind to standalone mays-orders "
            f"but ORDERS_TABLE is {ORDERS_TABLE!r} — reject implicit fallback"
        )

ORDER_ID_PREFIX = "ord_"
ORDER_SK = "#ORDER"
GSI1_PK = "LIST"
GSI3_INDEX = "gsi3"
OWNER_INDEX_KEY = "gsi3pk"
ORDER_ID_RE = re.compile(r"^ord_[A-Za-z0-9]{1,64}$")

# Public projection: explicit allowlists, never a blacklist copy.
PUBLIC_CUSTOMER_FIELDS = ("name", "email")
PUBLIC_ITEM_FIELDS = ("sku", "quantity", "unitPrice", "lineTotal")
PUBLIC_AGENT_TARGET_FIELDS = ("agentId", "capability", "agentVersion")
PUBLIC_AGENT_INPUT_FIELDS = ("schemaVersion", "data")
PUBLIC_AGENT_METADATA_FIELDS = ("source", "requestId")
PUBLIC_RESULT_CONTRACT_FIELDS = (
    "schemaVersion", "format", "expectedCapability", "delivery")
PUBLIC_PROCESSING_FIELDS = ("status", "attempt", "completedAt")
MAX_ERROR_MESSAGE = 500

# Same credential-shaped rule as the transport; the reader refuses to release
# a stored result that contains a secret-like key or value.
FORBIDDEN_KEY_PARTS = (
    "secret", "apikey", "api_key", "password", "passwd", "credential",
    "authorization", "bearer", "token", "jwt", "privatekey", "private_key",
)
FORBIDDEN_VALUE_PREFIXES = ("ris_", "Bearer ", "bearer ")

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


class PublicPayloadError(ValueError):
    """Stored data cannot be released without leaking a secret."""


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


def _err(status_code: int, code: str, message: str,
         details: Optional[Dict] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return {"statusCode": status_code, "headers": JSON_HEADERS,
            "body": json.dumps(body)}


def _normalize_issuer(value: Any) -> str:
    return str(value).strip().rstrip("/")


def _owner_key(issuer: Any, subject: Any) -> str:
    material = f"{_normalize_issuer(issuer)}\x00{subject}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _claims(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    context = event.get("requestContext") or {}
    authorizer = context.get("authorizer") or {}
    jwt = authorizer.get("jwt") or {}
    claims = jwt.get("claims")
    return claims if isinstance(claims, dict) else None


def _identity(event: Dict[str, Any]):
    """Return (identity, error_response). Request-time config, fail-closed."""
    issuer_config = os.environ.get("ORDERS_COGNITO_ISSUER", "").strip()
    client_config = os.environ.get("ORDERS_COGNITO_CLIENT_ID", "").strip()
    if not issuer_config or not client_config:
        return None, _err(503, "SERVICE_UNAVAILABLE",
                          "Identity configuration missing")
    claims = _claims(event)
    if claims is None:
        return None, _err(401, "UNAUTHORIZED", "Missing verified identity")
    issuer = claims.get("iss")
    subject = claims.get("sub")
    if not isinstance(issuer, str) or not issuer.strip():
        return None, _err(401, "UNAUTHORIZED", "Missing verified issuer")
    if not isinstance(subject, str) or not subject.strip():
        return None, _err(401, "UNAUTHORIZED", "Missing verified subject")
    token_use = claims.get("token_use")
    if token_use not in ("id", "access"):
        return None, _err(401, "UNAUTHORIZED", "Invalid token use")
    if _normalize_issuer(issuer) != _normalize_issuer(issuer_config):
        return None, _err(401, "UNAUTHORIZED", "Issuer mismatch")
    audience = claims.get("aud")
    if audience is None:
        audience = claims.get("client_id")
    if isinstance(audience, list):
        audience_ok = client_config in [str(item) for item in audience]
    else:
        audience_ok = str(audience) == client_config
    if not audience_ok:
        return None, _err(401, "UNAUTHORIZED", "Client mismatch")
    return {
        "issuer": _normalize_issuer(issuer),
        "subject": subject,
        "clientId": client_config,
        "ownerKey": _owner_key(issuer, subject),
    }, None


def _scan_public(value: Any, path: str = "value") -> None:
    """Reject credential-shaped keys/values before releasing stored data."""
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                raise PublicPayloadError(
                    f"forbidden public field at {path}.{key}")
            _scan_public(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_public(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if value.startswith(FORBIDDEN_VALUE_PREFIXES):
            raise PublicPayloadError(f"credential-shaped value at {path}")


def _pick(mapping: Any, fields) -> Dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    return {key: mapping[key] for key in fields if key in mapping}


def _public_agent_order(agent: Any) -> Dict[str, Any]:
    if not isinstance(agent, dict):
        return {}
    projected: Dict[str, Any] = {}
    for key in ("schemaVersion",):
        if key in agent:
            projected[key] = agent[key]
    for key, fields in (
        ("target", PUBLIC_AGENT_TARGET_FIELDS),
        ("input", PUBLIC_AGENT_INPUT_FIELDS),
        ("metadata", PUBLIC_AGENT_METADATA_FIELDS),
        ("resultContract", PUBLIC_RESULT_CONTRACT_FIELDS),
    ):
        value = _pick(agent.get(key), fields)
        if value:
            projected[key] = value
    return projected


def _public_processing(processing: Any) -> Dict[str, Any]:
    if not isinstance(processing, dict):
        return {}
    projected = _pick(processing, PUBLIC_PROCESSING_FIELDS)
    if "result" in processing:
        projected["result"] = processing["result"]
    error = processing.get("error")
    if isinstance(error, dict) and error.get("message"):
        projected["error"] = {
            "message": str(error["message"])[:MAX_ERROR_MESSAGE]}
    return projected


def _public(item: Dict[str, Any]) -> Dict[str, Any]:
    projected: Dict[str, Any] = {
        "orderId": item.get("orderId"),
        "orderType": item.get("orderType") or "retail",
        "status": item.get("status"),
        "customer": _pick(item.get("customer"), PUBLIC_CUSTOMER_FIELDS),
        "items": [
            _pick(entry, PUBLIC_ITEM_FIELDS)
            for entry in (item.get("items") or [])
            if isinstance(entry, dict)
        ],
        "currency": item.get("currency"),
        "totalAmount": item.get("totalAmount"),
        "createdAt": item.get("createdAt"),
        "updatedAt": item.get("updatedAt"),
    }
    agent_order = _public_agent_order(item.get("agentOrder"))
    if agent_order:
        projected["agentOrder"] = agent_order
    processing = _public_processing(item.get("processing"))
    if processing:
        projected["processing"] = processing
    _scan_public(projected)
    return projected


def _list_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if item.get("orderType") == "agent.execution":
        # Agent orders carry no retail fields; mirror the Orders-side list
        # projection instead of raising KeyError on customer/totalAmount.
        return {
            "orderId": item["orderId"],
            "orderType": item["orderType"],
            "status": item["status"],
            "createdAt": item.get("createdAt"),
            "updatedAt": item.get("updatedAt"),
        }
    return {
        "orderId": item["orderId"],
        "status": item["status"],
        "customer": {"name": item["customer"]["name"]},
        "totalAmount": item["totalAmount"],
        "createdAt": item.get("createdAt"),
        "updatedAt": item.get("updatedAt"),
    }


def _list_orders(table: Any, limit: int, identity: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = table.query(
            IndexName=GSI3_INDEX,
            KeyConditionExpression=f"{OWNER_INDEX_KEY} = :owner",
            ExpressionAttributeValues={":owner": identity["ownerKey"]},
            ScanIndexForward=False,
            Limit=limit,
        )
    except Exception as exc:
        code = None
        if hasattr(exc, "response"):
            code = exc.response.get("Error", {}).get("Code")
        if code in ("ValidationException", "ResourceNotFoundException"):
            raise PublicPayloadError("ownership index unavailable") from exc
        raise
    orders = [_list_item(item) for item in result.get("Items", [])]
    return {"orders": orders, "count": len(orders)}


def _load_order(table: Any, order_id: str) -> Optional[Dict[str, Any]]:
    result = table.get_item(
        Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK})
    return result.get("Item")


def _owner_matches(item: Dict[str, Any], identity: Dict[str, Any]) -> bool:
    stored = item.get("ownerKey")
    return isinstance(stored, str) and bool(stored) and stored == identity["ownerKey"]


def _get_order(table: Any, order_id: str,
               identity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    item = _load_order(table, order_id)
    if item is None or not _owner_matches(item, identity):
        return None
    return _public(item)


def _update_status(table: Any, order_id: str, new_status: str,
                   identity: Dict[str, Any]) -> Dict[str, Any]:
    """Gibt (http_code, payload) zurueck; 409 bei ungueltigem Uebergang/Race."""
    raw = _load_order(table, order_id)
    if raw is None or not _owner_matches(raw, identity):
        return 404, {"code": "ORDER_NOT_FOUND",
                     "message": f"Order {order_id} not found"}
    if new_status not in TRANSITIONS.get(raw.get("status"), set()):
        return 409, {
            "code": "INVALID_TRANSITION",
            "message": (f"Transition from {raw.get('status')} to "
                        f"{new_status} is not allowed"),
            "details": {"currentStatus": raw.get("status"),
                        "requestedStatus": new_status},
        }
    try:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        result = table.update_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
            UpdateExpression=(
                "SET #status = :newStatus, updatedAt = :now, "
                "#version = #version + :one"),
            ConditionExpression=(
                "attribute_exists(pk) AND #status = :currentStatus "
                "AND ownerKey = :ownerKey"),
            ExpressionAttributeNames={"#status": "status", "#version": "version"},
            ExpressionAttributeValues={
                ":newStatus": new_status,
                ":currentStatus": raw.get("status"),
                ":ownerKey": identity["ownerKey"],
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
            return 409, {"code": "CONFLICT",
                         "message": "Order was modified concurrently"}
        raise


def _valid_order_id(value: Any) -> Optional[str]:
    if isinstance(value, str) and ORDER_ID_RE.match(value):
        return value
    return None


_profile_table = None


class AgentOrderRejected(Exception):
    """Controlled rejection of an agent order (HTTP status + code)."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _get_profile_table():
    global _profile_table
    if _profile_table is None:  # pragma: no cover - live path
        import boto3

        _profile_table = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")
        ).Table(API_PROFILES_TABLE)
    return _profile_table


def _load_profile(profile_id: str, identity: Dict[str, Any],
                  table: Any = None) -> Dict[str, Any]:
    """Load and authorize the API profile referenced by the agent order."""
    if table is None and not API_PROFILES_TABLE:
        raise AgentOrderRejected(503, "SERVICE_UNAVAILABLE",
                                 "API profile store is not configured")
    store = table if table is not None else _get_profile_table()
    profile = store.get_item(Key={"apiProfileId": profile_id}).get("Item")
    if not isinstance(profile, dict):
        raise AgentOrderRejected(403, "AGENT_ORDER_REJECTED",
                                 "API profile cannot be resolved")
    if profile.get("status") != "ACTIVE":
        raise AgentOrderRejected(403, "AGENT_ORDER_REJECTED",
                                 "API profile is not active")
    owner = profile.get("ownerUserId")
    if owner != identity["subject"]:
        raise AgentOrderRejected(403, "AGENT_ORDER_REJECTED",
                                 "API profile belongs to another owner")
    if not profile.get("tenantId"):
        raise AgentOrderRejected(403, "AGENT_ORDER_REJECTED",
                                 "API profile has no tenant")
    return profile


def _send_order_dispatch(envelope: Dict[str, Any]) -> None:
    """Send the existing ORDER_DISPATCH contract to the RIS ingress queue."""
    if not RIS_DISPATCH_QUEUE_URL:
        raise AgentOrderRejected(503, "SERVICE_UNAVAILABLE",
                                 "Dispatch queue is not configured")
    import boto3

    sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "eu-central-1"))
    sqs.send_message(
        QueueUrl=RIS_DISPATCH_QUEUE_URL,
        MessageBody=json.dumps(envelope, separators=(",", ":")),
    )


def _set_dispatch_state(table: Any, order_id: str,
                        dispatch: Dict[str, Any]) -> None:
    """Best-effort dispatch state; never hides a failed send."""
    try:
        table.update_item(
            Key={"pk": f"{ORDER_ID_PREFIX}{order_id}", "sk": ORDER_SK},
            UpdateExpression="SET #dispatch = :dispatch",
            ExpressionAttributeNames={"#dispatch": "dispatch"},
            ExpressionAttributeValues={":dispatch": dispatch},
            ConditionExpression="attribute_exists(pk)",
            ReturnValues="NONE",
        )
    except Exception as exc:  # pragma: no cover - live path
        print(f"dispatch state not persisted: {type(exc).__name__}")


def _create_agent_order(table: Any, raw: Dict[str, Any],
                        identity: Dict[str, Any],
                        profile_table: Any = None) -> Dict[str, Any]:
    """Validate, persist and dispatch an agent order through Transport V1."""
    import secrets
    from datetime import datetime, timezone

    unknown = set(raw) - {"orderType", "agentOrder"}
    if unknown:
        raise AgentOrderRejected(
            400, "VALIDATION_ERROR",
            f"agent order contains unsupported field '{sorted(unknown)[0]}'")
    try:
        agent_order = validate_order_document(raw)
    except AgentOrderError as exc:
        raise AgentOrderRejected(400, "VALIDATION_ERROR", exc.message) from exc

    metadata = agent_order["metadata"]
    correlation_id = metadata.get("requestId")
    if not correlation_id:
        raise AgentOrderRejected(400, "VALIDATION_ERROR",
                                 "agentOrder.metadata.requestId is required")
    profile_ref = metadata.get("apiProfileRef")
    if not profile_ref:
        raise AgentOrderRejected(400, "VALIDATION_ERROR",
                                 "agentOrder.metadata.apiProfileRef is required")

    profile = _load_profile(profile_ref, identity, table=profile_table)

    order_id = f"{ORDER_ID_PREFIX}{secrets.token_hex(12)}"
    work_id = f"work-{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    idempotency_key = (metadata.get("idempotencyKey")
                       or f"{order_id}:{work_id}:ORDER_DISPATCH")
    envelope = build_dispatch_envelope(
        order_id=order_id,
        correlation_id=correlation_id,
        work_id=work_id,
        agent_id=agent_order["target"]["agentId"],
        capability=agent_order["target"]["capability"],
        payload=agent_order["input"]["data"],
        context_ref=profile_ref,
        idempotency_key=idempotency_key,
    )

    item = {
        "pk": f"{ORDER_ID_PREFIX}{order_id}",
        "sk": ORDER_SK,
        "orderId": order_id,
        "orderType": "agent.execution",
        "status": "PENDING",
        "agentOrder": agent_order,
        "agentOrderFingerprint": agent_order_fingerprint(agent_order),
        "expectedWorkId": work_id,
        "dispatch": {"status": "PENDING", "workId": work_id},
        "createdAt": now,
        "updatedAt": now,
        "version": 1,
        "gsi1pk": GSI1_PK,
        "gsi1sk": now,
        "ownerIssuer": identity["issuer"],
        "ownerSubject": identity["subject"],
        "ownerKey": identity["ownerKey"],
        "ownerClientId": identity["clientId"],
        "actorType": "user",
        "actorId": identity["subject"],
        "gsi3pk": identity["ownerKey"],
        "gsi3sk": f"{now}#{order_id}",
    }
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")

    try:
        _send_order_dispatch(envelope)
    except AgentOrderRejected:
        _set_dispatch_state(table, order_id,
                            {"status": "FAILED", "workId": work_id})
        raise
    except Exception as exc:
        _set_dispatch_state(table, order_id,
                            {"status": "FAILED", "workId": work_id})
        raise AgentOrderRejected(
            502, "DISPATCH_FAILED",
            f"Order {order_id} stored but dispatch failed "
            f"({type(exc).__name__})") from exc

    _set_dispatch_state(table, order_id, {
        "status": "SENT",
        "workId": work_id,
        "messageId": envelope["messageId"],
    })
    return _public(item)


def _validate_create(body: Any) -> tuple:
    """Minimal-Validierung nach beobachtetem Live-Verhalten (400 bei Verstoss)."""
    if not isinstance(body, dict):
        return None, "Request body must be a JSON object"
    customer = body.get("customer") or {}
    if not customer.get("name") or not customer.get("email"):
        return None, "Field 'customer.name' and 'customer.email' are required"
    items = body.get("items")
    if not isinstance(items, list) or not items:
        return None, "Field 'items' must be a non-empty list"
    clean = []
    for i, it in enumerate(items):
        if not isinstance(it, dict) or not it.get("sku"):
            return None, f"Field 'items[{i}].sku' is required"
        qty, price = it.get("quantity"), it.get("unitPrice")
        # Beobachtete Live-Regel: echte Integers (kein Float/Bool/String).
        if (isinstance(qty, bool) or not isinstance(qty, int)
                or isinstance(price, bool) or not isinstance(price, int)):
            return None, f"Field 'items[{i}].quantity/unitPrice' must be integers"
        if qty < 1 or price < 1:
            return None, f"Field 'items[{i}].quantity/unitPrice' must be integers >= 1"
        clean.append({"sku": it["sku"], "quantity": qty, "unitPrice": price,
                      "lineTotal": qty * price})
    currency = body.get("currency", "EUR")
    return {"customer": {"name": customer["name"], "email": customer["email"]},
            "items": clean, "currency": currency}, ""


def _send_order_created(order_id: str) -> None:
    """Worker-Anstoss (beobachtete Nachrichtenform des Live-Systems)."""
    import boto3

    sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "eu-central-1"))
    sqs.send_message(
        QueueUrl=ORDERS_SQS_QUEUE_URL,
        MessageBody=json.dumps({"orderId": order_id, "status": "CONFIRMED",
                                "metadata": {"reason": "order_created"}}),
        MessageAttributes={"orderId": {"StringValue": order_id, "DataType": "String"}},
    )


def _create_order(table: Any, data: Dict[str, Any],
                  identity: Dict[str, Any]) -> Dict[str, Any]:
    """PENDING anlegen (beobachtetes Schema) + Owner binden + Worker anstossen."""
    import secrets
    from datetime import datetime, timezone

    order_id = f"{ORDER_ID_PREFIX}{secrets.token_hex(12)}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    total = sum(it["lineTotal"] for it in data["items"])
    item = {
        "pk": f"{ORDER_ID_PREFIX}{order_id}",
        "sk": ORDER_SK,
        "orderId": order_id,
        "status": "PENDING",
        "customer": data["customer"],
        "items": data["items"],
        "currency": data["currency"],
        "totalAmount": total,
        "createdAt": now,
        "updatedAt": now,
        "version": 1,
        "gsi1pk": GSI1_PK,
        "gsi1sk": now,
        "ownerIssuer": identity["issuer"],
        "ownerSubject": identity["subject"],
        "ownerKey": identity["ownerKey"],
        "ownerClientId": identity["clientId"],
        "actorType": "user",
        "actorId": identity["subject"],
        "gsi3pk": identity["ownerKey"],
        "gsi3sk": f"{now}#{order_id}",
    }
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
    try:
        _send_order_created(order_id)
    except Exception as exc:
        raise RuntimeError(
            f"Order {order_id} angelegt, Worker-Anstoss fehlgeschlagen: "
            f"{type(exc).__name__}") from exc
    return _public(item)


def handler(event: Dict[str, Any], context: Any, table: Any = None,
            profile_table: Any = None) -> Dict[str, Any]:
    """HTTP-API-v2-Einstieg (routeKey). Tabellen nur fuer Unit-Tests injizierbar."""
    tbl = table if table is not None else _get_table()
    try:
        identity, identity_error = _identity(event)
        if identity_error is not None:
            return identity_error
        route = event.get("routeKey", "")
        if route == "POST /orders":
            try:
                raw = json.loads(event.get("body") or "{}")
            except (ValueError, TypeError):
                return _err(400, "VALIDATION_ERROR",
                            "Request body must be valid JSON")
            if isinstance(raw, dict) and (
                    "agentOrder" in raw
                    or raw.get("orderType") == "agent.execution"):
                try:
                    created = _create_agent_order(
                        tbl, raw, identity, profile_table=profile_table)
                except AgentOrderRejected as exc:
                    return _err(exc.status_code, exc.code, exc.message)
                return _ok(201, created)
            if isinstance(raw, dict) and raw.get("orderType") not in (
                    None, "", "retail"):
                return _err(400, "VALIDATION_ERROR",
                            "Unsupported orderType; agent orders require "
                            "orderType 'agent.execution' and an agentOrder")
            data, problem = _validate_create(raw)
            if data is None:
                return _err(400, "VALIDATION_ERROR", problem)
            return _ok(201, _create_order(tbl, data, identity))
        if route == "GET /orders":
            params = event.get("queryStringParameters") or {}
            try:
                limit = int(params.get("limit", "20"))
            except (TypeError, ValueError):
                return _err(400, "VALIDATION_ERROR",
                            "Query parameter 'limit' must be an integer")
            if limit < 1 or limit > 100:
                return _err(400, "VALIDATION_ERROR",
                            "Query parameter 'limit' must be 1..100")
            return _ok(200, _list_orders(tbl, limit, identity))
        if route == "GET /orders/{orderId}":
            order_id = _valid_order_id(
                (event.get("pathParameters") or {}).get("orderId"))
            if not order_id:
                return _err(400, "VALIDATION_ERROR", "Invalid orderId")
            order = _get_order(tbl, order_id, identity)
            if order is None:
                return _err(404, "ORDER_NOT_FOUND",
                            f"Order {order_id} not found")
            return _ok(200, order)
        if route == "PATCH /orders/{orderId}/status":
            order_id = _valid_order_id(
                (event.get("pathParameters") or {}).get("orderId"))
            if not order_id:
                return _err(400, "VALIDATION_ERROR", "Invalid orderId")
            try:
                body = json.loads(event.get("body") or "{}")
            except (ValueError, TypeError):
                return _err(400, "VALIDATION_ERROR",
                            "Request body must be valid JSON")
            status = body.get("status")
            if status not in VALID_STATUSES:
                return _err(400, "VALIDATION_ERROR",
                            "Field 'status' must be a valid status value")
            code, payload = _update_status(tbl, order_id, status, identity)
            if code != 200:
                return {"statusCode": code, "headers": JSON_HEADERS,
                        "body": json.dumps({"error": payload})}
            return _ok(200, payload)
        return _err(400, "VALIDATION_ERROR", f"Unsupported route: {route}")
    except PublicPayloadError as exc:
        # The message carries only the field path, never the value.
        import sys

        print(f"Stored order withheld: {exc}", file=sys.stderr)
        return _err(500, "INTERNAL_ERROR", "Stored order is not releasable")
    except Exception as exc:  # pragma: no cover - letzte Sicherung
        import sys

        print(f"Unexpected error: {type(exc).__name__}", file=sys.stderr)
        return _err(500, "INTERNAL_ERROR", "Internal error")
