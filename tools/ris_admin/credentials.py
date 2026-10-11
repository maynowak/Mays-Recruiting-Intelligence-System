#!/usr/bin/env python3
"""RIS Admin CLI - credential operations.

Thin wiring over the EXISTING RIS credential domain
(`agents.ecosystem.credentials`). No second credential generator, no second
lifecycle, no second authorization model: `issue_credential`,
`revoke_credential`, `list_credentials` and `get_credential_metadata` are
called directly and their audit events are preserved.

SECURITY MODEL
--------------
The RIS actor role is NEVER taken from a CLI flag. It is derived from the
authenticated AWS principal (STS GetCallerIdentity) resolved through an
explicit, operator-supplied authorization file:

    {
      "principals": {
        "arn:aws:iam::240571105849:user/ris-operator": {
          "role": "admin",
          "tenantId": "b34-1791208808"
        }
      }
    }

Without that file, or without a matching entry, every operation fails closed.
Owning an AWS profile is not sufficient: `sts:GetCallerIdentity` proves WHO is
calling, not that they are a RIS administrator, so the mapping must exist.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


class AdminAuthorizationError(Exception):
    """No trusted RIS administrative authorization could be established."""


class OutputDestinationError(Exception):
    """The secret output destination is unsafe or unusable."""


class CredentialOutputFailed(Exception):
    """The credential exists but the secret could not be persisted.

    Carries the credential id for administrative recovery. The secret is NOT
    carried: it exists only inside the domain layer and is never re-obtainable.
    """

    def __init__(self, credential_id: str, detail: str):
        super().__init__(detail)
        self.credential_id = credential_id
        self.detail = detail


# ----------------------------------------------------------------------
# Authorization
# ----------------------------------------------------------------------

def resolve_admin_authorization(
    authorization_file: Optional[str],
    principal_arn: str,
    operation: str,
) -> Dict[str, Any]:
    """Resolve the RIS actor contract for an authenticated AWS principal.

    Fails closed. There is deliberately no fallback, no default role and no
    flag-based override.
    """
    if not authorization_file:
        raise AdminAuthorizationError(
            "no RIS administrative authorization mapping configured; "
            "refusing to %s" % operation)
    if not os.path.exists(authorization_file):
        raise AdminAuthorizationError(
            "authorization file not found; refusing to %s" % operation)
    try:
        with open(authorization_file, "r", encoding="utf-8") as fh:
            policy = json.load(fh)
    except (OSError, ValueError) as exc:
        raise AdminAuthorizationError(
            "authorization file unreadable (%s); refusing to %s"
            % (type(exc).__name__, operation))

    entry = (policy.get("principals") or {}).get(principal_arn)
    if not entry:
        raise AdminAuthorizationError(
            "principal is not a mapped RIS administrator; refusing to %s"
            % operation)

    role = entry.get("role")
    if role not in ("admin", "staff", "owner"):
        raise AdminAuthorizationError(
            "authorization entry has no usable role; refusing to %s" % operation)
    tenant_id = entry.get("tenantId")
    if not tenant_id:
        raise AdminAuthorizationError(
            "authorization entry has no tenantId scope; refusing to %s"
            % operation)
    return {"actor_role": role, "actor_id": principal_arn,
            "actor_tenant": tenant_id}


# ----------------------------------------------------------------------
# Secure secret destination
# ----------------------------------------------------------------------

def precheck_output_destination(path: str) -> None:
    """Reject an unsafe destination BEFORE a credential is issued.

    Checks, in order:
      * the path is absolute or resolvable
      * no component is a symlink (prevents redirecting the secret)
      * the target does not already exist (never clobber)
      * the parent directory exists and is not world/group writable
    """
    if not path:
        raise OutputDestinationError("no secret output destination given")
    parent = os.path.dirname(os.path.abspath(path)) or "."
    if not os.path.isdir(parent):
        raise OutputDestinationError(
            "secret output directory does not exist")
    mode = stat.S_IMODE(os.stat(parent).st_mode)
    if mode & (stat.S_IWOTH | stat.S_IWGRP):
        raise OutputDestinationError(
            "secret output directory is writable by group or other")
    if os.path.islink(path):
        raise OutputDestinationError(
            "secret output path is a symlink")
    if os.path.exists(path):
        raise OutputDestinationError(
            "secret output file already exists; refusing to overwrite")


def open_secret_file(path: str) -> int:
    """Create the secret file exclusively, owner-only, never following links.

    The primary symlink guard is O_EXCL: on Linux open(O_CREAT|O_EXCL) fails
    with EEXIST when the final path component is a symlink, regardless of its
    target. O_NOFOLLOW is defence in depth for platforms or option combinations
    where O_EXCL alone might not cover it. 0o600 is owner read/write only, so
    the secret is never world-readable even momentarily.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, flags, 0o600)
    except FileExistsError:
        raise OutputDestinationError(
            "secret output file already exists; refusing to overwrite")
    except OSError as exc:
        raise OutputDestinationError(
            "secret output file could not be created (%s)"
            % type(exc).__name__)


def write_secret(fd: int, secret: str) -> None:
    """Write and fsync the secret. Never raises the secret back out."""
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(secret)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        raise CredentialOutputFailed("", "secret write failed (%s)"
                                     % type(exc).__name__)


# ----------------------------------------------------------------------
# Domain wiring
# ----------------------------------------------------------------------

def _stores(profile_store=None, credential_store=None):
    """Return (credential_store, profile_store).

    Either may be injected explicitly (tests, or a caller that only needs one
    half). Anything not supplied falls back to the configured DynamoDB store.
    """
    from agents.ecosystem.credentials import (
        DynamoDBCredentialStore,
        DynamoDBProfileStore,
    )
    credentials_table = os.getenv("CREDENTIALS_TABLE")
    profiles_table = os.getenv("API_PROFILES_TABLE")

    if credential_store is None:
        if not credentials_table:
            raise RuntimeError(
                "credential store is not configured; set CREDENTIALS_TABLE "
                "or pass an explicit store")
        credential_store = DynamoDBCredentialStore(table_name=credentials_table)
    if profile_store is None:
        if not profiles_table:
            raise RuntimeError(
                "profile store is not configured; set API_PROFILES_TABLE "
                "or pass an explicit store")
        profile_store = DynamoDBProfileStore(table_name=profiles_table)
    return credential_store, profile_store


def _credential_store(credential_store=None):
    """The credential half only. Listing, showing and revoking never touch
    the APIProfile store."""
    from agents.ecosystem.credentials import DynamoDBCredentialStore
    if credential_store is not None:
        return credential_store
    table = os.getenv("CREDENTIALS_TABLE")
    if not table:
        raise RuntimeError(
            "credential store is not configured; set CREDENTIALS_TABLE "
            "or pass an explicit store")
    return DynamoDBCredentialStore(table_name=table)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue(
    api_profile_id: str,
    expires_at: str,
    actor: Dict[str, Any],
    output_path: str,
    label: Optional[str] = None,
    reason: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    profile_store=None,
    credential_store=None,
) -> Dict[str, Any]:
    """Issue one credential and persist its secret exactly once.

    Order matters: the destination is validated and the exclusive file handle
    is opened BEFORE issuance, so the common failure (bad destination) cannot
    orphan a live credential. If issuance then fails, the placeholder is
    removed. If the WRITE fails after issuance, the credential genuinely
    exists and `CredentialOutputFailed` reports the id for administrative
    recovery - it never claims a rollback and never issues a second one.
    """
    from agents.ecosystem.credentials import issue_credential

    credential_store, profile_store = _stores(profile_store, credential_store)

    # Domain preconditions are evaluated first so an obviously bad request
    # never reaches the store.
    profile = profile_store.get_profile(api_profile_id)
    if profile is None:
        raise ValueError("apiProfileId %r does not exist" % api_profile_id)

    precheck_output_destination(output_path)
    fd = open_secret_file(output_path)

    try:
        result = issue_credential(
            credential_store,
            profile_store,
            api_profile_id,
            expires_at,
            actor["actor_role"],
            actor["actor_id"],
            label=label,
            now_iso=_now().isoformat(),
            reason=reason,
            actor_tenant=actor["actor_tenant"],
            idempotency_key=idempotency_key,
        )
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(output_path)
        except OSError:
            pass
        raise

    metadata = result.get("metadata") or {}
    secret = result.get("secret")

    if result.get("duplicate"):
        # Idempotent replay: the original secret is never re-issued, so there
        # is nothing to write. The placeholder file must go away.
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(output_path)
        except OSError:
            pass
        return {"credentialId": metadata.get("credentialId"),
                "duplicate": True,
                "secretWritten": False}

    try:
        write_secret(fd, secret or "")
    except CredentialOutputFailed as exc:
        raise CredentialOutputFailed(
            metadata.get("credentialId"), exc.detail)
    except OSError as exc:
        raise CredentialOutputFailed(
            metadata.get("credentialId"),
            "secret write failed (%s)" % type(exc).__name__)

    return {"credentialId": metadata.get("credentialId"),
            "apiProfileId": metadata.get("apiProfileId"),
            "tenantId": metadata.get("tenantId"),
            "status": metadata.get("status"),
            "duplicate": False,
            "secretWritten": True,
            "outputFile": os.path.abspath(output_path)}


def revoke(
    credential_id: str,
    actor: Dict[str, Any],
    reason: Optional[str] = None,
    credential_store=None,
) -> Dict[str, Any]:
    """Terminally revoke an existing credential."""
    from agents.ecosystem.credentials import revoke_credential

    credential_store = _credential_store(credential_store)
    meta = revoke_credential(
        credential_store,
        credential_id,
        actor["actor_role"],
        actor["actor_id"],
        reason=reason,
        actor_tenant=actor["actor_tenant"],
    )
    return {"credentialId": (meta or {}).get("credentialId", credential_id),
            "status": (meta or {}).get("status", "REVOKED")}


def list_all(actor: Dict[str, Any],
             api_profile_id: Optional[str] = None,
             reason: Optional[str] = None,
             credential_store=None):
    from agents.ecosystem.credentials import list_credentials

    credential_store = _credential_store(credential_store)
    return list_credentials(
        credential_store,
        actor["actor_role"],
        actor["actor_id"],
        api_profile_id=api_profile_id,
        actor_tenant=actor["actor_tenant"],
        reason=reason,
    )


def show(credential_id: str, actor: Dict[str, Any],
         reason: Optional[str] = None,
         credential_store=None):
    from agents.ecosystem.credentials import get_credential_metadata

    credential_store = _credential_store(credential_store)
    return get_credential_metadata(
        credential_store,
        actor["actor_role"],
        actor["actor_id"],
        credential_id,
        actor_tenant=actor["actor_tenant"],
        reason=reason,
    )