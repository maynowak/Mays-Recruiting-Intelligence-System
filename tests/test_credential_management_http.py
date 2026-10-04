"""Tests Gate 15: credential management HTTP layer (Human JWT only).

Handler parsing/validation/mapping over the P14 service. Stores are
in-memory fakes patched into handler._cred_sources. No productive
secrets (random test values, asserted absent everywhere).
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lambda"))

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.credentials import InMemoryCredentialStore  # noqa: E402


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def claims(sub="u1", tenant="t1", groups=()):
    return {"sub": sub, "email": "%s@x.example" % sub,
            "custom:tenant_id": tenant, "cognito:groups": list(groups)}


class Harness(unittest.TestCase):
    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        p = ap.create_profile(
            self.profiles, {"userId": "u1", "tenantId": "t1", "groups": []},
            "P1")
        ap.transition_status(
            self.profiles, {"userId": "a1", "tenantId": "t1",
                            "groups": ["admins"]}, p["apiProfileId"],
            "ACTIVE")
        self.pid = p["apiProfileId"]
        self.creds = InMemoryCredentialStore()
        self._exp = _ts(30)

    def sources(self):
        return {"credentials": self.creds, "profiles": self.profiles}

    def patched(self):
        import handler as h
        return patch.object(h, "_cred_sources", return_value=self.sources())

    def call(self, method, path, body=None, headers=None, cl=None,
             raw_body=None):
        import handler as h
        from unittest.mock import patch
        event = {
            "httpMethod": method, "path": path,
            "headers": dict(headers or {}),
            "body": raw_body if raw_body is not None
            else (json.dumps(body) if body is not None else None),
            "requestContext": {
                "requestId": "req-15",
                "authorizer": {"jwt": {"claims": cl or claims()}}},
        }
        sources = {"credentials": self.creds, "profiles": self.profiles}
        with patch.object(h, "_cred_sources", return_value=sources):
            out = h.handler(event, None)
        return out["statusCode"], json.loads(out["body"])

    def issue(self, role_groups=(), sub="u1", **kw):
        body = {"label": "Job Matcher", "expiresAt": self._exp}
        body.update(kw.pop("body", {}))
        headers = kw.pop("headers", {})
        status, out = self.call(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            body=body, headers=headers,
            cl=claims(sub, "t1", role_groups), **kw)
        return status, out


class TestIssueRoute(Harness):
    def test_201_with_secret(self):
        status, out = self.issue()
        self.assertEqual(status, 201)
        for key in ("credentialId", "apiProfileId", "label",
                    "credentialType", "status", "expiresAt", "createdAt",
                    "secret"):
            self.assertIn(key, out)
        self.assertTrue(out["secret"].startswith("ris_"))
        self.assertNotIn("digest", out)

    def test_400_bad_json(self):
        status, out = self.call(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            raw_body="{broken")
        self.assertEqual(status, 400)

    def test_400_missing_expires(self):
        status, _ = self.call(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            body={"label": "x"})
        self.assertEqual(status, 400)

    def test_400_unknown_field(self):
        status, _ = self.issue(body={"expiresAt": self._exp, "zzz": 1})
        self.assertEqual(status, 400)

    def test_400_bad_expires(self):
        status, _ = self.issue(body={"expiresAt": "soon"})
        self.assertEqual(status, 400)

    def test_401_no_jwt(self):
        import handler as h
        event = {"httpMethod": "POST",
                 "path": "/v1/apiprofiles/%s/credentials" % self.pid,
                 "headers": {}, "body": "{}",
                 "requestContext": {}}
        with self.patched():
            out = h.handler(event, None)
        self.assertEqual(out["statusCode"], 401)

    def test_403_staff_issue(self):
        status, _ = self.issue(role_groups=("Staff",), sub="s1")
        self.assertEqual(status, 403)

    def test_404_owner_foreign(self):
        other = ap.create_profile(
            self.profiles, {"userId": "u2", "tenantId": "t1", "groups": []},
            "Other")
        ap.transition_status(
            self.profiles, {"userId": "a1", "tenantId": "t1",
                            "groups": ["admins"]}, other["apiProfileId"],
            "ACTIVE")
        status, _ = self.call(
            "POST", "/v1/apiprofiles/%s/credentials" % other["apiProfileId"],
            body={"expiresAt": self._exp})
        self.assertEqual(status, 404)

    def test_409_idempotency_mismatch(self):
        headers = {"Idempotency-Key": "k-1"}
        self.issue(headers=headers)
        status, _ = self.issue(headers=headers,
                               body={"label": "Job Matcher",
                                     "expiresAt": _ts(60)})
        self.assertEqual(status, 409)

    def test_200_idempotent_replay_no_secret(self):
        headers = {"Idempotency-Key": "k-1"}
        self.issue(headers=headers)
        status, out = self.issue(headers=headers)
        self.assertEqual(status, 200)
        self.assertTrue(out["duplicate"])
        self.assertIsNone(out["secret"])

    def test_400_empty_idempotency_key(self):
        status, _ = self.issue(headers={"Idempotency-Key": "  "})
        self.assertEqual(status, 400)

    def test_503_unconfigured(self):
        import handler as h
        event = {"httpMethod": "POST",
                 "path": "/v1/apiprofiles/%s/credentials" % self.pid,
                 "headers": {},
                 "body": json.dumps({"expiresAt": self._exp}),
                 "requestContext": {"authorizer": {"jwt": {"claims":
                                  claims()}}}}
        out = h.handler(event, None)
        self.assertEqual(out["statusCode"], 503)

    def test_clientref_ignored_profile_wins(self):
        status, out = self.issue(
            body={"expiresAt": self._exp, "clientRef": "evil-app"})
        self.assertEqual(status, 201)
        self.assertNotEqual(out.get("clientRef"), "evil-app")


class TestListGet(Harness):
    def test_list_200_no_secret(self):
        self.issue()
        status, out = self.call(
            "GET", "/v1/apiprofiles/%s/credentials" % self.pid)
        self.assertEqual(status, 200)
        self.assertEqual(len(out["items"]), 1)
        item = out["items"][0]
        for key in ("credentialId", "apiProfileId", "label",
                    "credentialType", "status", "createdAt", "updatedAt",
                    "expiresAt", "lastUsedAt", "rotationOf"):
            self.assertIn(key, item)
        blob = json.dumps(out)
        self.assertNotIn("ris_", blob.replace("credentialType", ""))
        self.assertNotIn("digest", blob)

    def test_get_200(self):
        _, created = self.issue()
        status, out = self.call(
            "GET", "/v1/apiprofiles/%s/credentials/%s"
            % (self.pid, created["credentialId"]))
        self.assertEqual(status, 200)
        self.assertEqual(out["credentialId"], created["credentialId"])

    def test_get_404_unknown(self):
        status, _ = self.call(
            "GET", "/v1/apiprofiles/%s/credentials/cred_missing" % self.pid)
        self.assertEqual(status, 404)

    def test_get_404_cross_profile(self):
        _, created = self.issue()
        other = ap.create_profile(
            self.profiles, {"userId": "u1", "tenantId": "t1", "groups": []},
            "Other")
        ap.transition_status(
            self.profiles, {"userId": "a1", "tenantId": "t1",
                            "groups": ["admins"]}, other["apiProfileId"],
            "ACTIVE")
        status, _ = self.call(
            "GET", "/v1/apiprofiles/%s/credentials/%s"
            % (other["apiProfileId"], created["credentialId"]))
        self.assertEqual(status, 404)

    def test_wrong_method_404(self):
        status, _ = self.call(
            "PUT", "/v1/apiprofiles/%s/credentials" % self.pid,
            body={})
        self.assertEqual(status, 404)

    def test_unknown_action_404(self):
        _, created = self.issue()
        status, _ = self.call(
            "POST", "/v1/apiprofiles/%s/credentials/%s/bogus"
            % (self.pid, created["credentialId"]), body={})
        self.assertEqual(status, 404)


class TestLifecycleRoutes(Harness):
    def _cid(self, **kw):
        _, out = self.issue(**kw)
        return out["credentialId"]

    def _act(self, cid, action, body=None, **kw):
        return self.call("POST",
                         "/v1/apiprofiles/%s/credentials/%s/%s"
                         % (self.pid, cid, action),
                         body=body or {}, **kw)

    def test_rotate_201_revokes_old(self):
        cid = self._cid()
        status, out = self._act(cid, "rotate",
                                {"expiresAt": _ts(60)})
        self.assertEqual(status, 201)
        self.assertNotEqual(out["credentialId"], cid)
        self.assertTrue(out["secret"].startswith("ris_"))
        self.assertEqual(out["rotationOf"], cid)
        row = self.creds.get_credential(cid)
        self.assertEqual(row["status"], "REVOKED")

    def test_rotate_400_missing_expires(self):
        status, _ = self._act(self._cid(), "rotate", {})
        self.assertEqual(status, 400)

    def test_rotate_200_replay_no_secret(self):
        cid = self._cid()
        headers = {"Idempotency-Key": "rk-1"}
        self._act(cid, "rotate", {"expiresAt": _ts(60)},
                  headers=headers)
        status, out = self._act(cid, "rotate", {"expiresAt": _ts(60)},
                                headers=headers)
        self.assertEqual(status, 200)
        self.assertIsNone(out["secret"])

    def test_disable_200(self):
        status, out = self._act(self._cid(), "disable",
                                {"reason": "support case"})
        self.assertEqual(status, 200)
        self.assertEqual(out["status"], "DISABLED")

    def test_enable_200(self):
        cid = self._cid()
        self._act(cid, "disable", {"reason": "x"})
        status, out = self._act(cid, "enable", {})
        self.assertEqual(status, 200)
        self.assertEqual(out["status"], "ACTIVE")

    def test_enable_expired_409(self):
        cid = self._cid()
        self._act(cid, "disable", {"reason": "x"})
        row = self.creds.get_credential(cid)
        row["expiresAt"] = _ts(-1)
        self.creds.update_credential(cid, row)
        status, _ = self._act(cid, "enable", {})
        self.assertEqual(status, 409)

    def test_revoke_200(self):
        status, out = self._act(self._cid(), "revoke",
                                {"reason": "no longer required"})
        self.assertEqual(status, 200)
        self.assertEqual(out["status"], "REVOKED")
        self.assertNotIn("secret", out)
        self.assertNotIn("digest", json.dumps(out))

    def test_enable_revoked_409(self):
        cid = self._cid()
        self._act(cid, "revoke", {"reason": "x"})
        status, _ = self._act(cid, "enable", {})
        self.assertEqual(status, 409)

    def test_404_unknown_credential(self):
        status, _ = self._act("cred_missing", "revoke",
                              {"reason": "x"})
        self.assertEqual(status, 404)

    def test_400_empty_reason(self):
        status, _ = self._act(self._cid(), "disable", {"reason": "  "})
        self.assertEqual(status, 400)


class TestRoles(Harness):
    def test_owner_foreign_profile_neutral(self):
        # LIST on a foreign profile: neutral empty list (indistinguishable
        # from "no credentials" — no existence oracle).
        other = ap.create_profile(
            self.profiles, {"userId": "u2", "tenantId": "t1", "groups": []},
            "Other")
        ap.transition_status(
            self.profiles, {"userId": "a1", "tenantId": "t1",
                            "groups": ["admins"]}, other["apiProfileId"],
            "ACTIVE")
        status, out = self.call(
            "GET", "/v1/apiprofiles/%s/credentials" % other["apiProfileId"],
            cl=claims("u1"))
        self.assertEqual(status, 200)
        self.assertEqual(out["items"], [])

    def test_admin_foreign_profile_200(self):
        other = ap.create_profile(
            self.profiles, {"userId": "u2", "tenantId": "t1", "groups": []},
            "Other")
        ap.transition_status(
            self.profiles, {"userId": "a1", "tenantId": "t1",
                            "groups": ["admins"]}, other["apiProfileId"],
            "ACTIVE")
        status, out = self.call(
            "GET", "/v1/apiprofiles/%s/credentials" % other["apiProfileId"],
            cl=claims("a1", "t1", ("admins",)))
        self.assertEqual(status, 200)
        self.assertIn("items", out)

    def test_admin_crosstenant_with_reason(self):
        status, out = self.call(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            body={"expiresAt": self._exp, "reason": "incident-9"},
            cl=claims("a9", "tX", ("admins",)))
        self.assertEqual(status, 201)

    def test_admin_crosstenant_without_reason_403(self):
        status, _ = self.call(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            body={"expiresAt": self._exp},
            cl=claims("a9", "tX", ("admins",)))
        self.assertEqual(status, 403)

    def test_staff_support_disable(self):
        _, created = self.issue()
        status, _ = self.call(
            "POST", "/v1/apiprofiles/%s/credentials/%s/disable"
            % (self.pid, created["credentialId"]),
            body={"reason": "abuse ticket"},
            cl=claims("s1", "t1", ("Staff",)))
        self.assertEqual(status, 200)

    def test_staff_revoke_needs_path_binding(self):
        _, created = self.issue()
        other = ap.create_profile(
            self.profiles, {"userId": "u1", "tenantId": "t1", "groups": []},
            "Other")
        ap.transition_status(
            self.profiles, {"userId": "a1", "tenantId": "t1",
                            "groups": ["admins"]}, other["apiProfileId"],
            "ACTIVE")
        status, _ = self.call(
            "POST", "/v1/apiprofiles/%s/credentials/%s/revoke"
            % (other["apiProfileId"], created["credentialId"]),
            body={"reason": "x"},
            cl=claims("s1", "t1", ("Staff",)))
        self.assertEqual(status, 404)


class TestHeaderContract(Harness):
    def test_match_ok(self):
        status, _ = self.call(
            "GET", "/v1/apiprofiles/%s/credentials" % self.pid,
            headers={"X-Api-Profile": self.pid})
        self.assertEqual(status, 200)

    def test_mismatch_400(self):
        status, out = self.call(
            "GET", "/v1/apiprofiles/%s/credentials" % self.pid,
            headers={"X-Api-Profile": "aprof_other"})
        self.assertEqual(status, 400)
        self.assertEqual(out["error"], "Profile mismatch")


class TestHygiene(Harness):
    def test_no_secret_in_errors(self):
        status, out = self.call(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            raw_body="{broken")
        self.assertEqual(status, 400)
        self.assertNotIn("ris_", json.dumps(out))

    def test_no_jwt_no_auth_mirror(self):
        _, out = self.issue()
        blob = json.dumps(out)
        self.assertNotIn("eyJ", blob)
        self.assertNotIn("Authorization", blob)

    def test_no_secret_in_handler_logs(self):
        import logging
        _, created = self.issue()
        secret = created["secret"]
        with self.assertLogs(level="WARNING") as logs:
            self.call("GET",
                      "/v1/apiprofiles/%s/credentials" % self.pid)
            self.call("POST",
                      "/v1/apiprofiles/%s/credentials" % self.pid,
                      body={"expiresAt": _ts(60)})
        blob = "\n".join(logs.output)
        # handler paths add no secrets (service audit covered in P14)
        for line in blob.splitlines():
            if "credential-audit" not in line \
                    and "apiprofile-audit" not in line:
                self.assertNotIn(secret, line)

    def test_correlation_forwarded(self):
        with self.assertLogs("agents.ecosystem.credentials",
                             level="WARNING") as logs:
            self.call("GET", "/v1/apiprofiles/%s/credentials" % self.pid,
                      headers={"X-Correlation-Id": "corr-1"})
        blob = "\n".join(logs.output)
        self.assertIn("corr-1", blob)


class _VerifyHarness(Harness):
    def _resolver(self, rows):
        class R:
            def find_entitlements(self, user_id):
                return [dict(r) for r in rows
                        if r.get("userId") == user_id]
        return R()


class TestIntegration(_VerifyHarness):
    def test_issue_verify_lifecycle(self):
        from agents.ecosystem.credentials import verify_api_credential
        _, created = self.issue()
        secret = created["secret"]
        rows = [{"userId": "u1", "tenantId": "t1",
                 "agentId": "reference_agent", "entitlementId": "e1"}]
        catalog = {"reference_agent": "ACTIVE"}

        def check():
            return verify_api_credential(
                secret, "reference_agent", self.creds,
                _PShim(self.profiles), self._resolver(rows), catalog)

        self.assertEqual(check().http_status, 200)
        cid = created["credentialId"]
        from agents.ecosystem.credentials import disable_credential
        disable_credential(self.creds, cid, "admin", "a1", reason="x")
        self.assertEqual(check().http_status, 403)
        from agents.ecosystem.credentials import enable_credential
        enable_credential(self.creds, cid, "admin", "a1")
        self.assertEqual(check().http_status, 200)
        from agents.ecosystem.credentials import revoke_credential
        revoke_credential(self.creds, cid, "admin", "a1", reason="x")
        self.assertEqual(check().http_status, 403)


class _PShim:
    def __init__(self, store):
        self.store = store

    def get_profile(self, pid):
        return self.store.get_profile(pid)


if __name__ == "__main__":
    unittest.main()
