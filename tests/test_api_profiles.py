"""Tests Gate 10: APIProfile foundation, CRUD & selection.

Roles: owner (no groups) / admin (groups=['admins']) /
staff (groups=['Staff']). Tenant isolation enforced throughout.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.api_profiles import (  # noqa: E402
    DynamoDBApiProfileStore,
    InMemoryApiProfileStore,
    InvalidProfileTransition,
    ProfileConflict,
    ProfileNotFound,
    UnauthorizedProfileAction,
)


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def owner(uid="u1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": []}


def admin(uid="a1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": ["admins"]}


def staff(uid="s1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": ["Staff"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryApiProfileStore()

    def mk(self, name="P1", actor=None, **kw):
        return ap.create_profile(self.store, actor or owner(), name, **kw)


class TestOwnerCRUD(Base):
    def test_01_create_starts_pending(self):
        p = self.mk()
        self.assertEqual(p["status"], "PENDING")
        self.assertEqual(p["ownerUserId"], "u1")
        self.assertEqual(p["tenantId"], "t1")
        self.assertTrue(p["apiProfileId"].startswith("aprof_"))

    def test_02_no_self_provision_on_login(self):
        # Login alone creates nothing: store stays empty without create.
        self.assertEqual(
            ap.list_profiles(self.store, owner()), [])

    def test_03_owner_reads_own(self):
        p = self.mk()
        got = ap.get_profile(self.store, owner(), p["apiProfileId"])
        self.assertEqual(got["apiProfileId"], p["apiProfileId"])

    def test_04_owner_lists_own(self):
        self.mk("A")
        self.mk("B")
        self.assertEqual(len(ap.list_profiles(self.store, owner())), 2)

    def test_05_owner_updates_name(self):
        p = self.mk()
        out = ap.update_profile(self.store, owner(), p["apiProfileId"],
                                name="Renamed")
        self.assertEqual(out["name"], "Renamed")

    def test_06_owner_updates_description(self):
        p = self.mk()
        out = ap.update_profile(self.store, owner(), p["apiProfileId"],
                                description="hello")
        self.assertEqual(out["description"], "hello")

    def test_07_foreign_read_neutral(self):
        p = self.mk()
        self.assertIsNone(
            ap.get_profile(self.store, owner("u2"), p["apiProfileId"]))

    def test_08_owner_cannot_change_owner(self):
        p = self.mk()
        with self.assertRaises(ValueError):
            ap.update_profile(self.store, owner(), p["apiProfileId"],
                              ownerUserId="u2")

    def test_09_owner_cannot_change_tenant(self):
        p = self.mk()
        with self.assertRaises(ValueError):
            ap.update_profile(self.store, owner(), p["apiProfileId"],
                              tenantId="t2")

    def test_10_owner_cannot_change_clientref(self):
        p = self.mk()
        with self.assertRaises(ValueError):
            ap.update_profile(self.store, owner(), p["apiProfileId"],
                              clientRef="x")

    def test_11_owner_cannot_change_expiry(self):
        p = self.mk()
        with self.assertRaises(ValueError):
            ap.update_profile(self.store, owner(), p["apiProfileId"],
                              expiresAt=_ts(5))

    def test_create_ignores_owner_clientref_expiry(self):
        p = ap.create_profile(self.store, owner(), "N",
                              client_ref="x", expires_at=_ts(5))
        self.assertIsNone(p["clientRef"])
        self.assertIsNone(p["expiresAt"])

    def test_tamper_createdby_createdat_id_rejected(self):
        p = self.mk()
        for field in ("createdBy", "createdAt", "apiProfileId"):
            with self.assertRaises(ValueError):
                ap.update_profile(self.store, owner(), p["apiProfileId"],
                                  **{field: "forged"})


class TestAdmin(Base):
    def test_12_create_for_target(self):
        p = ap.create_profile(self.store, admin(), "T",
                              target_owner="u9")
        self.assertEqual(p["ownerUserId"], "u9")

    def test_13_read_foreign(self):
        p = self.mk()
        got = ap.get_profile(self.store, admin(), p["apiProfileId"],
                             reason="support")
        self.assertEqual(got["apiProfileId"], p["apiProfileId"])

    def test_14_set_clientref(self):
        p = self.mk()
        out = ap.set_client_ref(self.store, admin(), p["apiProfileId"],
                                "matcher-a", reason="link")
        self.assertEqual(out["clientRef"], "matcher-a")

    def test_15_set_expiry(self):
        p = self.mk()
        out = ap.set_expires_at(self.store, admin(), p["apiProfileId"],
                                _ts(10), reason="grant")
        self.assertIsNotNone(out["expiresAt"])

    def test_16_pending_to_active(self):
        p = self.mk()
        out = ap.transition_status(self.store, admin(), p["apiProfileId"],
                                   "ACTIVE")
        self.assertEqual(out["status"], "ACTIVE")

    def test_17_disabled_to_active(self):
        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "DISABLED", reason="abuse")
        out = ap.transition_status(self.store, admin(), p["apiProfileId"],
                                   "ACTIVE")
        self.assertEqual(out["status"], "ACTIVE")

    def test_18_revoked_terminal(self):
        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "REVOKED", reason="end")
        with self.assertRaises(InvalidProfileTransition):
            ap.transition_status(self.store, admin(), p["apiProfileId"],
                                 "ACTIVE")

    def test_admin_cannot_rewrite_owner(self):
        p = self.mk()
        with self.assertRaises(ValueError):
            ap.update_profile(self.store, admin(), p["apiProfileId"],
                              ownerUserId="u2")

    def test_admin_crosstenant_needs_reason(self):
        p = self.mk()  # tenant t1
        other_admin = admin("a9", "t2")
        with self.assertRaises(UnauthorizedProfileAction):
            ap.get_profile(self.store, other_admin, p["apiProfileId"])
        got = ap.get_profile(self.store, other_admin, p["apiProfileId"],
                             reason="incident-42")
        self.assertIsNotNone(got)

    def test_admin_lock_blocks_owner_reenable(self):
        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "DISABLED", reason="abuse")
        with self.assertRaises(UnauthorizedProfileAction):
            ap.transition_status(self.store, owner(), p["apiProfileId"],
                                 "ACTIVE")

    def test_owner_self_lock_unlock(self):
        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        ap.transition_status(self.store, owner(), p["apiProfileId"],
                             "DISABLED", reason="lost-device")
        out = ap.transition_status(self.store, owner(), p["apiProfileId"],
                                   "ACTIVE")
        self.assertEqual(out["status"], "ACTIVE")

    def test_expired_needs_renew(self):
        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        ap.set_expires_at(self.store, admin(), p["apiProfileId"],
                           _ts(-1), reason="test")
        raw = self.store.get_profile(p["apiProfileId"])
        self.assertEqual(ap.effective_status(raw), "EXPIRED")
        with self.assertRaises(InvalidProfileTransition):
            ap.transition_status(self.store, admin(), p["apiProfileId"],
                                 "DISABLED", reason="x")
        out = ap.renew_profile(self.store, admin(), p["apiProfileId"],
                               _ts(30), reason="extend")
        self.assertEqual(out["status"], "ACTIVE")


class TestStaff(Base):
    def test_19_no_create(self):
        with self.assertRaises(UnauthorizedProfileAction):
            self.mk(actor=staff())

    def test_20_no_activation(self):
        p = self.mk()
        with self.assertRaises(UnauthorizedProfileAction):
            ap.transition_status(self.store, staff(), p["apiProfileId"],
                                 "ACTIVE")

    def test_staff_disable_with_reason(self):
        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        out = ap.transition_status(self.store, staff(), p["apiProfileId"],
                                   "DISABLED", reason="abuse-ticket-7")
        self.assertEqual(out["status"], "DISABLED")

    def test_staff_disable_needs_reason(self):
        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        with self.assertRaises(ValueError):
            ap.transition_status(self.store, staff(), p["apiProfileId"],
                                 "DISABLED")

    def test_staff_reenable_self_locked(self):
        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        ap.transition_status(self.store, staff(), p["apiProfileId"],
                             "DISABLED", reason="abuse")
        out = ap.transition_status(self.store, staff(), p["apiProfileId"],
                                   "ACTIVE")
        self.assertEqual(out["status"], "ACTIVE")

    def test_staff_no_revoke(self):
        p = self.mk()
        with self.assertRaises(UnauthorizedProfileAction):
            ap.transition_status(self.store, staff(), p["apiProfileId"],
                                 "REVOKED", reason="x")

    def test_unknown_status_rejected(self):
        p = self.mk()
        with self.assertRaises(InvalidProfileTransition):
            ap.transition_status(self.store, admin(), p["apiProfileId"],
                                 "SUSPENDED")


class TestIdempotencyTenant(Base):
    def test_21_unique_per_owner(self):
        self.mk("Same")
        with self.assertRaises(ProfileConflict):
            self.mk("Same")
        with self.assertRaises(ProfileConflict):
            self.mk("same")  # case-insensitive

    def test_unique_scoped_to_owner(self):
        self.mk("Same")
        other = ap.create_profile(self.store, owner("u2"), "Same")
        self.assertEqual(other["ownerUserId"], "u2")

    def test_idempotency_key_replay(self):
        first = ap.create_profile(self.store, owner(), "K",
                                  idempotency_key="k-123")
        again = ap.create_profile(self.store, owner(), "K",
                                  idempotency_key="k-123")
        self.assertEqual(first["apiProfileId"], again["apiProfileId"])

    def test_idempotency_key_mismatch_conflicts(self):
        ap.create_profile(self.store, owner(), "K", idempotency_key="k-1")
        with self.assertRaises(ProfileConflict):
            ap.create_profile(self.store, owner(), "K",
                              idempotency_key="k-2")

    def test_22_foreign_tenant_blocked(self):
        p = self.mk()  # t1
        self.assertIsNone(
            ap.get_profile(self.store, owner("u2", "t2"),
                           p["apiProfileId"]))
        self.assertEqual(ap.list_profiles(self.store, owner("u2", "t2")),
                         [])

    def test_enumeration_neutral(self):
        for fake in ("aprof_deadbeefdeadbeef", "aprof_123", ""):
            self.assertIsNone(
                ap.get_profile(self.store, owner(), fake))


class TestSelection(Base):
    def setUp(self):
        self.store = InMemoryApiProfileStore()

    def active(self, name="P", actor=None, **kw):
        p = ap.create_profile(self.store, actor or owner(), name, **kw)
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        return self.store.get_profile(p["apiProfileId"])

    def test_header_constant(self):
        self.assertEqual(ap.SELECTION_HEADER, "X-Api-Profile")

    def test_23_own_active_resolves(self):
        p = self.active()
        got, info = ap.resolve_selection(self.store, owner(),
                                         p["apiProfileId"])
        self.assertEqual(got["apiProfileId"], p["apiProfileId"])
        self.assertEqual(info["outcome"], "resolved")

    def test_24_foreign_denied_neutral(self):
        p = self.active()
        got, info = ap.resolve_selection(self.store, owner("u2"),
                                         p["apiProfileId"])
        self.assertIsNone(got)
        self.assertEqual(info["outcome"], "denied")

    def test_25_unknown_denied_neutral(self):
        got, info = ap.resolve_selection(self.store, owner(),
                                         "aprof_missing")
        self.assertIsNone(got)

    def test_26_disabled_denied_neutral(self):
        p = self.active()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "DISABLED", reason="x")
        got, _ = ap.resolve_selection(self.store, owner(),
                                      p["apiProfileId"])
        self.assertIsNone(got)

    def test_27_zero_no_default(self):
        got, info = ap.resolve_selection(self.store, owner())
        self.assertIsNone(got)
        self.assertEqual(info["outcome"], "none")

    def test_28_one_default(self):
        p = self.active()
        got, info = ap.resolve_selection(self.store, owner())
        self.assertEqual(got["apiProfileId"], p["apiProfileId"])
        self.assertEqual(info["type"], "default")

    def test_29_many_require_explicit(self):
        self.active("A")
        self.active("B")
        got, info = ap.resolve_selection(self.store, owner())
        self.assertIsNone(got)
        self.assertEqual(info["outcome"], "explicit-required")

    def test_30_pending_not_default(self):
        ap.create_profile(self.store, owner(), "Pend")
        self.assertIsNone(ap.resolve_selection(self.store, owner())[0])

    def test_31_selection_grants_nothing(self):
        p = self.active()
        got, info = ap.resolve_selection(self.store, owner(),
                                         p["apiProfileId"])
        self.assertNotIn("entitlements", info)
        self.assertNotIn("authorized", info)

    def test_cross_tenant_selection_neutral(self):
        p = self.active()  # owner u1/t1
        # same user id, other tenant context must not resolve
        got, _ = ap.resolve_selection(
            self.store, {"userId": "u1", "tenantId": "t2", "groups": []},
            p["apiProfileId"])
        self.assertIsNone(got)

    def test_32_match_allows(self):
        p = self.active()
        self.assertTrue(
            ap.credential_profile_match(p, p["apiProfileId"]))

    def test_33_mismatch_blocks(self):
        p = self.active()
        self.assertFalse(
            ap.credential_profile_match(p, "aprof_other"))
        self.assertFalse(ap.credential_profile_match(None, "x"))
        self.assertFalse(ap.credential_profile_match(p, None))


class TestP9Integration(Base):
    def test_credential_bound_to_service_profile(self):
        from agents.ecosystem.credentials import (
            InMemoryCredentialStore,
            InMemoryProfileStore,
            VerifyOutcome,
            issue_credential,
            verify_api_credential,
        )

        p = self.mk()
        ap.transition_status(self.store, admin(), p["apiProfileId"],
                             "ACTIVE")
        creds = InMemoryCredentialStore()
        profiles = InMemoryProfileStore(
            {p["apiProfileId"]: self.store.get_profile(
                p["apiProfileId"])})
        issued = issue_credential(
            creds, profiles, p["apiProfileId"], expires_at=_ts(30),
            actor_role="admin", actor_id="a1")

        class Ents:
            def find_entitlements(self, user_id):
                return [{"userId": "u1", "tenantId": "t1",
                         "agentId": "reference_agent",
                         "entitlementId": "e1"}]

        decision = verify_api_credential(
            issued["secret"], "reference_agent", creds, profiles, Ents(),
            catalog={"reference_agent": "ACTIVE"}, request_id="r1")
        self.assertEqual(decision.outcome, VerifyOutcome.AUTHORIZED)
        self.assertEqual(decision.context["apiProfileId"],
                         p["apiProfileId"])

    def test_dynamodb_adapter_constructs_lazily(self):
        self.assertIsNotNone(DynamoDBApiProfileStore(table_name="t"))


if __name__ == "__main__":
    unittest.main()
