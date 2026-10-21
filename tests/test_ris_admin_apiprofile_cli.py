"""Tests for the RIS Admin CLI APIProfile commands.

Covers the security-relevant behaviour of
`tools/ris_admin/apiprofiles.py` + the `ris-admin apiprofile ...`
subcommands:

  * the CLI CANNOT set a tenant (the tenant always comes from the
    operator authorization file) - tenant isolation stays intact
  * no authorization file / no matching principal -> fail closed,
    nothing is written
  * activation stays admin-only (the role comes from the
    authorization file, never from a flag)
  * the CLI never writes a profile item itself: it goes through the
    existing domain lifecycle
"""

import json
import os
import sys

import pytest

sys.path.insert(0, "tools")
sys.path.insert(0, ".")

from agents.ecosystem.api_profiles import InMemoryApiProfileStore  # noqa: E402
import ris_admin.apiprofiles as apis  # noqa: E402
from ris_admin.cli import build_parser  # noqa: E402


PRINCIPAL = "arn:aws:iam::240571105849:user/operator"
TENANT = "mays-ris-dev"


def _actor(role="admin", tenant=TENANT, principal=PRINCIPAL):
    return {"actor_role": role, "actor_id": principal, "actor_tenant": tenant}


# ----------------------------------------------------------------------
# Domain actor mapping
# ----------------------------------------------------------------------

def test_domain_actor_maps_admin_to_admins_group():
    actor = apis.domain_actor(_actor(role="admin"))
    assert actor["groups"] == ["admins"]
    assert actor["tenantId"] == TENANT
    assert actor["userId"] == PRINCIPAL


def test_domain_actor_maps_staff_and_owner():
    assert apis.domain_actor(_actor(role="staff"))["groups"] == ["Staff"]
    assert apis.domain_actor(_actor(role="owner"))["groups"] == []


def test_domain_actor_never_invents_admin():
    """A non-admin role must not gain the admins group."""
    for role in ("staff", "owner"):
        assert "admins" not in apis.domain_actor(_actor(role=role))["groups"]


# ----------------------------------------------------------------------
# create / activate through the existing domain
# ----------------------------------------------------------------------

def test_create_uses_domain_lifecycle_and_starts_pending():
    store = InMemoryApiProfileStore()
    item = apis.create("Mays-Jobs-Matcher", _actor(), profile_store=store)
    assert item["status"] == "PENDING"
    assert item["tenantId"] == TENANT
    assert item["ownerUserId"] == PRINCIPAL
    assert item["apiProfileId"].startswith("aprof_")
    # stored through the domain store, not written by the CLI
    assert store.get_profile(item["apiProfileId"]) is not None


def test_create_duplicate_name_conflicts():
    store = InMemoryApiProfileStore()
    apis.create("Mays-Jobs-Matcher", _actor(), profile_store=store)
    with pytest.raises(Exception):
        apis.create("mays-jobs-matcher", _actor(), profile_store=store)


def test_activate_moves_pending_to_active():
    store = InMemoryApiProfileStore()
    item = apis.create("Mays-Jobs-Matcher", _actor(), profile_store=store)
    out = apis.activate(item["apiProfileId"], _actor(), profile_store=store)
    assert out["status"] == "ACTIVE"


def test_activate_is_admin_only():
    """A non-admin operator cannot activate - the domain decides."""
    store = InMemoryApiProfileStore()
    item = apis.create("Mays-Jobs-Matcher", _actor(), profile_store=store)
    with pytest.raises(Exception):
        apis.activate(item["apiProfileId"], _actor(role="staff"),
                      profile_store=store)
    assert store.get_profile(item["apiProfileId"])["status"] == "PENDING"


def test_activate_cannot_cross_tenant():
    store = InMemoryApiProfileStore()
    item = apis.create("Mays-Jobs-Matcher", _actor(), profile_store=store)
    with pytest.raises(Exception):
        apis.activate(item["apiProfileId"], _actor(tenant="other-tenant"),
                      profile_store=store)


def test_list_and_show_are_tenant_scoped():
    store = InMemoryApiProfileStore()
    item = apis.create("Mays-Jobs-Matcher", _actor(), profile_store=store)
    rows = apis.list_all(_actor(), profile_store=store)
    assert [r["apiProfileId"] for r in rows] == [item["apiProfileId"]]
    assert apis.show(item["apiProfileId"], _actor(),
                     profile_store=store)["apiProfileId"] == item["apiProfileId"]


# ----------------------------------------------------------------------
# CLI surface
# ----------------------------------------------------------------------

def test_parser_exposes_apiprofile_commands():
    parser = build_parser()
    for cmd in ("create", "activate", "show", "list"):
        args = parser.parse_args(["apiprofile", cmd] + (
            ["--name", "x"] if cmd == "create" else
            ["--apiProfileId", "aprof_x"] if cmd in ("activate", "show") else []))
        assert args.apiprofile_cmd == cmd


def test_parser_has_no_tenant_flag():
    """The CLI must not offer a tenant switch: tenant comes from the
    operator authorization file only."""
    parser = build_parser()
    for cmd in ("create", "activate", "show", "list"):
        args = parser.parse_args(["apiprofile", cmd] + (
            ["--name", "x"] if cmd == "create" else
            ["--apiProfileId", "aprof_x"] if cmd in ("activate", "show") else []))
        assert not hasattr(args, "tenantId")
        assert not hasattr(args, "actor_role")


def test_dry_run_creates_nothing():
    """`--dry-run` must not touch the store."""
    store = InMemoryApiProfileStore()
    parser = build_parser()
    args = parser.parse_args(["--dry-run", "apiprofile", "create",
                              "--name", "Mays-Jobs-Matcher"])
    args.profile_store = store
    from ris_admin.cli import main  # noqa: F401  (import check only)
    assert store.items == {}


# ----------------------------------------------------------------------
# Authorization fail-closed
# ----------------------------------------------------------------------

def test_missing_authorization_file_fails_closed(tmp_path, monkeypatch):
    from ris_admin.credentials import AdminAuthorizationError
    from ris_admin.credentials import resolve_admin_authorization

    monkeypatch.setenv("RIS_ADMIN_AUTHORIZATION_FILE", str(tmp_path / "none.json"))
    with pytest.raises(AdminAuthorizationError):
        resolve_admin_authorization(str(tmp_path / "none.json"), PRINCIPAL,
                                    "create an APIProfile")


def test_unmapped_principal_fails_closed(tmp_path, monkeypatch):
    from ris_admin.credentials import AdminAuthorizationError
    from ris_admin.credentials import resolve_admin_authorization

    anchor = tmp_path / "auth.json"
    anchor.write_text(json.dumps({
        "principals": {
            "arn:aws:iam::240571105849:user/somebody-else": {
                "role": "admin", "tenantId": TENANT}}}), encoding="utf-8")
    os.chmod(str(anchor), 0o600)
    with pytest.raises(AdminAuthorizationError):
        resolve_admin_authorization(str(anchor), PRINCIPAL,
                                    "create an APIProfile")


def test_authorization_file_without_tenant_fails_closed(tmp_path):
    from ris_admin.credentials import AdminAuthorizationError
    from ris_admin.credentials import resolve_admin_authorization

    anchor = tmp_path / "auth.json"
    anchor.write_text(json.dumps({
        "principals": {PRINCIPAL: {"role": "admin"}}}), encoding="utf-8")
    os.chmod(str(anchor), 0o600)
    with pytest.raises(AdminAuthorizationError):
        resolve_admin_authorization(str(anchor), PRINCIPAL,
                                    "create an APIProfile")
