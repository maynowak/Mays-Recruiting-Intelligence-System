#!/usr/bin/env python3
"""RIS Admin CLI - Offer and Entitlement-grant operations.

Thin wiring over the EXISTING RIS offer domain
(`agents.ecosystem.offers`). No second offer lifecycle, no second
authorization model: `create_offer`, `grant_offer`, `list_offers` and
`get_offer` are called directly, so the domain keeps every rule that
matters:

  * admin-only (`_require_admin` -> group `admins` in the actor)
  * name uniqueness across the offer catalog
  * agent validation against the CATALOG BEFORE anything is persisted
    (an offer can never reference a non-existent or non-executable agent)
  * mandatory `reason` for a grant, mandatory validity window
  * all-or-nothing entitlement writes, idempotency keys, overlap refusal
  * the audit trail of the domain is preserved

The CLI writes NO DynamoDB item itself.

WHY A CLI AND NOT THE HTTP ROUTE
--------------------------------
`POST /v1/offers` exists, but it authorizes on `cognito:groups` of the
calling JWT. The RIS operator principal used here owns an AWS profile,
not a Cognito group, and there is no password/id-token flow for it.
Rather than inventing a second admin path in the API, this adapter
reuses the trust anchor that `tools/ris_admin/credentials.py` already
establishes.

SECURITY MODEL (identical to tools/ris_admin/apiprofiles.py)
------------------------------------------------------------
The RIS actor role is NEVER taken from a CLI flag. It is derived from
the authenticated AWS principal (STS GetCallerIdentity) resolved through
the operator-supplied authorization file - the same trust anchor the
credential and APIProfile commands use. Without that file, or without a
matching entry, every operation fails closed. Owning an AWS profile is
not sufficient: `sts:GetCallerIdentity` proves WHO is calling, not that
they are a RIS administrator.

The resolved authorization contract is mapped onto the DOMAIN actor
contract like this:

    actor_role   admin|staff|owner  ->  cognito group (admins|Staff)
    actor_id     <principal ARN>     ->  domain actor userId (owner)
    actor_tenant <tenantId>         ->  domain actor tenantId

Tenant isolation therefore stays intact: an offer is created in, and a
grant is written into, the tenant named in the authorization file. There
is deliberately no `--tenantId` flag: the CLI cannot grant an
entitlement into a tenant its operator is not authorized for. The
target of a grant is the CONSUMER (the Cognito `sub`), never a tenant.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


class OfferOperationError(Exception):
    """A RIS offer operation could not be completed."""


# ----------------------------------------------------------------------
# Domain wiring
# ----------------------------------------------------------------------

def _offer_store(offer_store=None):
    """The offer store. Falls back to the configured DynamoDB table."""
    from agents.ecosystem.offers import DynamoDBOfferStore

    if offer_store is not None:
        return offer_store
    table = os.getenv("OFFERS_TABLE")
    if not table:
        raise RuntimeError(
            "offer store is not configured; set OFFERS_TABLE "
            "or pass an explicit store")
    return DynamoDBOfferStore(table_name=table)


def _entitlement_store(entitlement_store=None):
    """The entitlement store. Falls back to the configured DynamoDB table."""
    from agents.ecosystem.offers import DynamoDBEntitlementStore

    if entitlement_store is not None:
        return entitlement_store
    table = os.getenv("ENTITLEMENTS_TABLE")
    if not table:
        raise RuntimeError(
            "entitlement store is not configured; set ENTITLEMENTS_TABLE "
            "or pass an explicit store")
    return DynamoDBEntitlementStore(table_name=table)


def _profile_store(profile_store=None):
    """The APIProfile store (needed for APIPROFILE-scoped grants only)."""
    from agents.ecosystem.api_profiles import DynamoDBApiProfileStore

    if profile_store is not None:
        return profile_store
    table = os.getenv("API_PROFILES_TABLE")
    if not table:
        raise RuntimeError(
            "profile store is not configured; set API_PROFILES_TABLE "
            "or pass an explicit store")
    return DynamoDBApiProfileStore(table_name=table)


def _catalog(catalog=None):
    """The agent catalog the domain validates every agentId against.

    The canonical reader is reused (`agents.ecosystem.catalog_adapter.
    CatalogAdapter`) - the same source the runtime registry is filled
    from, so an offer can only reference an agent that really exists.
    """
    if catalog is not None:
        return catalog
    from agents.ecosystem.catalog_adapter import CatalogAdapter

    table = os.getenv("AGENT_CATALOG_TABLE")
    if not table:
        raise RuntimeError(
            "agent catalog is not configured; set AGENT_CATALOG_TABLE "
            "or pass an explicit catalog")
    return CatalogAdapter(table_name=table).get_all_agents()


def domain_actor(actor: Dict[str, Any]) -> Dict[str, Any]:
    """Authorization contract -> domain actor contract.

    The domain decides rights from `groups` (offers._is_admin). The role
    strings of the authorization file are mapped onto those groups;
    nothing else is invented.
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
           agent_ids: List[str],
           description: Optional[str] = None,
           status: str = "ACTIVE",
           offer_store=None,
           catalog=None) -> Dict[str, Any]:
    """Create an offer through the existing domain lifecycle.

    The domain validates every agentId against the catalog BEFORE the
    offer is persisted, so an offer can never be stored with a dangling
    or non-executable agent.
    """
    from agents.ecosystem.offers import create_offer

    return create_offer(
        _offer_store(offer_store),
        domain_actor(actor),
        name,
        agent_ids,
        _catalog(catalog),
        description=description,
        status=status,
    )


def grant(offer_id: str,
          actor: Dict[str, Any],
          target_user_id: str,
          valid_from: str,
          valid_until: str,
          reason: str,
          scope: str = "USER",
          api_profile_id: Optional[str] = None,
          idempotency_key: Optional[str] = None,
          offer_store=None,
          entitlement_store=None,
          profile_store=None,
          catalog=None) -> Dict[str, Any]:
    """Grant an offer to ONE consumer through the existing domain.

    The tenant is NOT a parameter: it always comes from the operator
    authorization file (the trust anchor). The target of the grant is the
    consumer (Cognito `sub`), which the operator selects deliberately.

    The domain decides scope semantics: `USER` (user-wide, no
    apiProfileId) and `APIPROFILE` (profile-bound, and only for a
    profile that belongs to the same target user and tenant). Both stay
    available; the domain refuses what does not hold.
    """
    from agents.ecosystem.offers import grant_offer

    tenant_id = (actor.get("actor_tenant") or "").strip()
    if not tenant_id:
        raise OfferOperationError(
            "no tenant scope in the operator authorization; refusing to grant")

    profiles = None
    if scope != "USER":
        profiles = _profile_store(profile_store)

    return grant_offer(
        _offer_store(offer_store),
        _entitlement_store(entitlement_store),
        profiles,
        _catalog(catalog),
        domain_actor(actor),
        offer_id,
        target_user_id,
        tenant_id,
        scope,
        api_profile_id=api_profile_id,
        valid_from=valid_from,
        valid_until=valid_until,
        reason=reason,
        idempotency_key=idempotency_key,
    )


def list_all(actor: Dict[str, Any],
             include_inactive: bool = False,
             offer_store=None) -> List[Dict[str, Any]]:
    """List the offers visible to the authorized actor."""
    from agents.ecosystem.offers import list_offers

    return list_offers(_offer_store(offer_store), domain_actor(actor),
                       include_inactive=include_inactive)


def show(offer_id: str, offer_store=None) -> Optional[Dict[str, Any]]:
    """Read one offer (missing -> None)."""
    from agents.ecosystem.offers import get_offer

    return get_offer(_offer_store(offer_store), offer_id)


__all__ = [
    "OfferOperationError",
    "create",
    "domain_actor",
    "grant",
    "list_all",
    "show",
]
