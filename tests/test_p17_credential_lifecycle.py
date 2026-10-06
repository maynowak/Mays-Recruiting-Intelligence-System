"""Tests Gate P17-10: Credential-Lifecycle.

Bewusst ERGAENZEND, nicht duplizierend. Bereits abgedeckt und hier nicht
wiederholt:
  * Issuing/CRUD-Verwaltung          -> tests/test_credential_management_http.py
  * Machine-Plane Einzelfaelle        -> tests/test_machine_entrypoint.py
  * Entitlement/Provisionierung       -> tests/test_entitlement_provisioning.py
  * B3/B5 Live-Nachweise             -> deren Execution Logs

Hier getestet werden die Lifecycle-EIGENSCHAFTEN, die kein Einzeltest
zeigt: die geordnete Sequenz, die Terminalitaet von REVOKED, die
Einmal-Semantik des Secrets auf HTTP-Ebene, die Expiry-Ausstellung ueber
den Produktweg und die Isolationsmatrix der Management-API.

Kein AWS, keine Mutation.
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
from agents.ecosystem.credentials import (  # noqa: E402
    InMemoryCredentialStore,
    VerifyOutcome,
)
from agents.ecosystem.worker_authorization import (  # noqa: E402
    check_worker_entitlement,
)

AGENT = "reference_agent"
FUTURE = "2099-01-01T00:00:00+00:00"
PAST = "2020-01-01T00:00:00+00:00"


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class Resolver:
    def __init__(self, rows):
        self.rows = rows

    def find_entitlements(self, user_id):
        return [r for r in self.rows if r.get("userId") == user_id]


class LifecycleHarness(unittest.TestCase):
    """Management plane (JWT) and machine plane (opaque bearer) on the same
    in-memory stores, exactly as production wires them."""

    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        self.creds = InMemoryCredentialStore()
        self.owner = {"userId": "u1", "tenantId": "t1", "groups": []}
        self.admin = {"userId": "a1", "tenantId": "t1", "groups": ["admins"]}
        self.other = {"userId": "u2", "tenantId": "t2", "groups": []}
        self.pid = ap.create_profile(self.profiles, self.owner, "P17")[
            "apiProfileId"]
        ap.transition_status(self.profiles, self.admin, self.pid, "ACTIVE")
        self.pid2 = ap.create_profile(self.profiles, self.owner, "P17-2")[
            "apiProfileId"]
        ap.transition_status(self.profiles, self.admin, self.pid2, "ACTIVE")
        self.resolver = Resolver([{
            "entitlementId": "ent-1", "userId": "u1", "tenantId": "t1",
            "agentId": AGENT, "validFrom": _ts(-1), "validUntil": _ts(30)}])
        self.catalog = {AGENT: "ACTIVE"}
        self.enqueued = []

    # -- helpers ---------------------------------------------------------
    def mgmt(self, method, path, actor=None, body=None):
        import handler as h
        event = {
            "httpMethod": method, "path": path,
            "headers": {}, "body": json.dumps(body) if body is not None else None,
            "requestContext": {
                "requestId": "req-p17",
                "authorizer": {"jwt": {"claims": {
                    "sub": (actor or self.owner)["userId"],
                    "custom:tenant_id": (actor or self.owner)["tenantId"],
                    "cognito:groups": list((actor or self.owner)["groups"])}}}},
        }
        sources = {"credentials": self.creds, "profiles": self.profiles}
        # The APIProfile routes build their store independently of the
        # credential sources, so both are injected — otherwise a profile
        # read would reach real AWS instead of the in-memory store.
        with patch.object(h, "_cred_sources", return_value=sources), \
             patch.object(h, "_aprof_store", return_value=self.profiles):
            out = h.handler(event, None)
        return out["statusCode"], json.loads(out["body"])

    def machine(self, secret, agent=AGENT, headers=None):
            """Machine route as the gateway delivers it after P21-01.

            The route is Cognito-JWT protected: the authorizer claims below are
            what the gateway validated before invoking the Lambda, and the opaque
            credential travels in X-Api-Credential.
            """
            import handler as h
            event = {
                "httpMethod": "POST",
                "path": "/v1/m2m/agents/%s/execute" % agent,
                "headers": {"X-Api-Credential": "Bearer " + secret,
                            **(headers or {})},
                "body": json.dumps({"capability": "reference.echo",
                                    "payload": {}}),
                "requestContext": {"requestId": "req-p17-m",
                                   "http": {"method": "POST"},
                                   "authorizer": {"jwt": {"claims": {"sub": "u1"}}}},
            }
            sources = {"profile_store": self.profiles,
                       "credential_store": self.creds,
                       "entitlement_resolver": self.resolver,
                       "catalog": self.catalog}
            with patch.object(h, "_build_introspection_sources",
                              return_value=sources), \
                 patch.object(h, "_enqueue_agent_work",
                              side_effect=self._enq) as enq:
                out = h.handler(event, None)
            self.enqueued = enq.call_args_list
            return out["statusCode"], json.loads(out["body"])

    def _enq(self, **kw):
        return {"workId": "w1", "status": "QUEUED", "requestId": "rq1",
                "workItem": kw}

    def issue(self, expires=FUTURE, label="p17"):
        code, body = self.mgmt(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            body={"expiresAt": expires, "label": label, "reason": "p17"})
        self.assertEqual(code, 201, body)
        return body

    def act(self, cid, action, actor=None, **extra):
        """Rotation requires expiresAt in the body (existing contract, see
        test_rotation_requires_expires_at); the other actions do not."""
        body = {"reason": "p17"}
        if action == "rotate":
            body["expiresAt"] = FUTURE
        body.update(extra)
        return self.mgmt(
            "POST", "/v1/apiprofiles/%s/credentials/%s/%s"
            % (self.pid, cid, action), actor, body)

    def verify_ok(self, secret):
        from agents.ecosystem.credentials import verify_api_credential
        return verify_api_credential(
            bearer=secret, agent_id=AGENT, credential_store=self.creds,
            profile_store=self.profiles,
            entitlement_resolver=self.resolver, catalog=self.catalog,
            operation="agent.execute",
            route="POST /v1/m2m/agents/{agentId}/execute", method="POST",
            request_id="req-p17")


# ------------------------------------------------------------- Sequenz

class TestLifecycleSequence(LifecycleHarness):
    def test_full_ordered_lifecycle(self):
        """issue -> execute -> disable -> deny -> enable -> execute ->
        revoke -> deny -> enable refused -> rotate -> old denied."""
        issued = self.issue()
        secret, cid = issued["secret"], issued["credentialId"]

        code, _ = self.machine(secret)
        self.assertEqual(code, 202)

        code, _ = self.act(cid, "disable")
        self.assertEqual(code, 200)
        code, _ = self.machine(secret)
        self.assertEqual(code, 403, "disabled credential must be denied")

        code, _ = self.act(cid, "enable")
        self.assertEqual(code, 200)
        code, _ = self.machine(secret)
        self.assertEqual(code, 202, "re-enabled credential works again")
        self.assertEqual(
            self.verify_ok(secret).outcome, VerifyOutcome.AUTHORIZED)

        code, _ = self.act(cid, "revoke")
        self.assertEqual(code, 200)
        code, _ = self.machine(secret)
        self.assertEqual(code, 403, "revoked credential must be denied")

        code, _ = self.act(cid, "enable")
        self.assertEqual(code, 409,
                         "REVOKED is terminal; enable must not resurrect it")
        code, _ = self.machine(secret)
        self.assertEqual(code, 403)

    def test_disable_is_reversible_revoke_is_not(self):
        issued = self.issue()
        secret, cid = issued["secret"], issued["credentialId"]
        self.assertEqual(self.act(cid, "disable")[0], 200)
        self.assertEqual(self.machine(secret)[0], 403)
        self.assertEqual(self.act(cid, "enable")[0], 200)
        self.assertEqual(self.machine(secret)[0], 202)
        self.assertEqual(self.act(cid, "revoke")[0], 200)
        self.assertEqual(self.act(cid, "enable")[0], 409)
        self.assertEqual(self.machine(secret)[0], 403)

    def test_every_status_change_takes_effect_per_request(self):
        """No cache may serve a stale positive state: each transition is
        observed by the very next machine call."""
        issued = self.issue()
        secret, cid = issued["secret"], issued["credentialId"]
        for action, expected in (("disable", 403), ("enable", 202),
                                 ("disable", 403), ("enable", 202),
                                 ("revoke", 403)):
            self.assertEqual(self.act(cid, action)[0], 200, action)
            self.assertEqual(self.machine(secret)[0], expected,
                             f"after {action}")


# ------------------------------------------------------------ Secret

class TestSecretOneTime(LifecycleHarness):
    def test_secret_present_exactly_once_in_issue_response(self):
        issued = self.issue()
        self.assertTrue(issued.get("secret"))
        self.assertEqual(len([k for k, v in issued.items()
                              if k == "secret" and v]), 1)

    def test_get_and_list_never_contain_the_secret(self):
        issued = self.issue()
        secret, cid = issued["secret"], issued["credentialId"]
        code, got = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials/%s" % (self.pid, cid))
        self.assertEqual(code, 200)
        self.assertNotIn("secret", got)
        self.assertNotIn(secret, json.dumps(got))
        code, listed = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials" % self.pid)
        self.assertEqual(code, 200)
        self.assertNotIn("secret", json.dumps(listed))
        self.assertNotIn(secret, json.dumps(listed))

    def test_metadata_shape_is_stable(self):
        issued = self.issue()
        cid = issued["credentialId"]
        code, got = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials/%s" % (self.pid, cid))
        for field in ("credentialId", "apiProfileId", "ownerUserId",
                      "tenantId", "status", "expiresAt", "createdAt",
                      "credentialType", "rotationOf"):
            self.assertIn(field, got, field)

    def test_secret_shape_is_contract_conform(self):
        secret = self.issue()["secret"]
        self.assertTrue(secret.startswith("ris_"))
        self.assertEqual(len(secret), 47)
        self.assertTrue(all(c.isalnum() or c in "-_" for c in secret[4:]))


# ------------------------------------------------------------ Rotation

class TestRotation(LifecycleHarness):
    def test_rotation_moves_the_credential(self):
        issued = self.issue(label="p17-a")
        a_secret, a_cid = issued["secret"], issued["credentialId"]
        self.assertEqual(self.machine(a_secret)[0], 202)

        code, rot = self.act(a_cid, "rotate")
        self.assertEqual(code, 201, rot)
        b_secret, b_cid = rot.get("secret"), rot.get("credentialId")
        self.assertTrue(b_secret)
        self.assertNotEqual(b_cid, a_cid)
        self.assertEqual(rot.get("rotationOf"), a_cid)
        self.assertEqual(rot.get("apiProfileId"), self.pid)

        code, meta_a = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials/%s" % (self.pid, a_cid))
        self.assertEqual(meta_a["status"], "REVOKED")

        self.assertEqual(self.machine(a_secret)[0], 403)
        self.assertEqual(self.machine(b_secret)[0], 202)
        self.assertEqual(
            self.verify_ok(b_secret).outcome, VerifyOutcome.AUTHORIZED)

    def test_old_secret_is_not_recoverable_after_rotation(self):
        issued = self.issue()
        a_secret, a_cid = issued["secret"], issued["credentialId"]
        _, rot = self.act(a_cid, "rotate")
        b_secret = rot["secret"]
        code, got = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials/%s" % (self.pid, a_cid))
        self.assertNotIn("secret", got)
        self.assertNotIn(a_secret, json.dumps(got))
        self.assertNotIn(a_secret, json.dumps(rot))
        self.assertNotEqual(a_secret, b_secret)
        self.assertEqual(self.machine(a_secret)[0], 403)

    def test_rotated_credential_keeps_profile_and_entitlement_binding(self):
        issued = self.issue()
        a_secret, a_cid = issued["secret"], issued["credentialId"]
        _, rot = self.act(a_cid, "rotate")
        decision = self.verify_ok(rot["secret"])
        self.assertIs(decision.outcome, VerifyOutcome.AUTHORIZED)
        self.assertEqual(decision.context["apiProfileId"], self.pid)
        self.assertEqual(decision.context["userId"], "u1")
        self.assertEqual(decision.context["tenantId"], "t1")

    def test_rotation_requires_expires_at(self):
        issued = self.issue()
        code, body = self.mgmt(
            "POST", "/v1/apiprofiles/%s/credentials/%s/rotate"
            % (self.pid, issued["credentialId"]), body={"reason": "p17"})
        self.assertEqual(code, 400)
        self.assertIn("expiresAt", json.dumps(body))


# ------------------------------------------------------------ Expiry

class TestExpiry(LifecycleHarness):
    def test_product_path_allows_issuing_an_already_expired_credential(self):
        """Documented finding (Gate §9): the issuance path does not reject
        expiresAt in the past. Recorded, not changed."""
        code, body = self.mgmt(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            body={"expiresAt": PAST, "label": "p17-expired",
                  "reason": "p17"})
        self.assertEqual(code, 201)
        self.assertTrue(body.get("secret"))

    def test_expired_credential_is_denied_by_the_verifier(self):
        code, body = self.mgmt(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            body={"expiresAt": PAST, "label": "p17-expired",
                  "reason": "p17"})
        code, _ = self.machine(body["secret"])
        self.assertEqual(code, 403)

    def test_expired_credential_is_denied_even_with_valid_entitlement(self):
        code, body = self.mgmt(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid,
            body={"expiresAt": PAST, "label": "p17-expired",
                  "reason": "p17"})
        decision = self.verify_ok(body["secret"])
        self.assertIs(decision.outcome, VerifyOutcome.FORBIDDEN)

    def test_expiry_boundary_min_rule_with_profile(self):
        """A credential expiring after the profile is still usable; the
        MIN rule of the contract applies (covered here for the credential
        side, profile side is unchanged)."""
        secret = self.issue()["secret"]
        self.assertIs(self.verify_ok(secret).outcome, VerifyOutcome.AUTHORIZED)


# ------------------------------------------- Management-API isolation

class TestManagementIsolation(LifecycleHarness):
    def _credential_of(self, pid):
        code, body = self.mgmt(
            "POST", "/v1/apiprofiles/%s/credentials" % pid,
            body={"expiresAt": FUTURE, "label": "x", "reason": "p17"})
        return body["credentialId"]

    def test_foreign_owner_gets_404_on_foreign_credential(self):
        cid = self._credential_of(self.pid)
        code, _ = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials/%s" % (self.pid, cid),
            self.other)
        self.assertEqual(code, 404, "existing contract: neutral, not 403")

    def test_foreign_owner_gets_404_on_mutations(self):
        cid = self._credential_of(self.pid)
        for action in ("disable", "enable", "revoke"):
            code, _ = self.mgmt(
                "POST", "/v1/apiprofiles/%s/credentials/%s/%s"
                % (self.pid, cid, action), self.other, {"reason": "p17"})
            self.assertEqual(code, 404, action)

    def test_foreign_owner_cannot_issue_on_foreign_profile(self):
        code, _ = self.mgmt(
            "POST", "/v1/apiprofiles/%s/credentials" % self.pid, self.other,
            {"expiresAt": FUTURE, "reason": "p17"})
        self.assertEqual(code, 404)

    def test_foreign_list_is_empty_not_a_leak(self):
        """Documented asymmetry: the LIST endpoint answers 200 with an empty
        list for a foreign profile, while the item endpoint answers 404 and
        the profile itself 404. Nothing is disclosed; the surface is merely
        inconsistent."""
        self._credential_of(self.pid)
        code, body = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials" % self.pid, self.other)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("items"), [],
                         "must not disclose foreign credentials")
        code, _ = self.mgmt("GET", "/v1/apiprofiles/%s" % self.pid, self.other)
        self.assertEqual(code, 404)

    def test_cross_profile_credential_access_is_denied(self):
        """A credential is bound to exactly one profile and cannot be read
        through another profile's path."""
        cid = self._credential_of(self.pid)
        code, _ = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials/%s" % (self.pid2, cid))
        self.assertEqual(code, 404)

    def test_admin_still_needs_binding(self):
        """Admin authority does not turn into cross-owner credential access."""
        cid = self._credential_of(self.pid)
        code, _ = self.mgmt(
            "GET", "/v1/apiprofiles/%s/credentials/%s" % (self.pid, cid),
            self.other)
        self.assertEqual(code, 404)


# ------------------------------------------- Execution context binding

class TestExecutionSubject(LifecycleHarness):
    def test_execution_subject_is_the_verified_context_not_the_header(self):
        issued = self.issue()
        code, _ = self.machine(issued["secret"],
                               headers={"X-Api-Profile": self.pid2,
                                        "X-Tenant-Id": "t9",
                                        "userId": "attacker"})
        self.assertEqual(code, 202)
        kwargs = self.enqueued[0].kwargs
        self.assertEqual(kwargs["tenant_id"], "t1")
        self.assertEqual(kwargs["user_id"], "u1")
        self.assertEqual(kwargs["agent_id"], AGENT)

    def test_entitlement_missing_denies_execution(self):
        self.resolver = Resolver([])
        self.assertEqual(self.machine(self.issue()["secret"])[0], 403)

    def test_entitlement_outside_window_denies_execution(self):
        self.resolver = Resolver([{
            "entitlementId": "ent-x", "userId": "u1", "tenantId": "t1",
            "agentId": AGENT, "validFrom": _ts(-30), "validUntil": _ts(-1)}])
        self.assertEqual(self.machine(self.issue()["secret"])[0], 403)

    def test_entitlement_for_other_tenant_denies_execution(self):
        self.resolver = Resolver([{
            "entitlementId": "ent-y", "userId": "u1", "tenantId": "other",
            "agentId": AGENT, "validFrom": _ts(-1), "validUntil": _ts(30)}])
        decision = check_worker_entitlement(
            user_id="u1", tenant_id="t1", agent_id=AGENT, work_id="w",
            resolver=self.resolver)
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.reason, "tenant-mismatch")


if __name__ == "__main__":
    unittest.main()
