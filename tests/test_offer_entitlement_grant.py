"""Tests Gate 11: Offer CRUD + Offer -> Entitlement grant.

No prices/billing anywhere (model has no such fields). No real AWS:
in-memory stores + fakes only.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem import offers as off  # noqa: E402
from agents.ecosystem.offers import (  # noqa: E402
    DynamoDBEntitlementStore,
    DynamoDBOfferStore,
    EntitlementNotFound,
    GrantConflict,
    GrantDenied,
    InMemoryEntitlementStore,
    InMemoryOfferStore,
    OfferConflict,
    UnauthorizedOfferAction,
)
from agents.ecosystem.worker_authorization import (  # noqa: E402
    check_worker_entitlement,
)


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def admin(uid="a1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": ["admins"]}


def staff(uid="s1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": ["Staff"]}


def user(uid="u1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": []}


CATALOG = {"agent-a": "ACTIVE", "agent-b": "ACTIVE", "agent-c": "ACTIVE",
           "old-agent": "INACTIVE", "ret-agent": "RETIRED"}


class Resolver:
    """P8-compatible entitlement source over the grant store."""

    def __init__(self, store):
        self.store = store

    def find_entitlements(self, user_id):
        return self.store.find_by_user(user_id)


class Base(unittest.TestCase):
    def setUp(self):
        self.offers = InMemoryOfferStore()
        self.ents = InMemoryEntitlementStore()
        self.profiles = ap.InMemoryApiProfileStore()
        self._from = _ts(-1)
        self._until = _ts(30)

    def mk_offer(self, name="Pack", agents=None, **kw):
        params = {"offer_store": self.offers, "actor": admin(),
                  "name": name,
                  "agent_ids": agents or ["agent-a", "agent-b"],
                  "catalog": CATALOG}
        params.update(kw)
        return off.create_offer(**params)

    def mk_profile(self, name="P", owner="u1", tenant="t1"):
        p = ap.create_profile(self.profiles, user(owner, tenant), name)
        ap.transition_status(self.profiles, admin(tenant=tenant),
                             p["apiProfileId"], "ACTIVE")
        return self.profiles.get_profile(p["apiProfileId"])

    def grant(self, offer_id, target="u1", tenant="t1", scope="USER",
              **kw):
        # Fixed windows per test-case (fresh timestamps would break
        # duplicate identity across calls).
        params = {"offer_store": self.offers,
                  "entitlement_store": self.ents,
                  "profile_store": self.profiles, "catalog": CATALOG,
                  "actor": admin(), "offer_id": offer_id,
                  "target_user_id": target, "tenant_id": tenant,
                  "scope": scope, "reason": "test"}
        params.setdefault("valid_from", self._from)
        params.setdefault("valid_until", self._until)
        params.update(kw)
        return off.grant_offer(**params)


class TestOfferCRUD(Base):
    def test_01_admin_creates_active(self):
        o = self.mk_offer()
        self.assertEqual(o["status"], "ACTIVE")
        self.assertEqual(o["agentIds"], ["agent-a", "agent-b"])
        self.assertTrue(o["offerId"].startswith("off_"))
        for forbidden in ("price", "currency", "billing", "payment",
                          "subscription"):
            self.assertNotIn(forbidden, o)

    def test_02_staff_create_denied(self):
        with self.assertRaises(UnauthorizedOfferAction):
            off.create_offer(self.offers, staff(), "X", ["agent-a"],
                             CATALOG)

    def test_03_user_create_denied(self):
        with self.assertRaises(UnauthorizedOfferAction):
            off.create_offer(self.offers, user(), "X", ["agent-a"],
                             CATALOG)

    def test_04_name_uniqueness(self):
        self.mk_offer("Pack")
        with self.assertRaises(OfferConflict):
            self.mk_offer("pack")

    def test_05_unknown_agent_denied(self):
        with self.assertRaises(GrantDenied):
            self.mk_offer(agents=["agent-a", "ghost-agent"])
        self.assertEqual(self.offers.list_offers(), [])

    def test_06_inactive_agent_denied(self):
        with self.assertRaises(GrantDenied):
            self.mk_offer(agents=["old-agent"])

    def test_07_deprecated_denied(self):
        with self.assertRaises(GrantDenied):
            off.create_offer(self.offers, admin(), "D", ["agent-a"],
                             {"agent-a": "DEPRECATED"})

    def test_08_retired_denied(self):
        with self.assertRaises(GrantDenied):
            self.mk_offer(agents=["ret-agent"])

    def test_09_unknown_status_denied(self):
        with self.assertRaises(GrantDenied):
            off.create_offer(self.offers, admin(), "D", ["agent-a"],
                             {"agent-a": "NOPE"})

    def test_10_admin_updates(self):
        o = self.mk_offer()
        out = off.update_offer(self.offers, admin(), o["offerId"],
                               CATALOG, name="Pack2",
                               description="d",
                               agent_ids=["agent-a", "agent-c"])
        self.assertEqual(out["name"], "Pack2")
        self.assertEqual(out["agentIds"], ["agent-a", "agent-c"])
        with self.assertRaises(ValueError):
            off.update_offer(self.offers, admin(), o["offerId"],
                             CATALOG, offerId="x")

    def test_11_deactivate(self):
        o = self.mk_offer()
        out = off.set_offer_status(self.offers, admin(), o["offerId"],
                                   "INACTIVE", reason="pause")
        self.assertEqual(out["status"], "INACTIVE")

    def test_12_inactive_blocks_grant(self):
        o = self.mk_offer()
        off.set_offer_status(self.offers, admin(), o["offerId"],
                             "INACTIVE", reason="pause")
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"])
        self.assertEqual(self.ents.find_by_user("u1"), [])

    def test_13_reactivate_allows_grant(self):
        o = self.mk_offer()
        off.set_offer_status(self.offers, admin(), o["offerId"],
                             "INACTIVE", reason="x")
        off.set_offer_status(self.offers, admin(), o["offerId"],
                             "ACTIVE", reason="resume")
        out = self.grant(o["offerId"])
        self.assertEqual(len(out["entitlementIds"]), 2)


class TestGrant(Base):
    def test_14_active_grant_ok(self):
        o = self.mk_offer()
        out = self.grant(o["offerId"])
        self.assertEqual(len(out["entitlementIds"]), 2)
        self.assertFalse(out["reused"])

    def test_15_user_wide_shape(self):
        o = self.mk_offer(agents=["agent-a"])
        out = self.grant(o["offerId"])
        row = self.ents.get_entitlement(out["entitlementIds"][0])
        self.assertEqual(row["userId"], "u1")
        self.assertEqual(row["tenantId"], "t1")
        self.assertEqual(row["agentId"], "agent-a")
        self.assertNotIn("apiProfileId", row)
        self.assertEqual(row["offerId"], o["offerId"])
        self.assertEqual(row["grantId"], out["grantId"])
        self.assertIsInstance(row["expiresAt"], int)

    def test_16_profile_bound_shape(self):
        p = self.mk_profile()
        o = self.mk_offer(agents=["agent-a"])
        out = self.grant(o["offerId"], scope="APIPROFILE",
                         api_profile_id=p["apiProfileId"])
        row = self.ents.get_entitlement(out["entitlementIds"][0])
        self.assertEqual(row["apiProfileId"], p["apiProfileId"])
        self.assertEqual(row["userId"], "u1")

    def test_17_foreign_profile_denied(self):
        other = ap.create_profile(self.profiles, user("u2"), "Other")
        ap.transition_status(self.profiles, admin(),
                             other["apiProfileId"], "ACTIVE")
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"], target="u1", scope="APIPROFILE",
                       api_profile_id=other["apiProfileId"])

    def test_18_wrong_tenant_denied(self):
        p = self.mk_profile()
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"], target="u1", tenant="tX",
                       scope="APIPROFILE",
                       api_profile_id=p["apiProfileId"])

    def test_19_pending_profile_denied(self):
        p = ap.create_profile(self.profiles, user(), "Pend")
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"], scope="APIPROFILE",
                       api_profile_id=p["apiProfileId"])

    def test_20_revoked_profile_denied(self):
        p = self.mk_profile()
        ap.transition_status(self.profiles, admin(), p["apiProfileId"],
                             "REVOKED", reason="end")
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"], scope="APIPROFILE",
                       api_profile_id=p["apiProfileId"])

    def test_21_bad_window_denied(self):
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"], valid_from=_ts(5),
                       valid_until=_ts(1))

    def test_22_missing_window_denied(self):
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"], valid_from=None, valid_until=None)

    def test_23_one_bad_agent_no_partial(self):
        o = self.mk_offer()
        live = dict(CATALOG)
        live["agent-b"] = "INACTIVE"
        before = len(self.ents.find_by_user("u1"))
        with self.assertRaises(GrantDenied):
            off.grant_offer(
                self.offers, self.ents, self.profiles, live,
                admin(), o["offerId"], "u1", "t1", "USER",
                valid_from=_ts(-1), valid_until=_ts(30),
                reason="test")
        self.assertEqual(len(self.ents.find_by_user("u1")), before)

    def test_24_duplicate_reuses(self):
        o = self.mk_offer(agents=["agent-a"])
        first = self.grant(o["offerId"])
        second = self.grant(o["offerId"])
        self.assertEqual(first["entitlementIds"],
                         second["entitlementIds"])
        self.assertEqual(len(self.ents.find_by_user("u1")), 1)

    def test_25_idempotency_same_key(self):
        o = self.mk_offer(agents=["agent-a"])
        first = self.grant(o["offerId"], idempotency_key="g-1")
        second = self.grant(o["offerId"], idempotency_key="g-1")
        self.assertEqual(first["entitlementIds"],
                         second["entitlementIds"])

    def test_26_idempotency_mismatch_conflicts(self):
        o = self.mk_offer(agents=["agent-a"])
        self.grant(o["offerId"], idempotency_key="g-1")
        with self.assertRaises(GrantConflict):
            self.grant(o["offerId"], valid_until=_ts(60),
                       idempotency_key="g-1")

    def test_27_overlap_conflicts_no_merge(self):
        o = self.mk_offer(agents=["agent-a"])
        self.grant(o["offerId"])
        with self.assertRaises(GrantConflict):
            self.grant(o["offerId"], valid_from=_ts(10),
                       valid_until=_ts(40))
        self.assertEqual(len(self.ents.find_by_user("u1")), 1)

    def test_28_offer_edit_keeps_existing(self):
        o = self.mk_offer(agents=["agent-a", "agent-b"])
        self.grant(o["offerId"])
        off.update_offer(self.offers, admin(), o["offerId"], CATALOG,
                         agent_ids=["agent-a", "agent-c"])
        rows = self.ents.find_by_user("u1")
        self.assertEqual({r["agentId"] for r in rows},
                         {"agent-a", "agent-b"})

    def test_29_inactive_keeps_existing(self):
        o = self.mk_offer(agents=["agent-a"])
        self.grant(o["offerId"])
        off.set_offer_status(self.offers, admin(), o["offerId"],
                             "INACTIVE", reason="x")
        rows = self.ents.find_by_user("u1")
        self.assertEqual(len(rows), 1)

    def test_user_scope_rejects_profile(self):
        o = self.mk_offer(agents=["agent-a"])
        p = self.mk_profile()
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"], scope="USER",
                       api_profile_id=p["apiProfileId"])

    def test_profile_scope_needs_profile(self):
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(GrantDenied):
            self.grant(o["offerId"], scope="APIPROFILE")

    def test_staff_grant_denied(self):
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(UnauthorizedOfferAction):
            off.grant_offer(
                self.offers, self.ents, self.profiles, CATALOG,
                staff(), o["offerId"], "u1", "t1", "USER",
                valid_from=_ts(-1), valid_until=_ts(30), reason="x")

    def test_37_crosstenant_grant_denied(self):
        o = self.mk_offer(agents=["agent-a"])
        with self.assertRaises(GrantDenied):
            off.grant_offer(
                self.offers, self.ents, self.profiles, CATALOG,
                admin("a9", "tX"), o["offerId"], "u1", "t1", "USER",
                valid_from=_ts(-1), valid_until=_ts(30), reason=None)

    def test_withdraw(self):
        o = self.mk_offer(agents=["agent-a"])
        out = self.grant(o["offerId"])
        eid = out["entitlementIds"][0]
        off.withdraw_entitlement(self.ents, admin(), eid, reason="abuse")
        self.assertIsNone(self.ents.get_entitlement(eid))
        with self.assertRaises(EntitlementNotFound):
            off.withdraw_entitlement(self.ents, admin(), eid,
                                     reason="x")


class TestP8Integration(Base):
    def _check(self, user="u1", tenant="t1", agent="reference_agent",
               profile=None):
        return check_worker_entitlement(
            user, tenant, agent, "w-1", resolver=Resolver(self.ents),
            api_profile_id=profile)

    def test_30_user_wide_recognized(self):
        o = self.mk_offer(agents=["agent-a"])
        self.grant(o["offerId"])
        # P8 view over granted rows (agent-a granted above)
        d = self._check(agent="agent-a")
        self.assertTrue(d.authorized)

    def test_31_profile_bound_recognized(self):
        p = self.mk_profile()
        o = self.mk_offer(agents=["agent-a"])
        self.grant(o["offerId"], scope="APIPROFILE",
                   api_profile_id=p["apiProfileId"])
        self.assertTrue(
            self._check(agent="agent-a",
                        profile=p["apiProfileId"]).authorized)
        denied = self._check(agent="agent-a")
        self.assertFalse(denied.authorized)
        # Profile-bound-only row, no context asserted: mismatch
        # (still DENIED, no oracle beyond the agent scope).
        self.assertEqual(denied.reason, "profile-mismatch")

    def test_32_expired_window_denied(self):
        o = self.mk_offer(agents=["agent-a"])
        self.grant(o["offerId"], valid_from=_ts(-30),
                   valid_until=_ts(-1))
        self.assertFalse(self._check(agent="agent-a").authorized)

    def test_33_future_window_denied(self):
        o = self.mk_offer(agents=["agent-a"])
        self.grant(o["offerId"], valid_from=_ts(1),
                   valid_until=_ts(30))
        self.assertFalse(self._check(agent="agent-a").authorized)


class TestP7P10(Base):
    def test_34_inactive_agent_grant_denied(self):
        with self.assertRaises(GrantDenied):
            self.mk_offer(agents=["agent-a", "old-agent"])

    def test_35_unknown_agent_grant_denied(self):
        with self.assertRaises(GrantDenied):
            self.mk_offer(agents=["ghost"])

    def test_36_owner_unchanged(self):
        p = self.mk_profile()
        o = self.mk_offer(agents=["agent-a"])
        self.grant(o["offerId"], scope="APIPROFILE",
                   api_profile_id=p["apiProfileId"])
        after = self.profiles.get_profile(p["apiProfileId"])
        self.assertEqual(after["ownerUserId"], "u1")
        self.assertEqual(after["tenantId"], "t1")

    def test_credential_offer_confusion(self):
        with self.assertRaises(GrantDenied):
            off.create_offer(self.offers, admin(), "X",
                             {"credentialId": "cred_x"}, CATALOG)

    def test_entitlement_row_as_offer_confusion(self):
        with self.assertRaises((GrantDenied, OfferConflict, ValueError,
                                AttributeError, TypeError)):
            off.grant_offer(
                self.offers, self.ents, self.profiles, CATALOG,
                admin(), "no-such-offer", "u1", "t1", "USER",
                valid_from=_ts(-1), valid_until=_ts(30), reason="x")

    def test_dynamodb_adapters_construct_lazily(self):
        self.assertIsNotNone(DynamoDBOfferStore(table_name="t"))
        self.assertIsNotNone(DynamoDBEntitlementStore(table_name="t"))


if __name__ == "__main__":
    unittest.main()
