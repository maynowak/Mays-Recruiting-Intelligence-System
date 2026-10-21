"""Tests for the RIS Admin CLI offer / entitlement-grant commands.

Covers the security-relevant behaviour of
`tools/ris_admin/offers.py` + the `ris-admin offer ...` subcommands:

  * the CLI CANNOT set a tenant (the tenant always comes from the
    operator authorization file) - tenant isolation stays intact
  * the CLI never writes an offer or an entitlement itself: it goes
    through the existing offer domain (`agents.ecosystem.offers`)
  * the domain keeps its rules: admin-only, catalog validation before
    persistence, name uniqueness, mandatory reason, mandatory window,
    all-or-nothing entitlement writes
  * no authorization file / no matching principal -> fail closed,
    nothing is written
"""

import json
import os
import sys

import pytest

sys.path.insert(0, "tools")
sys.path.insert(0, ".")

from agents.ecosystem.offers import (  # noqa: E402
    GrantDenied,
    InMemoryEntitlementStore,
    InMemoryOfferStore,
    UnauthorizedOfferAction,
)
import ris_admin.offers as offs  # noqa: E402
from ris_admin.cli import build_parser  # noqa: E402


PRINCIPAL = "arn:aws:iam::240571105849:user/operator"
TENANT = "mays-ris-dev"
CONSUMER = "a3e488c2-b071-70fa-6c0b-da4f3bc8a299"

CATALOG = {
    "jobsearch-agent": {"agentId": "jobsearch-agent", "status": "ACTIVE"},
    "reference_agent": {"agentId": "reference_agent", "status": "ACTIVE"},
    "blocked_agent": {"agentId": "blocked_agent", "status": "BLOCKED"},
}


def _actor(role="admin", tenant=TENANT, principal=PRINCIPAL):
    return {"actor_role": role, "actor_id": principal, "actor_tenant": tenant}


def _stores():
    return InMemoryOfferStore(), InMemoryEntitlementStore()


# ----------------------------------------------------------------------
# Domain actor mapping
# ----------------------------------------------------------------------

def test_domain_actor_maps_admin_to_admins_group():
    actor = offs.domain_actor(_actor(role="admin"))
    assert actor["groups"] == ["admins"]
    assert actor["tenantId"] == TENANT
    assert actor["userId"] == PRINCIPAL


def test_domain_actor_never_invents_admin():
    """A non-admin role must not gain the admins group."""
    for role in ("staff", "owner"):
        assert "admins" not in offs.domain_actor(_actor(role=role))["groups"]


# ----------------------------------------------------------------------
# create through the existing domain
# ----------------------------------------------------------------------

def test_create_uses_domain_and_validates_agents_against_catalog():
    offers, _ = _stores()
    item = offs.create("Jobsearch Basispaket", _actor(),
                       ["jobsearch-agent"], offer_store=offers,
                       catalog=CATALOG)
    assert item["status"] == "ACTIVE"
    assert item["agentIds"] == ["jobsearch-agent"]
    # stored through the domain store, not written by the CLI
    assert offers.get_offer(item["offerId"]) is not None


def test_create_refuses_unknown_agent():
    offers, _ = _stores()
    with pytest.raises(GrantDenied):
        offs.create("Jobsearch Basispaket", _actor(), ["does-not-exist"],
                    offer_store=offers, catalog=CATALOG)
    assert offers.list_offers() == []


def test_create_refuses_non_executable_agent():
    offers, _ = _stores()
    with pytest.raises(GrantDenied):
        offs.create("Jobsearch Basispaket", _actor(), ["blocked_agent"],
                    offer_store=offers, catalog=CATALOG)
    assert offers.list_offers() == []


def test_create_duplicate_name_conflicts():
    offers, _ = _stores()
    offs.create("Jobsearch Basispaket", _actor(), ["jobsearch-agent"],
                offer_store=offers, catalog=CATALOG)
    with pytest.raises(Exception):
        offs.create("jobsearch basispaket", _actor(), ["jobsearch-agent"],
                    offer_store=offers, catalog=CATALOG)


def test_create_is_admin_only():
    offers, _ = _stores()
    with pytest.raises(UnauthorizedOfferAction):
        offs.create("Jobsearch Basispaket", _actor(role="staff"),
                    ["jobsearch-agent"], offer_store=offers, catalog=CATALOG)
    assert offers.list_offers() == []


# ----------------------------------------------------------------------
# grant through the existing domain
# ----------------------------------------------------------------------

def _offer(offers, agent_ids=("jobsearch-agent", "reference_agent")):
    return offs.create("Jobsearch Basispaket", _actor(), list(agent_ids),
                       offer_store=offers, catalog=CATALOG)


def test_grant_writes_one_user_wide_entitlement_per_agent():
    offers, entitlements = _stores()
    offer = _offer(offers)
    out = offs.grant(offer["offerId"], _actor(), CONSUMER,
                     "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z",
                     "Partner-Angebot Jobsearch", offer_store=offers,
                     entitlement_store=entitlements, catalog=CATALOG)
    assert len(out["entitlementIds"]) == 2
    rows = entitlements.find_by_user(CONSUMER)
    assert len(rows) == 2
    # USER scope: user-wide, NO apiProfileId (the shape the worker
    # authorization treats as user-wide)
    assert all("apiProfileId" not in r for r in rows)
    assert {r["agentId"] for r in rows} == {"jobsearch-agent",
                                            "reference_agent"}
    assert all(r["tenantId"] == TENANT for r in rows)


def test_grant_uses_the_authorization_tenant_not_a_flag():
    """The tenant comes from the trust anchor, never from the caller."""
    offers, entitlements = _stores()
    offer = _offer(offers)
    offs.grant(offer["offerId"], _actor(tenant="mays-ris-dev"), CONSUMER,
               "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z",
               "Partner-Angebot Jobsearch", offer_store=offers,
               entitlement_store=entitlements, catalog=CATALOG)
    rows = entitlements.find_by_user(CONSUMER)
    assert all(r["tenantId"] == "mays-ris-dev" for r in rows)


def test_grant_needs_reason():
    offers, entitlements = _stores()
    offer = _offer(offers)
    with pytest.raises(GrantDenied):
        offs.grant(offer["offerId"], _actor(), CONSUMER,
                   "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z", "",
                   offer_store=offers, entitlement_store=entitlements,
                   catalog=CATALOG)
    assert entitlements.find_by_user(CONSUMER) == []


def test_grant_needs_a_valid_window():
    offers, entitlements = _stores()
    offer = _offer(offers)
    with pytest.raises(GrantDenied):
        offs.grant(offer["offerId"], _actor(), CONSUMER,
                   "2027-12-31T23:59:59Z", "2026-10-21T00:00:00Z", "reason",
                   offer_store=offers, entitlement_store=entitlements,
                   catalog=CATALOG)
    assert entitlements.find_by_user(CONSUMER) == []


def test_grant_is_admin_only():
    offers, entitlements = _stores()
    offer = _offer(offers)
    with pytest.raises(UnauthorizedOfferAction):
        offs.grant(offer["offerId"], _actor(role="staff"), CONSUMER,
                   "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z", "reason",
                   offer_store=offers, entitlement_store=entitlements,
                   catalog=CATALOG)
    assert entitlements.find_by_user(CONSUMER) == []


def test_grant_refuses_inactive_offer():
    offers, entitlements = _stores()
    offer = offs.create("Inaktiv", _actor(), ["jobsearch-agent"],
                        status="INACTIVE", offer_store=offers,
                        catalog=CATALOG)
    with pytest.raises(GrantDenied):
        offs.grant(offer["offerId"], _actor(), CONSUMER,
                   "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z", "reason",
                   offer_store=offers, entitlement_store=entitlements,
                   catalog=CATALOG)
    assert entitlements.find_by_user(CONSUMER) == []


def test_grant_is_idempotent_on_repeated_identical_call():
    offers, entitlements = _stores()
    offer = _offer(offers)
    first = offs.grant(offer["offerId"], _actor(), CONSUMER,
                       "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z",
                       "reason", offer_store=offers,
                       entitlement_store=entitlements, catalog=CATALOG)
    second = offs.grant(offer["offerId"], _actor(), CONSUMER,
                        "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z",
                        "reason", offer_store=offers,
                        entitlement_store=entitlements, catalog=CATALOG)
    assert second["reused"] is True
    assert sorted(second["entitlementIds"]) == sorted(first["entitlementIds"])
    assert len(entitlements.find_by_user(CONSUMER)) == 2


# ----------------------------------------------------------------------
# CLI surface
# ----------------------------------------------------------------------

def test_parser_exposes_offer_commands():
    parser = build_parser()
    for cmd in ("create", "grant", "list", "show"):
        argv = ["offer", cmd]
        if cmd == "create":
            argv += ["--name", "x", "--agent-ids", "jobsearch-agent"]
        if cmd == "grant":
            argv += ["--offerId", "off_x", "--user-id", CONSUMER,
                     "--reason", "r", "--valid-from", "2026-10-21T00:00:00Z",
                     "--valid-until", "2027-12-31T23:59:59Z"]
        if cmd == "show":
            argv += ["--offerId", "off_x"]
        args = parser.parse_args(argv)
        assert args.offer_cmd == cmd


def test_parser_has_no_tenant_flag():
    """The CLI must not offer a tenant switch: tenant comes from the
    operator authorization file only."""
    parser = build_parser()
    args = parser.parse_args([
        "offer", "grant", "--offerId", "off_x", "--user-id", CONSUMER,
        "--reason", "r", "--valid-from", "2026-10-21T00:00:00Z",
        "--valid-until", "2027-12-31T23:59:59Z"])
    assert not hasattr(args, "tenantId")
    assert not hasattr(args, "actor_role")


def test_dry_run_creates_nothing():
    """`--dry-run` must not touch the store."""
    parser = build_parser()
    args = parser.parse_args(["--dry-run", "offer", "create",
                              "--name", "Jobsearch Basispaket",
                              "--agent-ids", "jobsearch-agent"])
    assert args.dry_run is True
    assert args.offer_cmd == "create"


# ----------------------------------------------------------------------
# Configuration fail-closed
# ----------------------------------------------------------------------

def test_missing_offer_table_fails_closed(monkeypatch):
    monkeypatch.delenv("OFFERS_TABLE", raising=False)
    with pytest.raises(RuntimeError):
        offs.create("Jobsearch Basispaket", _actor(), ["jobsearch-agent"],
                    catalog=CATALOG)


def test_missing_entitlement_table_fails_closed(monkeypatch):
    offers, _ = _stores()
    offer = _offer(offers)
    monkeypatch.delenv("ENTITLEMENTS_TABLE", raising=False)
    with pytest.raises(RuntimeError):
        offs.grant(offer["offerId"], _actor(), CONSUMER,
                   "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z", "reason",
                   offer_store=offers, catalog=CATALOG)


def test_missing_catalog_fails_closed(monkeypatch):
    offers, entitlements = _stores()
    monkeypatch.delenv("AGENT_CATALOG_TABLE", raising=False)
    with pytest.raises(RuntimeError):
        offs.create("Jobsearch Basispaket", _actor(), ["jobsearch-agent"],
                    offer_store=offers)


# ----------------------------------------------------------------------
# Authorization fail-closed
# ----------------------------------------------------------------------

def test_missing_authorization_file_fails_closed(tmp_path):
    from ris_admin.credentials import (AdminAuthorizationError,
                                       resolve_admin_authorization)

    with pytest.raises(AdminAuthorizationError):
        resolve_admin_authorization(str(tmp_path / "none.json"), PRINCIPAL,
                                    "create an offer")


def test_unmapped_principal_fails_closed(tmp_path):
    from ris_admin.credentials import (AdminAuthorizationError,
                                       resolve_admin_authorization)

    anchor = tmp_path / "auth.json"
    anchor.write_text(json.dumps({
        "principals": {
            "arn:aws:iam::240571105849:user/somebody-else": {
                "role": "admin", "tenantId": TENANT}}}), encoding="utf-8")
    os.chmod(str(anchor), 0o600)
    with pytest.raises(AdminAuthorizationError):
        resolve_admin_authorization(str(anchor), PRINCIPAL,
                                    "create an offer")


def test_authorization_file_without_tenant_fails_closed(tmp_path):
    from ris_admin.credentials import (AdminAuthorizationError,
                                       resolve_admin_authorization)

    anchor = tmp_path / "auth.json"
    anchor.write_text(json.dumps({
        "principals": {PRINCIPAL: {"role": "admin"}}}), encoding="utf-8")
    os.chmod(str(anchor), 0o600)
    with pytest.raises(AdminAuthorizationError):
        resolve_admin_authorization(str(anchor), PRINCIPAL,
                                    "create an offer")


def test_grant_without_tenant_scope_fails_closed():
    offers, entitlements = _stores()
    offer = _offer(offers)
    with pytest.raises(offs.OfferOperationError):
        offs.grant(offer["offerId"], _actor(tenant=""), CONSUMER,
                   "2026-10-21T00:00:00Z", "2027-12-31T23:59:59Z", "reason",
                   offer_store=offers, entitlement_store=entitlements,
                   catalog=CATALOG)
    assert entitlements.find_by_user(CONSUMER) == []
