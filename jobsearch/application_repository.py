"""Scoped DynamoDB persistence for ApplicationV1.

The repository never accepts identity from a payload. All access paths include
the verified context and all writes use conditions or transactions.
"""

from __future__ import annotations

import hashlib
import base64
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

try:
    import boto3
    from boto3.dynamodb.conditions import Key
except ImportError:  # pragma: no cover - Lambda provides boto3
    boto3 = None
    Key = None

from jobsearch.application_contract import (
    ApplicationContractError, ApplicationContext, validate_create,
    validate_patch, validate_transition,
)


class ApplicationNotFound(LookupError):
    pass


class ApplicationConflict(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


_SECRET_CACHE: dict[str, bytes] = {}


def _cursor_secret() -> bytes:
    """Return the HMAC key, preferring a runtime secret over plain env.

    Resolution order:
      1. ``RIS_CURSOR_SECRET`` (tests/local only; never set in Terraform)
      2. ``RIS_CURSOR_SECRET_ARN`` -> Secrets Manager ``GetSecretValue``
    Missing or unreadable configuration fails closed: no static fallback.
    The value is cached per ARN for the life of the process and never logged.
    """
    raw = os.environ.get("RIS_CURSOR_SECRET")
    if raw:
        return raw.encode()
    arn = os.environ.get("RIS_CURSOR_SECRET_ARN")
    if not arn:
        raise RuntimeError("cursor secret is not configured")
    cached = _SECRET_CACHE.get(arn)
    if cached is not None:
        return cached
    if boto3 is None:
        raise RuntimeError("cursor secret is unavailable")
    try:
        payload = boto3.client("secretsmanager").get_secret_value(SecretId=arn)
    except Exception as exc:
        raise RuntimeError("cursor secret is unavailable") from exc
    value = payload.get("SecretString")
    if not value:
        raise RuntimeError("cursor secret is empty")
    data = value.encode()
    _SECRET_CACHE[arn] = data
    return data


class ApplicationRepository:
    def __init__(self, table_name: str | None = None, dynamodb: Any = None):
        self.table_name = table_name or os.environ.get("APPLICATIONS_TABLE")
        if not self.table_name:
            raise ValueError("APPLICATIONS_TABLE is required")
        self.dynamodb = dynamodb or boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    @staticmethod
    def _scope(ctx: ApplicationContext) -> str:
        return "|".join((ctx.tenant_id, ctx.user_id, ctx.partner_application_id, ctx.issuer))

    @staticmethod
    def _transaction_item(item: dict[str, Any]) -> dict[str, Any]:
        """Return native values; boto3's low-level client serializes them."""
        return dict(item)

    def _transact(self, items: list[dict[str, Any]]) -> None:
        self.table.meta.client.transact_write_items(
            TransactItems=[{action: self._transaction_item(value)
                            for action, value in item.items()}
                           for item in items])

    @staticmethod
    def _idempotency_key(ctx: ApplicationContext, key: str) -> str:
        return hashlib.sha256((ApplicationRepository._scope(ctx) + "|" + key).encode()).hexdigest()

    @staticmethod
    def _cursor_secret() -> bytes:
        return _cursor_secret()

    def issue_cursor(self, key: dict[str, Any], *, user_id: str, tenant_id: str,
                     partner_app_id: str | None, issuer: str | None,
                     scope: str, resource_type: str, limit: int) -> str:
        payload = {"key": key, "scope": scope, "resourceType": resource_type,
                   "limit": limit, "owner": "|".join((tenant_id, user_id, partner_app_id or "", issuer or ""))}
        raw = base64.urlsafe_b64encode(_json(payload).encode()).decode().rstrip("=")
        sig = hmac.new(self._cursor_secret(), raw.encode(), hashlib.sha256).hexdigest()
        return raw + "." + sig

    def resolve_cursor(self, token: str, *, user_id: str, tenant_id: str,
                       partner_app_id: str | None, issuer: str | None,
                       scope: str, resource_type: str, limit: int) -> dict[str, Any]:
        try:
            raw, sig = token.split(".", 1)
            expected = hmac.new(self._cursor_secret(), raw.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                raise ValueError
            payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            owner = "|".join((tenant_id, user_id, partner_app_id or "", issuer or ""))
            if payload.get("scope") != scope or payload.get("resourceType") != resource_type or payload.get("limit") != limit or payload.get("owner") != owner:
                raise ValueError
            return payload["key"]
        except Exception as exc:
            raise ValueError("invalid cursor") from exc

    def _owned(self, application_id: str, ctx: ApplicationContext, consistent: bool = True) -> dict[str, Any]:
        row = self.table.get_item(Key={"applicationId": application_id, "entityKey": "META"}, ConsistentRead=consistent).get("Item")
        if not row or row.get("ownerKey") != self._scope(ctx):
            raise ApplicationNotFound("application not found")
        return row

    @staticmethod
    def _public(row: Mapping[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in row.items() if k not in {"entityKey", "ownerKey", "idempotencyHash", "entityType"}}

    def create(self, data: Mapping[str, Any], ctx: ApplicationContext) -> dict[str, Any]:
        ctx.validate()
        parsed = validate_create(data)
        stamp, app_id = _now(), str(uuid.uuid4())
        idempotency_key = parsed.pop("idempotencyKey", None)
        request_hash = hashlib.sha256(_json(parsed).encode()).hexdigest()
        row = {
            **parsed, "schemaVersion": 1, "applicationId": app_id, "entityKey": "META",
            "entityType": "META", "userId": ctx.user_id, "tenantId": ctx.tenant_id,
            "partnerApplicationId": ctx.partner_application_id, "issuer": ctx.issuer,
            "ownerKey": self._scope(ctx), "status": "DRAFT", "version": 1,
            "createdAt": stamp, "updatedAt": stamp, "submittedAt": None,
        }
        items = [{"Put": {"TableName": self.table_name, "Item": row,
                            "ConditionExpression": "attribute_not_exists(applicationId)"}}]
        if idempotency_key:
            idem = self._idempotency_key(ctx, idempotency_key)
            row["idempotencyHash"] = idem
            items.append({"Put": {"TableName": self.table_name,
                                   "Item": {"applicationId": "IDEMP#" + idem, "entityKey": "IDEMP",
                                             "entityType": "IDEMP", "ownerKey": self._scope(ctx),
                                             "targetApplicationId": app_id, "requestHash": request_hash,
                                             "createdAt": stamp},
                                   "ConditionExpression": "attribute_not_exists(applicationId)"}})
        try:
            self._transact(items)
        except Exception as exc:
            # An idempotent retry returns the original row after the conditional
            # conflict; other conditional conflicts are safe conflicts.
            if idempotency_key:
                existing = self.table.get_item(Key={"applicationId": "IDEMP#" + self._idempotency_key(ctx, idempotency_key), "entityKey": "IDEMP"}, ConsistentRead=True).get("Item")
                if existing and existing.get("targetApplicationId"):
                    if existing.get("requestHash") != request_hash:
                        raise ApplicationConflict("IDEMPOTENCY_PAYLOAD_CONFLICT") from exc
                    return self._public(self._owned(existing["targetApplicationId"], ctx))
            raise ApplicationConflict("application already exists or could not be created") from exc
        return self._public(row)

    def get(self, application_id: str, ctx: ApplicationContext) -> dict[str, Any]:
        return self._public(self._owned(application_id, ctx))

    def list(self, ctx: ApplicationContext, limit: int = 50, cursor: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        if not 1 <= limit <= 100:
            raise ApplicationContractError("INVALID_LIMIT", "limit is invalid")
        kwargs: dict[str, Any] = {"IndexName": "gsi-owner", "KeyConditionExpression": Key("ownerKey").eq(self._scope(ctx)), "Limit": limit, "ScanIndexForward": False}
        if cursor:
            kwargs["ExclusiveStartKey"] = cursor
        result = self.table.query(**kwargs)
        return [self._public(x) for x in result.get("Items", []) if x.get("entityType") == "META"], result.get("LastEvaluatedKey")

    def patch(self, application_id: str, data: Mapping[str, Any], ctx: ApplicationContext) -> dict[str, Any]:
        current = self._owned(application_id, ctx)
        parsed = validate_patch(data)
        if parsed["expectedVersion"] != current.get("version"):
            raise ApplicationConflict("VERSION_CONFLICT")
        updates = {k: v for k, v in parsed.items() if k != "expectedVersion"}
        stamp = _now()
        current.update(updates, version=current["version"] + 1, updatedAt=stamp)
        try:
            self.table.put_item(Item=current, ConditionExpression="version = :expected AND ownerKey = :owner", ExpressionAttributeValues={":expected": parsed["expectedVersion"], ":owner": self._scope(ctx)})
        except Exception as exc:
            raise ApplicationConflict("VERSION_CONFLICT") from exc
        return self._public(current)

    def status(self, application_id: str, target: str, expected_version: int, confirm: bool, ctx: ApplicationContext) -> dict[str, Any]:
        current = self._owned(application_id, ctx)
        validate_transition(current["status"], target, confirm)
        if current["version"] != expected_version:
            raise ApplicationConflict("VERSION_CONFLICT")
        stamp = _now()
        history = {"applicationId": application_id, "entityKey": "HISTORY#" + stamp + "#" + str(uuid.uuid4()), "entityType": "HISTORY", "ownerKey": self._scope(ctx), "status": target, "createdAt": stamp, "actorUserId": ctx.user_id}
        current.update(status=target, version=expected_version + 1, updatedAt=stamp, submittedAt=stamp if target == "SUBMITTED" else current.get("submittedAt"))
        tx = [{"Put": {"TableName": self.table_name, "Item": current, "ConditionExpression": "version = :expected AND ownerKey = :owner", "ExpressionAttributeValues": {":expected": expected_version, ":owner": self._scope(ctx)}}}, {"Put": {"TableName": self.table_name, "Item": history, "ConditionExpression": "attribute_not_exists(applicationId)"}}]
        try:
            self._transact(tx)
        except Exception as exc:
            raise ApplicationConflict("VERSION_CONFLICT") from exc
        return self._public(current)

    def add_history(self, application_id: str, event: Mapping[str, Any], expected_version: int, ctx: ApplicationContext) -> dict[str, Any]:
        current = self._owned(application_id, ctx)
        if current["version"] != expected_version:
            raise ApplicationConflict("VERSION_CONFLICT")
        if not isinstance(event, Mapping) or not isinstance(event.get("type"), str):
            raise ApplicationContractError("INVALID_HISTORY", "history type is required")
        stamp = _now()
        item = {"applicationId": application_id, "entityKey": "HISTORY#" + stamp + "#" + str(uuid.uuid4()), "entityType": "HISTORY", "ownerKey": self._scope(ctx), "event": dict(event), "createdAt": stamp, "actorUserId": ctx.user_id}
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(applicationId)")
        except Exception as exc:
            raise ApplicationConflict("HISTORY_CONFLICT") from exc
        return item

    def add_cover_letter(self, application_id: str, letter: str, expected_version: int, ctx: ApplicationContext) -> dict[str, Any]:
        current = self._owned(application_id, ctx)
        if not isinstance(letter, str) or not letter.strip() or len(letter) > 100_000:
            raise ApplicationContractError("INVALID_COVER_LETTER", "cover letter is invalid")
        if current["version"] != expected_version:
            raise ApplicationConflict("VERSION_CONFLICT")
        stamp = _now(); version_id = str(uuid.uuid4())
        item = {"applicationId": application_id, "entityKey": "COVER#" + stamp + "#" + version_id, "entityType": "COVER_LETTER", "ownerKey": self._scope(ctx), "versionId": version_id, "text": letter, "createdAt": stamp, "actorUserId": ctx.user_id}
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(applicationId)")
        except Exception as exc:
            raise ApplicationConflict("COVER_LETTER_CONFLICT") from exc
        return {"versionId": version_id, "createdAt": stamp}

    def export(self, application_id: str, ctx: ApplicationContext) -> dict[str, Any]:
        app = self._owned(application_id, ctx)
        children = self.table.query(KeyConditionExpression=Key("applicationId").eq(application_id), ConsistentRead=True).get("Items", [])
        return {"application": self._public(app), "history": [{k: v for k, v in x.items() if k not in {"ownerKey", "entityType", "entityKey"}} for x in children if x.get("entityType") == "HISTORY"], "coverLetterVersions": [{k: v for k, v in x.items() if k not in {"ownerKey", "entityType", "entityKey"}} for x in children if x.get("entityType") == "COVER_LETTER"]}

    def delete(self, application_id: str, expected_version: int, ctx: ApplicationContext) -> None:
        current = self._owned(application_id, ctx)
        if current.get("version") != expected_version:
            raise ApplicationConflict("VERSION_CONFLICT")
        children = self.table.query(KeyConditionExpression=Key("applicationId").eq(application_id), ConsistentRead=True).get("Items", [])
        self._transact([{"Delete": {"TableName": self.table_name, "Key": {"applicationId": x["applicationId"], "entityKey": x["entityKey"]}, "ConditionExpression": "ownerKey = :owner", "ExpressionAttributeValues": {":owner": self._scope(ctx)}}} for x in children])
