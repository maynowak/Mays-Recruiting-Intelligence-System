"""Gate SECURITY-FIX-02: Cognito group-claim normalization.

Root cause: the API Gateway JWT authorizer delivers `cognito:groups`
stringified ("[admins]"), which the previous split(",") turned into
["[admins]"]. Every role check failed, so a Product Admin was silently
treated as a plain owner and a Staff user got owner rights (including
the prohibited profile create). Proof: P19 controlled A/B, Gate 01.

These tests pin the two invariants:
  1. all real-world claim shapes normalize to the SEMANTIC group names
  2. an unknown / malformed claim yields NO privilege at all
"""
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (str(REPO_ROOT / "lambda"), str(REPO_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

os.environ.setdefault("API_PROFILES_TABLE", "mays-ris-dev-api-profiles")
os.environ.setdefault("AWS_REGION", "eu-central-1")

import handler as h  # noqa: E402
from agents.ecosystem import api_profiles as ap  # noqa: E402


def _ctx(groups_claim):
    """Build an API-GW shaped event and return the extracted context."""
    claims = {"sub": "u", "custom:tenant_id": "t"}
    if groups_claim is not _ABSENT:
        claims["cognito:groups"] = groups_claim
    return h._extract_user_context(
        {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}})


class _Absent:
    pass


_ABSENT = _Absent()


def _actor(groups, user_id="u"):
    return {"userId": user_id, "tenantId": "t", "groups": groups}


class TestClaimForms(unittest.TestCase):
    """The ten required real-world shapes -> semantic group names."""

    def test_01_none(self):
        self.assertEqual(h._normalize_groups(None), [])

    def test_02_empty_list(self):
        self.assertEqual(h._normalize_groups([]), [])

    def test_03_native_admins(self):
        self.assertEqual(h._normalize_groups(["admins"]), ["admins"])

    def test_04_native_staff(self):
        self.assertEqual(h._normalize_groups(["Staff"]), ["Staff"])

    def test_05_stringified_admins(self):
        self.assertEqual(h._normalize_groups("[admins]"), ["admins"])

    def test_06_stringified_staff(self):
        self.assertEqual(h._normalize_groups("[Staff]"), ["Staff"])

    def test_07_stringified_multiple(self):
        self.assertEqual(h._normalize_groups('["admins", "Staff"]'),
                         ["admins", "Staff"])

    def test_08_comma_separated_multiple(self):
        self.assertEqual(h._normalize_groups("admins,Staff"),
                         ["admins", "Staff"])

    def test_09_empty_string(self):
        self.assertEqual(h._normalize_groups(""), [])
        self.assertEqual(h._normalize_groups("   "), [])

    def test_10_unexpected_type(self):
        for raw in (42, True, 3.5, {"a": 1}, object()):
            self.assertEqual(h._normalize_groups(raw), [], raw)

    def test_11_brackets_are_never_kept(self):
        for raw in ("[admins]", "[Staff]", '["admins"]', "[admins, Staff]"):
            for name in h._normalize_groups(raw):
                self.assertNotIn("[", name)
                self.assertNotIn("]", name)

    def test_12_duplicates_collapsed(self):
        self.assertEqual(h._normalize_groups('["admins","admins"]'),
                         ["admins"])

    def test_13_trailing_comma_ignored(self):
        self.assertEqual(h._normalize_groups("admins,"), ["admins"])

    def test_14_claim_absent_entirely(self):
        self.assertEqual(_ctx(_ABSENT)["groups"], [])


class TestNoPermissiveFallback(unittest.TestCase):
    """Security invariant: bad input yields LESS privilege, never more."""

    MALFORMED = [
        ("[not json", "unterminated"),
        ("[", "single bracket"),
        ("[[\"admins\"]]", "nested"),
        ("[<script>]", "illegal chars"),
        ("a] , admins", "stray bracket plus privileged token"),
        ("admin s", "inner space"),
        ("\x00admins", "control char"),
        (["admins", 7], "non-string entry"),
        ({"a": "admins"}, "dict"),
        (42, "number"),
    ]

    def test_20_malformed_never_privileged(self):
        for raw, label in self.MALFORMED:
            groups = h._normalize_groups(raw)
            actor = _actor(groups)
            self.assertFalse(ap._is_admin(actor), label)
            self.assertFalse(ap._is_staff(actor), label)

    def test_21_malformed_with_privileged_token_rejected_entirely(self):
        # Partial parsing would keep "admins" -> must reject the whole claim.
        self.assertEqual(h._normalize_groups("a] , admins"), [])
        self.assertEqual(h._normalize_groups("ok, admins"), ["ok", "admins"])

    def test_22_deprecated_admin_alias_not_promoted(self):
        groups = h._normalize_groups("Admin")
        actor = _actor(groups)
        self.assertFalse(ap._is_admin(actor))
        self.assertFalse(ap._is_staff(actor))

    def test_23_unknown_group_is_inert(self):
        groups = h._normalize_groups(["irgendeine-gruppe"])
        actor = _actor(groups)
        self.assertFalse(ap._is_admin(actor))
        self.assertFalse(ap._is_staff(actor))


class TestRoleSeparation(unittest.TestCase):
    """Owner / Product Admin / Staff stay strictly separated."""

    def test_30_owner_has_no_roles(self):
        ctx = _ctx(_ABSENT)
        self.assertEqual(ctx["groups"], [])
        actor = _actor(ctx["groups"])
        self.assertFalse(ap._is_admin(actor))
        self.assertFalse(ap._is_staff(actor))
        self.assertEqual(h._cred_actor(ctx)["role"], "owner")

    def test_31_product_admin_recognized_from_stringified(self):
        ctx = _ctx("[admins]")
        self.assertEqual(ctx["groups"], ["admins"])
        self.assertTrue(ap._is_admin(_actor(ctx["groups"])))
        self.assertFalse(ap._is_staff(_actor(ctx["groups"])))
        self.assertEqual(h._cred_actor(ctx)["role"], "admin")

    def test_32_product_admin_recognized_from_native(self):
        ctx = _ctx(["admins"])
        self.assertTrue(ap._is_admin(_actor(ctx["groups"])))

    def test_33_staff_recognized_from_stringified(self):
        ctx = _ctx("[Staff]")
        self.assertEqual(ctx["groups"], ["Staff"])
        self.assertTrue(ap._is_staff(_actor(ctx["groups"])))
        self.assertFalse(ap._is_admin(_actor(ctx["groups"])))
        self.assertEqual(h._cred_actor(ctx)["role"], "staff")

    def test_34_staff_never_escalates_to_admin(self):
        for raw in ("[Staff]", ["Staff"], "Staff"):
            groups = h._normalize_groups(raw)
            actor = _actor(groups)
            self.assertFalse(ap._is_admin(actor), raw)
            self.assertTrue(ap._is_staff(actor), raw)

    def test_35_credential_role_mapping_unchanged_contract(self):
        self.assertEqual(h._cred_actor({"groups": []})["role"], "owner")
        self.assertEqual(h._cred_actor({"groups": ["admins"]})["role"],
                         "admin")
        self.assertEqual(h._cred_actor({"groups": ["Staff"]})["role"],
                         "staff")

    def test_36_no_aws_context_role(self):
        """mayaws is a deployment context, never a RIS product role."""
        for raw in ("[mayaws]", ["mayaws"], "mayaws"):
            groups = h._normalize_groups(raw)
            actor = _actor(groups)
            self.assertFalse(ap._is_admin(actor))
            self.assertFalse(ap._is_staff(actor))
            self.assertEqual(h._cred_actor({"groups": groups})["role"],
                             "owner")


class TestStaffDomainContract(unittest.TestCase):
    """Domain level: the previously proven permissive path is closed."""

    def _store(self):
        return ap.InMemoryApiProfileStore()

    def _staff(self):
        return _actor(h._normalize_groups("[Staff]"), user_id="staff-u")

    def _owner(self):
        return _actor(h._normalize_groups(None), user_id="owner-u")

    def test_40_staff_cannot_create_profile(self):
        store = self._store()
        with self.assertRaises(ap.UnauthorizedProfileAction):
            ap.create_profile(store, self._staff(), "staff-should-fail")
        self.assertEqual(store.items, {})

    def test_41_staff_cannot_create_via_native_list_either(self):
        store = self._store()
        actor = _actor(h._normalize_groups(["Staff"]), user_id="staff-u")
        with self.assertRaises(ap.UnauthorizedProfileAction):
            ap.create_profile(store, actor, "still-should-fail")
        self.assertEqual(store.items, {})

    def test_42_owner_can_still_create(self):
        store = self._store()
        item = ap.create_profile(store, self._owner(), "owner-ok")
        self.assertEqual(item["status"], ap.STATUS_PENDING)
        self.assertEqual(len(store.items), 1)

    def test_43_admin_can_still_create_for_target_user(self):
        store = self._store()
        actor = _actor(h._normalize_groups("[admins]"), user_id="admin-u")
        item = ap.create_profile(store, actor, "for-other", target_owner="other")
        self.assertEqual(item["ownerUserId"], "other")
        self.assertEqual(item["createdBy"]["role"], "admin")

    def test_44_staff_support_read_still_possible(self):
        """The fix must not remove the allowed support function."""
        store = self._store()
        owner_item = ap.create_profile(store, self._owner(), "owned")
        staff = self._staff()
        # Without reason: refused.
        self.assertIsNone(
            ap.get_profile(store, staff, owner_item["apiProfileId"]))
        # With reason: allowed (audited support case).
        got = ap.get_profile(store, staff, owner_item["apiProfileId"],
                            reason="support-case")
        self.assertIsNotNone(got)
        self.assertEqual(got["apiProfileId"], owner_item["apiProfileId"])

    def test_45_staff_cannot_activate_pending(self):
        store = self._store()
        item = ap.create_profile(store, self._owner(), "pending-for-admin")
        with self.assertRaises(ap.UnauthorizedProfileAction):
            ap.transition_status(store, self._staff(), item["apiProfileId"],
                                 ap.STATUS_ACTIVE)
        self.assertEqual(store.get_profile(item["apiProfileId"])["status"],
                         ap.STATUS_PENDING)

    def test_46_admin_can_activate_pending_after_fix(self):
        store = self._store()
        item = ap.create_profile(store, self._owner(), "pending-for-admin")
        admin = _actor(h._normalize_groups("[admins]"), user_id="admin-u")
        out = ap.transition_status(store, admin, item["apiProfileId"],
                                   ap.STATUS_ACTIVE)
        self.assertEqual(out["status"], ap.STATUS_ACTIVE)


if __name__ == "__main__":
    unittest.main()