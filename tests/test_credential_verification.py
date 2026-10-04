"""Tests Gate 09: opaque bearer credential verification.

No productive secrets: all secrets are random test values, never
persisted outside the in-memory harness, never logged (asserted).
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.credentials import (  # noqa: E402
    CredentialNotFound,
    CredentialStoreUnavailable,
    DynamoDBCredentialStore,
    DynamoDBProfileStore,
    InMemoryCredentialStore,
    InMemoryProfileStore,
    UnauthorizedManagementAttempt,
    VerifyOutcome,
    digest_secret,
    disable_credential,
    enable_credential,
    generate_secret,
    issue_credential,
    revoke_credential,
    rotate_credential,
    valid_secret_format,
    verify_api_credential,
)


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _profile(pid="prof-1", status="ACTIVE", owner="u1", tenant="t1",
             expires=None, client="matcher-a"):
    # tenantId is REQUIRED persisted profile context (isolation rule;
    # P09 clarification of the P02 object contract).
    return {"apiProfileId": pid, "name": "P", "description": "d",
            "ownerUserId": owner, "tenantId": tenant, "clientRef": client,
            "status": status,
            "createdAt": _ts(-9), "updatedAt": _ts(-9),
            "expiresAt": expires, "createdBy": {"actor": "a", "role": "admin"},
            "updatedBy": {"actor": "a", "role": "admin"}}


class _Entitlements:
    def __init__(self, rows=None, fail=None):
        self._rows = list(rows or [])
        self.fail = fail

    def revoke_all(self):
        self._rows = []

    def find_entitlements(self, user_id):
        if self.fail is not None:
            raise self.fail
        return [dict(r) for r in self._rows if r.get("userId") == user_id]


def _ent(user="u1", tenant="t1", agent="reference_agent", eid="e1", **kw):
    row = {"userId": user, "tenantId": tenant, "agentId": agent,
           "entitlementId": eid}
    row.update(kw)
    return row


CATALOG = {"reference_agent": "ACTIVE", "old-agent": "INACTIVE"}


class Harness(unittest.TestCase):
    def setUp(self):
        self.creds = InMemoryCredentialStore()
        self.profiles = InMemoryProfileStore({"prof-1": _profile()})
        self.ents = _Entitlements([_ent()])

    def issue(self, pid="prof-1", **kw):
        params = {"credential_store": self.creds,
                  "profile_store": self.profiles,
                  "api_profile_id": pid, "expires_at": _ts(30),
                  "actor_role": "admin", "actor_id": "admin-1"}
        params.update(kw)
        return issue_credential(**params)

    def verify(self, secret, agent="reference_agent", **kw):
        params = {"bearer": secret, "agent_id": agent,
                  "credential_store": self.creds,
                  "profile_store": self.profiles,
                  "entitlement_resolver": self.ents,
                  "catalog": CATALOG, "request_id": "req-1"}
        params.update(kw)
        return verify_api_credential(**params)


class TestGenerationDigest(Harness):
    def test_secret_opaque_random(self):
        a, b = generate_secret(), generate_secret()
        self.assertTrue(valid_secret_format(a))
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("ris_"))
        for leak in ("u1", "prof-1", "t1"):
            self.assertNotIn(leak, a)

    def test_malformed_rejected(self):
        for bad in ("", None, "garbage", "ris_short", "jwt.a.b", 123):
            self.assertFalse(valid_secret_format(bad))

    def test_digest_deterministic_not_secret(self):
        s = generate_secret()
        self.assertEqual(digest_secret(s), digest_secret(s))
        self.assertNotIn(s, digest_secret(s))
        self.assertNotEqual(digest_secret(s), s)


class TestVerifyMatrix(Harness):
    def test_01_valid_authorized(self):
        issued = self.issue()
        d = self.verify(issued["secret"])
        self.assertEqual(d.outcome, VerifyOutcome.AUTHORIZED)
        self.assertEqual(d.http_status, 200)

    def test_02_unknown_401(self):
        d = self.verify(generate_secret())
        self.assertEqual(d.outcome, VerifyOutcome.UNAUTHORIZED)
        self.assertEqual(d.http_status, 401)

    def test_03_empty_401(self):
        d = self.verify("")
        self.assertEqual(d.http_status, 401)

    def test_04_malformed_401(self):
        d = self.verify("not-a-credential")
        self.assertEqual(d.http_status, 401)

    def test_05_disabled_403(self):
        issued = self.issue()
        disable_credential(self.creds, issued["metadata"]["credentialId"],
                           "admin", "admin-1")
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_06_revoked_403(self):
        issued = self.issue()
        revoke_credential(self.creds, issued["metadata"]["credentialId"],
                          "admin", "admin-1")
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_07_expired_credential_403(self):
        issued = self.issue(expires_at=_ts(-1))
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_08_missing_profile_403(self):
        issued = self.issue()
        del self.profiles.profiles["prof-1"]
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    # P14 refinement: issuance itself requires a usable (ACTIVE)
    # profile — these tests issue first, then degrade the profile, and
    # assert verify-time denial (intent preserved from P09).
    def test_09_pending_profile_403(self):
        issued = self.issue()
        self.profiles.profiles["prof-1"]["status"] = "PENDING"
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_10_disabled_profile_403(self):
        issued = self.issue()
        self.profiles.profiles["prof-1"]["status"] = "DISABLED"
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_11_expired_profile_403(self):
        issued = self.issue()
        self.profiles.profiles["prof-1"]["status"] = "EXPIRED"
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_12_revoked_profile_403(self):
        issued = self.issue()
        self.profiles.profiles["prof-1"]["status"] = "REVOKED"
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_13_profile_expired_by_date_403(self):
        issued = self.issue()
        self.profiles.profiles["prof-1"]["expiresAt"] = _ts(-1)
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)
        self.assertEqual(d.reason_category, "profile-expired")

    def test_14_wrong_tenant_403(self):
        issued = self.issue()
        self.profiles.profiles["prof-1"]["tenantId"] = "t-evil"
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_14b_profile_without_tenant_403(self):
        del self.profiles.profiles["prof-1"]["tenantId"]
        issued = self.issue()
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_15_no_entitlement_403(self):
        issued = self.issue()
        self.ents.revoke_all()
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_16_inactive_agent_403(self):
        issued = self.issue()
        d = self.verify(issued["secret"], agent="old-agent")
        self.assertEqual(d.http_status, 403)

    def test_17_full_success_context(self):
        issued = self.issue()
        d = self.verify(issued["secret"])
        self.assertTrue(d.authorized)
        for key in ("userId", "tenantId", "apiProfileId", "credentialId",
                    "entitlementRefs", "effectiveScope", "resolution"):
            self.assertIn(key, d.context)
        self.assertNotIn("digest", d.context)
        self.assertNotIn("secret", d.context)

    def test_18_revoke_after_verify_denies_next(self):
        issued = self.issue()
        cid = issued["metadata"]["credentialId"]
        self.assertTrue(self.verify(issued["secret"]).authorized)
        revoke_credential(self.creds, cid, "admin", "admin-1")
        again = self.verify(issued["secret"])
        self.assertFalse(again.authorized)
        self.assertEqual(again.http_status, 403)

    def test_19_disable_profile_after_verify_denies_next(self):
        issued = self.issue()
        self.assertTrue(self.verify(issued["secret"]).authorized)
        self.profiles.profiles["prof-1"]["status"] = "DISABLED"
        self.assertFalse(self.verify(issued["secret"]).authorized)


class TestSecretHygiene(Harness):
    def test_20_secret_nowhere_persisted_or_logged(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            issued = self.issue()
            secret = issued["secret"]
            self.verify(secret)
            self.verify("ris_" + "0" * 43)
        blob = "\n".join(logs.output)
        self.assertNotIn(secret, blob)
        for stored in list(self.creds.by_id.values()):
            for value in stored.values():
                self.assertNotEqual(value, secret)
        self.assertNotIn("digest", issued["metadata"])

    def test_21_digest_not_in_external_response(self):
        issued = self.issue()
        d = self.verify(issued["secret"])
        digest = self.creds.by_id[
            issued["metadata"]["credentialId"]]["digest"]
        self.assertNotIn(digest, repr(d.context))

    def test_22_no_authorization_header_in_audit(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            issued = self.issue()
            self.verify(issued["secret"])
        blob = "\n".join(logs.output).lower()
        self.assertNotIn("authorization", blob)

    def test_23_no_positive_cache_after_revocation(self):
        issued = self.issue()
        first = self.verify(issued["secret"])
        second = self.verify(issued["secret"])
        self.assertTrue(first.authorized and second.authorized)
        revoke_credential(self.creds, issued["metadata"]["credentialId"],
                          "admin", "admin-1")
        third = self.verify(issued["secret"])
        self.assertFalse(third.authorized)


class TestRotation(Harness):
    def test_24_rotation_new_id(self):
        issued = self.issue()
        old_id = issued["metadata"]["credentialId"]
        rotated = rotate_credential(
            self.creds, self.profiles, old_id, _ts(30),
            "admin", "admin-1")
        self.assertNotEqual(rotated["metadata"]["credentialId"], old_id)
        self.assertNotEqual(rotated["secret"], issued["secret"])
        self.assertTrue(
            self.verify(rotated["secret"]).authorized)

    def test_25_old_invalid_immediately(self):
        issued = self.issue()
        rotate_credential(self.creds, self.profiles,
                          issued["metadata"]["credentialId"], _ts(30),
                          "admin", "admin-1")
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)


class TestFailClosed(Harness):
    def test_store_failure_is_not_401_403(self):
        issued = self.issue()

        class Boom:
            def get_by_digest(self, digest):
                raise RuntimeError("db down")

        with self.assertRaises(CredentialStoreUnavailable):
            verify_api_credential(
                issued["secret"], "reference_agent", Boom(),
                self.profiles, self.ents, CATALOG)

    def test_profile_store_failure_is_not_401_403(self):
        issued = self.issue()

        class BoomProfile:
            def get_profile(self, pid):
                raise RuntimeError("db down")

        with self.assertRaises(CredentialStoreUnavailable):
            verify_api_credential(
                issued["secret"], "reference_agent", self.creds,
                BoomProfile(), self.ents, CATALOG)

    def test_entitlement_store_failure_is_not_denial(self):
        issued = self.issue()
        self.ents.fail = RuntimeError("db down")
        with self.assertRaises(CredentialStoreUnavailable):
            self.verify(issued["secret"])


class TestManagement(Harness):
    def test_issue_requires_admin(self):
        with self.assertRaises(UnauthorizedManagementAttempt):
            self.issue(actor_role="staff", actor_id="s1")

    def test_issue_requires_expiry(self):
        with self.assertRaises(ValueError):
            self.issue(expires_at="")

    def test_issue_requires_profile(self):
        with self.assertRaises(CredentialNotFound):
            self.issue(pid="nope")

    def test_staff_may_revoke_not_issue(self):
        issued = self.issue()
        revoke_credential(self.creds, issued["metadata"]["credentialId"],
                          "staff", "s1", reason="abuse")
        d = self.verify(issued["secret"])
        self.assertEqual(d.http_status, 403)

    def test_staff_enable_foreign_denied(self):
        issued = self.issue()
        cid = issued["metadata"]["credentialId"]
        disable_credential(self.creds, cid, "admin", "admin-1")
        with self.assertRaises(UnauthorizedManagementAttempt):
            enable_credential(self.creds, cid, "staff", "s1")
        back = enable_credential(self.creds, cid, "admin", "admin-1")
        self.assertEqual(back["status"], "ACTIVE")

    def test_last_used_updated(self):
        issued = self.issue()
        self.assertIsNone(
            self.creds.by_id[issued["metadata"]["credentialId"]]
            ["lastUsedAt"])
        self.verify(issued["secret"])
        self.assertIsNotNone(
            self.creds.by_id[issued["metadata"]["credentialId"]]
            ["lastUsedAt"])

    def test_dynamodb_adapters_construct_lazily(self):
        self.assertIsNotNone(DynamoDBCredentialStore(table_name="t"))
        self.assertIsNotNone(DynamoDBProfileStore(table_name="t"))


if __name__ == "__main__":
    unittest.main()
