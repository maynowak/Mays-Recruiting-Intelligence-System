"""DynamoDB repository for partner profile persistence (R02).

Persistence layer for the v1 partner profile contract. Reuses the contract
validation from `jobsearch.partner_profile_contract` (no second validation).

Atomic capacity limits are enforced with DynamoDB TransactWriteItems:
for every create, a counter item per capacity dimension is condition-checked
(count < max), the resource is conditionally put, and the counter is
atomically incremented -- all in one transaction. A cancelled transaction
leaves no partial state, so capacity can never be over-allocated.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from jobsearch.partner_profile_contract import (
    SCHEMA_VERSION,
    ProfileContractError,
    parse_resource,
    CVDocument,
    CVSearchProfile,
    ATSSearchProfile,
    ManualSearchProfile,
    validate_ats_assignment,
    MAX_CVS_PER_USER,
    MAX_SEARCH_PROFILES_PER_CV,
    MAX_ATS_PROFILES_PER_SEARCH_PROFILE,
)

logger = logging.getLogger(__name__)

# DynamoDB type serializer: uses boto3 at runtime, falls back to a small
# pure-Python serializer so the module stays importable and testable without
# boto3 installed.
try:  # pragma: no cover - runtime path
    from boto3.dynamodb.types import TypeSerializer as _TS

    def _serialize_value(value):
        return _TS().serialize(value)
except Exception:  # pragma: no cover - test fallback

    def _serialize_value(value):
        if value is None:
            return {"NULL": True}
        if isinstance(value, bool):
            return {"BOOL": value}
        if isinstance(value, (int, float)):
            return {"N": str(value)}
        if isinstance(value, str):
            return {"S": value}
        if isinstance(value, list):
            return {"L": [_serialize_value(v) for v in value]}
        if isinstance(value, dict):
            return {"M": {k: _serialize_value(v) for k, v in value.items()}}
        return {"S": str(value)}


def serializer(value):
    return _serialize_value(value)


def _normalize_numbers(value):
    """Convert DynamoDB ``Decimal`` values to native int/float.

    boto3 Table resources deserialize every DynamoDB number to ``Decimal``.
    The contract validators expect real ints (e.g. CVDocument.size), so the
    read path normalises before parsing instead of weakening validation.
    """
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_normalize_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_numbers(item) for key, item in value.items()}
    return value

PERSISTED_RESOURCE_TYPES = frozenset({
    "CVDocument",
    "CVSearchProfile",
    "ATSSearchProfile",
    "ManualSearchProfile",
})

CAPACITY_PREFIX = "capacity#"
CAPACITY_RESOURCE_TYPE = "CapacityCounter"

# resource_type -> max_count
CAPACITY_RULES: Dict[str, int] = {
    "CVDocument": MAX_CVS_PER_USER,
    "CVSearchProfile": MAX_SEARCH_PROFILES_PER_CV,
    "ATSSearchProfile": MAX_ATS_PROFILES_PER_SEARCH_PROFILE,
}

# resource_type -> counter key prefix (short, stable)
COUNTER_PREFIX: Dict[str, str] = {
    "CVDocument": "CV",
    "CVSearchProfile": "CVSP",
    "ATSSearchProfile": "ATS",
}

# Internal bookkeeping items that must never be returned as profile resources.
IDEMPOTENCY_RESOURCE_TYPE = "IdempotencyRecord"
LIFECYCLE_RESOURCE_TYPE = "LifecycleGuard"
SYSTEM_RESOURCE_TYPES = frozenset({
    CAPACITY_RESOURCE_TYPE, IDEMPOTENCY_RESOURCE_TYPE, LIFECYCLE_RESOURCE_TYPE,
})

LIFECYCLE_ACTIVE = "active"
LIFECYCLE_DELETING = "deleting"

# Defined idempotency lifetime (24h); the condition allows an expired key to be
# reused. DynamoDB TTL on ``expiresAt`` is a cleanup optimisation, not the
# correctness mechanism.
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60

# The resource's own id field, excluded from the idempotency payload hash so a
# server-generated retry id cannot change the fingerprint.
OWN_ID_FIELD = {
    "CVDocument": "cvId",
    "CVSearchProfile": "searchProfileId",
    "ATSSearchProfile": "atsProfileId",
    "ManualSearchProfile": "manualProfileId",
}


class PartnerProfileNotFoundError(Exception):
    pass


class PartnerProfileReadError(Exception):
    """A DynamoDB read failed.

    Raised instead of returning ``None`` so callers cannot turn an outage or a
    throttled read into a false 404/409.  Carries no backend detail.
    """


class PartnerProfileConflictError(Exception):
    pass


class PartnerProfileRepository:
    def __init__(self, table_name: Optional[str] = None, dynamodb=None):
        self.table_name = table_name or os.environ.get("PARTNER_PROFILE_TABLE")
        self._dynamodb = dynamodb
        self._table = None
        self._client = None

    @property
    def table(self):
        if self._table is None:
            if not self._dynamodb:
                import boto3
                self._dynamodb = boto3.resource("dynamodb")
            self._table = self._dynamodb.Table(self.table_name) if self.table_name else None
        return self._table

    @property
    def client(self):
        if self._client is None:
            if self._dynamodb is None:
                import boto3
                self._dynamodb = boto3.resource("dynamodb")
            # A boto3 *resource* client carries the DynamoDB resource
            # transformation, which would double-serialize the low-level
            # transaction items built below. Always use a plain client for
            # TransactWriteItems, derived from the same endpoint/credentials.
            base_client = getattr(getattr(self._dynamodb, "meta", None),
                                  "client", None)
            if base_client is None:
                self._client = self._dynamodb
            else:
                import boto3
                creds = getattr(
                    getattr(base_client, "_request_signer", None),
                    "_credentials", None)
                self._client = boto3.client(
                    "dynamodb",
                    endpoint_url=base_client.meta.endpoint_url,
                    region_name=base_client.meta.region_name,
                    aws_access_key_id=getattr(creds, "access_key", None),
                    aws_secret_access_key=getattr(creds, "secret_key", None),
                    aws_session_token=getattr(creds, "token", None),
                    config=base_client.meta.config,
                )
        return self._client

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _serialize(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {k: serializer(v) for k, v in item.items() if v is not None}

    def _identity_ok(self, item: Dict[str, Any], user_id: str, tenant_id: str,
                     partner_app_id: Optional[str], issuer: Optional[str]) -> bool:
        if item.get("userId") != user_id:
            return False
        if item.get("tenantId") != tenant_id:
            return False
        if partner_app_id is not None and item.get("partnerApplicationId") != partner_app_id:
            return False
        if issuer is not None and item.get("issuer") != issuer:
            return False
        return True

    def _resource_id(self, resource: Any) -> str:
        # stable server-side id: use provided id if present else generate
        for attr in ("ats_profile_id", "search_profile_id", "manual_profile_id", "cv_id"):
            val = getattr(resource, attr, None)
            if val:
                return val
        return uuid.uuid4().hex

    def _parent_id(self, resource: Any) -> Optional[str]:
        if isinstance(resource, CVDocument):
            return resource.user_id
        if isinstance(resource, CVSearchProfile):
            return resource.cv_id
        if isinstance(resource, ATSSearchProfile):
            return resource.search_profile_id
        if isinstance(resource, ManualSearchProfile):
            return resource.user_id
        return None

    def _to_item(self, resource: Any, *, user_id: str, tenant_id: str,
                 partner_app_id: Optional[str], issuer: Optional[str],
                 version: int = 1) -> Dict[str, Any]:
        payload = resource.to_dict()
        now = self._now()
        return {
            "resourceId": self._resource_id(resource),
            "resourceType": payload["resourceType"],
            "schemaVersion": payload.get("schemaVersion", SCHEMA_VERSION),
            "userId": user_id,
            "tenantId": tenant_id,
            "partnerApplicationId": partner_app_id,
            "issuer": issuer,
            "parentId": self._parent_id(resource),
            "version": version,
            "createdAt": now,
            "updatedAt": now,
            "payload": payload,
        }

    def _from_item(self, item: Dict[str, Any]) -> Any:
        if item.get("resourceType") in SYSTEM_RESOURCE_TYPES:
            return None
        payload = _normalize_numbers(dict(item.get("payload") or {}))
        # identity is authoritative from the stored item, never from payload
        payload["userId"] = item.get("userId")
        payload["tenantId"] = item.get("tenantId")
        obj = parse_resource(payload, strict=False)
        # expose the optimistic-lock version without polluting the contract DTO
        try:
            obj.version = _normalize_numbers(item.get("version", 1))
        except Exception:
            pass
        return obj

    def _counter_key(self, rt: str, parent_id: str) -> str:
        return f"capacity#{COUNTER_PREFIX[rt]}#{parent_id}"

    def _capacity_key(self, rt: str, user_id: str, tenant_id: str,
                      resource: Any) -> Optional[str]:
        if rt not in CAPACITY_RULES:
            return None
        parent_id = self._parent_id(resource) or user_id
        return self._counter_key(rt, parent_id)

    def _now_epoch(self) -> int:
        return int(time.time())

    def _guard_key(self, rt: str, resource_id: str) -> str:
        return f"lifecycle#{rt}#{resource_id}"

    def _idem_key(self, rt: str, user_id: str, tenant_id: str,
                  partner_app_id: Optional[str], issuer: Optional[str],
                  idempotency_key: str) -> str:
        # Identity is part of the digest, so two users/tenants/partners/issuers
        # can never collide on the same client-supplied key. The raw key is
        # never stored.
        material = "\x1f".join([
            rt or "", user_id or "", tenant_id or "",
            partner_app_id or "", issuer or "", idempotency_key or "",
        ])
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return f"idem#{rt}#{digest}"

    def _payload_hash(self, resource: Any) -> str:
        rt = getattr(resource, "resource_type", "")
        data = resource.to_dict()
        data.pop(OWN_ID_FIELD.get(rt, ""), None)
        data.pop("createdAt", None)
        data.pop("updatedAt", None)
        data.pop("schemaVersion", None)
        # resourceType is implied by the idempotency key; keeping it is harmless.
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _condition_check(self, key: str, expression: str,
                         values: Dict[str, Any],
                         names: Optional[Dict[str, str]] = None
                         ) -> Dict[str, Any]:
        check = {
            "TableName": self.table_name,
            "Key": {"resourceId": {"S": key}},
            "ConditionExpression": expression,
            "ExpressionAttributeValues": values,
        }
        if names:
            check["ExpressionAttributeNames"] = names
        return {"ConditionCheck": check}

    def _parent_checks(self, resource: Any, user_id: str, tenant_id: str
                       ) -> List[Dict[str, Any]]:
        """Atomic parent-existence + parent-not-deleting guards (R05-A).

        These are ConditionChecks on the parent resource and its lifecycle
        guard, i.e. distinct items from the child Put and the child counter.
        """
        rt = getattr(resource, "resource_type", "")
        checks: List[Dict[str, Any]] = []
        if isinstance(resource, CVSearchProfile):
            parent_id = resource.cv_id
            parent_type = "CVDocument"
        elif isinstance(resource, ATSSearchProfile):
            parent_id = resource.search_profile_id
            parent_type = "CVSearchProfile"
        else:
            return checks
        checks.append(self._condition_check(
            parent_id,
            "attribute_exists(resourceId) AND userId = :pu AND tenantId = :pt",
            {":pu": {"S": user_id}, ":pt": {"S": tenant_id}},
        ))
        checks.append(self._condition_check(
            self._guard_key(parent_type, parent_id),
            "attribute_not_exists(resourceId) OR #s = :gactive",
            {":gactive": {"S": LIFECYCLE_ACTIVE}},
            names={"#s": "state"},
        ))
        return checks

    def _cancelled_indices(self, exc: Exception) -> Dict[int, str]:
        reasons = getattr(exc, "response", {}).get("CancellationReasons", []) or []
        out: Dict[int, str] = {}
        for idx, reason in enumerate(reasons):
            if reason.get("Code") == "ConditionalCheckFailed":
                out[idx] = reason.get("Message", "")
        return out

    def _ensure_counter(self, key: str) -> None:
        """Ensure a capacity counter item exists with count 0 (idempotent).

        The counter item is created once and then only incremented/decremented
        atomically inside transactions. It is never deleted.
        """
        try:
            resp = self.table.get_item(Key={"resourceId": key},
                                       ConsistentRead=True)
        except Exception as e:
            logger.error("get_item counter failed: %s", e)
            raise PartnerProfileReadError("Counter read failed") from e
        if resp.get("Item"):
            return
        now = self._now()
        parts = key.split("#", 2)
        item = {
            "resourceId": key,
            "resourceType": CAPACITY_RESOURCE_TYPE,
            "count": 0,
            "userId": parts[1] if len(parts) > 1 else "",
            "tenantId": "",
            # No parentId: an empty string is an invalid GSI key value in
            # DynamoDB. Omitting it keeps counter items out of gsi-parent.
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(resourceId)",
            )
        except Exception as e:
            if "ConditionalCheckFailed" in str(e):
                return  # another request created it first
            raise

    def _check_parent_exists(self, resource: Any, user_id: str, tenant_id: str,
                             partner_app_id: Optional[str], issuer: Optional[str]) -> None:
        if isinstance(resource, CVSearchProfile):
            parent = self.get(resource.cv_id, user_id, tenant_id, partner_app_id, issuer)
            if parent is None or not isinstance(parent, CVDocument):
                raise ProfileContractError("INVALID_HIERARCHY", "Parent CV not found")
            if parent.user_id != resource.user_id or parent.tenant_id != resource.tenant_id:
                raise ProfileContractError("INVALID_HIERARCHY", "Identity mismatch with parent CV")
        elif isinstance(resource, ATSSearchProfile):
            parent = self.get(resource.search_profile_id, user_id, tenant_id, partner_app_id, issuer)
            if parent is None or not isinstance(parent, CVSearchProfile):
                raise ProfileContractError("INVALID_HIERARCHY", "Parent search profile not found")
            validate_ats_assignment(resource, parent)

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create(self, resource: Any, *, user_id: str, tenant_id: str,
               partner_app_id: Optional[str] = None, issuer: Optional[str] = None,
               idempotency_key: Optional[str] = None) -> str:
        if self.table is None:
            raise RuntimeError("DynamoDB table not configured")
        rt = getattr(resource, "resource_type", None)
        if rt not in PERSISTED_RESOURCE_TYPES:
            raise ValueError(f"Unsupported resource type: {rt}")
        rid = self._resource_id(resource)
        if (rid.startswith(CAPACITY_PREFIX) or rid.startswith("lifecycle#")
                or rid.startswith("idem#")):
            raise ValueError("Reserved ID prefix")

        # Fast, non-authoritative hierarchy read. The transaction below is the
        # authoritative guard for create-vs-parent-delete races.
        self._check_parent_exists(resource, user_id, tenant_id, partner_app_id, issuer)

        transact_items: List[Dict[str, Any]] = []
        idem_index: Optional[int] = None
        capacity_index: Optional[int] = None
        parent_indices: List[int] = []
        now_iso = self._now()
        now_epoch = self._now_epoch()
        idem_key: Optional[str] = None
        payload_hash: Optional[str] = None

        if idempotency_key:
            idem_key = self._idem_key(rt, user_id, tenant_id, partner_app_id,
                                      issuer, idempotency_key)
            payload_hash = self._payload_hash(resource)
            idem_item = {
                "resourceId": idem_key,
                "resourceType": IDEMPOTENCY_RESOURCE_TYPE,
                "targetResourceId": rid,
                "payloadHash": payload_hash,
                "userId": user_id,
                "tenantId": tenant_id,
                "partnerApplicationId": partner_app_id,
                "issuer": issuer,
                "createdAt": now_iso,
                "updatedAt": now_iso,
                "expiresAt": now_epoch + IDEMPOTENCY_TTL_SECONDS,
            }
            idem_index = len(transact_items)
            transact_items.append({
                "Put": {
                    "TableName": self.table_name,
                    "Item": self._serialize(idem_item),
                    "ConditionExpression":
                        "attribute_not_exists(resourceId) OR expiresAt < :now",
                    "ExpressionAttributeValues": {":now": {"N": str(now_epoch)}},
                }
            })

        if rt in CAPACITY_RULES:
            max_count = CAPACITY_RULES[rt]
            ckey = self._capacity_key(rt, user_id, tenant_id, resource)
            # Counter must exist before the transaction conditions it.
            self._ensure_counter(ckey)
            # AWS rule: one action per item per transaction. The capacity
            # condition is therefore on the counter Update itself.
            capacity_index = len(transact_items)
            transact_items.append({
                "Update": {
                    "TableName": self.table_name,
                    "Key": {"resourceId": {"S": ckey}},
                    "ConditionExpression": "#c < :max",
                    "UpdateExpression": "SET #c = #c + :inc, updatedAt = :now",
                    "ExpressionAttributeNames": {"#c": "count"},
                    "ExpressionAttributeValues": {
                        ":max": {"N": str(max_count)},
                        ":inc": {"N": "1"},
                        ":now": {"S": now_iso},
                    },
                }
            })

        for check in self._parent_checks(resource, user_id, tenant_id):
            parent_indices.append(len(transact_items))
            transact_items.append(check)

        item = self._to_item(resource, user_id=user_id, tenant_id=tenant_id,
                            partner_app_id=partner_app_id, issuer=issuer, version=1)
        resource_index = len(transact_items)
        transact_items.append({
            "Put": {
                "TableName": self.table_name,
                "Item": self._serialize(item),
                "ConditionExpression": "attribute_not_exists(resourceId)",
            }
        })

        try:
            self.client.transact_write_items(TransactItems=transact_items)
        except self.client.exceptions.TransactionCanceledException as e:
            failed = self._cancelled_indices(e)
            if idem_index is not None and idem_index in failed:
                record = self._get_raw(idem_key) or {}
                if not record:
                    raise PartnerProfileConflictError("Idempotency conflict")
                if record.get("payloadHash") != payload_hash:
                    raise PartnerProfileConflictError(
                        "Idempotency key reused with a different payload")
                target = record.get("targetResourceId")
                if not target:
                    raise PartnerProfileConflictError(
                        "Idempotency record is incomplete")
                return target
            if capacity_index is not None and capacity_index in failed:
                raise PartnerProfileConflictError("Capacity exceeded")
            if any(idx in failed for idx in parent_indices):
                raise PartnerProfileConflictError(
                    "Parent is being deleted or is not accessible")
            if resource_index in failed:
                raise PartnerProfileConflictError("Resource already exists")
            raise PartnerProfileConflictError("Transaction cancelled")
        except Exception as e:
            if "ConditionalCheckFailed" in str(e):
                raise PartnerProfileConflictError(str(e))
            raise
        return rid

    def get(self, resource_id: str, user_id: str, tenant_id: str,
            partner_app_id: Optional[str] = None, issuer: Optional[str] = None) -> Optional[Any]:
        if self.table is None:
            return None
        try:
            resp = self.table.get_item(Key={"resourceId": resource_id},
                                       ConsistentRead=True)
        except Exception as e:
            logger.error("get_item failed: %s", e)
            raise PartnerProfileReadError("Profile read failed") from e
        item = resp.get("Item")
        if not item:
            return None
        if not self._identity_ok(item, user_id, tenant_id, partner_app_id, issuer):
            return None
        try:
            return self._from_item(item)
        except ProfileContractError as e:
            # A stored item that cannot be parsed is not "not found" and must
            # never be emitted as an incomplete resource.
            logger.error("stored profile is not a valid resource: %s", e)
            raise PartnerProfileReadError("Stored profile is unreadable") from e

    def list_by_user(self, user_id: str, tenant_id: str,
                     resource_type: Optional[str] = None,
                     partner_app_id: Optional[str] = None,
                     issuer: Optional[str] = None,
                     limit: int = 50,
                     cursor: Optional[Dict[str, Any]] = None) -> Tuple[List[Any], Optional[Dict[str, Any]]]:
        if self.table is None:
            return [], None
        kwargs: Dict[str, Any] = {
            "IndexName": "gsi-user",
            "KeyConditionExpression": "userId = :u",
            # Native values: self.table is a boto3 resource Table, which
            # serialises them exactly once.
            "ExpressionAttributeValues": {":u": user_id},
            "Limit": limit,
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = cursor
        if resource_type:
            # resourceType is the gsi-user range key, so it belongs in the
            # KeyConditionExpression, never in a FilterExpression.
            kwargs["KeyConditionExpression"] += " AND resourceType = :rt"
            kwargs["ExpressionAttributeValues"][":rt"] = resource_type
        kwargs["ExpressionAttributeValues"][":t"] = tenant_id
        # Only real profile resources carry a payload. Capacity counters,
        # idempotency records and lifecycle guards do not, so this non-key
        # filter keeps them out without touching the index keys.
        filters = ["tenantId = :t", "attribute_exists(payload)"]
        if partner_app_id is not None:
            filters.append("partnerApplicationId = :p")
            kwargs["ExpressionAttributeValues"][":p"] = partner_app_id
        if issuer is not None:
            filters.append("issuer = :i")
            kwargs["ExpressionAttributeValues"][":i"] = issuer
        kwargs["FilterExpression"] = " AND ".join(filters)
        try:
            resp = self.table.query(**kwargs)
        except Exception as e:
            logger.error("gsi-user query failed: %s", e)
            raise PartnerProfileReadError("Profile list failed") from e
        items = []
        for it in resp.get("Items", []):
            obj = self._from_item(it)
            if obj is not None:
                items.append(obj)
        return items, resp.get("LastEvaluatedKey")

    def list_by_parent(self, parent_id: str, user_id: str, tenant_id: str,
                       resource_type: Optional[str] = None,
                       partner_app_id: Optional[str] = None,
                       issuer: Optional[str] = None,
                       limit: int = 50,
                       cursor: Optional[Dict[str, Any]] = None) -> Tuple[List[Any], Optional[Dict[str, Any]]]:
        if self.table is None:
            return [], None
        kwargs: Dict[str, Any] = {
            "IndexName": "gsi-parent",
            "KeyConditionExpression": "parentId = :p",
            "ExpressionAttributeValues": {
                ":p": parent_id,
                ":u": user_id,
                ":t": tenant_id,
            },
            "Limit": limit,
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = cursor
        filters = ["userId = :u", "tenantId = :t",
                   "attribute_exists(payload)"]
        if resource_type:
            filters.append("resourceType = :rt")
            kwargs["ExpressionAttributeValues"][":rt"] = resource_type
        if partner_app_id is not None:
            filters.append("partnerApplicationId = :pa")
            kwargs["ExpressionAttributeValues"][":pa"] = partner_app_id
        if issuer is not None:
            filters.append("issuer = :i")
            kwargs["ExpressionAttributeValues"][":i"] = issuer
        kwargs["FilterExpression"] = " AND ".join(filters)
        try:
            resp = self.table.query(**kwargs)
        except Exception as e:
            # Fail closed: a failed GSI query is not an empty page and must
            # never be replaced by a differently paginated user-level list.
            logger.error("gsi-parent query failed: %s", e)
            raise PartnerProfileReadError("Profile list failed") from e
        items = []
        for it in resp.get("Items", []):
            obj = self._from_item(it)
            if obj is not None:
                items.append(obj)
        return items, resp.get("LastEvaluatedKey")

    def _get_raw(self, resource_id: str) -> Optional[Dict[str, Any]]:
        if self.table is None:
            return None
        try:
            resp = self.table.get_item(Key={"resourceId": resource_id},
                                       ConsistentRead=True)
            return resp.get("Item")
        except Exception as e:
            logger.error("get_item raw failed: %s", e)
            raise PartnerProfileReadError("Profile read failed") from e

    def update(self, resource: Any, *, user_id: str, tenant_id: str,
               partner_app_id: Optional[str] = None, issuer: Optional[str] = None,
               expected_version: Optional[int] = None) -> bool:
        if self.table is None:
            return False
        rid = self._resource_id(resource)
        raw = self._get_raw(rid)
        if not raw:
            return False
        if not self._identity_ok(raw, user_id, tenant_id, partner_app_id, issuer):
            return False
        cur_ver = _normalize_numbers(raw.get("version", 1))
        if expected_version is not None and expected_version != cur_ver:
            raise PartnerProfileConflictError(f"Version conflict: expected {expected_version}, got {cur_ver}")
        item = self._to_item(resource, user_id=user_id, tenant_id=tenant_id,
                            partner_app_id=partner_app_id, issuer=issuer, version=cur_ver + 1)
        item["resourceId"] = rid
        item["createdAt"] = raw.get("createdAt") or item["createdAt"]
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="version = :v",
                ExpressionAttributeValues={":v": cur_ver},
            )
        except Exception as e:
            if "ConditionalCheckFailed" in str(e):
                raise PartnerProfileConflictError("Concurrent update conflict")
            raise
        return True

    def delete(self, resource_id: str, user_id: str, tenant_id: str,
               partner_app_id: Optional[str] = None, issuer: Optional[str] = None,
               expected_version: Optional[int] = None,
               child_type: Optional[str] = None) -> bool:
        if self.table is None:
            return False
        raw = self._get_raw(resource_id)
        if not raw:
            return False
        if not self._identity_ok(raw, user_id, tenant_id, partner_app_id, issuer):
            return False
        cur_ver = _normalize_numbers(raw.get("version", 1))
        if expected_version is not None and expected_version != cur_ver:
            raise PartnerProfileConflictError("Version conflict on delete")
        rt = raw.get("resourceType")

        transact_items: List[Dict[str, Any]] = [{
            "Delete": {
                "TableName": self.table_name,
                "Key": {"resourceId": {"S": resource_id}},
                "ConditionExpression": "userId = :u AND tenantId = :t AND version = :v",
                "ExpressionAttributeValues": {
                    ":u": {"S": user_id},
                    ":t": {"S": tenant_id},
                    ":v": {"N": str(cur_ver)},
                },
            }
        }]
        if partner_app_id is not None:
            transact_items[0]["Delete"]["ConditionExpression"] += " AND partnerApplicationId = :p"
            transact_items[0]["Delete"]["ExpressionAttributeValues"][":p"] = {"S": partner_app_id}
        if issuer is not None:
            transact_items[0]["Delete"]["ConditionExpression"] += " AND issuer = :i"
            transact_items[0]["Delete"]["ExpressionAttributeValues"][":i"] = {"S": issuer}

        # Decrement the matching capacity counter atomically alongside the delete.
        if rt in CAPACITY_RULES:
            parent_id = raw.get("parentId") or user_id
            ckey = self._counter_key(rt, parent_id)
            transact_items.append({
                "Update": {
                    "TableName": self.table_name,
                    "Key": {"resourceId": {"S": ckey}},
                    "ConditionExpression": "#c > :zero",
                    "UpdateExpression": "SET #c = #c - :inc, updatedAt = :now",
                    "ExpressionAttributeNames": {"#c": "count"},
                    "ExpressionAttributeValues": {
                        ":inc": {"N": "1"},
                        ":zero": {"N": "0"},
                        ":now": {"S": self._now()},
                    },
                }
            })

        child_index: Optional[int] = None
        if child_type:
            # Atomic child guard: the parent can only be deleted while the
            # child counter is zero. A concurrent child create increments the
            # same counter in its own transaction, so exactly one wins.
            child_counter = self._counter_key(child_type, resource_id)
            child_index = len(transact_items)
            transact_items.append(self._condition_check(
                child_counter,
                "attribute_not_exists(resourceId) OR #c = :zero",
                {":zero": {"N": "0"}},
                names={"#c": "count"},
            ))

        try:
            self.client.transact_write_items(TransactItems=transact_items)
        except self.client.exceptions.TransactionCanceledException as e:
            failed = self._cancelled_indices(e)
            if child_index is not None and child_index in failed:
                raise PartnerProfileConflictError(
                    "Resource has child profiles; delete refused")
            return False
        except Exception as e:
            if "ConditionalCheckFailed" in str(e):
                return False
            raise
        return True

    # ------------------------------------------------------------------ #
    # Two-phase parent delete (R05-A, used by the CV handler around S3)
    # ------------------------------------------------------------------ #
    def reserve_parent_delete(self, resource_id: str, *, user_id: str,
                              tenant_id: str,
                              partner_app_id: Optional[str] = None,
                              issuer: Optional[str] = None,
                              child_type: Optional[str] = None,
                              expected_version: Optional[int] = None
                              ) -> Dict[str, Any]:
        """Phase A: atomically mark the parent as deleting and verify no children.

        The guard Update and the child-counter ConditionCheck are distinct
        items, so the AWS one-action-per-item rule holds. Raises
        ``PartnerProfileConflictError`` for children/version and
        ``PartnerProfileNotFoundError`` for missing/foreign parents.
        """
        raw = self._get_raw(resource_id)
        if not raw:
            raise PartnerProfileNotFoundError("Parent not found")
        if not self._identity_ok(raw, user_id, tenant_id, partner_app_id, issuer):
            raise PartnerProfileNotFoundError("Parent not found")
        cur_ver = _normalize_numbers(raw.get("version", 1))
        if expected_version is not None and expected_version != cur_ver:
            raise PartnerProfileConflictError("Version conflict on delete")
        rt = raw.get("resourceType")
        guard_key = self._guard_key(rt, resource_id)

        parent_expr = "attribute_exists(resourceId) AND userId = :u AND tenantId = :t"
        parent_values = {":u": {"S": user_id}, ":t": {"S": tenant_id}}
        if expected_version is not None:
            parent_expr += " AND version = :v"
            parent_values[":v"] = {"N": str(expected_version)}

        items: List[Dict[str, Any]] = [{
            "Update": {
                "TableName": self.table_name,
                "Key": {"resourceId": {"S": guard_key}},
                "ConditionExpression":
                    "attribute_not_exists(resourceId) OR #s IN (:active, :deleting)",
                "UpdateExpression": "SET #s = :deleting, updatedAt = :now",
                "ExpressionAttributeNames": {"#s": "state"},
                "ExpressionAttributeValues": {
                    ":active": {"S": LIFECYCLE_ACTIVE},
                    ":deleting": {"S": LIFECYCLE_DELETING},
                    ":now": {"S": self._now()},
                },
            }
        }, self._condition_check(resource_id, parent_expr, parent_values)]

        child_counter_index: Optional[int] = None
        if child_type:
            child_counter = self._counter_key(child_type, resource_id)
            child_counter_index = len(items)
            items.append(self._condition_check(
                child_counter,
                "attribute_not_exists(resourceId) OR #c = :zero",
                {":zero": {"N": "0"}},
                names={"#c": "count"},
            ))

        try:
            self.client.transact_write_items(TransactItems=items)
        except self.client.exceptions.TransactionCanceledException as e:
            failed = self._cancelled_indices(e)
            if child_counter_index is not None and child_counter_index in failed:
                raise PartnerProfileConflictError(
                    "Resource has child profiles; delete refused")
            if 1 in failed:
                raise PartnerProfileNotFoundError("Parent not found")
            if 0 in failed:
                raise PartnerProfileConflictError("Delete already in progress")
            raise PartnerProfileConflictError("Delete reservation refused")

        return {
            "resource_id": resource_id,
            "guard_key": guard_key,
            "child_type": child_type,
            "counter_key": self._counter_key(rt, raw.get("parentId") or user_id),
        }

    def release_parent_delete(self, reservation: Dict[str, Any], *,
                              user_id: str, tenant_id: str,
                              partner_app_id: Optional[str] = None,
                              issuer: Optional[str] = None) -> bool:
        """Rollback Phase A after an S3 failure; metadata stays intact."""
        try:
            self.table.update_item(
                Key={"resourceId": reservation["guard_key"]},
                UpdateExpression="SET #s = :active, updatedAt = :now",
                ConditionExpression="#s = :deleting",
                ExpressionAttributeNames={"#s": "state"},
                ExpressionAttributeValues={
                    ":active": LIFECYCLE_ACTIVE,
                    ":deleting": LIFECYCLE_DELETING,
                    ":now": self._now(),
                },
            )
        except Exception:
            logger.warning("delete reservation release failed")
            return False
        return True

    def finalize_parent_delete(self, reservation: Dict[str, Any], *,
                               user_id: str, tenant_id: str,
                               partner_app_id: Optional[str] = None,
                               issuer: Optional[str] = None,
                               expected_version: Optional[int] = None
                               ) -> bool:
        """Phase C: delete the resource + counter + guard atomically."""
        resource_id = reservation["resource_id"]
        raw = self._get_raw(resource_id)
        if not raw:
            return False
        if not self._identity_ok(raw, user_id, tenant_id, partner_app_id, issuer):
            return False
        cur_ver = _normalize_numbers(raw.get("version", 1))
        if expected_version is not None and expected_version != cur_ver:
            raise PartnerProfileConflictError("Version conflict on delete")
        rt = raw.get("resourceType")

        items: List[Dict[str, Any]] = [{
            "Delete": {
                "TableName": self.table_name,
                "Key": {"resourceId": {"S": resource_id}},
                "ConditionExpression":
                    "userId = :u AND tenantId = :t AND version = :v",
                "ExpressionAttributeValues": {
                    ":u": {"S": user_id}, ":t": {"S": tenant_id},
                    ":v": {"N": str(cur_ver)},
                },
            }
        }]
        if partner_app_id is not None:
            items[0]["Delete"]["ConditionExpression"] += " AND partnerApplicationId = :p"
            items[0]["Delete"]["ExpressionAttributeValues"][":p"] = {"S": partner_app_id}
        if issuer is not None:
            items[0]["Delete"]["ConditionExpression"] += " AND issuer = :i"
            items[0]["Delete"]["ExpressionAttributeValues"][":i"] = {"S": issuer}

        if rt in CAPACITY_RULES:
            items.append({
                "Update": {
                    "TableName": self.table_name,
                    "Key": {"resourceId": {"S": reservation["counter_key"]}},
                    "ConditionExpression": "#c > :zero",
                    "UpdateExpression": "SET #c = #c - :inc, updatedAt = :now",
                    "ExpressionAttributeNames": {"#c": "count"},
                    "ExpressionAttributeValues": {
                        ":inc": {"N": "1"}, ":zero": {"N": "0"},
                        ":now": {"S": self._now()},
                    },
                }
            })

        items.append({
            "Delete": {
                "TableName": self.table_name,
                "Key": {"resourceId": {"S": reservation["guard_key"]}},
                "ConditionExpression": "#s = :deleting",
                "ExpressionAttributeNames": {"#s": "state"},
                "ExpressionAttributeValues": {
                    ":deleting": {"S": LIFECYCLE_DELETING},
                },
            }
        })

        if reservation.get("child_type"):
            child_counter = self._counter_key(reservation["child_type"], resource_id)
            items.append(self._condition_check(
                child_counter,
                "attribute_not_exists(resourceId) OR #c = :zero",
                {":zero": {"N": "0"}},
                names={"#c": "count"},
            ))

        try:
            self.client.transact_write_items(TransactItems=items)
        except self.client.exceptions.TransactionCanceledException as e:
            raise PartnerProfileConflictError("Delete finalization refused")
        except Exception as e:
            if "ConditionalCheckFailed" in str(e):
                raise PartnerProfileConflictError("Delete finalization refused")
            raise
        return True
