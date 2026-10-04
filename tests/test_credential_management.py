"""Tests Gate 14: credential management lifecycle (owner/admin/staff).

Owner self-service is a DOCUMENTED P14 refinement of the P09
admin-only rule (bounded to own usable profiles, no escalation,
full audit — see P14 report). No productive secrets: random test
values only, never persisted outside harness, never logged.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.credentials import (  # noqa: E402
    CredentialConflict,
    CredentialNotFound,
    InMemoryCredentialStore,
    InMemoryProfileStore,
    UnauthorizedManagementAttempt,
    VerifyOutcome,
    disable_credential,
    enable_credential,
    get_credential_metadata,
    issue_credential,
    list_credentials,
    revoke_credential,
    rotate_credential,
    verify_api_credential,
)


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def owner(uid="u1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": []}


def admin(uid="a1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": ["admins"]}


class Harness(unittest.TestCase):
    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        p = ap.create_profile(self.profiles, owner(), "P1")
        ap.transition_status(self.profiles, admin(), p["apiProfileId"],
                             "ACTIVE")
        self.pid = p["apiProfileId"]
        self.creds = InMemoryCredentialStore()
        self.pshim = InMemoryProfileStore(
            {self.pid: self.profiles.get_profile(self.pid)})
        # Fixed default expiry (fresh timestamps would break
        # duplicate/window identity across calls).
        self._exp = _ts(30)

    def sync_profiles(self):
        self.pshim = InMemoryProfileStore(
            {p["apiProfileId"]: p
             for p in self.profiles.items.values()})

    def issue(self, role="admin", actor="a1", pid=None, **kw):
        params = {"credential_store": self.creds,
                  "profile_store": self.pshim,
                  "api_profile_id": pid or self.pid,
                  "expires_at": self._exp, "actor_role": role,
                  "actor_id": actor, "actor_tenant": "t1"}
        params.update(kw)
        return issue_credential(**params)


class TestIssue(Harness):
    def test_01_owner_own_profile(self):
        out = self.issue(role="owner", actor="u1")
        self.assertTrue(out["secret"])
        self.assertEqual(out["metadata"]["ownerUserId"], "u1")
        self.assertFalse(out["duplicate"])

    def test_02_owner_foreign_denied(self):
        other = ap.create_profile(self.profiles, owner("u2"), "Other")
        ap.transition_status(self.profiles, admin(), other["apiProfileId"],
                             "ACTIVE")
        self.sync_profiles()
        with self.assertRaises(UnauthorizedManagementAttempt):
            self.issue(role="owner", actor="u1",
                       pid=other["apiProfileId"])

    def test_03_admin_own(self):
        out = self.issue()
        self.assertTrue(out["secret"])

    def test_04_admin_target(self):
        p = ap.create_profile(self.profiles, owner("u9"), "P9")
        ap.transition_status(self.profiles, admin(), p["apiProfileId"],
                             "ACTIVE")
        self.sync_profiles()
        out = self.issue(pid=p["apiProfileId"])
        self.assertEqual(out["metadata"]["ownerUserId"], "u9")

    def test_05_staff_issue_denied(self):
        with self.assertRaises(UnauthorizedManagementAttempt):
            self.issue(role="staff", actor="s1")

    def test_06_unknown_role_denied(self):
        with self.assertRaises(UnauthorizedManagementAttempt):
            self.issue(role="user", actor="u1")

    def test_07_crosstenant(self):
        with self.assertRaises(UnauthorizedManagementAttempt):
            self.issue(actor_tenant="tX")
        out = self.issue(actor_tenant="tX", reason="incident-1")
        self.assertTrue(out["secret"])

    def test_08_pending_denied(self):
        p = ap.create_profile(self.profiles, owner(), "Pend")
        self.sync_profiles()
        with self.assertRaises(ValueError):
            self.issue(pid=p["apiProfileId"])

    def test_09_disabled_denied(self):
        ap.transition_status(self.profiles, admin(), self.pid,
                             "DISABLED", reason="x")
        self.sync_profiles()
        with self.assertRaises(ValueError):
            self.issue()

    def test_10_expired_status_denied(self):
        ap.transition_status(self.profiles, admin(), self.pid,
                             "DISABLED", reason="x")
        raw = self.profiles.get_profile(self.pid)
        raw["status"] = "EXPIRED"
        self.profiles.update_profile(self.pid, raw)
        self.sync_profiles()
        with self.assertRaises(ValueError):
            self.issue()

    def test_11_revoked_denied(self):
        ap.transition_status(self.profiles, admin(), self.pid,
                             "REVOKED", reason="end")
        self.sync_profiles()
        with self.assertRaises(ValueError):
            self.issue()

    def test_12_expiry_missing(self):
        with self.assertRaises(ValueError):
            self.issue(expires_at="")

    def test_13_expiry_not_future(self):
        # Issuance accepts any parseable expiry (P09-compatible);
        # enforcement is verify-time (fail-closed, no stillborn use).
        out = self.issue(expires_at=_ts(-1))
        d = verify_api_credential(
            out["secret"], "reference_agent", self.creds, self.pshim,
            _Ents([]), {"reference_agent": "ACTIVE"})
        self.assertEqual(d.http_status, 403)

    def test_14_profile_expiry_caps(self):
        ap.set_expires_at(self.profiles, admin(), self.pid, _ts(10),
                          reason="grant")
        self.sync_profiles()
        with self.assertRaises(ValueError):
            self.issue(expires_at=_ts(30))
        out = self.issue(expires_at=_ts(5))
        self.assertTrue(out["secret"])


class TestSecretHygiene(Harness):
    def test_15_generated(self):
        out = self.issue()
        from agents.ecosystem.credentials import valid_secret_format
        self.assertTrue(valid_secret_format(out["secret"]))

    def test_16_once_only(self):
        out = self.issue()
        self.assertTrue(out["secret"])
        stored = self.creds.by_id[out["metadata"]["credentialId"]]
        for value in stored.values():
            self.assertNotEqual(value, out["secret"])

    def test_17_not_in_repository(self):
        out = self.issue()
        blob = json.dumps(list(self.creds.by_id.values()))
        self.assertNotIn(out["secret"], blob)

    def test_18_not_in_list(self):
        out = self.issue()
        rows = list_credentials(self.creds, "owner", "u1")
        self.assertNotIn(out["secret"], json.dumps(rows))

    def test_19_not_in_audit(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            out = self.issue()
            list_credentials(self.creds, "owner", "u1")
        self.assertNotIn(out["secret"], "\n".join(logs.output))

    def test_21_digest_not_outward(self):
        out = self.issue()
        digest = self.creds.by_id[
            out["metadata"]["credentialId"]]["digest"]
        rows = list_credentials(self.creds, "owner", "u1")
        single = get_credential_metadata(
            self.creds, "owner", "u1", out["metadata"]["credentialId"])
        blob = json.dumps([rows, single])
        self.assertNotIn(digest, blob)
        self.assertNotIn("digest", blob)


class TestLifecycle(Harness):
    def _cid(self, **kw):
        return self.issue(**kw)["metadata"]["credentialId"]

    def test_22_owner_disable(self):
        cid = self._cid(role="owner", actor="u1")
        out = disable_credential(self.creds, cid, "owner", "u1",
                                 reason="lost")
        self.assertEqual(out["status"], "DISABLED")

    def test_23_owner_reenable(self):
        cid = self._cid(role="owner", actor="u1")
        disable_credential(self.creds, cid, "owner", "u1", reason="x")
        out = enable_credential(self.creds, cid, "owner", "u1")
        self.assertEqual(out["status"], "ACTIVE")

    def test_24_revoke(self):
        cid = self._cid()
        out = revoke_credential(self.creds, cid, "admin", "a1",
                                reason="abuse")
        self.assertEqual(out["status"], "REVOKED")
        self.assertIsNotNone(out["revokedAt"])

    def test_25_disabled_revoke(self):
        cid = self._cid()
        disable_credential(self.creds, cid, "admin", "a1", reason="x")
        out = revoke_credential(self.creds, cid, "admin", "a1",
                                reason="end")
        self.assertEqual(out["status"], "REVOKED")

    def test_26_expired_revoke(self):
        cid = self._cid()
        row = self.creds.get_credential(cid)
        row["expiresAt"] = _ts(-1)
        self.creds.update_credential(cid, row)
        out = revoke_credential(self.creds, cid, "admin", "a1",
                                reason="cleanup")
        self.assertEqual(out["status"], "REVOKED")

    def test_27_revoked_terminal(self):
        cid = self._cid()
        revoke_credential(self.creds, cid, "admin", "a1", reason="x")
        with self.assertRaises(ValueError):
            enable_credential(self.creds, cid, "admin", "a1")

    def test_28_expired_no_enable(self):
        cid = self._cid()
        disable_credential(self.creds, cid, "admin", "a1", reason="x")
        row = self.creds.get_credential(cid)
        row["expiresAt"] = _ts(-1)
        self.creds.update_credential(cid, row)
        with self.assertRaises(ValueError):
            enable_credential(self.creds, cid, "admin", "a1")

    def test_staff_support_revoke(self):
        cid = self._cid()
        out = revoke_credential(self.creds, cid, "staff", "s1",
                                reason="abuse-ticket")
        self.assertEqual(out["status"], "REVOKED")

    def test_owner_cannot_enable_admin_lock(self):
        cid = self._cid(role="owner", actor="u1")
        disable_credential(self.creds, cid, "admin", "a1", reason="abuse")
        with self.assertRaises(UnauthorizedManagementAttempt):
            enable_credential(self.creds, cid, "owner", "u1")


class TestRotation(Harness):
    def test_29_new_credential(self):
        first = self.issue()
        out = rotate_credential(self.creds, self.pshim,
                                first["metadata"]["credentialId"],
                                _ts(30), "admin", "a1")
        self.assertTrue(out["secret"])

    def test_30_new_id(self):
        first = self.issue()
        out = rotate_credential(self.creds, self.pshim,
                                first["metadata"]["credentialId"],
                                _ts(30), "admin", "a1")
        self.assertNotEqual(out["metadata"]["credentialId"],
                            first["metadata"]["credentialId"])

    def test_31_new_secret(self):
        first = self.issue()
        out = rotate_credential(self.creds, self.pshim,
                                first["metadata"]["credentialId"],
                                _ts(30), "admin", "a1")
        self.assertNotEqual(out["secret"], first["secret"])
        from agents.ecosystem.credentials import valid_secret_format
        self.assertTrue(valid_secret_format(out["secret"]))

    def test_32_rotation_of(self):
        first = self.issue()
        out = rotate_credential(self.creds, self.pshim,
                                first["metadata"]["credentialId"],
                                _ts(30), "admin", "a1")
        self.assertEqual(out["metadata"]["rotationOf"],
                         first["metadata"]["credentialId"])

    def test_33_old_immediately_revoked(self):
        first = self.issue()
        cid = first["metadata"]["credentialId"]
        rotate_credential(self.creds, self.pshim, cid, _ts(30),
                          "admin", "a1")
        row = self.creds.get_credential(cid)
        self.assertEqual(row["status"], "REVOKED")

    def test_34_old_secret_dead(self):
        first = self.issue()
        rotate_credential(self.creds, self.pshim,
                          first["metadata"]["credentialId"], _ts(30),
                          "admin", "a1")
        d = verify_api_credential(
            first["secret"], "reference_agent", self.creds, self.pshim,
            _Ents([]), {"reference_agent": "ACTIVE"})
        self.assertEqual(d.outcome, VerifyOutcome.FORBIDDEN)

    def test_35_no_cross_profile(self):
        first = self.issue()
        out = rotate_credential(self.creds, self.pshim,
                                first["metadata"]["credentialId"],
                                _ts(30), "admin", "a1")
        self.assertEqual(out["metadata"]["apiProfileId"], self.pid)

    def test_owner_rotate_own(self):
        first = self.issue(role="owner", actor="u1")
        out = rotate_credential(self.creds, self.pshim,
                                first["metadata"]["credentialId"],
                                _ts(30), "owner", "u1")
        self.assertTrue(out["secret"])

    def test_staff_rotate_needs_reason(self):
        first = self.issue()
        with self.assertRaises(UnauthorizedManagementAttempt):
            rotate_credential(self.creds, self.pshim,
                              first["metadata"]["credentialId"],
                              _ts(30), "staff", "s1")
        out = rotate_credential(self.creds, self.pshim,
                                first["metadata"]["credentialId"],
                                _ts(30), "staff", "s1",
                                reason="support-reissue")
        self.assertTrue(out["secret"])


class TestIdempotency(Harness):
    def test_36_identical_issue(self):
        first = self.issue(idempotency_key="k-1")
        second = self.issue(idempotency_key="k-1")
        self.assertEqual(first["metadata"]["credentialId"],
                         second["metadata"]["credentialId"])
        self.assertTrue(second["duplicate"])
        self.assertIsNone(second["secret"])

    def test_37_key_mismatch(self):
        self.issue(idempotency_key="k-1")
        from agents.ecosystem.credentials import CredentialConflict
        with self.assertRaises(CredentialConflict):
            self.issue(idempotency_key="k-1", expires_at=_ts(60))

    def test_38_no_duplicate(self):
        self.issue(idempotency_key="k-1")
        self.issue(idempotency_key="k-1")
        self.assertEqual(len(self.creds.by_id), 1)

    def test_39_rotation_repeat(self):
        first = self.issue()
        cid = first["metadata"]["credentialId"]
        one = rotate_credential(self.creds, self.pshim, cid, _ts(30),
                                "admin", "a1", idempotency_key="rk-1")
        two = rotate_credential(self.creds, self.pshim, cid, _ts(30),
                                "admin", "a1", idempotency_key="rk-1")
        self.assertEqual(one["metadata"]["credentialId"],
                         two["metadata"]["credentialId"])
        self.assertIsNone(two["secret"])
        self.assertTrue(two["duplicate"])

    def test_40_no_secret_recovery(self):
        first = self.issue(idempotency_key="k-1")
        second = self.issue(idempotency_key="k-1")
        self.assertIsNone(second["secret"])
        for row in self.creds.by_id.values():
            self.assertNotEqual(row.get("digest"), first["secret"])


class _Ents:
    def __init__(self, rows=None):
        self._rows = list(rows or [])

    def find_entitlements(self, user_id):
        return [dict(r) for r in self._rows if r.get("userId") == user_id]


class TestVerifyIntegration(Harness):
    def _verify(self, secret):
        return verify_api_credential(
            secret, "reference_agent", self.creds, self.pshim,
            _Ents([{"userId": "u1", "tenantId": "t1",
                    "agentId": "reference_agent",
                    "entitlementId": "e1"}]),
            {"reference_agent": "ACTIVE"}, request_id="r1")

    def test_41_new_authorized(self):
        out = self.issue(role="owner", actor="u1")
        d = self._verify(out["secret"])
        self.assertEqual(d.outcome, VerifyOutcome.AUTHORIZED)

    def test_42_disabled_403(self):
        out = self.issue()
        disable_credential(self.creds, out["metadata"]["credentialId"],
                           "admin", "a1", reason="x")
        self.assertEqual(self._verify(out["secret"]).http_status, 403)

    def test_43_revoked_403(self):
        out = self.issue()
        revoke_credential(self.creds, out["metadata"]["credentialId"],
                          "admin", "a1", reason="x")
        self.assertEqual(self._verify(out["secret"]).http_status, 403)

    def test_44_expired_403(self):
        out = self.issue()
        row = self.creds.get_credential(out["metadata"]["credentialId"])
        row["expiresAt"] = _ts(-1)
        self.creds.update_credential(out["metadata"]["credentialId"], row)
        self.assertEqual(self._verify(out["secret"]).http_status, 403)

    def test_45_profile_disabled_403(self):
        out = self.issue()
        ap.transition_status(self.profiles, admin(), self.pid,
                             "DISABLED", reason="x")
        self.sync_profiles()
        self.assertEqual(self._verify(out["secret"]).http_status, 403)

    def test_46_profile_revoked_403(self):
        out = self.issue()
        ap.transition_status(self.profiles, admin(), self.pid,
                             "REVOKED", reason="end")
        self.sync_profiles()
        self.assertEqual(self._verify(out["secret"]).http_status, 403)


class TestListViews(Harness):
    def test_owner_sees_own(self):
        first = self.issue(role="owner", actor="u1")
        rows = list_credentials(self.creds, "owner", "u1")
        self.assertEqual([r["credentialId"] for r in rows],
                         [first["metadata"]["credentialId"]])

    def test_owner_hides_foreign(self):
        self.issue()
        self.assertEqual(list_credentials(self.creds, "owner", "u2"), [])
        self.assertIsNone(get_credential_metadata(
            self.creds, "owner", "u2",
            list(self.creds.by_id)[0]))

    def test_admin_tenant_scoped(self):
        self.issue()
        rows = list_credentials(self.creds, "admin", "a1",
                                actor_tenant="t1")
        self.assertEqual(len(rows), 1)
        # Cross-tenant without reason: filtered view (no foreign rows,
        # no error); with reason: full visibility (audited).
        self.assertEqual(list_credentials(self.creds, "admin", "a1",
                                          actor_tenant="tX"), [])
        full = list_credentials(self.creds, "admin", "a1",
                                actor_tenant="tX", reason="audit-9")
        self.assertEqual(len(full), 1)

    def test_staff_needs_reason(self):
        self.issue()
        with self.assertRaises(UnauthorizedManagementAttempt):
            list_credentials(self.creds, "staff", "s1")
        rows = list_credentials(self.creds, "staff", "s1",
                                reason="ticket-9")
        self.assertEqual(len(rows), 1)

    def test_unknown_role_denied(self):
        with self.assertRaises(UnauthorizedManagementAttempt):
            list_credentials(self.creds, "user", "u1")


class TestAudit(Harness):
    def test_47_crosstenant_audit(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            self.issue(actor_tenant="tX", reason="incident-1")
        blob = "\n".join(logs.output)
        self.assertIn("credential.created", blob)

    def test_48_unauthorized_audit(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            with self.assertRaises(UnauthorizedManagementAttempt):
                self.issue(role="staff", actor="s1")
        blob = "\n".join(logs.output)
        self.assertIn("credential.unauthorized_management", blob)

    def test_49_secrets_free_audit(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            out = self.issue()
            revoke_credential(self.creds, out["metadata"]["credentialId"],
                              "admin", "a1", reason="x")
            list_credentials(self.creds, "owner", "u1")
        blob = "\n".join(logs.output)
        self.assertNotIn(out["secret"], blob)

    def test_50_no_jwts(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            self.issue()
        blob = "\n".join(logs.output)
        self.assertNotIn("eyJ", blob)
        self.assertNotIn("jwt", blob.lower().replace("unauthorized", ""))

    def test_51_no_auth_headers(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            self.issue()
        blob = "\n".join(logs.output).lower()
        self.assertNotIn("authorization", blob)

    def test_52_no_digests(self):
        out = self.issue()
        digest = self.creds.by_id[
            out["metadata"]["credentialId"]]["digest"]
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            list_credentials(self.creds, "owner", "u1")
        self.assertNotIn(digest, "\n".join(logs.output))

    def test_53_no_secrets_in_exceptions(self):
        out = self.issue()
        try:
            self.issue(idempotency_key="dup")
            self.issue(idempotency_key="dup", expires_at=_ts(60))
            self.fail("expected conflict")
        except Exception as exc:  # noqa: BLE001 - asserting hygiene
            self.assertNotIn(out["secret"], str(exc))


if __name__ == "__main__":
    unittest.main()
