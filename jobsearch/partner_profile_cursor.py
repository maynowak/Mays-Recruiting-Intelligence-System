"""R07-FIX-04: opaque, server-side pagination cursors.

A cursor is a 256-bit random bearer token. The client never sees DynamoDB
keys: the token maps to a server-side record in the existing partner-profile
table. The record is bound to the verified identity and to the exact query
(scope, resource type, parent id, page size), and expires after 15 minutes.

This design was chosen over AES-256-GCM because the Lambda bundle builder only
packages Python sources (no native wheels) and the project has no managed
cursor key. No new table, no new IAM action and no secret are required. A
stolen token is still useless without the matching authenticated identity, and
authorization is always re-checked by the normal RIS request path.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

CURSOR_VERSION = 1
CURSOR_TTL_SECONDS = 15 * 60
CURSOR_MAX_LENGTH = 256
CURSOR_MAX_KEY_BYTES = 4096
CURSOR_PREFIX = "rp1_"
CURSOR_RESOURCE_TYPE = "CursorToken"
CURSOR_SCOPE = "partner-profile-list"

_CURSOR_TOKEN_BYTES = 32


class CursorError(Exception):
    """Invalid, expired, unknown or foreign cursor. Safe to return as 400."""


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def cursor_item_key(token: str) -> str:
    return f"cursor#{_token_digest(token)}"


def query_digest(*, scope: str, resource_type: str,
                 parent_id: Optional[str]) -> str:
    """Stable digest of the query context, excluding auth identity.

    Page size is deliberately not bound: the DynamoDB ``LastEvaluatedKey`` is
    valid for the same query regardless of page size, and clients may omit
    ``limit`` on a continuation request. Scope/resource/parent prevent
    cross-list and cross-parent reuse.
    """
    canonical = json.dumps({
        "scope": scope,
        "resourceType": resource_type,
        "parentId": parent_id or "",
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_valid_token(token: Any) -> bool:
    if not isinstance(token, str):
        return False
    if len(token) > CURSOR_MAX_LENGTH or not token.startswith(CURSOR_PREFIX):
        return False
    body = token[len(CURSOR_PREFIX):]
    if len(body) != 43:
        return False
    try:
        raw = base64.urlsafe_b64decode(body.encode("ascii") + b"=")
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return False
    return len(raw) == _CURSOR_TOKEN_BYTES


def _identity_value(value: Optional[str]) -> str:
    return value or ""


def _normalize_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class CursorStore:
    """Issue and resolve server-side cursor records in a DynamoDB table."""

    def __init__(self, table: Any, table_name: str):
        self.table = table
        self.table_name = table_name

    def issue(self, last_evaluated_key: Dict[str, Any], *,
              user_id: str, tenant_id: str,
              partner_app_id: Optional[str] = None,
              issuer: Optional[str] = None,
              scope: str = CURSOR_SCOPE,
              resource_type: str,
              parent_id: Optional[str] = None,
              limit: int = 50) -> str:
        if not isinstance(last_evaluated_key, dict) or not last_evaluated_key:
            raise ValueError("last_evaluated_key must be a non-empty object")
        try:
            encoded_key = json.dumps(last_evaluated_key, sort_keys=True,
                                     separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("last_evaluated_key is not serialisable") from exc
        if len(encoded_key.encode("utf-8")) > CURSOR_MAX_KEY_BYTES:
            raise ValueError("last_evaluated_key is too large")

        now_epoch = int(time.time())
        now_iso = datetime.now(timezone.utc).isoformat()
        digest = query_digest(scope=scope, resource_type=resource_type,
                              parent_id=parent_id)
        for _ in range(3):
            token = CURSOR_PREFIX + secrets.token_urlsafe(_CURSOR_TOKEN_BYTES)
            item = {
                "resourceId": cursor_item_key(token),
                "resourceType": CURSOR_RESOURCE_TYPE,
                "version": CURSOR_VERSION,
                "scope": scope,
                "queryHash": digest,
                "lastEvaluatedKey": last_evaluated_key,
                "userId": user_id,
                "tenantId": tenant_id,
                "partnerApplicationId": _identity_value(partner_app_id),
                "issuer": _identity_value(issuer),
                "issuedAt": now_epoch,
                "createdAt": now_iso,
                "updatedAt": now_iso,
                "expiresAt": now_epoch + CURSOR_TTL_SECONDS,
            }
            try:
                self.table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(resourceId)",
                )
                return token
            except Exception as exc:
                if "ConditionalCheckFailed" in str(exc):
                    continue  # astronomically unlikely token collision
                raise
        raise RuntimeError("cursor token collision")

    def resolve(self, token: Any, *,
                user_id: str, tenant_id: str,
                partner_app_id: Optional[str] = None,
                issuer: Optional[str] = None,
                scope: str = CURSOR_SCOPE,
                resource_type: str,
                parent_id: Optional[str] = None,
                limit: int = 50) -> Dict[str, Any]:
        if not _is_valid_token(token):
            raise CursorError("Invalid cursor")
        try:
            resp = self.table.get_item(
                Key={"resourceId": cursor_item_key(token)},
                ConsistentRead=True)
        except Exception:
            # Backing-store failures are infrastructure errors, not 400s.
            raise
        item = resp.get("Item")
        if not item:
            raise CursorError("Invalid cursor")
        if _normalize_int(item.get("version")) != CURSOR_VERSION:
            raise CursorError("Invalid cursor")
        if item.get("scope") != scope:
            raise CursorError("Invalid cursor")
        digest = query_digest(scope=scope, resource_type=resource_type,
                              parent_id=parent_id)
        if item.get("queryHash") != digest:
            raise CursorError("Invalid cursor")
        if (item.get("userId") != user_id
                or item.get("tenantId") != tenant_id
                or _identity_value(item.get("partnerApplicationId"))
                != _identity_value(partner_app_id)
                or _identity_value(item.get("issuer"))
                != _identity_value(issuer)):
            raise CursorError("Invalid cursor")
        expires_at = _normalize_int(item.get("expiresAt"))
        if expires_at is None or expires_at <= int(time.time()):
            try:
                self.table.delete_item(
                    Key={"resourceId": cursor_item_key(token)})
            except Exception:
                pass
            raise CursorError("Invalid cursor")
        key = item.get("lastEvaluatedKey")
        if not isinstance(key, dict) or not key:
            raise CursorError("Invalid cursor")
        return key
