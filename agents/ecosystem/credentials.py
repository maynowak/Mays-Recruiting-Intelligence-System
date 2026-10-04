"""
Opaque bearer credentials for machine / Job-Matcher access.

Contract: PROMPT 03 (C1-C7) + PROMPT 05-R3 + PROMPT 06-R2 / Gate P09.

A credential is NOT a Cognito JWT, NOT a password, NOT an APIProfile,
NOT an entitlement, NOT an AWS secret. It belongs to exactly ONE
APIProfile, is verified server-side on every use, is revocable, and
its raw value is handed out exactly ONCE (at issuance) — afterwards
it is unrecoverable (only a salt-free SHA-256 lookup digest with
domain separation is persisted; digests are never returned).

Human/browser login stays Cognito-JWT (untouched path).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CREDENTIAL_TYPE = "opaque-bearer-v1"
SECRET_PREFIX = "ris_"
SECRET_RANDOM_BYTES = 32
# Domain separation for the lookup digest (P03: deterministic + separated).
DIGEST_DOMAIN = "ris-cred-v1:"
DIGEST_ALGO = "sha256"

_SECRET_RE = re.compile(r"\Aris_[A-Za-z0-9_-]{40,60}\Z")


class CredentialStatus(Enum):
    """Stored credential lifecycle (no PENDING by contract)."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    REVOKED = "REVOKED"


class VerifyOutcome(Enum):
    """Verification result classes (HTTP mapping: 401 vs 403)."""

    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"  # 401: unknown/invalid/malformed
    FORBIDDEN = "FORBIDDEN"  # 403: known but unusable/unauthorized


class CredentialStoreUnavailable(Exception):
    """Entitlement/credential/profile store unreachable (maps to 503,
    never to 401/403). Infrastructure failure != invalid credential."""


class UnauthorizedManagementAttempt(Exception):
    """Management actor lacks the required role (audited)."""


class CredentialNotFound(Exception):
    """Management target does not exist."""


# ------------------------------------------------------------------
# Generation + digest (ZS4/ZS5: crypto-random, opaque, once-only)
# ------------------------------------------------------------------

def generate_secret() -> str:
    """Create one opaque bearer secret (32 random bytes, base64url).

    No speaking content, no user/profile/tenant data, never derived
    from IDs or timestamps.
    """
    raw = secrets.token_bytes(SECRET_RANDOM_BYTES)
    return SECRET_PREFIX + base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def valid_secret_format(value: Any) -> bool:
    """Structural format check (prefix + charset + length)."""
    return isinstance(value, str) and _SECRET_RE.match(value) is not None


def digest_secret(secret: str) -> str:
    """Deterministic lookup digest (SHA-256, domain-separated).

    The digest is for server-side lookup only: it is never a
    credential, never returned externally, never logged.
    """
    return hashlib.new(
        DIGEST_ALGO, (DIGEST_DOMAIN + secret).encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> Optional[datetime]:
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
    """Structured audit event (never carries secrets/digests/headers).

    Returns the audit reference for correlation.
    """
    audit_ref = uuid.uuid4().hex[:16]
    safe = {k: v for k, v in fields.items()}
    logger.warning("credential-audit ref=%s action=%s outcome=%s %s",
                   audit_ref, action, outcome,
                   " ".join(f"{k}={v}" for k, v in sorted(safe.items())))
    return audit_ref


# ------------------------------------------------------------------
# Management authorization (P02 roles: admin full, staff support-only)
# ------------------------------------------------------------------

def _require_management(actor_role: Optional[str],
                        allowed: List[str], action: str,
                        actor_id: Optional[str] = None) -> None:
    if actor_role not in allowed:
        _audit("unauthorized-management-attempt", "denied",
               {"action": action, "actor": actor_id or "?",
                "role": actor_role or "?"})
        raise UnauthorizedManagementAttempt(
            f"role {actor_role!r} may not {action}")


# ------------------------------------------------------------------
# Issuance (once-only secret) + lifecycle + rotation
# ------------------------------------------------------------------

def issue_credential(credential_store: Any,
                     profile_store: Any,
                     api_profile_id: str,
                     expires_at: str,
                     actor_role: str,
                     actor_id: str,
                     label: Optional[str] = None,
                     now_iso: Optional[str] = None) -> Dict[str, Any]:
    """Issue one credential for an EXISTING APIProfile.

    Returns {"metadata": {...}, "secret": "<once-only>"}.
    expires_at is MANDATORY (no product-policy default invented).
    Profile must exist (any status — usability is enforced at verify
    time, which also enables admin pre-provisioning for PENDING).
    Admin only.
    """
    _require_management(actor_role, ["admin"], "issue", actor_id)
    if not expires_at or _parse_time(expires_at) is None:
        raise ValueError("expires_at is required (ISO timestamp)")
    profile = profile_store.get_profile(api_profile_id)
    if profile is None:
        raise CredentialNotFound(f"api profile {api_profile_id!r} missing")

    secret = generate_secret()
    stamp = now_iso or _utcnow_iso()
    metadata = {
        "credentialId": "cred_" + uuid.uuid4().hex[:16],
        "apiProfileId": api_profile_id,
        "ownerUserId": profile.get("ownerUserId"),
        "tenantId": profile.get("tenantId"),
        "label": label or "default",
        "credentialType": CREDENTIAL_TYPE,
        "status": CredentialStatus.ACTIVE.value,
        "digest": digest_secret(secret),
        "clientRef": profile.get("clientRef"),
        "createdAt": stamp,
        "updatedAt": stamp,
        "expiresAt": expires_at,
        "lastUsedAt": None,
        "revokedAt": None,
        "revokedBy": None,
        "revokeReason": None,
        "disabledBy": None,
        "rotationOf": None,
        "createdBy": {"actor": actor_id, "role": actor_role},
    }
    credential_store.put_credential(metadata)
    _audit("credential-issued", "success",
           {"credentialId": metadata["credentialId"],
            "apiProfileId": api_profile_id,
            "tenant": metadata["tenantId"]})
    return {"metadata": {k: v for k, v in metadata.items()
                         if k != "digest"},
            "secret": secret}


def _load_for_management(credential_store: Any,
                         credential_id: str) -> Dict[str, Any]:
    meta = credential_store.get_credential(credential_id)
    if meta is None:
        raise CredentialNotFound(f"credential {credential_id!r} missing")
    return dict(meta)


def revoke_credential(credential_store: Any, credential_id: str,
                      actor_role: str, actor_id: str,
                      reason: str = "revoked") -> Dict[str, Any]:
    """Terminal revocation (admin + staff-support). Immediate effect:
    the next verification denies (no cache anywhere)."""
    _require_management(actor_role, ["admin", "staff"], "revoke", actor_id)
    meta = _load_for_management(credential_store, credential_id)
    stamp = _utcnow_iso()
    meta.update({"status": CredentialStatus.REVOKED.value,
                 "revokedAt": stamp, "revokedBy": actor_id,
                 "revokeReason": reason, "updatedAt": stamp})
    credential_store.update_credential(credential_id, meta)
    _audit("credential-revoked", "success",
           {"credentialId": credential_id,
            "apiProfileId": meta.get("apiProfileId"),
            "actor": actor_id, "reason": reason})
    return {k: v for k, v in meta.items() if k != "digest"}


def disable_credential(credential_store: Any, credential_id: str,
                       actor_role: str, actor_id: str,
                       reason: str = "disabled") -> Dict[str, Any]:
    """Reversible lock (admin + staff-support, reason mandatory)."""
    _require_management(actor_role, ["admin", "staff"], "disable", actor_id)
    meta = _load_for_management(credential_store, credential_id)
    meta.update({"status": CredentialStatus.DISABLED.value,
                 "disabledBy": actor_id, "revokeReason": reason,
                 "updatedAt": _utcnow_iso()})
    credential_store.update_credential(credential_id, meta)
    _audit("credential-disabled", "success",
           {"credentialId": credential_id, "actor": actor_id,
            "reason": reason})
    return {k: v for k, v in meta.items() if k != "digest"}


def enable_credential(credential_store: Any, credential_id: str,
                      actor_role: str, actor_id: str) -> Dict[str, Any]:
    """Re-activate (admin always; staff only self-disabled ones)."""
    _require_management(actor_role, ["admin", "staff"], "enable", actor_id)
    meta = _load_for_management(credential_store, credential_id)
    if meta.get("status") != CredentialStatus.DISABLED.value:
        raise ValueError("only DISABLED credentials can be enabled")
    if actor_role == "staff" and meta.get("disabledBy") != actor_id:
        _audit("unauthorized-management-attempt", "denied",
               {"action": "enable-foreign", "actor": actor_id})
        raise UnauthorizedManagementAttempt(
            "staff may only re-enable self-disabled credentials")
    meta.update({"status": CredentialStatus.ACTIVE.value,
                 "disabledBy": None, "updatedAt": _utcnow_iso()})
    credential_store.update_credential(credential_id, meta)
    _audit("credential-enabled", "success",
           {"credentialId": credential_id, "actor": actor_id})
    return {k: v for k, v in meta.items() if k != "digest"}


def rotate_credential(credential_store: Any, profile_store: Any,
                      credential_id: str, expires_at: str,
                      actor_role: str, actor_id: str,
                      label: Optional[str] = None) -> Dict[str, Any]:
    """Rotation without profile change: B is new (new id + secret),
    A is revoked IMMEDIATELY (no silent overlap). Admin only.
    Overlap windows are a later explicit admin act (data boundary
    ready: rotationOf chain + independent statuses)."""
    _require_management(actor_role, ["admin"], "rotate", actor_id)
    old = _load_for_management(credential_store, credential_id)
    issued = issue_credential(
        credential_store, profile_store, old["apiProfileId"],
        expires_at, actor_role, actor_id, label=label or old.get("label"))
    new_meta_full = credential_store.get_credential(
        issued["metadata"]["credentialId"])
    new_meta_full["rotationOf"] = credential_id
    credential_store.update_credential(
        issued["metadata"]["credentialId"], new_meta_full)
    revoke_credential(credential_store, credential_id,
                      actor_role, actor_id, reason="rotated")
    _audit("credential-rotated", "success",
           {"oldCredentialId": credential_id,
            "newCredentialId": issued["metadata"]["credentialId"],
            "actor": actor_id})
    out_meta = {k: v for k, v in new_meta_full.items() if k != "digest"}
    return {"metadata": out_meta, "secret": issued["secret"]}


# ------------------------------------------------------------------
# Verification (P06 interface: verify(request) -> Decision)
# ------------------------------------------------------------------

class VerifyDecision:
    """Verification outcome (internal object, never serialized raw)."""

    def __init__(self, outcome: VerifyOutcome,
                 reason_category: str,
                 context: Optional[Dict[str, Any]] = None,
                 audit_ref: Optional[str] = None) -> None:
        self.outcome = outcome
        self.reason_category = reason_category
        self.context = context or {}
        self.audit_ref = audit_ref

    @property
    def authorized(self) -> bool:
        return self.outcome == VerifyOutcome.AUTHORIZED

    @property
    def http_status(self) -> int:
        return {VerifyOutcome.AUTHORIZED: 200,
                VerifyOutcome.UNAUTHORIZED: 401,
                VerifyOutcome.FORBIDDEN: 403}[self.outcome]


def _deny(outcome: VerifyOutcome, reason: str,
          fields: Dict[str, Any]) -> VerifyDecision:
    """Neutral external denial + categorized internal audit (no oracle)."""
    audit_ref = _audit("verification", outcome.value.lower(), fields)
    return VerifyDecision(outcome, reason, {}, audit_ref)


class _Denied(Exception):
    """Internal denial signal (outcome + reason + audit fields)."""

    def __init__(self, outcome: VerifyOutcome, reason: str,
                 fields: Dict[str, Any]) -> None:
        super().__init__(reason)
        self.outcome = outcome
        self.reason = reason
        self.fields = fields


def resolve_credential_profile(
    bearer: Any,
    credential_store: Any,
    profile_store: Any,
    now: Optional[datetime] = None,
    base: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Shared credential+profile boundary (P09 steps 1-11, P12 reuse).

    Validates presence/format, digest lookup, credential status,
    profile existence/status, both expiries (MIN rule) and
    owner/tenant consistency incl. tenantId presence. Raises _Denied
    (never returns details). No entitlement/catalog logic here.
    """
    moment = now or datetime.now(timezone.utc)
    fields: Dict[str, Any] = dict(base or {})

    # 1-2. Present + well-formed? (no lookup on garbage.)
    if not bearer or not valid_secret_format(bearer):
        raise _Denied(VerifyOutcome.UNAUTHORIZED, "malformed", fields)
    # NOTE for introspection callers: P09 verification additionally
    # requires an operation target (agent_id); this boundary does not.

    # 3-4. Digest + lookup (failures propagate: 503, never 401/403).
    try:
        meta = credential_store.get_by_digest(digest_secret(bearer))
    except Exception as exc:
        raise CredentialStoreUnavailable(str(exc)) from exc
    if meta is None:
        raise _Denied(VerifyOutcome.UNAUTHORIZED, "unknown-credential",
                      fields)
    meta = dict(meta)
    fields.update({"credentialId": meta.get("credentialId"),
                   "apiProfileId": meta.get("apiProfileId"),
                   "tenant": meta.get("tenantId")})

    # 5. Credential status.
    if meta.get("status") == CredentialStatus.REVOKED.value:
        raise _Denied(VerifyOutcome.FORBIDDEN, "credential-revoked",
                      fields)
    if meta.get("status") != CredentialStatus.ACTIVE.value:
        raise _Denied(VerifyOutcome.FORBIDDEN, "credential-disabled",
                      fields)

    # 6-7. Profile load + existence.
    try:
        profile = profile_store.get_profile(meta.get("apiProfileId"))
    except Exception as exc:
        raise CredentialStoreUnavailable(str(exc)) from exc
    if profile is None:
        raise _Denied(VerifyOutcome.FORBIDDEN, "profile-missing", fields)
    profile = dict(profile)

    # 8. Profile status.
    if profile.get("status") != "ACTIVE":
        raise _Denied(
            VerifyOutcome.FORBIDDEN,
            f"profile-{str(profile.get('status') or 'unknown').lower()}",
            fields)

    # 9-10. Expiry MIN rule (credential expiresAt mandatory).
    cred_end = _parse_time(meta.get("expiresAt"))
    prof_end = _parse_time(profile.get("expiresAt")) \
        if profile.get("expiresAt") else None
    aware_now = moment if moment.tzinfo else moment.replace(
        tzinfo=timezone.utc)
    if cred_end is None or aware_now > cred_end:
        raise _Denied(VerifyOutcome.FORBIDDEN, "credential-expired",
                      fields)
    if prof_end is not None and aware_now > prof_end:
        raise _Denied(VerifyOutcome.FORBIDDEN, "profile-expired", fields)

    # 11. Owner/tenant consistency (tenantId REQUIRED persisted context).
    if not profile.get("tenantId") or not profile.get("ownerUserId"):
        raise _Denied(VerifyOutcome.FORBIDDEN, "profile-context-missing",
                      fields)
    if meta.get("ownerUserId") != profile.get("ownerUserId") or \
            meta.get("tenantId") != profile.get("tenantId"):
        raise _Denied(VerifyOutcome.FORBIDDEN, "owner-tenant-mismatch",
                      fields)
    return meta, profile


def verify_api_credential(
    bearer: Any,
    agent_id: Optional[str],
    credential_store: Any,
    profile_store: Any,
    entitlement_resolver: Any,
    catalog: Optional[Dict[str, Any]] = None,
    operation: Optional[str] = None,
    route: Optional[str] = None,
    method: Optional[str] = None,
    request_time: Optional[datetime] = None,
    request_id: Optional[str] = None,
    selection_hint: Optional[str] = None,
) -> VerifyDecision:
    """Verify one bearer credential for one operation target.

    agent_id (the operation target) is REQUIRED: the verifier never
    guesses the target (capability->agent mapping is routing concern).
    catalog maps agentId -> raw status (central executable check).
    Steps follow P03/P05/P06 order; 401 = unknown/invalid/malformed,
    403 = known but unusable/unauthorized. Store failures raise
    CredentialStoreUnavailable (caller maps to 503, never 401/403).
    """
    now = request_time or datetime.now(timezone.utc)
    base = {"route": route or "?", "request": request_id or "?"}

    # 1-11. Shared credential+profile boundary (steps incl. expiry MIN
    # rule and owner/tenant consistency). Operation target still
    # required below (verifier never guesses it).
    if not agent_id:
        return _deny(VerifyOutcome.UNAUTHORIZED, "missing-target", base)
    try:
        meta, profile = resolve_credential_profile(
            bearer, credential_store, profile_store, now, base)
    except _Denied as denied:
        return _deny(denied.outcome, denied.reason, denied.fields)
    audit_base = dict(base)
    audit_base.update({"credentialId": meta.get("credentialId"),
                       "apiProfileId": meta.get("apiProfileId"),
                       "tenant": meta.get("tenantId")})

    # 12. Client binding: metadata/audit only by contract (never blocks).
    audit_base["clientRef"] = profile.get("clientRef")
    if selection_hint is not None:
        audit_base["selectionHint"] = "provided"

    # 13. Entitlement (existing contract, no second world; scopes: none
    # in v1 = no additional restriction).
    from agents.ecosystem.worker_authorization import (
        check_worker_entitlement,
    )
    try:
        auth = check_worker_entitlement(
            user_id=profile.get("ownerUserId"),
            tenant_id=profile.get("tenantId"),
            agent_id=agent_id,
            work_id=request_id,
            request_time=now,
            resolver=entitlement_resolver)
    except Exception as exc:
        raise CredentialStoreUnavailable(str(exc)) from exc
    if not auth.authorized:
        return _deny(VerifyOutcome.FORBIDDEN,
                      f"entitlement-{auth.reason}", audit_base)

    # 14. Agent catalog / capability (central executable check).
    if catalog is None:
        raise ValueError("catalog is required")
    from agents.ecosystem.agent_status import is_executable_status

    raw_status = catalog.get(agent_id)
    if isinstance(raw_status, dict):
        raw_status = raw_status.get("status")
    if hasattr(raw_status, "value") and not isinstance(raw_status, str):
        pass  # enum member passes through
    if not is_executable_status(raw_status):
        return _deny(VerifyOutcome.FORBIDDEN, "agent-not-executable",
                      audit_base)

    # 15. AUTHORIZED (context only — never secrets/digests/headers).
    context = {"userId": profile.get("ownerUserId"),
               "tenantId": profile.get("tenantId"),
               "apiProfileId": meta.get("apiProfileId"),
               "credentialId": meta.get("credentialId"),
               "entitlementRefs": [auth.entitlement_id]
               if auth.entitlement_id else [],
               "effectiveScope": "profile-union-no-restriction",
               "resolution": {"selectedBy": "credential",
                              "agentId": agent_id}}
    audit_ref = _audit("verification", "authorized", audit_base)
    try:
        credential_store.mark_used(meta.get("credentialId"),
                                   _utcnow_iso())
    except Exception as exc:  # usage accounting never fails the request
        logger.warning("lastUsedAt update failed (ignored): %s", exc)
    return VerifyDecision(VerifyOutcome.AUTHORIZED, "authorized",
                          context, audit_ref)


class InMemoryCredentialStore:
    """Test/harness credential store (same interface as DynamoDB one)."""

    def __init__(self) -> None:
        self.by_id: Dict[str, Dict[str, Any]] = {}
        self.by_digest: Dict[str, Dict[str, Any]] = {}

    def put_credential(self, metadata: Dict[str, Any]) -> None:
        self.by_id[metadata["credentialId"]] = dict(metadata)
        self.by_digest[metadata["digest"]] = self.by_id[
            metadata["credentialId"]]

    def get_by_digest(self, digest: str) -> Optional[Dict[str, Any]]:
        item = self.by_digest.get(digest)
        return dict(item) if item else None

    def get_credential(self, credential_id: str) -> Optional[Dict[str, Any]]:
        item = self.by_id.get(credential_id)
        return dict(item) if item else None

    def update_credential(self, credential_id: str,
                          metadata: Dict[str, Any]) -> None:
        if credential_id not in self.by_id:
            raise CredentialNotFound(credential_id)
        self.by_id[credential_id] = dict(metadata)
        self.by_digest[metadata["digest"]] = self.by_id[credential_id]

    def mark_used(self, credential_id: str, timestamp: str) -> None:
        item = self.by_id.get(credential_id)
        if item is not None:
            item["lastUsedAt"] = timestamp


class InMemoryProfileStore:
    """Test/harness APIProfile store (profiles are P02 objects)."""

    def __init__(self, profiles: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.profiles = dict(profiles or {})

    def get_profile(self, api_profile_id: str) -> Optional[Dict[str, Any]]:
        item = self.profiles.get(api_profile_id)
        return dict(item) if item else None


class DynamoDBCredentialStore:
    """Production credential store (lazy, read/write metadata only).

    Required table design (LATER TF gate, NOT created here):
    PK credentialId + GSI on digest (proposal name "gsi-digest").
    """

    def __init__(self, table: Any = None, table_name: Optional[str] = None,
                 digest_index: str = "gsi-digest") -> None:
        self._table = table
        self._table_name = table_name
        self._digest_index = digest_index

    def _table_obj(self) -> Any:
        if self._table is not None:
            return self._table
        if not self._table_name:
            raise RuntimeError("credential table_name is required")
        import boto3

        import os

        return boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "eu-central-1"),
        ).Table(self._table_name)

    def put_credential(self, metadata: Dict[str, Any]) -> None:
        self._table_obj().put_item(
            Item=dict(metadata),
            ConditionExpression="attribute_not_exists(credentialId)")

    def get_by_digest(self, digest: str) -> Optional[Dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        response = self._table_obj().query(
            IndexName=self._digest_index,
            KeyConditionExpression=Key("digest").eq(digest))
        items = response.get("Items", [])
        return dict(items[0]) if items else None

    def get_credential(self, credential_id: str) -> Optional[Dict[str, Any]]:
        response = self._table_obj().get_item(
            Key={"credentialId": credential_id})
        item = response.get("Item")
        return dict(item) if item else None

    def update_credential(self, credential_id: str,
                          metadata: Dict[str, Any]) -> None:
        clean = {k: v for k, v in dict(metadata).items()
                 if v is not None}
        self._table_obj().put_item(Item=clean)

    def mark_used(self, credential_id: str, timestamp: str) -> None:
        self._table_obj().update_item(
            Key={"credentialId": credential_id},
            UpdateExpression="SET lastUsedAt = :t",
            ExpressionAttributeValues={":t": timestamp})


class DynamoDBProfileStore:
    """Production APIProfile read access (lazy; table from later gate)."""

    def __init__(self, table: Any = None, table_name: Optional[str] = None) -> None:
        self._table = table
        self._table_name = table_name

    def _table_obj(self) -> Any:
        if self._table is not None:
            return self._table
        if not self._table_name:
            raise RuntimeError("profile table_name is required")
        import boto3

        import os

        return boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "eu-central-1"),
        ).Table(self._table_name)

    def get_profile(self, api_profile_id: str) -> Optional[Dict[str, Any]]:
        response = self._table_obj().get_item(
            Key={"apiProfileId": api_profile_id})
        item = response.get("Item")
        return dict(item) if item else None


__all__ = [
    "CREDENTIAL_TYPE",
    "CredentialStatus",
    "VerifyOutcome",
    "VerifyDecision",
    "CredentialStoreUnavailable",
    "UnauthorizedManagementAttempt",
    "CredentialNotFound",
    "generate_secret",
    "valid_secret_format",
    "digest_secret",
    "issue_credential",
    "revoke_credential",
    "disable_credential",
    "enable_credential",
    "rotate_credential",
    "verify_api_credential",
    "InMemoryCredentialStore",
    "InMemoryProfileStore",
    "DynamoDBCredentialStore",
    "DynamoDBProfileStore",
]
