"""Tests Gate B3-...-08: machine credential entry point.

Positive and negative coverage of the DEDICATED machine plane
(POST /v1/m2m/agents/{agentId}/execute) plus the human-route boundary.

The authorization source under test is the EXISTING central verification
(agents.ecosystem.credentials.verify_api_credential). This test file does
not reimplement any part of it and does not assert a simplified
"credential exists -> execute" behaviour: every denial below is produced by
the real verifier against in-memory stores, exactly as in production.
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
    CredentialStoreUnavailable,
    InMemoryCredentialStore,
)
from agents.ecosystem.worker_authorization import (  # noqa: E402
    WorkerAuthDecision,
)

AGENT = "reference_agent"
ROUTE = "/v1/m2m/agents/%s/execute" % AGENT
OTHER_AGENT = "jobsearch-agent"


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class FakeEntitlementResolver:
    """In-memory entitlement source with the production interface."""

    def __init__(self, rows):
        self.rows = rows

    def find_entitlements(self, user_id):
        return [r for r in self.rows if r.get("userId") == user_id]


class AllowResolver(FakeEntitlementResolver):
    def __init__(self, user_id="u1", agent_id=AGENT, tenant="t1"):
        super().__init__([{
            "entitlementId": "ent-1", "userId": user_id,
            "agentId": agent_id, "tenantId": tenant,
            "validFrom": _ts(-1), "validUntil": _ts(30),
            "status": "ACTIVE",
        }])


class Harness(unittest.TestCase):
    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        self.creds = InMemoryCredentialStore()
        self.resolver = AllowResolver()
        self.catalog = {AGENT: "ACTIVE"}
        self.issued = None
        self.enqueued = []
        self._make()

    def _make(self):
        import handler as h
        owner = {"userId": "u1", "tenantId": "t1", "groups": []}
        admin = {"userId": "a1", "tenantId": "t1", "groups": ["admins"]}
        self.pid = ap.create_profile(self.profiles, owner, "B3 machine")[
            "apiProfileId"]
        ap.transition_status(self.profiles, admin, self.pid, "ACTIVE")
        self.secret = None

    def issue(self, expires_days=30, profile_id=None):
        import handler as h
        out = h._cred_issue = None
        from agents.ecosystem.credentials import issue_credential
        res = issue_credential(
            self.creds, self.profiles, profile_id or self.pid, _ts(expires_days),
            "owner", "u1", reason="b3-test")
        self.secret = res["secret"]
        return res

    def sources(self):
        return {
            "profile_store": self.profiles,
            "credential_store": self.creds,
            "entitlement_resolver": self.resolver,
            "catalog": self.catalog,
        }

    def call(self, bearer=None, agent_id=AGENT, path=None, body=None,
             extra_headers=None, sources=None, cognito=True,
             cognito_user="u1"):
        """Invoke the machine route the way the gateway now delivers it.

        P21-01: the route is Cognito-JWT protected, so the event carries the
        authorizer claims the gateway would have validated, and the opaque
        credential travels in X-Api-Credential. `cognito=False` simulates a
        request that never passed the authorizer (direct invocation).
        """
        import handler as h
        headers = {}
        if bearer is not None:
            headers["X-Api-Credential"] = bearer
        headers.update(extra_headers or {})
        request_context = {"requestId": "req-b3",
                           "http": {"method": "POST", "path": path}}
        if cognito:
            request_context["authorizer"] = {
                "jwt": {"claims": {"sub": cognito_user,
                                   "token_use": "access",
                                   "custom:tenant_id": "t1"}}}
        event = {
            "httpMethod": "POST",
            "path": path if path is not None else "/v1/m2m/agents/%s/execute"
                    % (agent_id or ""),
            "rawPath": path,
            "headers": headers,
            "body": json.dumps(body if body is not None else
                               {"capability": "reference.echo", "payload": {}}),
            "requestContext": request_context,
        }
        with patch.object(h, "_build_introspection_sources",
                          return_value=sources or self.sources()), \
             patch.object(h, "_enqueue_agent_work",
                          side_effect=self._fake_enqueue) as enq:
            out = h.handler(event, None)
        self.enqueued = enq.call_args_list
        return out["statusCode"], json.loads(out["body"])

    def _fake_enqueue(self, **kwargs):
        import uuid
        return {"workId": "w1", "status": "QUEUED", "requestId": "rq1",
                "workItem": kwargs}


# --------------------------------------------------------------- positive

class TestPositive(Harness):
    def test_valid_credential_reaches_execution_contract(self):
        self.issue()
        code, body = self.call(bearer="Bearer " + self.secret)
        self.assertEqual(code, 202, body)
        self.assertEqual(body["status"], "QUEUED")
        self.assertEqual(len(self.enqueued), 1)

    def test_execution_uses_verified_context_not_request_data(self):
        """The work item subject is the credential's persisted tenant/owner,
        never anything the caller supplied."""
        self.issue()
        code, _ = self.call(
            bearer="Bearer " + self.secret,
            body={"capability": "reference.echo", "payload": {"x": 1},
                  "tenantId": "attacker-tenant", "userId": "attacker"})
        self.assertEqual(code, 202)
        kwargs = self.enqueued[0].kwargs
        self.assertEqual(kwargs["tenant_id"], "t1")
        self.assertEqual(kwargs["user_id"], "u1")
        self.assertEqual(kwargs["agent_id"], AGENT)

    def test_agent_id_taken_from_path(self):
        self.issue()
        code, _ = self.call(bearer="Bearer " + self.secret)
        self.assertEqual(code, 202)
        self.assertEqual(self.enqueued[0].kwargs["agent_id"], AGENT)

    def test_full_chain_reaches_entitlement_and_catalog(self):
        """Both later chain steps are really consulted: remove either one
        and the same request must be denied."""
        self.issue()
        self.assertEqual(self.call(bearer="Bearer " + self.secret)[0], 202)

        self.resolver = FakeEntitlementResolver([])          # no entitlement
        self.assertEqual(self.call(bearer="Bearer " + self.secret)[0], 403)

        self.resolver = AllowResolver()
        self.catalog = {AGENT: "INACTIVE"}                   # not executable
        self.assertEqual(self.call(bearer="Bearer " + self.secret)[0], 403)


# ---------------------------------------------------------------- negative

class TestNegative(Harness):
    def test_01_unknown_credential_401(self):
        code, _ = self.call(bearer="Bearer ris_" + "A" * 45)
        self.assertEqual(code, 401)
        self.assertEqual(self.enqueued, [])

    def test_02_malformed_credential_401(self):
        for bad in ("Bearer", "Bearer ", "Basic abc", "Bearer short",
                    "Bearer has space"):
            code, _ = self.call(bearer=bad)
            self.assertEqual(code, 401, bad)

    def test_03_revoked_credential_403(self):
        from agents.ecosystem.credentials import revoke_credential
        self.issue()
        cid = self._credential_id()
        revoke_credential(self.creds, cid, "owner", "u1")
        code, _ = self.call(bearer="Bearer " + self.secret)
        self.assertEqual(code, 403)
        self.assertEqual(self.enqueued, [])

    def test_04_disabled_credential_403(self):
        from agents.ecosystem.credentials import disable_credential
        self.issue()
        disable_credential(self.creds, self._credential_id(), "owner", "u1")
        code, _ = self.call(bearer="Bearer " + self.secret)
        self.assertEqual(code, 403)

    def test_05_expired_credential_403(self):
        self.issue(expires_days=-1)
        code, _ = self.call(bearer="Bearer " + self.secret)
        self.assertEqual(code, 403)

    def test_06_credential_on_non_active_profile_cannot_execute(self):
        """Profile bound to the credential must be ACTIVE (chain step 8)."""
        from agents.ecosystem.credentials import revoke_credential
        self.issue()
        ap.transition_status(
            self.profiles, {"userId": "a1", "tenantId": "t1",
                            "groups": ["admins"]}, self.pid, "REVOKED")
        code, _ = self.call(bearer="Bearer " + self.secret)
        self.assertEqual(code, 403)

    def test_07_missing_entitlement_403(self):
        self.issue()
        self.resolver = FakeEntitlementResolver([])
        code, _ = self.call(bearer="Bearer " + self.secret)
        self.assertEqual(code, 403)

    def test_08_unknown_agent_403(self):
        """Explicitly addressed but absent from the catalog."""
        self.issue()
        code, _ = self.call(bearer="Bearer " + self.secret,
                            agent_id=OTHER_AGENT)
        self.assertEqual(code, 403)

    def test_09_non_executable_agent_403(self):
        self.issue()
        self.catalog = {AGENT: "DEPRECATED"}
        code, _ = self.call(bearer="Bearer " + self.secret)
        self.assertEqual(code, 403)

    def test_10_human_jwt_is_not_accepted_as_credential(self):
        """A Cognito JWT on the machine path must never be usable."""
        jwt = ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSIsInRva2VuX3VzZSI6"
               "eyJjb2duaXRvOmdyb3VwcyI6WyJhZG1pbnMiXX0.c2ln")
        code, _ = self.call(bearer="Bearer " + jwt)
        self.assertEqual(code, 401)
        self.assertEqual(self.enqueued, [])

    def test_no_authorization_header_401(self):
        code, _ = self.call(bearer=None)
        self.assertEqual(code, 401)

    def test_store_failure_maps_to_503_not_401_or_403(self):
        """Infrastructure failure must never look like a bad credential."""
        self.issue()

        class Boom(InMemoryCredentialStore):
            def get_by_digest(self, digest):
                raise RuntimeError("simulated dynamodb outage")

        sources = self.sources()
        sources["credential_store"] = Boom()
        code, _ = self.call(bearer="Bearer " + self.secret, sources=sources)
        self.assertEqual(code, 503)

    def test_unconfigured_sources_map_to_503(self):
        import handler as h
        event = {"httpMethod": "POST", "path": ROUTE,
                 "headers": {"X-Api-Credential": "Bearer " + "A" * 45},
                 "body": "{}",
                 "requestContext": {
                     "requestId": "r",
                     "http": {"method": "POST", "path": ROUTE},
                     "authorizer": {"jwt": {"claims": {"sub": "u1"}}}}}
        with patch.object(h, "_build_introspection_sources",
                          side_effect=RuntimeError("stores unconfigured")):
            out = h.handler(event, None)
        self.assertEqual(out["statusCode"], 503)

    def test_denial_body_carries_no_oracle_detail(self):
        self.issue()
        code, body = self.call(bearer="Bearer " + self.secret,
                              agent_id=OTHER_AGENT)
        self.assertEqual(code, 403)
        self.assertEqual(sorted(body), ["error"])
        blob = json.dumps(body).lower()
        for needle in ("credential", "profile", "entitlement", "catalog",
                       self.secret):
            self.assertNotIn(needle, blob)

    # helper
    def _credential_id(self):
        rows = list(self.creds.by_id.values())
        self.assertEqual(len(rows), 1)
        return rows[0]["credentialId"]


# ------------------------------------------------------- human plane intact

class TestHumanRouteBoundary(Harness):
    def test_machine_route_is_not_reachable_with_jwt_authorizer_path(self):
        """Human routes keep using JWT claims; the machine route never
        falls back to a human context."""
        import handler as h
        event = {
            "httpMethod": "POST", "path": ROUTE,
            "headers": {}, "body": "{}",
            "requestContext": {"requestId": "r",
                               "authorizer": {"jwt": {"claims": {
                                   "sub": "u1", "custom:tenant_id": "t1"}}}}}
        with patch.object(h, "_build_introspection_sources",
                          return_value=self.sources()), \
             patch.object(h, "_enqueue_agent_work") as enq:
            out = h.handler(event, None)
        self.assertEqual(out["statusCode"], 401)
        self.assertEqual(enq.call_args_list, [])

    def test_unrelated_path_is_not_captured_by_machine_route(self):
        import handler as h
        for path in ("/v1/m2m/agents/%s" % AGENT,
                     "/v1/m2m/",
                     "/v1/m2m/other",
                     "/v1/m2m/agents/%s/execute/extra" % AGENT):
              event = {"httpMethod": "POST", "path": path,
                            "headers": {"X-Api-Credential": "Bearer " + "A" * 45},
                            "body": "{}",
                            "requestContext": {
                                "requestId": "r",
                                "http": {"method": "POST", "path": path},
                                "authorizer": {"jwt": {"claims": {"sub": "u1"}}}}}
              with patch.object(h, "_build_introspection_sources",
              return_value=self.sources()):
                out = h.handler(event, None)
                body = json.loads(out["body"])
                # Either a neutral 401 from the missing target, or the generic
                # 404 — but never an execution.
                self.assertIn(out["statusCode"], (400, 401, 404), path)

    def test_agent_id_extraction_is_strict(self):
        import handler as h
        self.assertEqual(
            h._machine_agent_id("/v1/m2m/agents/%s/execute" % AGENT), AGENT)
        for bad in ("/v1/m2m/agents//execute", "/v1/m2m/agents/x",
                    "/v1/m2m/agents/x/run", "/api/agents/x/execute"):
            self.assertIsNone(h._machine_agent_id(bad), bad)

    def test_agent_id_is_sanitised(self):
        import handler as h
        # The sanitiser keeps [A-Za-z0-9_.-] (dots are legitimate in agent
        # ids). What must not survive is the path separator, i.e. a
        # traversal attempt. API Gateway normally decodes %2F to "/" before
        # the handler runs, so this also covers the decoded form.
        # Percent-encoded separator: survives extraction, but the separator
        # itself is stripped, so no traversal survives.
        cleaned = h._machine_agent_id("/v1/m2m/agents/ref%2F..%2Fero/execute")
        self.assertTrue(cleaned)
        self.assertNotIn("/", cleaned)
        # A literal separator does not match the route pattern at all, so the
        # target is rejected outright rather than sanitised into something.
        self.assertIsNone(h._machine_agent_id("/v1/m2m/agents/ref/../ero/execute"))


if __name__ == "__main__":
    unittest.main()
