"""DynamoDB persistence for partner consents (V1).

Layout (single table, no GSI):

    scopeKey = tenant|partner|issuer|subject
    entityKey:
      PURPOSE#<purpose>        current state (one row per purpose)
      EVENT#<occurredAt>#<id>  append-only history
      IDEMP#<hash>             reserved for future request idempotency

Current state is updated with a conditional write on ``version``; every change
also writes a history event in the same transaction. History rows are never
updated or deleted by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

try:
    import boto3
    from boto3.dynamodb.conditions import Key
except ImportError:  # pragma: no cover - Lambda provides boto3
    boto3 = None
    Key = None

from jobsearch.consent_contract import (
    EVENT_GRANTED, EVENT_REGRANTED, EVENT_WITHDRAWN,
    STATUS_GRANTED, STATUS_NOT_GRANTED, STATUS_WITHDRAWN,
    ConsentContext, ConsentContractError, status_payload,
    validate_notice_version, validate_purpose,
)


class ConsentConflict(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity(purpose: str) -> str:
    return "PURPOSE#" + purpose


class ConsentRepository:
    def __init__(self, table_name: str | None = None, dynamodb: Any = None):
        self.table_name = table_name or os.environ.get("CONSENTS_TABLE")
        if not self.table_name:
            raise ValueError("CONSENTS_TABLE is required")
        self.dynamodb = dynamodb or boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    # -- reads ---------------------------------------------------------
    def _current(self, ctx: ConsentContext, purpose: str) -> dict[str, Any] | None:
        return self.table.get_item(
            Key={"scopeKey": ctx.scope_key, "entityKey": _entity(purpose)},
            ConsistentRead=True,
        ).get("Item")

    def get(self, ctx: ConsentContext, purpose: str) -> dict[str, Any]:
        ctx.validate()
        purpose = validate_purpose(purpose)
        row = self._current(ctx, purpose)
        if not row:
            return status_payload(purpose, status=STATUS_NOT_GRANTED,
                                  notice_version=None, granted_at=None,
                                  withdrawn_at=None, version=0)
        return status_payload(
            purpose, status=row.get("status"),
            notice_version=row.get("noticeVersion"),
            granted_at=row.get("grantedAt"),
            withdrawn_at=row.get("withdrawnAt"),
            version=int(row.get("version") or 0),
        )

    def has_consent(self, ctx: ConsentContext, purpose: str) -> bool:
        return self.get(ctx, purpose)["status"] == STATUS_GRANTED

    def history(self, ctx: ConsentContext, purpose: str, *,
                limit: int = 50, cursor: dict[str, Any] | None = None,
                ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        ctx.validate()
        purpose = validate_purpose(purpose)
        if not 1 <= limit <= 100:
            raise ConsentContractError("INVALID_LIMIT", "limit is invalid")
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": (
                Key("scopeKey").eq(ctx.scope_key)
                & Key("entityKey").begins_with("EVENT#" + purpose + "#")
            ),
            "Limit": limit,
            "ScanIndexForward": False,
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = cursor
        result = self.table.query(**kwargs)
        events = [{
            "eventId": x.get("eventId"),
            "purpose": x.get("purpose"),
            "event": x.get("event"),
            "status": x.get("status"),
            "noticeVersion": x.get("noticeVersion"),
            "occurredAt": x.get("occurredAt"),
        } for x in result.get("Items", [])]
        return events, result.get("LastEvaluatedKey")

    # -- writes --------------------------------------------------------
    def grant(self, ctx: ConsentContext, purpose: str,
              notice_version: str) -> dict[str, Any]:
        ctx.validate()
        purpose = validate_purpose(purpose)
        version = validate_notice_version(purpose, notice_version)
        for _ in range(2):
            row = self._current(ctx, purpose)
            if (row and row.get("status") == STATUS_GRANTED
                    and row.get("noticeVersion") == version):
                return status_payload(
                    purpose, status=STATUS_GRANTED, notice_version=version,
                    granted_at=row.get("grantedAt"), withdrawn_at=None,
                    version=int(row.get("version") or 0))

            previous = (row or {}).get("status") or STATUS_NOT_GRANTED
            if previous == STATUS_GRANTED:
                raise ConsentContractError(
                    "CONSENT_ALREADY_GRANTED",
                    "a different notice version is already granted")

            stamp = _now()
            event = EVENT_REGRANTED if previous == STATUS_WITHDRAWN else EVENT_GRANTED
            expected = int((row or {}).get("version") or 0)
            base = {
                "scopeKey": ctx.scope_key,
                "entityKey": _entity(purpose),
                "purpose": purpose,
                "status": STATUS_GRANTED,
                "noticeVersion": version,
                "grantedAt": stamp,
                "withdrawnAt": None,
                "version": expected + 1,
                "updatedAt": stamp,
                "subject": ctx.user_id,
            }
            condition = ("attribute_not_exists(scopeKey)" if not row
                         else "version = :expected")
            try:
                self._transact([
                    {"Put": {
                        "TableName": self.table_name,
                        "Item": dict(base),
                        "ConditionExpression": condition,
                        **({"ExpressionAttributeValues": {":expected": expected}}
                           if row else {}),
                    }},
                    {"Put": {
                        "TableName": self.table_name,
                        "Item": self._event_item(ctx, purpose, event, version, stamp),
                        "ConditionExpression": "attribute_not_exists(entityKey)",
                    }},
                ])
                return status_payload(
                    purpose, status=STATUS_GRANTED, notice_version=version,
                    granted_at=stamp, withdrawn_at=None,
                    version=expected + 1)
            except Exception as exc:  # conditional conflict -> retry once
                if "ConditionalCheckFailed" in str(exc):
                    continue
                raise ConsentConflict("consent write failed") from exc
        raise ConsentConflict("consent version conflict")

    def withdraw(self, ctx: ConsentContext, purpose: str,
                 notice_version: str | None = None) -> dict[str, Any]:
        ctx.validate()
        purpose = validate_purpose(purpose)
        row = self._current(ctx, purpose)
        current = (row or {}).get("status") or STATUS_NOT_GRANTED
        if current == STATUS_WITHDRAWN:
            return status_payload(
                purpose, status=STATUS_WITHDRAWN,
                notice_version=(row or {}).get("noticeVersion"),
                granted_at=(row or {}).get("grantedAt"),
                withdrawn_at=(row or {}).get("withdrawnAt"),
                version=int((row or {}).get("version") or 0))
        if current != STATUS_GRANTED:
            raise ConsentContractError(
                "NOT_GRANTED", "there is no active consent to withdraw")

        version = validate_notice_version(purpose, notice_version) if notice_version \
            else (row or {}).get("noticeVersion")
        version = validate_notice_version(purpose, version)
        stamp = _now()
        expected = int((row or {}).get("version") or 0)
        updated = dict(row or {})
        updated.update(status=STATUS_WITHDRAWN, withdrawnAt=stamp,
                       version=expected + 1, updatedAt=stamp)
        try:
            self._transact([
                {"Put": {
                    "TableName": self.table_name,
                    "Item": updated,
                    "ConditionExpression": "version = :expected",
                    "ExpressionAttributeValues": {":expected": expected},
                }},
                {"Put": {
                    "TableName": self.table_name,
                    "Item": self._event_item(ctx, purpose, EVENT_WITHDRAWN,
                                             version, stamp),
                    "ConditionExpression": "attribute_not_exists(entityKey)",
                }},
            ])
        except Exception as exc:
            if "ConditionalCheckFailed" in str(exc):
                raise ConsentConflict("consent version conflict") from exc
            raise ConsentConflict("consent write failed") from exc
        return status_payload(
            purpose, status=STATUS_WITHDRAWN, notice_version=version,
            granted_at=(row or {}).get("grantedAt"), withdrawn_at=stamp,
            version=expected + 1)

    # -- helpers -------------------------------------------------------
    def _event_item(self, ctx: ConsentContext, purpose: str, event: str,
                    notice_version: str, stamp: str) -> dict[str, Any]:
        event_id = str(uuid.uuid4())
        return {
            "scopeKey": ctx.scope_key,
            "entityKey": "EVENT#" + purpose + "#" + stamp + "#" + event_id,
            "eventId": event_id,
            "purpose": purpose,
            "event": event,
            "status": STATUS_GRANTED if event in (EVENT_GRANTED, EVENT_REGRANTED)
            else STATUS_WITHDRAWN,
            "noticeVersion": notice_version,
            "occurredAt": stamp,
            "subject": ctx.user_id,
            "identityRef": ctx.scope_key,
        }

    def _transact(self, items: list[dict[str, Any]]) -> None:
        self.table.meta.client.transact_write_items(TransactItems=items)


def idempotency_hash(ctx: ConsentContext, purpose: str, operation: str) -> str:
    """Stable hash helper for future request-level idempotency records."""
    raw = json.dumps([ctx.scope_key, purpose, operation], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()
