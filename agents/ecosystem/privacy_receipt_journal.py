"""R08-A1: durable privacy receipt journal repository.

A dedicated DynamoDB table stores validated ``PrivacyReceiptV1`` records for
one verified identity scope. The journal is append-only from the repository's
point of view (no update API), uses conditional inserts for idempotency and
never scans in the normal read path.

Production writes are fail-closed until the retention/legal policy and the
R08-A2 integration are approved: ``PRIVACY_RECEIPT_JOURNAL_ENABLED`` must be
explicitly ``true``. R08-A1 does not wire the journal into CRUD handlers.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from agents.ecosystem.privacy_receipt import (
    PrivacyContextV1, PrivacyReceiptError, PrivacyReceiptV1,
    receipt_matches_context,
)

JOURNAL_TABLE_ENV = "PRIVACY_RECEIPTS_TABLE"
JOURNAL_ENABLED_ENV = "PRIVACY_RECEIPT_JOURNAL_ENABLED"
JOURNAL_SCOPE = "privacy-receipts"
JOURNAL_RESOURCE_TYPE = "PrivacyReceipt"
JOURNAL_PAGE_LIMIT = 50
JOURNAL_MAX_LIMIT = 50


class PrivacyReceiptJournalError(Exception):
    """Controlled journal error; carries no receipt content or secrets."""


class PrivacyReceiptJournalDisabled(PrivacyReceiptJournalError):
    """Journal is not enabled by policy/configuration."""


class PrivacyReceiptConflict(PrivacyReceiptJournalError):
    """A receipt ID is reused with a different semantic payload."""


class PrivacyReceiptNotFound(PrivacyReceiptJournalError):
    """Receipt is missing or belongs to another identity context."""


class PrivacyReceiptStorageError(PrivacyReceiptJournalError):
    """DynamoDB read/write failed; the operation must not be reported as success."""


class PrivacyReceiptIntegrityError(PrivacyReceiptJournalError):
    """Stored receipt failed contract/content verification."""


class PrivacyReceiptInvalidCursor(PrivacyReceiptJournalError):
    """Cursor is invalid, expired or bound to another context."""


def scope_key(context: PrivacyContextV1) -> str:
    """Opaque partition key for one exact identity scope."""
    material = "\x1f".join([
        context.tenant_id, context.partner_application_id,
        context.issuer, context.user_id,
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def receipt_content_hash(receipt: PrivacyReceiptV1) -> str:
    """Hash the semantic receipt, excluding the server-set timestamp.

    This lets an identical retry (which receives a new server timestamp) be
    recognised as the same operation, while any changed field yields a
    different hash and is rejected.
    """
    data = receipt.to_dict()
    data["recordedAt"] = ""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_numbers(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_normalize_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_numbers(item) for key, item in value.items()}
    return value


class PrivacyReceiptJournal:
    """Durable receipt journal scoped by verified identity."""

    def __init__(self, *, table_name: Optional[str] = None,
                 dynamodb: Any = None, table: Any = None,
                 enabled: Optional[bool] = None,
                 cursor_repo: Any = None,
                 clock=_utcnow) -> None:
        self.table_name = table_name or os.environ.get(JOURNAL_TABLE_ENV)
        self._dynamodb = dynamodb
        self._table = table
        if enabled is None:
            enabled = os.environ.get(
                JOURNAL_ENABLED_ENV, "false").strip().lower() == "true"
        self.enabled = bool(enabled)
        self._cursor_repo = cursor_repo
        self._clock = clock

    @property
    def table(self):
        if self._table is None:
            if self._dynamodb is None:
                import boto3
                self._dynamodb = boto3.resource("dynamodb")
            self._table = self._dynamodb.Table(self.table_name)
        return self._table

    @property
    def cursor_repo(self):
        if self._cursor_repo is None:
            from jobsearch.partner_profile_repository import (
                PartnerProfileRepository,
            )
            self._cursor_repo = PartnerProfileRepository()
        return self._cursor_repo

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise PrivacyReceiptJournalDisabled(
                "Privacy receipt journal is disabled")
        if not self.table_name and self._table is None:
            raise PrivacyReceiptJournalDisabled(
                "Privacy receipt journal is not configured")

    # ------------------------------------------------------------------ #
    # append / get
    # ------------------------------------------------------------------ #
    def append_receipt(self, receipt: PrivacyReceiptV1,
                       context: PrivacyContextV1) -> PrivacyReceiptV1:
        self._ensure_enabled()
        if not isinstance(receipt, PrivacyReceiptV1):
            raise PrivacyReceiptError(
                "INVALID_RECEIPT", "receipt must be PrivacyReceiptV1")
        if not receipt_matches_context(receipt, context):
            raise PrivacyReceiptJournalError("Receipt context mismatch")

        now = self._clock()
        stored = replace(receipt, recorded_at=now.isoformat())
        stored.validate(now=now)
        content_hash = receipt_content_hash(stored)
        scope = scope_key(context)
        item = {
            "receiptId": stored.receipt_id,
            "scopeKey": scope,
            "scopeSort": f"{stored.recorded_at}#{stored.receipt_id}",
            "subjectRef": stored.subject_ref,
            "tenantRef": stored.tenant_ref,
            "partnerApplicationRef": stored.partner_application_ref,
            "issuerRef": stored.issuer_ref,
            "eventType": stored.event_type,
            "recordedAt": stored.recorded_at,
            "schemaVersion": stored.schema_version,
            "contentHash": content_hash,
            "payload": stored.to_dict(),
            "createdAt": now.isoformat(),
            "updatedAt": now.isoformat(),
        }
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(receiptId)",
            )
            return stored
        except Exception as exc:
            if "ConditionalCheckFailed" not in str(exc):
                raise PrivacyReceiptStorageError(
                    "Receipt write failed") from exc
            # Conditional insert failed: a receipt with this ID exists.
            try:
                existing = self.get_receipt(receipt.receipt_id, context)
            except PrivacyReceiptNotFound:
                raise PrivacyReceiptConflict(
                    "Receipt id is already in use") from exc
            if existing.receipt_id != receipt.receipt_id:
                raise PrivacyReceiptConflict("Receipt id conflict") from exc
            if receipt_content_hash(existing) != content_hash:
                raise PrivacyReceiptConflict(
                    "Receipt id reused with a different payload") from exc
            return existing

    def get_receipt(self, receipt_id: str,
                    context: PrivacyContextV1) -> PrivacyReceiptV1:
        self._ensure_enabled()
        if not isinstance(receipt_id, str) or not receipt_id:
            raise PrivacyReceiptNotFound("Receipt not found")
        try:
            response = self.table.get_item(
                Key={"receiptId": receipt_id}, ConsistentRead=True)
        except Exception as exc:
            raise PrivacyReceiptStorageError(
                "Receipt read failed") from exc
        item = response.get("Item")
        if not item:
            raise PrivacyReceiptNotFound("Receipt not found")
        return self._parse_item(item, context)

    def list_receipts(self, context: PrivacyContextV1,
                      cursor: Optional[str] = None,
                      limit: int = JOURNAL_PAGE_LIMIT
                      ) -> Tuple[List[PrivacyReceiptV1], Optional[str]]:
        self._ensure_enabled()
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = JOURNAL_PAGE_LIMIT
        limit = max(1, min(limit, JOURNAL_MAX_LIMIT))
        scope = scope_key(context)
        start_key = None
        if cursor:
            from jobsearch.partner_profile_cursor import CursorError
            try:
                start_key = self.cursor_repo.resolve_cursor(
                    cursor, user_id=context.user_id,
                    tenant_id=context.tenant_id,
                    partner_app_id=context.partner_application_id,
                    issuer=context.issuer, scope=JOURNAL_SCOPE,
                    resource_type=JOURNAL_RESOURCE_TYPE,
                    parent_id=scope, limit=limit)
            except CursorError as exc:
                raise PrivacyReceiptInvalidCursor("Invalid cursor") from exc
            except Exception as exc:
                raise PrivacyReceiptStorageError(
                    "Receipt cursor read failed") from exc
        kwargs: Dict[str, Any] = {
            "IndexName": "gsi-subject",
            "KeyConditionExpression": "scopeKey = :s",
            "ExpressionAttributeValues": {":s": scope},
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if start_key:
            kwargs["ExclusiveStartKey"] = start_key
        try:
            response = self.table.query(**kwargs)
        except Exception as exc:
            raise PrivacyReceiptStorageError(
                "Receipt list failed") from exc
        receipts = [self._parse_item(item, context)
                    for item in response.get("Items", [])]
        next_cursor = None
        last_key = response.get("LastEvaluatedKey")
        if last_key:
            try:
                next_cursor = self.cursor_repo.issue_cursor(
                    last_key, user_id=context.user_id,
                    tenant_id=context.tenant_id,
                    partner_app_id=context.partner_application_id,
                    issuer=context.issuer, scope=JOURNAL_SCOPE,
                    resource_type=JOURNAL_RESOURCE_TYPE,
                    parent_id=scope, limit=limit)
            except Exception as exc:
                raise PrivacyReceiptStorageError(
                    "Receipt cursor write failed") from exc
        return receipts, next_cursor

    # ------------------------------------------------------------------ #
    def _parse_item(self, item: Dict[str, Any],
                    context: PrivacyContextV1) -> PrivacyReceiptV1:
        if (item.get("subjectRef") != context.user_id
                or item.get("tenantRef") != context.tenant_id
                or item.get("partnerApplicationRef")
                != context.partner_application_id
                or item.get("issuerRef") != context.issuer):
            # Do not reveal another identity's receipt.
            raise PrivacyReceiptNotFound("Receipt not found")
        payload = item.get("payload")
        if not isinstance(payload, dict):
            raise PrivacyReceiptIntegrityError("Receipt payload is missing")
        payload = _normalize_numbers(payload)
        try:
            receipt = PrivacyReceiptV1.from_dict(payload)
        except PrivacyReceiptError as exc:
            raise PrivacyReceiptIntegrityError(
                "Stored receipt is invalid") from exc
        if receipt_content_hash(receipt) != item.get("contentHash"):
            raise PrivacyReceiptIntegrityError(
                "Stored receipt content hash mismatch")
        if receipt.receipt_id != item.get("receiptId"):
            raise PrivacyReceiptIntegrityError(
                "Stored receipt id mismatch")
        return receipt
