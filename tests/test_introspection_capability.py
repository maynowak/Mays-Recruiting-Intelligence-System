"""Tests Gate 12: read-only introspection / capability contract.

Three contexts (human/profile/credential), positive-only, no oracle,
no secrets. No productive credentials (random test values only).
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lambda"))

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem import offers as off  # noqa: E402
from agents.ecosystem.credentials import (  # noqa: E402
    InMemoryCredentialStore,
    issue_credential,
)
from agents.ecosystem.introspection import (  # noqa: E402
    IntrospectionUnavailable,
    introspect_credential,
    introspect_human,
    introspect_profile,
)


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def admin(uid="a1", tenant="t1"):
    return {"userId": uid, "tenantId": tenant, "groups": ["admins"]}


def _ent(user="u1", tenant="t1", agent="agent-a", profile=None, **kw):
    row = {"userId": user, "tenantId": tenant, "agentId": agent,
           "entitlementId": "e-%s" % agent}
    if profile is not None:
        row["apiProfileId"] = profile
    row.update(kw)
    return row


CATALOG = {
    "agent-a": {"status": "ACTIVE", "name": "A",
                "capabilities": ["cap.a"]},
    "agent-b": {"status": "ACTIVE", "name": "B",
                "capabilities": ["cap.b"]},
    "old-agent": {"status": "INACTIVE", "name": "Old",
                  "capabilities": ["cap.old"]},
    "dep-agent": "DEPRECATED",
    "ret-agent": {"status": "RETIRED"},
}


class Ents:
    def __init__(self, rows=None, fail=None):
        self._rows = list(rows or [])
        self.fail = fail

    def find_entitlements(self, user_id):
        if self.fail is not None:
            raise self.fail
        return [dict(r) for r in self._rows if r.get("userId") == user_id]


class Harness(unittest.TestCase):
    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        p = ap.create_profile(self.profiles,
                              {"userId": "u1", "tenantId": "t1",
                               "groups": []}, "P1")
        ap.transition_status(self.profiles, admin(), p["apiProfileId"],
                             "ACTIVE")
        self.pid = p["apiProfileId"]
        self.ents = Ents([_ent()])
        self.offers = off.InMemoryOfferStore()
        self.creds = InMemoryCredentialStore()
        self.catalog = dict(CATALOG)

    def sources(self, **kw):
        from agents.ecosystem.introspection import _sources
        params = {"profile_store": self.profiles,
                  "entitlement_resolver": self.ents,
                  "offer_store": self.offers,
                  "catalog": self.catalog,
                  "credential_store": self.creds}
        params.update(kw)
        return _sources(**params)

    def issue(self, pid=None, **kw):
        params = {"credential_store": self.creds,
                  "profile_store": _ProfileShim(self.profiles),
                  "api_profile_id": pid or self.pid,
                  "expires_at": _ts(30), "actor_role": "admin",
                  "actor_id": "a1"}
        params.update(kw)
        return issue_credential(**params)

    def _event(self, headers=None):
        return {
            "headers": headers or {},
            "requestContext": {
                "requestId": "req-9",
                "authorizer": {"jwt": {"claims": {
                    "sub": "u1", "email": "u@x.example",
                    "custom:tenant_id": "t1",
                    "cognito:groups": []}}}},
        }

    def _patched(self):
        import handler as h
        from unittest.mock import patch
        sources = self.sources()
        return patch.object(h, "_build_introspection_sources",
                            return_value=sources)


class _ProfileShim:
    """P09 profile-store protocol over the P10 repository."""

    def __init__(self, store):
        self.store = store

    def get_profile(self, pid):
        return self.store.get_profile(pid)


class TestHuman(Harness):
    def test_01_human_context(self):
        status, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual(status, 200)
        for key in ("context", "subject", "capabilities", "validity",
                    "resolution"):
            self.assertIn(key, body)
        self.assertEqual(body["context"], "human")
        self.assertEqual(body["subject"],
                         {"userId": "u1", "tenantId": "t1"})
        self.assertIn("checkedAt", body["validity"])
        self.assertEqual(
            [a["agentId"] for a in body["capabilities"]], ["agent-a"])
        self.assertEqual(len(body["allowedProfiles"]), 1)

    def test_02_no_identity_401(self):
        status, body = introspect_human(None, None, self.sources())
        self.assertEqual(status, 401)


class TestProfile(Harness):
    def test_03_own_profile(self):
        status, body = introspect_profile("u1", "t1", self.sources(),
                                          self.pid)
        self.assertEqual(status, 200)
        self.assertEqual(body["context"], "profile")
        self.assertEqual(body["profile"]["apiProfileId"], self.pid)
        self.assertEqual(body["profile"]["status"], "ACTIVE")

    def test_04_foreign_404(self):
        status, _ = introspect_profile("u2", "t1", self.sources(),
                                       self.pid)
        self.assertEqual(status, 404)

    def test_05_unknown_404(self):
        status, _ = introspect_profile("u1", "t1", self.sources(),
                                       "aprof_missing")
        self.assertEqual(status, 404)

    def test_06_default_single(self):
        status, body = introspect_profile("u1", "t1", self.sources(),
                                          None)
        self.assertEqual(status, 200)
        self.assertEqual(body["resolution"]["selectedBy"], "default")

    def test_07_multiple_needs_explicit(self):
        ap.create_profile(self.profiles,
                          {"userId": "u1", "tenantId": "t1", "groups": []},
                          "P2")
        second = ap.create_profile(
            self.profiles, {"userId": "u1", "tenantId": "t1", "groups": []},
            "P2b")
        ap.transition_status(self.profiles, admin(),
                             second["apiProfileId"], "ACTIVE")
        status, _ = introspect_profile("u1", "t1", self.sources(), None)
        self.assertEqual(status, 404)

    def _status_case(self, status=None, expired=False):
        p = ap.create_profile(self.profiles,
                              {"userId": "u1", "tenantId": "t1",
                               "groups": []}, "S-%s" % status)
        if status != "PENDING":
            if expired:
                ap.transition_status(self.profiles, admin(),
                                     p["apiProfileId"], "ACTIVE")
                ap.set_expires_at(self.profiles, admin(),
                                  p["apiProfileId"], _ts(-1),
                                  reason="test")
            else:
                ap.transition_status(self.profiles, admin(),
                                     p["apiProfileId"], "ACTIVE")
                if status != "ACTIVE":
                    ap.transition_status(
                        self.profiles, admin(), p["apiProfileId"], status,
                        reason="test")
        return p["apiProfileId"]

    def test_08_pending_404(self):
        pid = self._status_case("PENDING")
        status, _ = introspect_profile("u1", "t1", self.sources(), pid)
        self.assertEqual(status, 404)

    def test_09_disabled_404(self):
        pid = self._status_case("DISABLED")
        status, _ = introspect_profile("u1", "t1", self.sources(), pid)
        self.assertEqual(status, 404)

    def test_10_expired_404(self):
        pid = self._status_case("ACTIVE", expired=True)
        status, _ = introspect_profile("u1", "t1", self.sources(), pid)
        self.assertEqual(status, 404)

    def test_11_revoked_404(self):
        p = ap.create_profile(self.profiles,
                              {"userId": "u1", "tenantId": "t1",
                               "groups": []}, "S-REV")
        ap.transition_status(self.profiles, admin(), p["apiProfileId"],
                             "ACTIVE")
        ap.transition_status(self.profiles, admin(), p["apiProfileId"],
                             "REVOKED", reason="end")
        status, _ = introspect_profile("u1", "t1", self.sources(),
                                       p["apiProfileId"])
        self.assertEqual(status, 404)


class TestCapabilities(Harness):
    def test_12_user_wide(self):
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual([a["agentId"] for a in body["capabilities"]],
                         ["agent-a"])

    def test_13_profile_bound(self):
        self.ents = Ents([_ent(agent="agent-b", profile=self.pid)])
        _, body = introspect_profile("u1", "t1", self.sources(), self.pid)
        self.assertEqual([a["agentId"] for a in body["capabilities"]],
                         ["agent-b"])

    def test_14_union(self):
        self.ents = Ents([_ent(agent="agent-a"),
                          _ent(agent="agent-b", profile=self.pid)])
        _, body = introspect_profile("u1", "t1", self.sources(), self.pid)
        self.assertEqual([a["agentId"] for a in body["capabilities"]],
                         ["agent-a", "agent-b"])

    def test_15_scope_reduces(self):
        _, body = introspect_profile("u1", "t1", self.sources(), self.pid,
                                     scope_filter={"agent-a"})
        caps = body["capabilities"]
        self.assertEqual([a["agentId"] for a in caps], ["agent-a"])
        self.assertTrue(all(a["scopeRestricted"] for a in caps))

    def test_16_scope_never_expands(self):
        _, body = introspect_profile("u1", "t1", self.sources(), self.pid,
                                     scope_filter={"agent-b"})
        self.assertEqual(body["capabilities"], [])

    def test_17_foreign_tenant_excluded(self):
        self.ents = Ents([_ent(tenant="t2")])
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual(body["capabilities"], [])

    def test_18_unknown_agent_excluded(self):
        self.ents = Ents([_ent(agent="ghost-agent")])
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual(body["capabilities"], [])

    def test_19_inactive_excluded(self):
        self.ents = Ents([_ent(agent="old-agent")])
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual(body["capabilities"], [])

    def test_20_deprecated_excluded(self):
        self.ents = Ents([_ent(agent="dep-agent")])
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual(body["capabilities"], [])

    def test_21_retired_excluded(self):
        self.ents = Ents([_ent(agent="ret-agent")])
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual(body["capabilities"], [])

    def test_expired_entitlement_excluded(self):
        self.ents = Ents([_ent(validUntil=_ts(-1))])
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual(body["capabilities"], [])


class TestOffers(Harness):
    def _mk(self, name, status="ACTIVE", agents=None):
        return off.create_offer(
            self.offers, admin(), name, agents or ["agent-a"],
            {"agent-a": "ACTIVE", "agent-b": "ACTIVE"})

    def test_22_active_listed(self):
        self._mk("Pack")
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual([o["name"] for o in body["offers"]], ["Pack"])

    def test_23_inactive_hidden(self):
        made = self._mk("Old")
        off.set_offer_status(self.offers, admin(), made["offerId"],
                             "INACTIVE", reason="x")
        _, body = introspect_human("u1", "t1", self.sources())
        self.assertEqual(body["offers"], [])

    def test_24_no_prices(self):
        self._mk("Pack")
        _, body = introspect_human("u1", "t1", self.sources())
        blob = json.dumps(body).lower()
        for word in ("price", "billing", "subscription", "payment",
                     "currency"):
            self.assertNotIn(word, blob)


class TestCredentialCtx(Harness):
    def test_credential_view(self):
        issued = self.issue()
        status, body = introspect_credential(issued["secret"],
                                             self.sources())
        self.assertEqual(status, 200)
        self.assertEqual(body["context"], "credential")
        self.assertEqual(body["profile"]["apiProfileId"], self.pid)
        self.assertEqual(body["credential"]["credentialId"],
                         issued["metadata"]["credentialId"])
        self.assertEqual([a["agentId"] for a in body["capabilities"]],
                         ["agent-a"])

    def test_credential_mismatch_hint_403(self):
        issued = self.issue()
        status, _ = introspect_credential(
            issued["secret"], self.sources(), selection_hint="aprof_x")
        self.assertEqual(status, 403)

    def test_credential_unknown_401(self):
        from agents.ecosystem.credentials import generate_secret
        status, _ = introspect_credential(generate_secret(),
                                          self.sources())
        self.assertEqual(status, 401)


class TestHygiene(Harness):
    def test_25_no_secrets(self):
        issued = self.issue()
        secret = issued["secret"]
        _, human = introspect_human("u1", "t1", self.sources())
        _, prof = introspect_profile("u1", "t1", self.sources(), self.pid)
        _, cred = introspect_credential(secret, self.sources())
        blob = json.dumps([human, prof, cred])
        self.assertNotIn(secret, blob)

    def test_26_no_jwts(self):
        _, body = introspect_human("u1", "t1", self.sources())
        blob = json.dumps(body)
        self.assertNotIn("eyJ", blob)
        self.assertNotIn("Authorization", blob)
        self.assertNotIn("authorization", blob.lower().replace(
            "unauthorized", ""))

    def test_27_no_digests(self):
        issued = self.issue()
        digest = self.creds.by_id[
            issued["metadata"]["credentialId"]]["digest"]
        _, body = introspect_credential(issued["secret"], self.sources())
        self.assertNotIn(digest, json.dumps(body))

    def test_28_positive_only(self):
        self.ents = Ents([_ent(agent="ghost-agent")])
        _, body = introspect_human("u1", "t1", self.sources())
        blob = json.dumps(body)
        self.assertNotIn("allowed\": false", blob)
        self.assertNotIn("reason", blob)
        self.assertNotIn("denied", blob)

    def test_29_no_oracle(self):
        _, body = introspect_human("u1", "t1", self.sources())
        blob = json.dumps(body)
        for word in ("old-agent", "dep-agent", "ret-agent", "ghost",
                     "ENTITLEMENT", "entitlement-"):
            self.assertNotIn(word, blob)

    def test_30_audit_secrets_free(self):
        issued = self.issue()
        with self.assertLogs("agents.ecosystem.introspection",
                             level="WARNING") as logs:
            introspect_credential(issued["secret"], self.sources())
            introspect_human("u1", "t1", self.sources())
        blob = "\n".join(logs.output)
        self.assertNotIn(issued["secret"], blob)


class TestHandler(Harness):
    def test_handler_200_human(self):
        import handler as h
        with self._patched():
            out = h._handle_introspection(self._event(), None)
        self.assertEqual(out["statusCode"], 200)
        body = json.loads(out["body"])
        self.assertEqual(body["context"], "human")

    def test_handler_401(self):
        import handler as h
        event = {"headers": {}, "requestContext": {}}
        with self._patched():
            out = h._handle_introspection(event, None)
        self.assertEqual(out["statusCode"], 401)

    def test_handler_404_unknown_hint(self):
        import handler as h
        event = self._event({"X-Api-Profile": "aprof_missing"})
        with self._patched():
            out = h._handle_introspection(event, None)
        self.assertEqual(out["statusCode"], 404)

    def test_handler_503_unconfigured(self):
        import handler as h
        out = h._handle_introspection(self._event(), None)
        self.assertEqual(out["statusCode"], 503)

    def test_handler_credential_param(self):
        import handler as h
        issued = self.issue()
        with self._patched():
            out = h._handle_introspection(
                self._event(), None, bearer_credential=issued["secret"])
        self.assertEqual(out["statusCode"], 200)
        body = json.loads(out["body"])
        self.assertEqual(body["context"], "credential")


class TestDispatchP13(Harness):
    """P13: GET /v1/introspection dispatches to _handle_introspection."""

    def _dispatch_event(self, headers=None):
        event = self._event(headers)
        event["httpMethod"] = "GET"
        event["path"] = "/v1/introspection"
        return event

    def test_dispatch_delegates(self):
        import handler as h
        from unittest.mock import patch
        with patch.object(
                h, "_handle_introspection",
                return_value={"statusCode": 200,
                              "body": "{}"}) as mock:
            out = h.handler(self._dispatch_event(
                {"X-Api-Profile": "aprof_x"}), None)
        self.assertEqual(out["statusCode"], 200)
        mock.assert_called_once()
        args, _ = mock.call_args
        self.assertEqual(
            args[0]["headers"], {"X-Api-Profile": "aprof_x"})

    def test_dispatch_unauthenticated_401(self):
        import handler as h
        event = {"httpMethod": "GET", "path": "/v1/introspection",
                 "headers": {}, "requestContext": {}}
        with self._patched():
            out = h.handler(event, None)
        self.assertEqual(out["statusCode"], 401)

    def test_dispatch_unconfigured_503(self):
        import handler as h
        out = h.handler(self._dispatch_event(), None)
        self.assertEqual(out["statusCode"], 503)


if __name__ == "__main__":
    unittest.main()
