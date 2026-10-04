"""
APIProfile foundation: persistence contract, repository, service
(CRUD + lifecycle + roles), selection/default resolution, audit.

Contract: PROMPT 02 (object/lifecycle/roles) + PROMPT 04-R3
(CRUD/idempotency) + PROMPT 05-R4 (selection/default) +
PROMPT 06 (interfaces) / Gate P10.

Boundaries (enforced, never mixed):
  UserProfile  = personal user data (separate domain, untouched here)
  APIProfile   = API usage context (THIS module)
  Credential   = technical proof (P09 module, references profiles)
  Entitlement  = concrete permission (existing table, grant = later gate)
  Offer        = grantable package (later gate, NOT here)
  Tenant       = isolation dimension (never owner)
  Owner        = ownerUserId exclusively (no assigned/shared owner)

Table contract (for the later TF gate — NOT provisioned here):
  name pattern  "{project}-{env}-api-profiles" (repo convention)
  PK            apiProfileId (S)
  GSI-1         "gsi-owner" HASH ownerUserId, projection ALL
  billing       PAY_PER_REQUEST, SSE default (repo convention)
  NO TTL       (expired profiles stay EXPIRED records for audit;
                deletion only via explicit admin cleanup, later gate)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SELECTION_HEADER = "X-Api-Profile"

ADMIN_GROUP = "admins"
STAFF_GROUP = "Staff"

STATUS_PENDING = "PENDING"
STATUS_ACTIVE = "ACTIVE"
STATUS_DISABLED = "DISABLED"
STATUS_EXPIRED = "EXPIRED"  # derived, never stored directly
STATUS_REVOKED = "REVOKED"

_STORED_STATUSES = frozenset(
    {STATUS_PENDING, STATUS_ACTIVE, STATUS_DISABLED, STATUS_REVOKED})

# Actor transitions (EXPIRED is derived, REVOKED terminal).
_ALLOWED = {
    STATUS_PENDING: frozenset({STATUS_ACTIVE, STATUS_DISABLED,
                               STATUS_REVOKED}),
    STATUS_ACTIVE: frozenset({STATUS_DISABLED, STATUS_REVOKED}),
    STATUS_DISABLED: frozenset({STATUS_ACTIVE, STATUS_REVOKED}),
    STATUS_REVOKED: frozenset(),
}


class ProfileNotFound(Exception):
    """Neutral not-found (foreign/missing/deleted are indistinguishable)."""


class ProfileConflict(Exception):
    """Name-unique violation / idempotency mismatch (409 analog)."""


class UnauthorizedProfileAction(Exception):
    """Role/ownership/tenant violation (audited)."""


class InvalidProfileTransition(Exception):
    """Disallowed lifecycle transition."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    logger.warning("apiprofile-audit ref=%s action=%s outcome=%s %s",
                   audit_ref, action, outcome,
                   " ".join(f"{k}={v}" for k, v in sorted(fields.items())))
    return audit_ref


def _is_admin(actor: Dict[str, Any]) -> bool:
    return ADMIN_GROUP in (actor.get("groups") or [])


def _is_staff(actor: Dict[str, Any]) -> bool:
    return STAFF_GROUP in (actor.get("groups") or [])


def effective_status(item: Dict[str, Any],
                     now: Optional[datetime] = None) -> str:
    """Authoritative usability status (derived EXPIRED beats stored).

    REVOKED is terminal and dominates everything. Otherwise a passed
    expiresAt derives EXPIRED (PENDING/ACTIVE/DISABLED with elapsed
    expiry are NOT usable). No scheduler needed.
    """
    stored = item.get("status")
    if stored == STATUS_REVOKED:
        return STATUS_REVOKED
    end = _parse_time(item.get("expiresAt"))
    if end is not None:
        moment = now or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if moment > end:
            return STATUS_EXPIRED
    return stored


def _public(item: Dict[str, Any]) -> Dict[str, Any]:
    """External view (never leaks storage internals like idempotency keys)."""
    return {k: v for k, v in dict(item).items()
            if k != "idempotencyKey"}


def _check_tenant(item: Dict[str, Any], actor: Dict[str, Any],
                  action: str, reason: Optional[str] = None) -> None:
    """Tenant isolation: same tenant, or admin with reason (audited)."""
    if item.get("tenantId") == actor.get("tenantId"):
        return
    if _is_admin(actor) and reason:
        _audit("cross-tenant-access", "allowed",
               {"action": action, "actor": actor.get("userId"),
                "profile": item.get("apiProfileId"),
                "tenant": item.get("tenantId"), "reason": reason})
        return
    _audit("cross-tenant-access", "denied",
           {"action": action, "actor": actor.get("userId"),
            "tenant": actor.get("tenantId")})
    raise UnauthorizedProfileAction("tenant isolation")


# ------------------------------------------------------------------
# Repository layer (in-memory for tests; DynamoDB adapter lazy)
# ------------------------------------------------------------------

class InMemoryApiProfileStore:
    """Test/harness store (same interface as the DynamoDB one)."""

    def __init__(self) -> None:
        self.items: Dict[str, Dict[str, Any]] = {}

    def put_profile(self, item: Dict[str, Any]) -> None:
        if item["apiProfileId"] in self.items:
            raise ProfileConflict("apiProfileId exists")
        self.items[item["apiProfileId"]] = dict(item)

    def get_profile(self, api_profile_id: str) -> Optional[Dict[str, Any]]:
        item = self.items.get(api_profile_id)
        return dict(item) if item else None

    def list_by_owner(self, owner_user_id: str) -> List[Dict[str, Any]]:
        return [dict(i) for i in self.items.values()
                if i.get("ownerUserId") == owner_user_id]

    def update_profile(self, api_profile_id: str,
                       item: Dict[str, Any]) -> None:
        if api_profile_id not in self.items:
            raise ProfileNotFound(api_profile_id)
        self.items[api_profile_id] = dict(item)


class DynamoDBApiProfileStore:
    """Production store (lazy; table from the later TF gate).

    Required table design: PK apiProfileId (S) + GSI "gsi-owner"
    HASH ownerUserId (ALL) + PAY_PER_REQUEST + SSE default, NO TTL.
    """

    def __init__(self, table: Any = None, table_name: Optional[str] = None,
                 owner_index: str = "gsi-owner") -> None:
        self._table = table
        self._table_name = table_name
        self._owner_index = owner_index

    def _table_obj(self) -> Any:
        if self._table is not None:
            return self._table
        if not self._table_name:
            raise RuntimeError("api-profile table_name is required")
        import boto3

        import os

        return boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "eu-central-1"),
        ).Table(self._table_name)

    def put_profile(self, item: Dict[str, Any]) -> None:
        from botocore.exceptions import ClientError

        try:
            self._table_obj().put_item(
                Item={k: v for k, v in dict(item).items()
                      if v is not None},
                ConditionExpression="attribute_not_exists(apiProfileId)")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == \
                    "ConditionalCheckFailedException":
                raise ProfileConflict("apiProfileId exists") from exc
            raise

    def get_profile(self, api_profile_id: str) -> Optional[Dict[str, Any]]:
        response = self._table_obj().get_item(
            Key={"apiProfileId": api_profile_id})
        item = response.get("Item")
        return dict(item) if item else None

    def list_by_owner(self, owner_user_id: str) -> List[Dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        response = self._table_obj().query(
            IndexName=self._owner_index,
            KeyConditionExpression=Key("ownerUserId").eq(owner_user_id))
        return [dict(i) for i in response.get("Items", [])]

    def update_profile(self, api_profile_id: str,
                       item: Dict[str, Any]) -> None:
        self._table_obj().put_item(
            Item={k: v for k, v in dict(item).items() if v is not None})


# ------------------------------------------------------------------
# Service layer (CRUD + lifecycle + roles + tenant + idempotency)
# ------------------------------------------------------------------

def _actor_label(actor: Dict[str, Any]) -> str:
    return str(actor.get("userId") or "?")


def create_profile(store: Any, actor: Dict[str, Any], name: str,
                   description: Optional[str] = None,
                   target_owner: Optional[str] = None,
                   client_ref: Optional[str] = None,
                   expires_at: Optional[str] = None,
                   idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    """Create a profile (starts PENDING, never ACTIVE, never on login).

    ownerUserId = actor, unless admin + explicit target_owner.
    tenantId = actor tenant (server-derived, never payload).
    Owner-supplied clientRef/expiresAt are IGNORED (admin-only fields;
    repo spoof-immunization convention).
    Name UNIQUE per owner (else ProfileConflict); optional
    idempotency_key makes retries safe (match -> existing, else 409).
    Staff may NOT create. Admin may create for others.
    """
    groups = actor.get("groups") or []
    if _is_staff(actor) and not _is_admin(actor):
        _audit("profile-create", "denied",
               {"actor": _actor_label(actor), "reason": "staff-no-create"})
        raise UnauthorizedProfileAction("staff may not create profiles")
    owner = target_owner or actor.get("userId")
    if target_owner and target_owner != actor.get("userId") \
            and not _is_admin(actor):
        raise UnauthorizedProfileAction("only admin creates for others")
    if not owner or not actor.get("tenantId"):
        raise UnauthorizedProfileAction("owner/tenant required")
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("name is required")

    for existing in store.list_by_owner(owner):
        if (existing.get("name") or "").strip().lower() \
                == clean_name.lower():
            if idempotency_key and existing.get("idempotencyKey") \
                    == idempotency_key:
                return dict(existing)
            raise ProfileConflict("name exists for owner")

    stamp = _utcnow_iso()
    item = {
        "apiProfileId": "aprof_" + uuid.uuid4().hex[:16],
        "name": clean_name,
        "description": (description or "").strip() or None,
        "ownerUserId": owner,
        "tenantId": actor.get("tenantId"),
        "clientRef": None,  # admin-only; owner input ignored by design
        "status": STATUS_PENDING,
        "createdAt": stamp,
        "updatedAt": stamp,
        "expiresAt": None,  # admin-only; owner input ignored by design
        "createdBy": {"actor": _actor_label(actor),
                      "role": "admin" if _is_admin(actor) else "owner"},
        "updatedBy": {"actor": _actor_label(actor),
                      "role": "admin" if _is_admin(actor) else "owner"},
        "disabledBy": None,
        "idempotencyKey": idempotency_key,
    }
    if expires_at is not None or client_ref is not None:
        _audit("profile-create-field-ignored", "noted",
               {"actor": _actor_label(actor),
                "fields": "clientRef/expiresAt owner-supplied"})
    store.put_profile(item)
    _audit("profile-create", "success",
           {"profile": item["apiProfileId"], "owner": owner,
            "actor": _actor_label(actor),
            "tenant": item["tenantId"]})
    return _public(item)


def get_profile(store: Any, actor: Dict[str, Any], api_profile_id: str,
                reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read (neutral None for foreign/missing — no oracle)."""
    item = store.get_profile(api_profile_id)
    if item is None:
        return None
    if item.get("ownerUserId") == actor.get("userId"):
        _check_tenant(item, actor, "read", reason)
        return _public(item)
    if _is_admin(actor) or _is_staff(actor):
        _check_tenant(item, actor, "read", reason)
        if _is_staff(actor) and not reason:
            return None
        return _public(item)
    return None


def list_profiles(store: Any, actor: Dict[str, Any],
                  reason: Optional[str] = None) -> List[Dict[str, Any]]:
    """Owner: own profiles. Admin: tenant profiles (cross-tenant needs
    reason). Staff: support case with reason only."""
    if _is_admin(actor):
        # Tenant listing without tenant GSI: owner-listing is per owner;
        # admin enumerates own + explicitly requested scopes only.
        # Full cross-tenant enumeration is NOT offered (least privilege).
        mine = store.list_by_owner(actor.get("userId"))
        visible = [i for i in mine
                   if i.get("tenantId") == actor.get("tenantId")]
        return [_public(i) for i in visible]
    if _is_staff(actor):
        if not reason:
            return []
        _audit("profile-list", "support",
               {"actor": _actor_label(actor), "reason": reason})
        return []
    return [_public(i)
            for i in store.list_by_owner(actor.get("userId") or "")
            if i.get("tenantId") == actor.get("tenantId")]


def update_profile(store: Any, actor: Dict[str, Any], api_profile_id: str,
                   name: Optional[str] = None,
                   description: Optional[str] = None,
                   reason: Optional[str] = None,
                   **unknown: Any) -> Optional[Dict[str, Any]]:
    """Explicit allowlist update (name/description only). Unknown fields
    are REJECTED (no blind merge); immutable/system/admin-only fields
    can never pass through here. Foreign profiles -> neutral None."""
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")
    item = store.get_profile(api_profile_id)
    if item is None:
        return None
    own = item.get("ownerUserId") == actor.get("userId")
    if not own and not _is_admin(actor):
        _check_tenant(item, actor, "update", reason)
        return None
    _check_tenant(item, actor, "update", reason)
    if name is not None:
        clean = name.strip()
        if not clean:
            raise ValueError("name must not be empty")
        for other in store.list_by_owner(item["ownerUserId"]):
            if other.get("apiProfileId") != item["apiProfileId"] and \
                    (other.get("name") or "").strip().lower() \
                    == clean.lower():
                raise ProfileConflict("name exists for owner")
        item["name"] = clean
    if description is not None:
        item["description"] = description.strip() or None
    item["updatedAt"] = _utcnow_iso()
    item["updatedBy"] = {"actor": _actor_label(actor),
                         "role": "admin" if _is_admin(actor) else "owner"}
    store.update_profile(item["apiProfileId"], item)
    _audit("profile-update", "success",
           {"profile": item["apiProfileId"], "actor": _actor_label(actor)})
    return _public(item)


def set_client_ref(store: Any, actor: Dict[str, Any], api_profile_id: str,
                   client_ref: Optional[str],
                   reason: Optional[str] = None) -> Dict[str, Any]:
    """Admin-only clientRef mutation (audited; cross-tenant needs reason)."""
    if not _is_admin(actor):
        raise UnauthorizedProfileAction("clientRef is admin-only")
    item = store.get_profile(api_profile_id)
    if item is None:
        raise ProfileNotFound(api_profile_id)
    _check_tenant(item, actor, "set-client-ref", reason)
    item["clientRef"] = client_ref
    item["updatedAt"] = _utcnow_iso()
    item["updatedBy"] = {"actor": _actor_label(actor), "role": "admin"}
    store.update_profile(item["apiProfileId"], item)
    _audit("profile-client-ref", "success",
           {"profile": item["apiProfileId"], "actor": _actor_label(actor)})
    return _public(item)


def set_expires_at(store: Any, actor: Dict[str, Any], api_profile_id: str,
                   expires_at: Optional[str],
                   reason: Optional[str] = None) -> Dict[str, Any]:
    """Admin-only expiry mutation (audited; must parse when set)."""
    if not _is_admin(actor):
        raise UnauthorizedProfileAction("expiresAt is admin-only")
    if expires_at is not None and _parse_time(expires_at) is None:
        raise ValueError("expiresAt must be a valid ISO timestamp or None")
    item = store.get_profile(api_profile_id)
    if item is None:
        raise ProfileNotFound(api_profile_id)
    _check_tenant(item, actor, "set-expiry", reason)
    item["expiresAt"] = expires_at
    item["updatedAt"] = _utcnow_iso()
    item["updatedBy"] = {"actor": _actor_label(actor), "role": "admin"}
    store.update_profile(item["apiProfileId"], item)
    _audit("profile-expiry", "success",
           {"profile": item["apiProfileId"], "actor": _actor_label(actor)})
    return _public(item)


def transition_status(store: Any, actor: Dict[str, Any], api_profile_id: str,
                      to_status: str,
                      reason: Optional[str] = None) -> Dict[str, Any]:
    """Lifecycle transition with role matrix (P02/P04).

    Owner self-service: ACTIVE<->DISABLED on own profiles, except
    admin-locked ones. DISABLED requires reason. REVOKED admin-only.
    PENDING->ACTIVE admin-only. EXPIRED is derived (never a target).
    """
    if to_status not in _STORED_STATUSES:
        raise InvalidProfileTransition(f"unknown status {to_status!r}")
    item = store.get_profile(api_profile_id)
    if item is None:
        raise ProfileNotFound(api_profile_id)
    _check_tenant(item, actor, "transition", reason)
    effective = effective_status(item)
    if effective == STATUS_REVOKED or to_status == STATUS_EXPIRED:
        raise InvalidProfileTransition("REVOKED terminal; EXPIRED derived")
    if effective == STATUS_EXPIRED:
        raise InvalidProfileTransition("expired: renew first")
    if item.get("status") not in _ALLOWED or \
            to_status not in _ALLOWED[item["status"]]:
        raise InvalidProfileTransition(
            f"{item.get('status')} -> {to_status} not allowed")

    admin, staff = _is_admin(actor), _is_staff(actor)
    own = item.get("ownerUserId") == actor.get("userId")
    if to_status == STATUS_REVOKED:
        if not admin:
            raise UnauthorizedProfileAction("revoke is admin-only")
    elif to_status == STATUS_ACTIVE and item.get("status") == STATUS_PENDING:
        if not admin:
            raise UnauthorizedProfileAction("activation is admin-only")
    elif to_status == STATUS_DISABLED:
        if not reason:
            raise ValueError("disabling requires reason")
        if not (admin or staff or own):
            raise UnauthorizedProfileAction("may not disable")
    elif to_status == STATUS_ACTIVE and item.get("status") == STATUS_DISABLED:
        disabler = item.get("disabledBy") or {}
        if admin:
            pass
        elif own and disabler.get("actor") == _actor_label(actor) \
                and disabler.get("role") != "admin":
            pass
        elif staff and disabler.get("actor") == _actor_label(actor):
            pass
        else:
            raise UnauthorizedProfileAction("may not re-enable")
    else:
        raise UnauthorizedProfileAction("transition not permitted")

    item["status"] = to_status
    item["disabledBy"] = {"actor": _actor_label(actor),
                          "role": "admin" if admin else (
                              "staff" if staff else "owner"),
                          "reason": reason} if to_status == STATUS_DISABLED \
        else (None if to_status == STATUS_ACTIVE else item.get("disabledBy"))
    item["updatedAt"] = _utcnow_iso()
    item["updatedBy"] = {"actor": _actor_label(actor),
                         "role": "admin" if admin else (
                             "staff" if staff else "owner")}
    store.update_profile(item["apiProfileId"], item)
    _audit("profile-transition", "success",
           {"profile": item["apiProfileId"], "to": to_status,
            "actor": _actor_label(actor), "reason": reason or "-"})
    return _public(item)


def renew_profile(store: Any, actor: Dict[str, Any], api_profile_id: str,
                  new_expires_at: str,
                  reason: Optional[str] = None) -> Dict[str, Any]:
    """Admin renewal from derived-EXPIRED (new expiry + ACTIVE)."""
    if not _is_admin(actor):
        raise UnauthorizedProfileAction("renew is admin-only")
    if _parse_time(new_expires_at) is None:
        raise ValueError("new_expires_at must be a valid ISO timestamp")
    item = store.get_profile(api_profile_id)
    if item is None:
        raise ProfileNotFound(api_profile_id)
    _check_tenant(item, actor, "renew", reason)
    if effective_status(item) != STATUS_EXPIRED:
        raise InvalidProfileTransition("renew only from EXPIRED")
    item["expiresAt"] = new_expires_at
    item["status"] = STATUS_ACTIVE
    item["updatedAt"] = _utcnow_iso()
    item["updatedBy"] = {"actor": _actor_label(actor), "role": "admin"}
    store.update_profile(item["apiProfileId"], item)
    _audit("profile-renew", "success",
           {"profile": item["apiProfileId"], "actor": _actor_label(actor)})
    return _public(item)


# ------------------------------------------------------------------
# Selection + default resolution (P05-R4 / P06-R3)
# ------------------------------------------------------------------

def resolve_selection(store: Any, actor: Dict[str, Any],
                      selection_hint: Optional[str] = None,
                      request_id: Optional[str] = None
                      ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Resolve an APIProfile context (UNTRUSTED hint in, verified out).

    Returns (profile|None, resolution info). Missing hint -> default
    rule (0/1/n ACTIVE-effective own profiles). Explicit hint ->
    existence + owner-or-competent + tenant + ACTIVE-effective, else
    neutral None (no oracle: unknown/foreign/inactive identical).
    Selection NEVER authorizes (P05 contract).
    """
    if selection_hint:
        item = store.get_profile(selection_hint)
        info = {"type": "explicit", "hint": "provided",
                "request": request_id or "-"}
        if item is None or item.get("ownerUserId") != actor.get("userId"):
            if item is not None and _is_admin(actor):
                try:
                    _check_tenant(item, actor, "select", reason="admin")
                    if effective_status(item) != STATUS_ACTIVE:
                        raise ProfileNotFound(selection_hint)
                    _audit("selection-resolved", "explicit-admin", dict(
                        info, profile=item["apiProfileId"],
                        actor=_actor_label(actor)))
                    return dict(item), dict(info, outcome="resolved")
                except (UnauthorizedProfileAction, ProfileNotFound):
                    pass
            _audit("selection-denied", "neutral", dict(
                info, actor=_actor_label(actor)))
            return None, dict(info, outcome="denied")
        try:
            _check_tenant(item, actor, "select")
        except UnauthorizedProfileAction:
            _audit("selection-denied", "neutral", dict(
                info, actor=_actor_label(actor)))
            return None, dict(info, outcome="denied")
        if effective_status(item) != STATUS_ACTIVE:
            _audit("selection-denied", "neutral", dict(
                info, actor=_actor_label(actor)))
            return None, dict(info, outcome="denied")
        _audit("selection-resolved", "explicit", dict(
            info, profile=item["apiProfileId"],
            actor=_actor_label(actor)))
        return dict(item), dict(info, outcome="resolved")

    own_active = [i for i in store.list_by_owner(actor.get("userId") or "")
                  if i.get("tenantId") == actor.get("tenantId")
                  and effective_status(i) == STATUS_ACTIVE]
    info = {"type": "default", "request": request_id or "-",
            "candidates": len(own_active)}
    if len(own_active) == 1:
        _audit("selection-resolved", "default", dict(
            info, profile=own_active[0]["apiProfileId"],
            actor=_actor_label(actor)))
        return dict(own_active[0]), dict(info, outcome="resolved")
    _audit("selection-denied" if len(own_active) > 1 else "selection-none",
           "neutral", dict(info, actor=_actor_label(actor)))
    return None, dict(info, outcome="explicit-required"
                      if len(own_active) > 1 else "none")


def credential_profile_match(profile: Optional[Dict[str, Any]],
                             credential_profile_id: Optional[str],
                             request_id: Optional[str] = None) -> bool:
    """Credential binding is authoritative (P05/P09): header profile
    MUST equal the credential profile — mismatch denies, no override,
    no guessing. Audited either way."""
    ok = profile is not None and credential_profile_id is not None \
        and profile.get("apiProfileId") == credential_profile_id
    _audit("credential-profile-match" if ok else "credential-profile-mismatch",
           "match" if ok else "mismatch",
           {"profile": (profile or {}).get("apiProfileId"),
            "request": request_id or "-"})
    return ok


__all__ = [
    "SELECTION_HEADER",
    "ADMIN_GROUP",
    "STAFF_GROUP",
    "STATUS_PENDING",
    "STATUS_ACTIVE",
    "STATUS_DISABLED",
    "STATUS_EXPIRED",
    "STATUS_REVOKED",
    "ProfileNotFound",
    "ProfileConflict",
    "UnauthorizedProfileAction",
    "InvalidProfileTransition",
    "effective_status",
    "InMemoryApiProfileStore",
    "DynamoDBApiProfileStore",
    "create_profile",
    "get_profile",
    "list_profiles",
    "update_profile",
    "set_client_ref",
    "set_expires_at",
    "transition_status",
    "renew_profile",
    "resolve_selection",
    "credential_profile_match",
]
