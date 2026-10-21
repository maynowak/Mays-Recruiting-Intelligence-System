#!/usr/bin/env python3
"""RIS Admin CLI - APIProfile operations.

Thin wiring over the EXISTING RIS APIProfile domain
(`agents.ecosystem.api_profiles`). No second lifecycle, no second
authorization model: `create_profile`, `transition_status`,
`get_profile` and `list_profiles` are called directly and their audit
events are preserved.

SECURITY MODEL (identical to tools/ris_admin/credentials.py)
------------------------------------------------------------
The RIS actor role is NEVER taken from a CLI flag. It is derived from
the authenticated AWS principal (STS GetCallerIdentity) resolved through
an explicit, operator-supplied authorization file - the same trust
anchor the credential commands use. Without that file, or without a
matching entry, every operation fails closed. Owning an AWS profile is
not sufficient: `sts:GetCallerIdentity` proves WHO is calling, not that
they are a RIS administrator.

The resolved authorization contract is mapped onto the DOMAIN actor
contract like this:

    actor_role   admin|staff|owner  ->  cognito group (admins|Staff)
    actor_id     <principal ARN>     ->  domain actor userId (owner)
    actor_tenant <tenantId>         ->  domain actor tenantId

Tenant isolation therefore stays intact: a profile created through the
CLI is owned by the operator principal and bound to the tenant named in
the authorization file - never to a tenant supplied on the command line.
There is deliberately no `--tenantId` flag: the CLI cannot write a
profile into a tenant it is not authorized for.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


class ApiProfileOperationError(Exception):
    """A RIS APIProfile operation could not be completed."""


# ----------------------------------------------------------------------
# Domain wiring
# ----------------------------------------------------------------------

def _profile_store(profile_store=None):
    """The APIProfile store. Falls back to the configured DynamoDB table."""
    from agents.ecosystem.api_profiles import DynamoDBApiProfileStore

    if profile_store is not None:
        return profile_store
    table = os.getenv("API_PROFILES_TABLE")
    if not table:
        raise RuntimeError(
            "profile store is not configured; set API_PROFILES_TABLE "
            "or pass an explicit store")
    return DynamoDBApiProfileStore(table_name=table)


def domain_actor(actor: Dict[str, Any]) -> Dict[str, Any]:
    """Authorization contract -> domain actor contract.

    The domain decides rights from `groups` (api_profiles._is_admin /
    _is_staff). The role strings of the authorization file are mapped
    onto those groups; nothing else is invented.
    """
    role = actor.get("actor_role")
    groups: List[str] = []
    if role == "admin":
        groups = ["admins"]
    elif role == "staff":
        groups = ["Staff"]
    return {
        "userId": actor.get("actor_id"),
        "tenantId": actor.get("actor_tenant"),
        "groups": groups,
    }


# ----------------------------------------------------------------------
# Operations
# ----------------------------------------------------------------------

def create(name: str,
           actor: Dict[str, Any],
           description: Optional[str] = None,
           target_owner: Optional[str] = None,
           idempotency_key: Optional[str] = None,
           profile_store=None) -> Dict[str, Any]:
    """Create an APIProfile through the existing domain lifecycle.

    The domain decides the initial status (always PENDING) and the
    owner/tenant binding. The CLI never writes a profile item itself.
    """
    from agents.ecosystem.api_profiles import create_profile

    store = _profile_store(profile_store)
    return create_profile(
        store,
        domain_actor(actor),
        name,
        description=description,
        target_owner=target_owner,
        idempotency_key=idempotency_key,
    )


def activate(api_profile_id: str,
             actor: Dict[str, Any],
             reason: Optional[str] = None,
             profile_store=None) -> Dict[str, Any]:
    """PENDING -> ACTIVE through the existing domain lifecycle.

    Activation stays admin-only inside the domain; the CLI cannot
    bypass it because the role comes from the authorization file.
    """
    from agents.ecosystem.api_profiles import transition_status

    store = _profile_store(profile_store)
    return transition_status(
        store,
        domain_actor(actor),
        api_profile_id,
        "ACTIVE",
        reason=reason,
    )


def show(api_profile_id: str,
         actor: Dict[str, Any],
         reason: Optional[str] = None,
         profile_store=None) -> Optional[Dict[str, Any]]:
    """Read one profile. Foreign/missing stays indistinguishable (None)."""
    from agents.ecosystem.api_profiles import get_profile

    store = _profile_store(profile_store)
    return get_profile(store, domain_actor(actor), api_profile_id,
                       reason=reason)


def list_all(actor: Dict[str, Any],
             reason: Optional[str] = None,
             profile_store=None) -> List[Dict[str, Any]]:
    """List the profiles visible to the authorized actor."""
    from agents.ecosystem.api_profiles import list_profiles

    store = _profile_store(profile_store)
    return list_profiles(store, domain_actor(actor), reason=reason)


__all__ = [
    "ApiProfileOperationError",
    "activate",
    "create",
    "domain_actor",
    "list_all",
    "show",
]
