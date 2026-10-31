"""DynamoDB repository for partner profile persistence (R02).

Persistence layer for the v1 partner profile contract. Reuses the contract
validation from `jobsearch.partner_profile_contract` (no second validation).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from jobsearch.partner_profile_contract import (
    SCHEMA_VERSION,
    ProfileContractError,
    parse_resource,
    CVDocument,
    CVSearchProfile,
    ATSSearchProfile,
    ManualSearchProfile,
    validate_cv_capacity,
    validate_search_profile_capacity,
    validate_ats_profile_capacity,
    validate_ats_assignment,
    MAX_CVS_PER_USER,
    MAX_SEARCH_PROFILES_PER_CV,
    MAX_ATS_PROFILES_PER_SEARCH_PROFILE,
)

logger = logging.getLogger(__name__)

PERSISTED_RESOURCE_TYPES = frozenset({
    "CVDocument",
    "CVSearchProfile",
    "ATSSearchProfile",
    "ManualSearchProfile",
})


class PartnerProfileNotFoundError(Exception):
    pass


class PartnerProfileConflictError(Exception):
    pass


class PartnerProfileRepository:
    def __init__(self, table_name: Optional[str] = None, dynamodb=None):
        self.table_name = table_name or os.environ.get("PARTNER_PROFILE_TABLE")
        self._dynamodb = dynamodb
        self._table = None

    @property
    def table(self):
        if self._table is None:
            if not self._dynamodb:
                import boto3
                self._dynamodb = boto3.resource("dynamodb")
            self._table = self._dynamodb.Table(self.table_name) if self.table_name else None
        return self._table

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

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
        item = {
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
        return item

    def _resource_id(self, resource: Any) -> str:
        # stable server-side id: use provided id if present else generate
        for attr in ("ats_profile_id", "search_profile_id", "manual_profile_id", "cv_id"):
            val = getattr(resource, attr, None)
            if val:
                return val
        return uuid.uuid4().hex

    def _from_item(self, item: Dict[str, Any]) -> Any:
        payload = item.get("payload") or {}
        # ensure identity from item authoritative
        payload = dict(payload)
        payload["userId"] = item.get("userId")
        payload["tenantId"] = item.get("tenantId")
        return parse_resource(payload, strict=False)

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create(self, resource: Any, *, user_id: str, tenant_id: str,
               partner_app_id: Optional[str] = None, issuer: Optional[str] = None) -> str:
        if self.table is None:
            raise RuntimeError("DynamoDB table not configured")
        rt = getattr(resource, "resource_type", None)
        if rt not in PERSISTED_RESOURCE_TYPES:
            raise ValueError(f"Unsupported resource type: {rt}")
        # capacity checks
        self._check_capacity_on_create(resource, user_id, tenant_id, partner_app_id, issuer)
        # parent existence check
        self._check_parent_exists(resource, user_id, tenant_id, partner_app_id, issuer)
        item = self._to_item(resource, user_id=user_id, tenant_id=tenant_id,
                            partner_app_id=partner_app_id, issuer=issuer, version=1)
        rid = item["resourceId"]
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(resourceId)",
            )
        except Exception as e:
            # conditional failure
            if "ConditionalCheckFailed" in str(e):
                raise PartnerProfileConflictError(f"Resource already exists: {rid}")
            raise
        return rid

    def _check_capacity_on_create(self, resource, user_id, tenant_id, partner_app_id, issuer):
        if isinstance(resource, CVDocument):
            existing = self.list_by_user(user_id, tenant_id, "CVDocument",
                                        partner_app_id=partner_app_id, issuer=issuer, limit=1000)[0]
            validate_cv_capacity(existing + [resource])
        elif isinstance(resource, CVSearchProfile):
            existing = self.list_by_parent(resource.cv_id, user_id, tenant_id, "CVSearchProfile",
                                          partner_app_id=partner_app_id, issuer=issuer, limit=1000)[0]
            validate_search_profile_capacity(existing + [resource])
        elif isinstance(resource, ATSSearchProfile):
            existing = self.list_by_parent(resource.search_profile_id, user_id, tenant_id, "ATSSearchProfile",
                                          partner_app_id=partner_app_id, issuer=issuer, limit=1000)[0]
            validate_ats_profile_capacity(existing + [resource])

    def _check_parent_exists(self, resource, user_id, tenant_id, partner_app_id, issuer):
        if isinstance(resource, CVSearchProfile):
            parent = self.get(resource.cv_id, user_id, tenant_id, partner_app_id, issuer)
            if parent is None or not isinstance(parent, CVDocument):
                raise ProfileContractError("INVALID_HIERARCHY", "Parent CV not found")
            # identity consistency
            if parent.user_id != resource.user_id or parent.tenant_id != resource.tenant_id:
                raise ProfileContractError("INVALID_HIERARCHY", "Identity mismatch with parent CV")
        elif isinstance(resource, ATSSearchProfile):
            parent = self.get(resource.search_profile_id, user_id, tenant_id, partner_app_id, issuer)
            if parent is None or not isinstance(parent, CVSearchProfile):
                raise ProfileContractError("INVALID_HIERARCHY", "Parent search profile not found")
            validate_ats_assignment(resource, parent)

    def get(self, resource_id: str, user_id: str, tenant_id: str,
            partner_app_id: Optional[str] = None, issuer: Optional[str] = None) -> Optional[Any]:
        if self.table is None:
            return None
        try:
            resp = self.table.get_item(Key={"resourceId": resource_id})
        except Exception as e:
            logger.error("get_item failed: %s", e)
            return None
        item = resp.get("Item")
        if not item:
            return None
        if not self._identity_ok(item, user_id, tenant_id, partner_app_id, issuer):
            return None
        return self._from_item(item)

    def list_by_user(self, user_id: str, tenant_id: str,
                     resource_type: Optional[str] = None,
                     partner_app_id: Optional[str] = None,
                     issuer: Optional[str] = None,
                     limit: int = 50,
                     cursor: Optional[Dict[str, Any]] = None) -> Tuple[List[Any], Optional[Dict[str, Any]]]:
        if self.table is None:
            return [], None
        # Use GSI gsi-user (hashKey userId). Filter tenant/resourceType server-side.
        kwargs: Dict[str, Any] = {
            "IndexName": "gsi-user",
            "KeyConditionExpression": "userId = :u",
            "ExpressionAttributeValues": {":u": user_id},
            "Limit": limit,
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = cursor
        # filter tenant and resource type
        filters = ["tenantId = :t"]
        kwargs["ExpressionAttributeValues"][":t"] = tenant_id
        if resource_type:
            filters.append("resourceType = :rt")
            kwargs["ExpressionAttributeValues"][":rt"] = resource_type
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
            logger.error("query failed: %s", e)
            return [], None
        items = [self._from_item(it) for it in resp.get("Items", [])]
        # tenant identity double-check
        items = [r for r in items if True]
        return items, resp.get("LastEvaluatedKey")

    def list_by_parent(self, parent_id: str, user_id: str, tenant_id: str,
                       resource_type: Optional[str] = None,
                       partner_app_id: Optional[str] = None,
                       issuer: Optional[str] = None,
                       limit: int = 50,
                       cursor: Optional[Dict[str, Any]] = None) -> Tuple[List[Any], Optional[Dict[str, Any]]]:
        if self.table is None:
            return [], None
        # Query via gsi-parent if available; fallback scan-filter
        try:
            kwargs: Dict[str, Any] = {
                "IndexName": "gsi-parent",
                "KeyConditionExpression": "parentId = :p",
                "ExpressionAttributeValues": {":p": parent_id},
                "Limit": limit,
            }
            if cursor:
                kwargs["ExclusiveStartKey"] = cursor
            filters = ["userId = :u", "tenantId = :t"]
            kwargs["ExpressionAttributeValues"][":u"] = user_id
            kwargs["ExpressionAttributeValues"][":t"] = tenant_id
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
            resp = self.table.query(**kwargs)
        except Exception:
            # fallback: list by user and filter parentId
            items, _ = self.list_by_user(user_id, tenant_id, resource_type, partner_app_id, issuer, limit=1000)
            filtered = [r for r in items if getattr(r, "_parent_id", None) == parent_id or self._parent_of(r) == parent_id]
            return filtered, None
        items = [self._from_item(it) for it in resp.get("Items", [])]
        return items, resp.get("LastEvaluatedKey")

    def _parent_of(self, resource: Any) -> Optional[str]:
        if isinstance(resource, CVSearchProfile):
            return resource.cv_id
        if isinstance(resource, ATSSearchProfile):
            return resource.search_profile_id
        return None

    def update(self, resource: Any, *, user_id: str, tenant_id: str,
               partner_app_id: Optional[str] = None, issuer: Optional[str] = None,
               expected_version: Optional[int] = None) -> bool:
        if self.table is None:
            return False
        rid = self._resource_id(resource)
        existing = self.get(rid, user_id, tenant_id, partner_app_id, issuer)
        if existing is None:
            return False
        # identity mutation guard: resource identity must match existing
        if getattr(resource, "user_id", None) not in (None, existing.user_id if hasattr(existing, "user_id") else None):
            raise ProfileContractError("CLIENT_IDENTITY_FORBIDDEN", "Cannot change owner identity")
        if getattr(resource, "tenant_id", None) not in (None, existing.tenant_id if hasattr(existing, "tenant_id") else None):
            raise ProfileContractError("CLIENT_IDENTITY_FORBIDDEN", "Cannot change tenant identity")
        new_version = (existing.version if hasattr(existing, "version") else 1) + 1 if False else None
        # version from item not on typed object; fetch raw
        raw = self._get_raw(rid)
        cur_ver = raw.get("version", 1) if raw else 1
        if expected_version is not None and expected_version != cur_ver:
            raise PartnerProfileConflictError(f"Version conflict: expected {expected_version}, got {cur_ver}")
        item = self._to_item(resource, user_id=user_id, tenant_id=tenant_id,
                            partner_app_id=partner_app_id, issuer=issuer, version=cur_ver + 1)
        item["resourceId"] = rid
        item["createdAt"] = raw.get("createdAt") if raw else item["createdAt"]
        try:
            cond = "version = :v" if expected_version is None else "version = :v"
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

    def _get_raw(self, resource_id: str) -> Optional[Dict[str, Any]]:
        if self.table is None:
            return None
        try:
            resp = self.table.get_item(Key={"resourceId": resource_id})
            return resp.get("Item")
        except Exception:
            return None

    def delete(self, resource_id: str, user_id: str, tenant_id: str,
               partner_app_id: Optional[str] = None, issuer: Optional[str] = None,
               expected_version: Optional[int] = None) -> bool:
        if self.table is None:
            return False
        existing = self.get(resource_id, user_id, tenant_id, partner_app_id, issuer)
        if existing is None:
            return False
        raw = self._get_raw(resource_id)
        cur_ver = raw.get("version", 1) if raw else 1
        if expected_version is not None and expected_version != cur_ver:
            raise PartnerProfileConflictError("Version conflict on delete")
        try:
            kwargs = {
                "Key": {"resourceId": resource_id},
                "ConditionExpression": "userId = :u AND tenantId = :t AND version = :v",
                "ExpressionAttributeValues": {":u": user_id, ":t": tenant_id, ":v": cur_ver},
            }
            if partner_app_id is not None:
                kwargs["ConditionExpression"] += " AND partnerApplicationId = :p"
                kwargs["ExpressionAttributeValues"][":p"] = partner_app_id
            if issuer is not None:
                kwargs["ConditionExpression"] += " AND issuer = :i"
                kwargs["ExpressionAttributeValues"][":i"] = issuer
            self.table.delete_item(**kwargs)
        except Exception as e:
            if "ConditionalCheckFailed" in str(e):
                return False
            raise
        return True
