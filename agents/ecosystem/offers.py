"""
Offer catalog + Offer -> Entitlement grant (user-wide / APIProfile-bound).

Contract: PROMPT 04-R1 (minimal offer), PROMPT 05-R2 (final),
PROMPT 06-R5 (grant sequence) / Gate P11.

An offer is a grantable package of agent rights owned by the RIS
platform (NO per-offer owner, NO prices/billing/subscriptions).
A grant creates one entitlement row per offer agent — atomically
(all-or-nothing), idempotently, never partially, never silently
merged/extended. Offer edits and INACTIVE affect FUTURE grants
only; existing entitlements live until expiry/withdrawal.

Entitlement rows reuse the EXISTING schema (entitlementId PK,
userId/agentId GSIs, validFrom/validUntil windows, TTL expiresAt)
plus two additive attributes: apiProfileId (absent = user-wide)
and offerId/grantId provenance. No second permission world.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ADMIN_GROUP = "admins"

STATUS_ACTIVE = "ACTIVE"
STATUS_INACTIVE = "INACTIVE"

SCOPE_USER = "USER"
SCOPE_PROFILE = "APIPROFILE"


class OfferNotFound(Exception):
    """Offer unknown (grant refused)."""


class OfferConflict(Exception):
    """Name uniqueness / idempotency mismatch (409 analog)."""


class GrantDenied(Exception):
    """Grant refused (inactive offer, bad agent, bad target, bad window)."""


class GrantConflict(Exception):
    """Overlapping grant or idempotency-key mismatch (no silent merge)."""


class UnauthorizedOfferAction(Exception):
    """Non-admin offer/grant action (audited)."""


class EntitlementNotFound(Exception):
    """Withdrawal target missing."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch(value: str) -> int:
    from dateutil.parser import parse

    moment = parse(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp())


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        from dateutil.parser import parse
        parsed = parse(value)
    except Exception:
        try:
            parsed = datetime.fromisoformat(value)
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _audit(action: str, outcome: str, fields: Dict[str, Any]) -> str:
    audit_ref = uuid.uuid4().hex[:16]
    logger.warning("offer-audit ref=%s action=%s outcome=%s %s",
                   audit_ref, action, outcome,
                   " ".join(f"{k}={v}" for k, v in sorted(fields.items())))
    return audit_ref


def _is_admin(actor: Dict[str, Any]) -> bool:
    return ADMIN_GROUP in (actor.get("groups") or [])


def _actor_label(actor: Dict[str, Any]) -> str:
    return str(actor.get("userId") or "?")


def _require_admin(actor: Dict[str, Any], action: str) -> None:
    if not _is_admin(actor):
        _audit("unauthorized-offer-action", "denied",
               {"action": action, "actor": _actor_label(actor),
                "role": "staff" if "Staff" in (actor.get("groups") or [])
                else "user"})
        raise UnauthorizedOfferAction(f"only admin may {action}")


def _same_name(a: Any, b: Any) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


# ------------------------------------------------------------------
# Offer stores (in-memory for tests; DynamoDB adapter lazy)
# ------------------------------------------------------------------

class InMemoryOfferStore:
    """Test/harness offer store (same interface as DynamoDB one)."""

    def __init__(self) -> None:
        self.items: Dict[str, Dict[str, Any]] = {}

    def put_offer(self, item: Dict[str, Any]) -> None:
        if item["offerId"] in self.items:
            raise OfferConflict("offerId exists")
        self.items[item["offerId"]] = dict(item)

    def get_offer(self, offer_id: str) -> Optional[Dict[str, Any]]:
        item = self.items.get(offer_id)
        return dict(item) if item else None

    def list_offers(self) -> List[Dict[str, Any]]:
        return [dict(i) for i in self.items.values()]

    def update_offer(self, offer_id: str, item: Dict[str, Any]) -> None:
        if offer_id not in self.items:
            raise OfferNotFound(offer_id)
        self.items[offer_id] = dict(item)


class DynamoDBOfferStore:
    """Production offer store (lazy; table from the later TF gate).

    Required table design (NOT created here): PK offerId (S) +
    PAY_PER_REQUEST + SSE default. Name uniqueness enforced in the
    service layer (scan + conditional discipline, documented).
    """

    def __init__(self, table: Any = None,
                 table_name: Optional[str] = None) -> None:
        self._table = table
        self._table_name = table_name

    def _table_obj(self) -> Any:
        if self._table is not None:
            return self._table
        if not self._table_name:
            raise RuntimeError("offer table_name is required")
        import boto3

        import os

        return boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "eu-central-1"),
        ).Table(self._table_name)

    def put_offer(self, item: Dict[str, Any]) -> None:
        from botocore.exceptions import ClientError

        try:
            self._table_obj().put_item(
                Item={k: v for k, v in dict(item).items()
                      if v is not None},
                ConditionExpression="attribute_not_exists(offerId)")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == \
                    "ConditionalCheckFailedException":
                raise OfferConflict("offerId exists") from exc
            raise

    def get_offer(self, offer_id: str) -> Optional[Dict[str, Any]]:
        response = self._table_obj().get_item(Key={"offerId": offer_id})
        item = response.get("Item")
        return dict(item) if item else None

    def list_offers(self) -> List[Dict[str, Any]]:
        response = self._table_obj().scan()
        return [dict(i) for i in response.get("Items", [])]

    def update_offer(self, offer_id: str, item: Dict[str, Any]) -> None:
        self._table_obj().put_item(
            Item={k: v for k, v in dict(item).items() if v is not None})


# ------------------------------------------------------------------
# Entitlement stores (EXISTING schema + apiProfileId/offerId/grantId)
# ------------------------------------------------------------------

class InMemoryEntitlementStore:
    """Test/harness entitlement store (existing row shape + additions)."""

    def __init__(self) -> None:
        self.items: Dict[str, Dict[str, Any]] = {}

    def put_entitlements_batch(self, rows: List[Dict[str, Any]]) -> None:
        for row in rows:  # atomic: validate first (no partial writes)
            if row["entitlementId"] in self.items:
                raise GrantConflict("entitlementId exists")
        for row in rows:
            self.items[row["entitlementId"]] = dict(row)

    def find_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        return [dict(i) for i in self.items.values()
                if i.get("userId") == user_id]

    def find_by_key(self, idempotency_key: str) -> List[Dict[str, Any]]:
        return [dict(i) for i in self.items.values()
                if i.get("idempotencyKey") == idempotency_key]

    def get_entitlement(self, entitlement_id: str
                        ) -> Optional[Dict[str, Any]]:
        item = self.items.get(entitlement_id)
        return dict(item) if item else None

    def delete_entitlement(self, entitlement_id: str) -> None:
        if entitlement_id not in self.items:
            raise EntitlementNotFound(entitlement_id)
        del self.items[entitlement_id]


class DynamoDBEntitlementStore:
    """Production entitlement writes/reads (EXISTING table, lazy).

    Uses the provisioned table (PK entitlementId, gsi-user, gsi-agent)
    with CORRECT IndexName usage. Writes are transactional
    (all-or-nothing). apiProfileId/offerId/grantId are plain
    schemaless attributes — no TF change required for them.
    """

    def __init__(self, table: Any = None, table_name: Optional[str] = None,
                 user_index: str = "gsi-user") -> None:
        self._table = table
        self._table_name = table_name
        self._user_index = user_index

    def _table_obj(self) -> Any:
        if self._table is not None:
            return self._table
        if not self._table_name:
            raise RuntimeError("entitlement table_name is required")
        import boto3

        import os

        return boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "eu-central-1"),
        ).Table(self._table_name)

    def _to_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        item: Dict[str, Any] = {}
        for key, value in row.items():
            if value is None:
                continue
            if isinstance(value, bool):
                item[key] = {"BOOL": value}
            elif isinstance(value, (int, float)):
                item[key] = {"N": str(value)}
            elif isinstance(value, str):
                item[key] = {"S": value}
            elif isinstance(value, dict):
                item[key] = {"M": {k: ({"S": str(v)} if isinstance(
                    v, str) else {"BOOL": v}) for k, v in value.items()}}
            else:
                item[key] = {"S": str(value)}
        return item

    def put_entitlements_batch(self, rows: List[Dict[str, Any]]) -> None:
        from botocore.exceptions import ClientError
        import boto3
        import os

        table = self._table_obj()
        transact = [{"Put": {
            "TableName": table.table_name,
            "Item": self._to_item(row),
            "ConditionExpression": "attribute_not_exists(entitlementId)",
        }} for row in rows]
        try:
            client = boto3.client(
                "dynamodb",
                region_name=os.environ.get("AWS_REGION", "eu-central-1"),
            )
            client.transact_write_items(TransactItems=transact)
        except ClientError as exc:
            raise GrantConflict(f"batch write refused: {exc}") from exc

    def find_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        response = self._table_obj().query(
            IndexName=self._user_index,
            KeyConditionExpression=Key("userId").eq(user_id))
        return [dict(i) for i in response.get("Items", [])]

    def find_by_key(self, idempotency_key: str) -> List[Dict[str, Any]]:
        # No key-GSI exists for idempotency keys (documented scale note:
        # grant keys are rare admin operations, scan+filter suffices —
        # same discipline as existing handler-side entitlement filtering).
        response = self._table_obj().scan(
            FilterExpression="idempotencyKey = :k",
            ExpressionAttributeValues={":k": idempotency_key})
        return [dict(i) for i in response.get("Items", [])]

    def get_entitlement(self, entitlement_id: str
                        ) -> Optional[Dict[str, Any]]:
        response = self._table_obj().get_item(
            Key={"entitlementId": entitlement_id})
        item = response.get("Item")
        return dict(item) if item else None

    def delete_entitlement(self, entitlement_id: str) -> None:
        self._table_obj().delete_item(
            Key={"entitlementId": entitlement_id})


# ------------------------------------------------------------------
# Offer CRUD (admin-only management; neutral reads)
# ------------------------------------------------------------------

def _validate_agents(agent_ids: Any, catalog: Dict[str, Any]) -> List[str]:
    """Every agent must exist and be executable NOW (P7 central)."""
    from agents.ecosystem.agent_status import is_executable_status

    if not isinstance(agent_ids, list) or len(agent_ids) < 1:
        raise GrantDenied("offer needs at least one agentId")
    clean = []
    for agent_id in agent_ids:
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise GrantDenied(f"invalid agentId {agent_id!r}")
        raw = catalog.get(agent_id.strip())
        if raw is None:
            raise GrantDenied(f"unknown agent {agent_id!r}")
        status = raw.get("status") if isinstance(raw, dict) else raw
        if not is_executable_status(status):
            raise GrantDenied(f"agent not executable: {agent_id!r}")
        clean.append(agent_id.strip())
    return clean


def _public_offer(item: Dict[str, Any]) -> Dict[str, Any]:
    """External offer view (no storage internals)."""
    return {k: v for k, v in dict(item).items()}


def create_offer(offer_store: Any, actor: Dict[str, Any], name: str,
                 agent_ids: List[str], catalog: Dict[str, Any],
                 description: Optional[str] = None,
                 status: str = STATUS_ACTIVE) -> Dict[str, Any]:
    """Create an offer (admin only; starts ACTIVE so it is immediately
    grantable; all agents validated BEFORE persistence — no partial)."""
    _require_admin(actor, "offer-create")
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("name is required")
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise ValueError("status must be ACTIVE or INACTIVE")
    agents = _validate_agents(agent_ids, catalog)
    for existing in offer_store.list_offers():
        if _same_name(existing.get("name"), clean_name):
            raise OfferConflict("offer name exists")
    stamp = _utcnow_iso()
    item = {
        "offerId": "off_" + uuid.uuid4().hex[:16],
        "name": clean_name,
        "description": (description or "").strip() or None,
        "status": status,
        "agentIds": agents,
        "createdAt": stamp,
        "updatedAt": stamp,
        "createdBy": {"actor": _actor_label(actor), "role": "admin"},
        "updatedBy": {"actor": _actor_label(actor), "role": "admin"},
    }
    offer_store.put_offer(item)
    _audit("offer-created", "success",
           {"offerId": item["offerId"], "actor": _actor_label(actor),
            "agents": ",".join(agents)})
    return _public_offer(item)


def get_offer(offer_store: Any, offer_id: str) -> Optional[Dict[str, Any]]:
    """Neutral read (missing -> None)."""
    item = offer_store.get_offer(offer_id)
    return _public_offer(item) if item else None


def list_offers(offer_store: Any, actor: Dict[str, Any],
                include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Admin sees all; others see ACTIVE display offers only."""
    items = offer_store.list_offers()
    if _is_admin(actor) and include_inactive:
        return [_public_offer(i) for i in items]
    if _is_admin(actor):
        return [_public_offer(i) for i in items]
    return [_public_offer(i) for i in items
            if i.get("status") == STATUS_ACTIVE]


def update_offer(offer_store: Any, actor: Dict[str, Any], offer_id: str,
                 catalog: Dict[str, Any],
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 agent_ids: Optional[List[str]] = None,
                 **unknown: Any) -> Dict[str, Any]:
    """Allowlist update (admin only). Agent changes affect FUTURE
    grants only — existing entitlements are never rewritten."""
    _require_admin(actor, "offer-update")
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")
    item = offer_store.get_offer(offer_id)
    if item is None:
        raise OfferNotFound(offer_id)
    if name is not None:
        clean = name.strip()
        if not clean:
            raise ValueError("name must not be empty")
        for other in offer_store.list_offers():
            if other.get("offerId") != offer_id and _same_name(
                    other.get("name"), clean):
                raise OfferConflict("offer name exists")
        item["name"] = clean
    if description is not None:
        item["description"] = description.strip() or None
    if agent_ids is not None:
        item["agentIds"] = _validate_agents(agent_ids, catalog)
    item["updatedAt"] = _utcnow_iso()
    item["updatedBy"] = {"actor": _actor_label(actor), "role": "admin"}
    offer_store.update_offer(offer_id, item)
    _audit("offer-updated", "success",
           {"offerId": offer_id, "actor": _actor_label(actor)})
    return _public_offer(item)


def set_offer_status(offer_store: Any, actor: Dict[str, Any],
                     offer_id: str, status: str,
                     reason: Optional[str] = None) -> Dict[str, Any]:
    """ACTIVE <-> INACTIVE (admin only, reason mandatory, audited).

    INACTIVE blocks FUTURE grants only — existing entitlements stay
    valid until expiry/withdrawal (P04 contract, no retroaction).
    """
    _require_admin(actor, "offer-status")
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise ValueError("status must be ACTIVE or INACTIVE")
    if not reason:
        raise ValueError("status change requires reason")
    item = offer_store.get_offer(offer_id)
    if item is None:
        raise OfferNotFound(offer_id)
    item["status"] = status
    item["updatedAt"] = _utcnow_iso()
    item["updatedBy"] = {"actor": _actor_label(actor), "role": "admin"}
    offer_store.update_offer(offer_id, item)
    _audit("offer-status", "success",
           {"offerId": offer_id, "to": status,
            "actor": _actor_label(actor), "reason": reason})
    return _public_offer(item)


def _windows_ok(valid_from: Any, valid_until: Any) -> None:
    start, end = _parse_time(valid_from), _parse_time(valid_until)
    if start is None or end is None:
        raise GrantDenied("validFrom/validUntil required and parseable")
    if not start < end:
        raise GrantDenied("validFrom must be before validUntil")


def grant_offer(offer_store: Any, entitlement_store: Any,
                profile_store: Any, catalog: Dict[str, Any],
                actor: Dict[str, Any], offer_id: str, target_user_id: str,
                tenant_id: str, scope: str,
                api_profile_id: Optional[str] = None,
                valid_from: Optional[str] = None,
                valid_until: Optional[str] = None,
                reason: Optional[str] = None,
                idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    """Grant an offer (admin only): one entitlement row per offer agent.

    Scope USER (apiProfileId forbidden) XOR APIPROFILE (profile must
    exist, belong to target, match tenant, be ACTIVE-usable).
    All-or-nothing: full validation BEFORE any write; identical grants
    reuse rows; overlapping windows conflict; key mismatch conflicts.
    """
    _require_admin(actor, "grant")
    target_user_id = (target_user_id or "").strip()
    tenant_id = (tenant_id or "").strip()
    if not target_user_id or not tenant_id:
        raise GrantDenied("target user/tenant required")
    if actor.get("tenantId") != tenant_id and not reason:
        raise GrantDenied("cross-tenant grant needs reason")
    if scope == SCOPE_USER and api_profile_id:
        raise GrantDenied("USER scope takes no apiProfileId")
    if scope == SCOPE_PROFILE and not api_profile_id:
        raise GrantDenied("APIPROFILE scope needs apiProfileId")
    if scope not in (SCOPE_USER, SCOPE_PROFILE):
        raise GrantDenied(f"unknown scope {scope!r}")
    if not reason:
        raise GrantDenied("grant needs reason")

    offer = offer_store.get_offer(offer_id)
    if offer is None:
        raise GrantDenied("offer missing")
    if offer.get("status") != STATUS_ACTIVE:
        raise GrantDenied("offer not active")

    agents = _validate_agents(offer.get("agentIds"), catalog)

    profile_ctx: Optional[str] = None
    if scope == SCOPE_PROFILE:
        import agents.ecosystem.api_profiles as api_profiles

        admin_view = {"userId": _actor_label(actor),
                      "tenantId": tenant_id, "groups": ["admins"]}
        profile = api_profiles.get_profile(profile_store, admin_view,
                                           api_profile_id,
                                           reason=reason or "grant")
        if profile is None:
            raise GrantDenied("api profile missing")
        if profile.get("ownerUserId") != target_user_id:
            raise GrantDenied("profile owner mismatch")
        if profile.get("tenantId") != tenant_id:
            raise GrantDenied("profile tenant mismatch")
        if api_profiles.effective_status(profile) != "ACTIVE":
            raise GrantDenied(
                "profile not usable: "
                f"{api_profiles.effective_status(profile)}")
        profile_ctx = api_profile_id

    _windows_ok(valid_from, valid_until)
    if idempotency_key:
        keyed = entitlement_store.find_by_key(idempotency_key)
        if keyed:
            same = [r for r in keyed
                    if r.get("offerId") == offer_id
                    and r.get("userId") == target_user_id
                    and r.get("tenantId") == tenant_id
                    and (r.get("apiProfileId") or None) == profile_ctx
                    and r.get("validFrom") == valid_from
                    and r.get("validUntil") == valid_until]
            if same and len(same) == len(agents):
                _audit("grant-duplicate-key", "reused",
                       {"offerId": offer_id, "target": target_user_id,
                        "actor": _actor_label(actor)})
                return {"grantId": same[0].get("grantId"),
                        "entitlementIds": [r["entitlementId"]
                                           for r in same],
                        "reused": True}
            raise GrantConflict("idempotency key content mismatch")

    existing = entitlement_store.find_by_user(target_user_id)
    for agent_id in agents:
        twin = [r for r in existing
                if r.get("agentId") == agent_id
                and r.get("tenantId") == tenant_id
                and (r.get("apiProfileId") or None) == profile_ctx
                and r.get("validFrom") == valid_from
                and r.get("validUntil") == valid_until]
        if twin:
            continue
        clash = [r for r in existing
                  if r.get("agentId") == agent_id
                  and r.get("tenantId") == tenant_id
                  and (r.get("apiProfileId") or None) == profile_ctx]
        if clash:
            raise GrantConflict(
                f"overlapping grant exists for {agent_id!r} "
                "(withdraw first, no silent merge)")

    stamp = _utcnow_iso()
    grant_id = "grt_" + uuid.uuid4().hex[:16]
    rows = []
    for agent_id in agents:
        twin = [r for r in existing
                if r.get("agentId") == agent_id
                and r.get("tenantId") == tenant_id
                and (r.get("apiProfileId") or None) == profile_ctx
                and r.get("validFrom") == valid_from
                and r.get("validUntil") == valid_until]
        if twin:
            continue
        row: Dict[str, Any] = {
            "entitlementId": "ent_" + uuid.uuid4().hex[:16],
            "userId": target_user_id,
            "tenantId": tenant_id,
            "agentId": agent_id,
            "validFrom": valid_from,
            "validUntil": valid_until,
            "expiresAt": _epoch(valid_until),
            "offerId": offer_id,
            "grantId": grant_id,
            "createdAt": stamp,
            "createdBy": {"actor": _actor_label(actor), "role": "admin"},
        }
        if profile_ctx is not None:
            row["apiProfileId"] = profile_ctx
        if idempotency_key:
            row["idempotencyKey"] = idempotency_key
        rows.append(row)

    if not rows:
        # All agents already have identical entitlements → idempotent reuse
        entitlement_ids = []
        grant_ids = set()
        for agent_id in agents:
            twin = [r for r in existing
                    if r.get("agentId") == agent_id
                    and r.get("tenantId") == tenant_id
                    and (r.get("apiProfileId") or None) == profile_ctx
                    and r.get("validFrom") == valid_from
                    and r.get("validUntil") == valid_until]
            if not twin:
                # Should not happen because rows is empty, but guard
                continue
            entitlement_ids.append(twin[0].get("entitlementId"))
            grant_ids.add(twin[0].get("grantId"))
        grant_id_existing = next(iter(grant_ids)) if grant_ids else grant_id
        _audit("grant-authorized", "reused",
               {"grantId": grant_id_existing, "offerId": offer_id,
                "target": target_user_id, "scope": scope,
                "profile": profile_ctx or "-",
                "agents": ",".join(agents),
                "actor": _actor_label(actor), "reason": reason})
        return {"grantId": grant_id_existing, "entitlementIds": entitlement_ids, "reused": True}

    entitlement_store.put_entitlements_batch(rows)
    fresh = entitlement_store.find_by_user(target_user_id)
    ids = []
    for agent_id in agents:
        match = [r for r in fresh
                 if r.get("agentId") == agent_id
                 and r.get("tenantId") == tenant_id
                 and (r.get("apiProfileId") or None) == profile_ctx
                 and r.get("validFrom") == valid_from
                 and r.get("validUntil") == valid_until]
        ids.append(match[0]["entitlementId"])
    _audit("grant-authorized", "success",
           {"grantId": grant_id, "offerId": offer_id,
            "target": target_user_id, "scope": scope,
            "profile": profile_ctx or "-",
            "agents": ",".join(agents),
            "actor": _actor_label(actor), "reason": reason})
    return {"grantId": grant_id, "entitlementIds": ids, "reused": False}


def withdraw_entitlement(entitlement_store: Any, actor: Dict[str, Any],
                         entitlement_id: str,
                         reason: Optional[str] = None) -> None:
    """Explicit withdrawal (admin only, audited). No silent expiry
    beyond windows/TTL; overlap recovery = withdraw + re-grant."""
    _require_admin(actor, "withdraw")
    if not reason:
        raise ValueError("withdrawal requires reason")
    row = entitlement_store.get_entitlement(entitlement_id)
    if row is None:
        raise EntitlementNotFound(entitlement_id)
    entitlement_store.delete_entitlement(entitlement_id)
    _audit("entitlement-withdrawn", "success",
           {"entitlementId": entitlement_id,
            "userId": row.get("userId"), "agentId": row.get("agentId"),
            "actor": _actor_label(actor), "reason": reason})


__all__ = [
    "ADMIN_GROUP",
    "STATUS_ACTIVE",
    "STATUS_INACTIVE",
    "SCOPE_USER",
    "SCOPE_PROFILE",
    "OfferNotFound",
    "OfferConflict",
    "GrantDenied",
    "GrantConflict",
    "UnauthorizedOfferAction",
    "EntitlementNotFound",
    "InMemoryOfferStore",
    "DynamoDBOfferStore",
    "InMemoryEntitlementStore",
    "DynamoDBEntitlementStore",
    "create_offer",
    "get_offer",
    "list_offers",
    "update_offer",
    "set_offer_status",
    "grant_offer",
    "withdraw_entitlement",
]