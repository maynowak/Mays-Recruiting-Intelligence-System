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
    EVENT_GRANTED, EVENT_REGRANTED, EVENT_WITHDRAWN, NOTICE_DRAFT,
    STATUS_GRANTED, STATUS_NOT_GRANTED, STATUS_WITHDRAWN,
    ConsentContext, ConsentContractError, notice_version as lookup_notice_version,
    status_payload,
    validate_consent_proof, validate_notice_version, validate_purpose,
)


class ConsentConflict(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity(purpose: str) -> str:
    return "PURPOSE#" + purpose


def _proof_matches(row: dict[str, Any], consent: bool, categories: list[str],
                   external_version: str | None,
                   external_sha256: str | None) -> bool:
    """Whether a stored grant already carries exactly the requested proof."""
    return (
        (row.get("specialCategoriesConsent") is True) == consent
        and [value for value in (row.get("specialCategories") or [])
             if isinstance(value, str)] == categories
        and (row.get("externalTextVersion") or None) == external_version
        and (row.get("externalTextSha256") or None) == external_sha256
    )


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
            special_categories_consent=row.get("specialCategoriesConsent") is True,
            special_categories=row.get("specialCategories") or [],
            external_text_version=row.get("externalTextVersion"),
            external_text_sha256=row.get("externalTextSha256"),
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
            "specialCategoriesConsent": x.get("specialCategoriesConsent") is True,
            "specialCategories": [
                value for value in (x.get("specialCategories") or [])
                if isinstance(value, str)
            ],
            "externalTextVersion": x.get("externalTextVersion"),
            "externalTextSha256": x.get("externalTextSha256"),
        } for x in result.get("Items", [])]
        return events, result.get("LastEvaluatedKey")

    # -- writes --------------------------------------------------------
    def grant(self, ctx: ConsentContext, purpose: str,
              notice_version: str,
              enforce_notice_state: bool | None = None,
              special_categories_consent: bool = False,
              special_categories: object = None,
              external_text_version: str | None = None,
              external_text_sha256: str | None = None) -> dict[str, Any]:
        """Record a grant with an optional Art. 9 / external-text proof.

        ``enforce_notice_state`` is the caller's effective enforcement
        decision (global flag OR a scoped pilot identity). ``None`` keeps the
        previous behavior of reading ``CONSENT_NOTICE_STATE_ENFORCED`` from the
        environment. It only affects a *new* or *regranted* consent; an
        idempotent repeat of an existing grant is validated by identifier and
        proof.

        The proof fields are validated before any write. Repeating a grant with
        the same proof is idempotent; a different external text or special
        category scope for an already granted consent raises
        ``RECONSENT_REQUIRED`` instead of silently reusing the old consent.
        """
        ctx.validate()
        purpose = validate_purpose(purpose)
        consent, categories, external_version, external_sha256 = (
            validate_consent_proof(
                purpose,
                special_categories_consent=special_categories_consent,
                special_categories=special_categories,
                external_text_version=external_text_version,
                external_text_sha256=external_text_sha256))
        # Identifier check only. State enforcement is applied once we know a
        # new grant is actually being written, so repeating an existing grant
        # stays idempotent even after its notice version became SUPERSEDED.
        version = validate_notice_version(purpose, notice_version,
                                          require_active=False)
        for _ in range(2):
            row = self._current(ctx, purpose)
            if (row and row.get("status") == STATUS_GRANTED
                    and row.get("noticeVersion") == version):
                if not _proof_matches(row, consent, categories,
                                      external_version, external_sha256):
                    raise ConsentContractError(
                        "RECONSENT_REQUIRED",
                        "a different consent text or category scope is already "
                        "granted; withdraw before granting new proof")
                return status_payload(
                    purpose, status=STATUS_GRANTED, notice_version=version,
                    granted_at=row.get("grantedAt"), withdrawn_at=None,
                    version=int(row.get("version") or 0),
                    special_categories_consent=consent,
                    special_categories=categories,
                    external_text_version=external_version,
                    external_text_sha256=external_sha256)

            previous = (row or {}).get("status") or STATUS_NOT_GRANTED
            if previous == STATUS_GRANTED:
                raise ConsentContractError(
                    "CONSENT_ALREADY_GRANTED",
                    "a different notice version is already granted")

            # A brand-new or re-granted consent must not be recorded against a
            # draft/superseded text when state enforcement is enabled.
            version = validate_notice_version(
                purpose, version, require_active=enforce_notice_state)
            # The structured-CV purpose is not approved. Even in the legacy
            # technical mode (state enforcement off), a DRAFT must not become
            # a real consent unless the separate local test switch is set.
            if purpose == "cv-builder-profile-storage":
                entry = lookup_notice_version(purpose, version)
                if (entry is not None and entry.state == NOTICE_DRAFT
                        and os.environ.get(
                            "STRUCTURED_CV_PROFILE_TEST_MODE", "false"
                        ).strip().lower() != "true"):
                    raise ConsentContractError(
                        "NOTICE_NOT_APPROVED",
                        "structured CV notice is not legally approved")

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
                # Stored proof. Never inferred from the notice or the browser.
                "specialCategoriesConsent": consent,
                "specialCategories": list(categories),
                "externalTextVersion": external_version,
                "externalTextSha256": external_sha256,
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
                        "Item": self._event_item(
                            ctx, purpose, event, version, stamp,
                            special_categories_consent=consent,
                            special_categories=categories,
                            external_text_version=external_version,
                            external_text_sha256=external_sha256),
                        "ConditionExpression": "attribute_not_exists(entityKey)",
                    }},
                ])
                return status_payload(
                    purpose, status=STATUS_GRANTED, notice_version=version,
                    granted_at=stamp, withdrawn_at=None,
                    version=expected + 1,
                    special_categories_consent=consent,
                    special_categories=categories,
                    external_text_version=external_version,
                    external_text_sha256=external_sha256)
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
                version=int((row or {}).get("version") or 0),
                special_categories_consent=(row or {}).get(
                    "specialCategoriesConsent") is True,
                special_categories=(row or {}).get("specialCategories") or [],
                external_text_version=(row or {}).get("externalTextVersion"),
                external_text_sha256=(row or {}).get("externalTextSha256"))
        if current != STATUS_GRANTED:
            raise ConsentContractError(
                "NOT_GRANTED", "there is no active consent to withdraw")

        version = validate_notice_version(purpose, notice_version,
                                          require_active=False) if notice_version \
            else (row or {}).get("noticeVersion")
        # Withdrawal must stay possible even if the granted notice version is
        # now draft-only or superseded; it never establishes a new consent.
        version = validate_notice_version(purpose, version, require_active=False)
        stamp = _now()
        expected = int((row or {}).get("version") or 0)
        updated = dict(row or {})
        updated.update(status=STATUS_WITHDRAWN, withdrawnAt=stamp,
                       version=expected + 1, updatedAt=stamp)
        proof = {
            "special_categories_consent":
                (row or {}).get("specialCategoriesConsent") is True,
            "special_categories": (row or {}).get("specialCategories") or [],
            "external_text_version": (row or {}).get("externalTextVersion"),
            "external_text_sha256": (row or {}).get("externalTextSha256"),
        }
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
                                             version, stamp, **proof),
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
            version=expected + 1,
            special_categories_consent=proof["special_categories_consent"],
            special_categories=proof["special_categories"],
            external_text_version=proof["external_text_version"],
            external_text_sha256=proof["external_text_sha256"])

    # -- helpers -------------------------------------------------------
    def _event_item(self, ctx: ConsentContext, purpose: str, event: str,
                    notice_version: str, stamp: str, *,
                    special_categories_consent: bool = False,
                    special_categories: object = None,
                    external_text_version: str | None = None,
                    external_text_sha256: str | None = None) -> dict[str, Any]:
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
            # Proof is copied onto every event so the append-only history can
            # reconstruct exactly which text/categories were consented to.
            "specialCategoriesConsent": special_categories_consent is True,
            "specialCategories": [
                value for value in (special_categories or [])
                if isinstance(value, str)
            ],
            "externalTextVersion": external_text_version,
            "externalTextSha256": external_text_sha256,
        }

    def _transact(self, items: list[dict[str, Any]]) -> None:
        self.table.meta.client.transact_write_items(TransactItems=items)


def idempotency_hash(ctx: ConsentContext, purpose: str, operation: str) -> str:
    """Stable hash helper for future request-level idempotency records."""
    raw = json.dumps([ctx.scope_key, purpose, operation], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()
