"""Structured CV builder profile persistence (contract v1).

This module is deliberately separate from the PDF/CV document and search-profile
resources. It reuses the existing partner-profile DynamoDB table and cursor
store, but stores a distinct ``StructuredCvProfile`` resource with a
server-derived owner key and a dedicated owner index.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - Lambda provides boto3
    import boto3
    from boto3.dynamodb.types import TypeSerializer
except ImportError:  # pragma: no cover
    boto3 = None
    TypeSerializer = None

from jobsearch.partner_profile_cursor import CursorError, CursorStore

RESOURCE_TYPE = "StructuredCvProfile"
SCHEMA_VERSION = 1
IMPORT_REVIEW_SCHEMA_VERSION = 1
PROFILE_ID_PREFIX = "cvp-"
PROFILE_ID_RE = re.compile(r"^cvp-[0-9a-fA-F-]{8,80}$")
MAX_PROFILES_PER_OWNER = 20
MAX_PAYLOAD_BYTES = 300_000
MAX_ITEM_BYTES = 400_000
MAX_REVIEW_ITEMS = 500
MAX_REVIEW_TEXT = 2_000
TARGETS = frozenset({
    "ignore", "profile", "experience", "education", "skills", "projects",
    "certificates", "links",
})
STATUSES = frozenset({"pending", "accepted", "ignored"})
REASONS = frozenset({
    "unknown-section", "training", "certification-goal", "target-roles",
    "document-notes", "incomplete-experience", "incomplete-education",
    "incomplete-language", "project-reference", "ambiguous",
})
TEMPLATES = frozenset({"classic", "modern", "compact"})
LEVELS = frozenset({"basic", "conversational", "professional", "fluent", "native"})
LINK_KINDS = frozenset({"portfolio", "github", "linkedin", "other"})
DATE_RE = re.compile(r"^(?:(?:19|20)\d{2}-(?:0[1-9]|1[0-2]))?$")
IDEM_TTL_SECONDS = 24 * 60 * 60
CAPACITY_PREFIX = "capacity#SCVP#"
IDEM_PREFIX = "idem#StructuredCvProfile#"
CURSOR_SCOPE = "structured-cv-profile-list"
SYSTEM_TYPES = frozenset({"StructuredCvIdempotency", "StructuredCvCapacity", "CursorToken"})


class StructuredCvError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        self.code = code
        self.status = status
        super().__init__(message)


class StructuredCvNotFound(StructuredCvError):
    def __init__(self):
        super().__init__("NOT_FOUND", "Structured CV profile not found", 404)


class StructuredCvConflict(StructuredCvError):
    def __init__(self, code: str = "VERSION_CONFLICT"):
        super().__init__(code, "Structured CV profile version conflict", 409)


class StructuredCvCapacity(StructuredCvError):
    def __init__(self):
        super().__init__("CAPACITY_EXCEEDED", "Structured CV profile capacity exceeded", 409)


def _unknown(value: Any, allowed: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise StructuredCvError("VALIDATION_ERROR", f"{label} must be an object")
    unknown = set(value) - allowed
    if unknown:
        raise StructuredCvError("VALIDATION_ERROR", f"Unknown fields in {label}: {sorted(unknown)}")


def _str(value: Any, label: str, *, max_len: int, required: bool = False) -> str:
    if value is None:
        if required:
            raise StructuredCvError("VALIDATION_ERROR", f"{label} is required")
        return ""
    if not isinstance(value, str):
        raise StructuredCvError("VALIDATION_ERROR", f"{label} must be a string")
    if len(value) > max_len:
        raise StructuredCvError("PAYLOAD_TOO_LARGE", f"{label} exceeds {max_len} characters", 413)
    if required and not value.strip():
        raise StructuredCvError("VALIDATION_ERROR", f"{label} is required")
    return value


def _month(value: Any, label: str) -> str:
    text = _str(value, label, max_len=7)
    if text and not DATE_RE.fullmatch(text):
        raise StructuredCvError("VALIDATION_ERROR", f"{label} must be YYYY-MM or empty")
    return text


def _list(value: Any, label: str, *, max_items: int) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StructuredCvError("VALIDATION_ERROR", f"{label} must be an array")
    if len(value) > max_items:
        raise StructuredCvError("VALIDATION_ERROR", f"{label} exceeds {max_items} entries")
    return value


def _validate_draft(draft: Any) -> None:
    _unknown(draft, {"schemaVersion", "personal", "profile", "experience", "education", "skills", "projects", "certificates", "languages", "links"}, "cvData")
    if draft.get("schemaVersion") != 1:
        raise StructuredCvError("UNSUPPORTED_SCHEMA_VERSION", "cvData.schemaVersion must be 1")
    _unknown(draft.get("personal"), {"fullName", "email", "phone", "location"}, "cvData.personal")
    for key, max_len in (("fullName", 200), ("email", 320), ("phone", 80), ("location", 200)):
        _str(draft["personal"].get(key), f"cvData.personal.{key}", max_len=max_len)
    _unknown(draft.get("profile"), {"headline", "summary"}, "cvData.profile")
    _str(draft["profile"].get("headline"), "cvData.profile.headline", max_len=200)
    _str(draft["profile"].get("summary"), "cvData.profile.summary", max_len=4000)
    for index, entry in enumerate(_list(draft.get("experience"), "cvData.experience", max_items=20)):
        _unknown(entry, {"id", "employer", "position", "startMonth", "endMonth", "current", "description"}, "experience")
        _str(entry.get("id"), "experience.id", max_len=200, required=True)
        _str(entry.get("employer"), "experience.employer", max_len=200)
        _str(entry.get("position"), "experience.position", max_len=200)
        _month(entry.get("startMonth"), "experience.startMonth")
        _month(entry.get("endMonth"), "experience.endMonth")
        if not isinstance(entry.get("current"), bool):
            raise StructuredCvError("VALIDATION_ERROR", "experience.current must be boolean")
        _str(entry.get("description"), "experience.description", max_len=5000)
    for entry in _list(draft.get("education"), "cvData.education", max_items=20):
        _unknown(entry, {"id", "institution", "degree", "startMonth", "endMonth", "current", "description"}, "education")
        _str(entry.get("id"), "education.id", max_len=200, required=True)
        _str(entry.get("institution"), "education.institution", max_len=200)
        _str(entry.get("degree"), "education.degree", max_len=200)
        _month(entry.get("startMonth"), "education.startMonth")
        _month(entry.get("endMonth"), "education.endMonth")
        if not isinstance(entry.get("current"), bool):
            raise StructuredCvError("VALIDATION_ERROR", "education.current must be boolean")
        _str(entry.get("description"), "education.description", max_len=5000)
    skills = _list(draft.get("skills"), "cvData.skills", max_items=100)
    for skill in skills:
        _str(skill, "cvData.skills[]", max_len=100, required=True)
    for entry in _list(draft.get("projects"), "cvData.projects", max_items=20):
        _unknown(entry, {"id", "name", "description", "technologies"}, "project")
        _str(entry.get("id"), "project.id", max_len=200, required=True)
        _str(entry.get("name"), "project.name", max_len=200)
        _str(entry.get("description"), "project.description", max_len=3000)
        for technology in _list(entry.get("technologies"), "project.technologies", max_items=100):
            _str(technology, "project.technologies[]", max_len=100, required=True)
    for entry in _list(draft.get("certificates"), "cvData.certificates", max_items=20):
        _unknown(entry, {"id", "name", "issuer", "date"}, "certificate")
        _str(entry.get("id"), "certificate.id", max_len=200, required=True)
        _str(entry.get("name"), "certificate.name", max_len=200)
        _str(entry.get("issuer"), "certificate.issuer", max_len=200)
        _month(entry.get("date"), "certificate.date")
    for entry in _list(draft.get("languages"), "cvData.languages", max_items=20):
        _unknown(entry, {"id", "language", "level"}, "language")
        _str(entry.get("id"), "language.id", max_len=200, required=True)
        _str(entry.get("language"), "language.language", max_len=100)
        if entry.get("level") not in LEVELS:
            raise StructuredCvError("VALIDATION_ERROR", "language.level is invalid")
    for entry in _list(draft.get("links"), "cvData.links", max_items=20):
        _unknown(entry, {"id", "kind", "label", "url"}, "link")
        _str(entry.get("id"), "link.id", max_len=200, required=True)
        if entry.get("kind") not in LINK_KINDS:
            raise StructuredCvError("VALIDATION_ERROR", "link.kind is invalid")
        _str(entry.get("label"), "link.label", max_len=200)
        _str(entry.get("url"), "link.url", max_len=1000)


def _validate_review(review: Any) -> None:
    if review is None:
        return
    _unknown(review, {"schemaVersion", "sourceName", "pageCount", "pendingAcknowledged", "selectedSections", "skills", "items", "total", "pending", "accepted", "ignored"}, "importReview")
    if review.get("schemaVersion") != IMPORT_REVIEW_SCHEMA_VERSION:
        raise StructuredCvError("UNSUPPORTED_SCHEMA_VERSION", "importReview.schemaVersion must be 1")
    _str(review.get("sourceName"), "importReview.sourceName", max_len=200)
    if review.get("pageCount") is not None and (isinstance(review["pageCount"], bool) or not isinstance(review["pageCount"], int) or review["pageCount"] < 1):
        raise StructuredCvError("VALIDATION_ERROR", "importReview.pageCount is invalid")
    if review.get("pendingAcknowledged") is not None and not isinstance(review["pendingAcknowledged"], bool):
        raise StructuredCvError("VALIDATION_ERROR", "importReview.pendingAcknowledged must be boolean")
    _list(review.get("selectedSections"), "importReview.selectedSections", max_items=20)
    skills = review.get("skills")
    if skills is not None:
        _unknown(skills, {"total", "selected", "unselected", "limited"}, "importReview.skills")
        for key in ("total", "selected", "unselected"):
            if isinstance(skills.get(key), bool) or not isinstance(skills.get(key), int) or skills[key] < 0:
                raise StructuredCvError("VALIDATION_ERROR", f"importReview.skills.{key} is invalid")
        if not isinstance(skills.get("limited"), bool):
            raise StructuredCvError("VALIDATION_ERROR", "importReview.skills.limited is invalid")
    items = _list(review.get("items"), "importReview.items", max_items=MAX_REVIEW_ITEMS)
    for item in items:
        _unknown(item, {"id", "index", "text", "original", "edited", "target", "status", "applied", "page", "sectionHeading", "reason", "suggestedTarget"}, "importReview.items")
        _str(item.get("id"), "review.id", max_len=200, required=True)
        if isinstance(item.get("index"), bool) or not isinstance(item.get("index"), int) or item["index"] < 0:
            raise StructuredCvError("VALIDATION_ERROR", "review.index is invalid")
        _str(item.get("text"), "review.text", max_len=MAX_REVIEW_TEXT)
        _str(item.get("original"), "review.original", max_len=MAX_REVIEW_TEXT)
        if not isinstance(item.get("edited"), bool):
            raise StructuredCvError("VALIDATION_ERROR", "review.edited must be boolean")
        if item.get("target") not in TARGETS or item.get("suggestedTarget") not in TARGETS:
            raise StructuredCvError("VALIDATION_ERROR", "review target is invalid")
        if item.get("status") not in STATUSES:
            raise StructuredCvError("VALIDATION_ERROR", "review.status is invalid")
        if not isinstance(item.get("applied"), bool):
            raise StructuredCvError("VALIDATION_ERROR", "review.applied is required")
        if item.get("applied") and item.get("status") != "accepted":
            raise StructuredCvError("VALIDATION_ERROR", "applied review items must be accepted")
        if item.get("page") is not None and (isinstance(item["page"], bool) or not isinstance(item["page"], int) or item["page"] < 1):
            raise StructuredCvError("VALIDATION_ERROR", "review.page is invalid")
        _str(item.get("sectionHeading"), "review.sectionHeading", max_len=200)
        if item.get("reason") not in REASONS:
            raise StructuredCvError("VALIDATION_ERROR", "review.reason is invalid")
    for key in ("total", "pending", "accepted", "ignored"):
        if isinstance(review.get(key), bool) or not isinstance(review.get(key), int) or review[key] < 0:
            raise StructuredCvError("VALIDATION_ERROR", f"importReview.{key} is invalid")
    if review["total"] != len(items):
        raise StructuredCvError("IMPORT_REVIEW_INCOMPLETE", "importReview.total must equal items")
    counts = {status: sum(1 for item in items if item["status"] == status) for status in STATUSES}
    if review["pending"] != counts["pending"] or review["accepted"] != counts["accepted"] or review["ignored"] != counts["ignored"]:
        raise StructuredCvError("IMPORT_REVIEW_INCOMPLETE", "importReview counts do not match items")
    if review["total"] > 0 and not items:
        raise StructuredCvError("IMPORT_REVIEW_INCOMPLETE", "review items are required")


def validate_create_body(body: Any) -> Dict[str, Any]:
    _unknown(body, {"name", "cvData", "template", "importReview"}, "body")
    name = _str(body.get("name"), "name", max_len=80, required=True).strip()
    if not name:
        raise StructuredCvError("VALIDATION_ERROR", "name is required")
    if body.get("template") not in TEMPLATES:
        raise StructuredCvError("VALIDATION_ERROR", "template is invalid")
    _validate_draft(body.get("cvData"))
    _validate_review(body.get("importReview"))
    result = {"name": name, "cvData": body["cvData"], "template": body["template"]}
    if body.get("importReview") is not None:
        result["importReview"] = body["importReview"]
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise StructuredCvError("PAYLOAD_TOO_LARGE", "profile payload exceeds 300000 bytes", 413)
    return result


def validate_stored_profile(profile: Any) -> Dict[str, Any]:
    _unknown(profile, {"schemaVersion", "profileId", "name", "cvData", "template", "importReview", "version", "createdAt", "updatedAt"}, "StructuredCvProfileV1")
    if profile.get("schemaVersion") != SCHEMA_VERSION:
        raise StructuredCvError("UNSUPPORTED_SCHEMA_VERSION", "schemaVersion must be 1")
    if not isinstance(profile.get("profileId"), str) or not PROFILE_ID_RE.match(profile["profileId"]):
        raise StructuredCvError("VALIDATION_ERROR", "profileId is invalid")
    _str(profile.get("name"), "name", max_len=80, required=True)
    if profile.get("template") not in TEMPLATES:
        raise StructuredCvError("VALIDATION_ERROR", "template is invalid")
    _validate_draft(profile.get("cvData"))
    _validate_review(profile.get("importReview"))
    if isinstance(profile.get("version"), bool) or not isinstance(profile.get("version"), int) or profile["version"] < 1:
        raise StructuredCvError("VALIDATION_ERROR", "version is invalid")
    _str(profile.get("createdAt"), "createdAt", max_len=80, required=True)
    _str(profile.get("updatedAt"), "updatedAt", max_len=80, required=True)
    encoded = json.dumps(profile, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise StructuredCvError("PAYLOAD_TOO_LARGE", "profile payload exceeds 300000 bytes", 413)
    return profile


def owner_key(ctx: Dict[str, str]) -> str:
    material = "\x1f".join([ctx.get("tenantId", ""), ctx.get("partnerApplicationId", ""),
                            ctx.get("issuer", ""), ctx.get("userId", "")])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(value: Any) -> Dict[str, Any]:
    return TypeSerializer().serialize(value)


def _check_item_size(item: Dict[str, Any]) -> None:
    # Conservative JSON byte count; DynamoDB's limit is 400 KB per item.
    encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":"),
                         default=str).encode("utf-8")
    if len(encoded) > MAX_ITEM_BYTES:
        raise StructuredCvError("PAYLOAD_TOO_LARGE", "stored profile item exceeds DynamoDB limit", 413)


def _plain(value: Any) -> Any:
    """Convert DynamoDB Decimal values to JSON-native numbers."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


class StructuredCvProfileRepository:
    """Owner-scoped repository on the existing partner-profiles table."""

    def __init__(self, table_name: Optional[str] = None, dynamodb: Any = None):
        self.table_name = table_name or os.environ.get("PARTNER_PROFILE_TABLE")
        if not self.table_name:
            raise RuntimeError("PARTNER_PROFILE_TABLE is required")
        self.dynamodb = dynamodb or boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)
        self.client = self.table.meta.client
        self.cursors = CursorStore(self.table, self.table_name)

    def _owner(self, ctx: Dict[str, str]) -> str:
        for key in ("userId", "tenantId", "partnerApplicationId", "issuer"):
            if not isinstance(ctx.get(key), str) or not ctx[key]:
                raise StructuredCvError("UNAUTHENTICATED", "verified owner context is incomplete", 401)
        return owner_key(ctx)

    def _from_item(self, item: Dict[str, Any], ctx: Dict[str, str]) -> Dict[str, Any]:
        if item.get("resourceType") != RESOURCE_TYPE:
            raise StructuredCvNotFound()
        if item.get("ownerKey") != self._owner(ctx):
            raise StructuredCvNotFound()
        for key in ("userId", "tenantId", "partnerApplicationId", "issuer"):
            if item.get(key) != ctx[key]:
                raise StructuredCvNotFound()
        payload = _plain(dict(item.get("payload") or {}))
        payload["version"] = int(item.get("version", payload.get("version", 1)))
        payload["createdAt"] = item.get("createdAt", payload.get("createdAt"))
        payload["updatedAt"] = item.get("updatedAt", payload.get("updatedAt"))
        return validate_stored_profile(payload)

    def get(self, profile_id: str, ctx: Dict[str, str]) -> Dict[str, Any]:
        response = self.table.get_item(Key={"resourceId": profile_id}, ConsistentRead=True)
        item = response.get("Item")
        if not item:
            raise StructuredCvNotFound()
        return self._from_item(item, ctx)

    def list(self, ctx: Dict[str, str], *, limit: int = 20, cursor: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        if not 1 <= limit <= 50:
            raise StructuredCvError("VALIDATION_ERROR", "limit must be between 1 and 50")
        owner = self._owner(ctx)
        exclusive = None
        if cursor:
            try:
                exclusive = self.cursors.resolve(
                    cursor, user_id=ctx["userId"], tenant_id=ctx["tenantId"],
                    partner_app_id=ctx["partnerApplicationId"], issuer=ctx["issuer"],
                    scope=CURSOR_SCOPE, resource_type=RESOURCE_TYPE, limit=limit)
            except CursorError as exc:
                raise StructuredCvError("VALIDATION_ERROR", "Invalid cursor") from exc
        params: Dict[str, Any] = {
            "IndexName": "gsi-structured-owner",
            "KeyConditionExpression": "ownerKey = :owner",
            "ExpressionAttributeValues": {":owner": owner},
            "Limit": limit,
        }
        if exclusive:
            params["ExclusiveStartKey"] = exclusive
        response = self.table.query(**params)
        items = [self._from_item(item, ctx) for item in response.get("Items", [])]
        next_key = response.get("LastEvaluatedKey")
        next_cursor = None
        if next_key:
            next_cursor = self.cursors.issue(
                next_key, user_id=ctx["userId"], tenant_id=ctx["tenantId"],
                partner_app_id=ctx["partnerApplicationId"], issuer=ctx["issuer"],
                scope=CURSOR_SCOPE, resource_type=RESOURCE_TYPE, limit=limit)
        return items, next_cursor

    def _item(self, profile: Dict[str, Any], ctx: Dict[str, str]) -> Dict[str, Any]:
        return {
            "resourceId": profile["profileId"],
            "resourceType": RESOURCE_TYPE,
            "ownerKey": self._owner(ctx),
            "userId": ctx["userId"],
            "tenantId": ctx["tenantId"],
            "partnerApplicationId": ctx["partnerApplicationId"],
            "issuer": ctx["issuer"],
            "version": profile["version"],
            "createdAt": profile["createdAt"],
            "updatedAt": profile["updatedAt"],
            "payload": profile,
        }

    @staticmethod
    def _payload_hash(body: Dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()

    def create(self, body: Any, ctx: Dict[str, str], *, idempotency_key: str) -> Dict[str, Any]:
        if not isinstance(idempotency_key, str) or not 16 <= len(idempotency_key) <= 128:
            raise StructuredCvError("VALIDATION_ERROR", "Idempotency-Key is required")
        clean = validate_create_body(body)
        owner = self._owner(ctx)
        payload_hash = self._payload_hash(clean)
        idem_material = "\x1f".join([owner, idempotency_key])
        idem_id = IDEM_PREFIX + hashlib.sha256(idem_material.encode("utf-8")).hexdigest()
        profile_id = PROFILE_ID_PREFIX + str(uuid.uuid4())
        now = _now()
        profile = {
            "schemaVersion": SCHEMA_VERSION,
            "profileId": profile_id,
            **clean,
            "version": 1,
            "createdAt": now,
            "updatedAt": now,
        }
        validate_stored_profile(profile)
        item = self._item(profile, ctx)
        _check_item_size(item)
        idem = {
            "resourceId": idem_id,
            "resourceType": "StructuredCvIdempotency",
            "targetResourceId": profile_id,
            "payloadHash": payload_hash,
            "userId": ctx["userId"], "tenantId": ctx["tenantId"],
            "partnerApplicationId": ctx["partnerApplicationId"], "issuer": ctx["issuer"],
            "createdAt": now, "updatedAt": now,
            "expiresAt": int(time.time()) + IDEM_TTL_SECONDS,
        }
        counter_id = CAPACITY_PREFIX + owner
        try:
            self.client.transact_write_items(TransactItems=[
                {"Put": {"TableName": self.table_name, "Item": {k: _serialize(v) for k, v in idem.items()},
                         "ConditionExpression": "attribute_not_exists(resourceId) OR expiresAt < :now",
                         "ExpressionAttributeValues": {":now": _serialize(int(time.time()))}}},
                {"Update": {"TableName": self.table_name, "Key": {"resourceId": _serialize(counter_id)},
                            "UpdateExpression": "SET #c = if_not_exists(#c, :zero) + :one, updatedAt = :now",
                            "ConditionExpression": "attribute_not_exists(#c) OR #c < :max",
                            "ExpressionAttributeNames": {"#c": "count"},
                            "ExpressionAttributeValues": {":zero": _serialize(0), ":one": _serialize(1),
                                                          ":max": _serialize(MAX_PROFILES_PER_OWNER),
                                                          ":now": _serialize(now)}}},
                {"Put": {"TableName": self.table_name, "Item": {k: _serialize(v) for k, v in item.items()},
                         "ConditionExpression": "attribute_not_exists(resourceId)"}},
            ])
        except Exception as exc:
            if "TransactionCanceled" in type(exc).__name__ or "TransactionCanceled" in str(exc):
                existing = self.table.get_item(Key={"resourceId": idem_id}, ConsistentRead=True).get("Item")
                if existing and existing.get("payloadHash") == payload_hash:
                    target = existing.get("targetResourceId")
                    if target:
                        return self.get(target, ctx)
                # Distinguish capacity from a different idempotency payload.
                if existing:
                    raise StructuredCvConflict("IDEMPOTENCY_CONFLICT")
                raise StructuredCvCapacity()
            raise
        return profile

    def update(self, profile_id: str, body: Any, ctx: Dict[str, str], *, expected_version: Optional[int]) -> Dict[str, Any]:
        if expected_version is None or isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise StructuredCvError("PRECONDITION_REQUIRED", "If-Match version is required", 428)
        _unknown(body, {"name", "cvData", "template", "importReview"}, "body")
        current = self.get(profile_id, ctx)
        if current["version"] != expected_version:
            raise StructuredCvConflict()
        merged = {k: current[k] for k in ("schemaVersion", "profileId", "name", "cvData", "template", "version", "createdAt", "updatedAt")}
        if "importReview" in current:
            merged["importReview"] = current["importReview"]
        for key in ("name", "cvData", "template", "importReview"):
            if key in body:
                merged[key] = body[key]
        if "importReview" in merged and merged["importReview"] is None:
            merged.pop("importReview", None)
        cleaned = validate_create_body({k: merged[k] for k in ("name", "cvData", "template", "importReview") if k in merged})
        now = _now()
        profile = {**current, **cleaned, "version": current["version"] + 1, "updatedAt": now}
        if "importReview" not in cleaned:
            profile.pop("importReview", None)
        validate_stored_profile(profile)
        _check_item_size(self._item(profile, ctx))
        self.table.update_item(
            Key={"resourceId": profile_id},
            UpdateExpression="SET #v = :next, #u = :now, #p = :p",
            ConditionExpression="#v = :expected AND ownerKey = :owner",
            ExpressionAttributeNames={"#v": "version", "#u": "updatedAt", "#p": "payload"},
            ExpressionAttributeValues={":next": profile["version"], ":now": now, ":p": profile,
                                       ":expected": expected_version, ":owner": self._owner(ctx)},
        )
        return profile

    def delete(self, profile_id: str, ctx: Dict[str, str], *, expected_version: Optional[int] = None) -> None:
        current = self.get(profile_id, ctx)
        if expected_version is not None and current["version"] != expected_version:
            raise StructuredCvConflict()
        kwargs: Dict[str, Any] = {
            "Key": {"resourceId": profile_id},
            "ConditionExpression": "ownerKey = :owner",
            "ExpressionAttributeValues": {":owner": self._owner(ctx)},
        }
        if expected_version is not None:
            kwargs["ConditionExpression"] += " AND #v = :expected"
            kwargs["ExpressionAttributeNames"] = {"#v": "version"}
            kwargs["ExpressionAttributeValues"][":expected"] = expected_version
        self.table.delete_item(**kwargs)
        # Capacity is a soft allocation counter. A failure here must not turn
        # a successful owner-bound delete into an error; the next create can
        # still be rejected and is recoverable by an operator.
        try:
            self.table.update_item(
                Key={"resourceId": CAPACITY_PREFIX + self._owner(ctx)},
                UpdateExpression="SET #c = #c - :one, updatedAt = :now",
                ConditionExpression="#c > :zero",
                ExpressionAttributeNames={"#c": "count"},
                ExpressionAttributeValues={":one": 1, ":zero": 0, ":now": _now()},
            )
        except Exception:
            pass

    def erase_for_user(self, user_id: str, tenant_id: Optional[str] = None) -> int:
        """Delete all structured profiles for a user across partner scopes.

        Account erasure is user-scoped; normal CRUD remains owner-scoped. This
        uses the existing ``gsi-user`` index as a server-side lookup and still
        re-checks tenant/identity before every delete.
        """
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id is required")
        deleted = 0
        start_key = None
        while True:
            params = {
                "IndexName": "gsi-user",
                "KeyConditionExpression": "userId = :u AND resourceType = :t",
                "ExpressionAttributeValues": {":u": user_id, ":t": RESOURCE_TYPE},
                "Limit": 50,
            }
            if start_key:
                params["ExclusiveStartKey"] = start_key
            response = self.table.query(**params)
            for item in response.get("Items", []):
                if tenant_id is not None and item.get("tenantId") != tenant_id:
                    continue
                ctx = {
                    "userId": item.get("userId"), "tenantId": item.get("tenantId"),
                    "partnerApplicationId": item.get("partnerApplicationId"),
                    "issuer": item.get("issuer"),
                }
                try:
                    self.delete(item.get("resourceId"), ctx)
                    deleted += 1
                except StructuredCvNotFound:
                    continue
            start_key = response.get("LastEvaluatedKey")
            if not start_key:
                return deleted

    def export(self, profile_id: str, ctx: Dict[str, str]) -> Dict[str, Any]:
        return {
            "schemaVersion": 1,
            "exportedAt": _now(),
            "source": "ris-structured-cv-profile",
            "profile": self.get(profile_id, ctx),
        }

    def erase_all(self, ctx: Dict[str, str]) -> int:
        """Owner-scoped idempotent account-erasure foundation."""
        deleted = 0
        cursor = None
        while True:
            items, cursor = self.list(ctx, limit=50, cursor=cursor)
            for item in items:
                try:
                    self.delete(item["profileId"], ctx)
                    deleted += 1
                except StructuredCvNotFound:
                    continue
            if not cursor:
                return deleted
