"""G02 — Authorization matrix for the Addition Agent (math.add).

RIS-MO-ADDITION-AGENT-E2E-01, gate G02.

Local contract tests only. No AWS, no Cognito, no network, no real credentials.
The stores are the repository's in-memory implementations; the HTTP boundary is
the real ``handler`` entry point with only the AWS side effects patched
(``_build_introspection_sources``, ``_enqueue_agent_work``, partner registry).

Matrix under test
-----------------
1. Partner A, valid JWT + RIS key, entitlement      -> 202 ALLOW
2. Partner B, valid credential but no entitlement   -> 403 DENY
3. Partner A, wrong RIS key                         -> 401 DENY
4. Partner A, revoked key                           -> 403 DENY
5. Inactive agent                                   -> 403 DENY
6. Foreign APIProfile / tenant context              -> 403 DENY
plus: the enqueued work item must not contain the secret.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.credentials import (  # noqa: E402
    InMemoryCredentialStore,
    issue_credential,
    revoke_credential,
)

AGENT = "addition_agent"
CAPABILITY = "math.add"
PAYLOAD = {"left": 17, "right": 25}
SECRET = "ris_" + "A" * 47
# Sentinel: "use the credential issued in setUp()". Resolved in call() so the
# default never depends on import-time module state.
USE_VALID = "<use-valid-credential>"


def _ts(offset_days):
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).isoformat()


def _claims(sub="user-a", tenant="tenant-a", client_id="client-a"):
    return {"sub": sub, "token_use": "access",
            "custom:tenant_id": tenant, "client_id": client_id}


def _event(credential=USE_VALID, tenant="tenant-a", agent=AGENT, body=None):
    headers = {}
    if credential is not None:
        headers["X-Api-Credential"] = credential
    return {
        "httpMethod": "POST",
        "path": "/v1/m2m/agents/%s/execute" % agent,
        "headers": headers,
        "body": json.dumps(body if body is not None else {
            "capability": CAPABILITY, "payload": PAYLOAD,
            "idempotencyKey": "idem-g02",
        }),
        "requestContext": {
            "requestId": "req-g02",
            "http": {"method": "POST",
                     "path": "/v1/m2m/agents/%s/execute" % agent},
            "authorizer": {"jwt": {"claims": _claims(tenant=tenant)}},
        },
    }


class _Resolver:
    """Entitlement resolver double: rows are explicit, nothing is invented."""

    def __init__(self, rows):
        self.rows = rows

    def find_entitlements(self, user_id):
        return [r for r in self.rows if r.get("userId") == user_id]


def _entitlement(user_id="user-a", agent=AGENT):
    # NOTE: the entitlement contract has no `status` field. Validity is
    # temporal (validFrom/validUntil) plus agent/tenant match; withdrawal
    # deletes the row (offer store delete_entitlement).
    return {"entitlementId": "ent-g02", "userId": user_id, "agentId": agent,
            "tenantId": "tenant-a", "validFrom": _ts(-1),
            "validUntil": _ts(30)}


class AuthorizationHarness(unittest.TestCase):
    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        self.credentials = InMemoryCredentialStore()
        # Partner A: APIProfile owned by user-a / tenant-a.
        self.pid = ap.create_profile(
            self.profiles,
            {"userId": "user-a", "tenantId": "tenant-a", "groups": []},
            "g02 partner A",
        )["apiProfileId"]
        ap.transition_status(
            self.profiles,
            {"userId": "admin", "tenantId": "tenant-a", "groups": ["admins"]},
            self.pid,
            "ACTIVE",
        )
        issued = issue_credential(
            self.credentials, self.profiles, self.pid, _ts(30),
            "admin", "admin", label="g02",
        )
        self.secret = issued["secret"]
        self.cid = issued["metadata"]["credentialId"]
        self.catalog = {AGENT: "ACTIVE"}
        self.registry_tenant = "tenant-a"
        self.registry_profile = self.pid

    # -- harness ---------------------------------------------------------
    def sources(self, catalog=None, resolver=None):
        return {
            "profile_store": self.profiles,
            "credential_store": self.credentials,
            "entitlement_resolver": resolver or _Resolver([_entitlement()]),
            "catalog": self.catalog if catalog is None else catalog,
        }

    def call(self, event, sources=None):
        enqueued = []

        if event.get("headers", {}).get("X-Api-Credential") == USE_VALID:
            event["headers"]["X-Api-Credential"] = self.secret

        def _enq(**kwargs):
            enqueued.append(kwargs)
            return {"workId": "w-g02", "status": "QUEUED",
                    "requestId": "rq-g02", "workItem": kwargs}

        def registry_stub(client_id):
            return {
                "applicationId": "app-a",
                "cognitoClientId": client_id,
                "apiProfileId": self.registry_profile,
                "tenantId": self.registry_tenant,
                "status": "ACTIVE",
            }

        with patch.object(h, "_build_introspection_sources",
                          return_value=sources or self.sources()), \
             patch.object(h, "_enqueue_agent_work", side_effect=_enq), \
             patch("agents.ecosystem.partner_registry."
                   "resolve_partner_application", side_effect=registry_stub):
            out = h.handler(event, None)
        return out["statusCode"], json.loads(out["body"]), enqueued


class TestPartnerAIsAllowed(AuthorizationHarness):
    def test_valid_jwt_and_key_and_entitlement_is_allowed(self):
        code, body, enqueued = self.call(_event())
        self.assertEqual(202, code, body)
        self.assertEqual("QUEUED", body["status"])
        self.assertEqual(1, len(enqueued))
        self.assertEqual(AGENT, enqueued[0]["agent_id"])
        self.assertEqual(CAPABILITY, enqueued[0]["capability"])
        self.assertEqual(PAYLOAD, enqueued[0]["payload"])

    def test_addition_payload_survives_the_boundary_unchanged(self):
        _code, _body, enqueued = self.call(_event())
        item = enqueued[0]
        self.assertEqual(17, item["payload"]["left"])
        self.assertEqual(25, item["payload"]["right"])
        self.assertEqual("user-a", item["user_id"])
        self.assertEqual("tenant-a", item["tenant_id"])

    def test_secret_never_appears_in_the_enqueued_work_item(self):
        _code, body, enqueued = self.call(_event())
        serialized = json.dumps({"work": enqueued, "response": body})
        self.assertNotIn(self.secret, serialized)
        self.assertNotIn("X-Api-Credential", serialized)
        self.assertNotIn("x-api-credential", serialized.lower())


class TestPartnerBIsDenied(AuthorizationHarness):
    def test_partner_without_entitlement_is_denied(self):
        code, _body, enqueued = self.call(
            _event(), sources=self.sources(resolver=_Resolver([]))
        )
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_entitlement_for_another_agent_is_denied(self):
        code, _body, enqueued = self.call(
            _event(),
            sources=self.sources(
                resolver=_Resolver([_entitlement(agent="reference_agent")])
            ),
        )
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_expired_entitlement_is_denied(self):
        """Entitlements are temporal: an elapsed validUntil denies."""
        expired = _entitlement()
        expired["validFrom"] = _ts(-10)
        expired["validUntil"] = _ts(-1)
        code, _body, enqueued = self.call(
            _event(), sources=self.sources(resolver=_Resolver([expired]))
        )
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_withdrawn_entitlement_is_denied(self):
        """Withdrawal deletes the row (no status field) -> denied."""
        code, _body, enqueued = self.call(
            _event(), sources=self.sources(resolver=_Resolver([]))
        )
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_entitlement_not_yet_valid_is_denied(self):
        future = _entitlement()
        future["validFrom"] = _ts(1)
        future["validUntil"] = _ts(30)
        code, _body, enqueued = self.call(
            _event(), sources=self.sources(resolver=_Resolver([future]))
        )
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)


class TestCredentialAndAgentState(AuthorizationHarness):
    def test_wrong_key_is_401(self):
        code, _body, enqueued = self.call(
            _event(credential="ris_" + "z" * 47)
        )
        self.assertEqual(401, code)
        self.assertEqual([], enqueued)

    def test_missing_key_is_401(self):
        code, _body, enqueued = self.call(_event(credential=None))
        self.assertEqual(401, code)
        self.assertEqual([], enqueued)

    def test_revoked_key_is_403(self):
        revoke_credential(self.credentials, self.cid, "admin", "admin")
        code, _body, enqueued = self.call(_event(credential=self.secret))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_inactive_agent_is_denied(self):
        code, _body, enqueued = self.call(
            _event(), sources=self.sources(catalog={AGENT: "INACTIVE"})
        )
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_unknown_agent_is_denied(self):
        code, _body, enqueued = self.call(
            _event(), sources=self.sources(catalog={})
        )
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)


class TestForeignContextIsDenied(AuthorizationHarness):
    def test_foreign_tenant_binding_is_denied(self):
        self.registry_tenant = "tenant-b"
        code, _body, enqueued = self.call(_event())
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_foreign_api_profile_binding_is_denied(self):
        self.registry_profile = "profile-b"
        code, _body, enqueued = self.call(_event())
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_cognito_tenant_does_not_override_the_credential_tenant(self):
        """A different Cognito tenant must not become the execution tenant."""
        code, _body, enqueued = self.call(_event(tenant="tenant-b"))
        # The execution identity comes from the credential profile (tenant-a).
        # Either the request is denied, or it can never execute as tenant-b.
        if code == 202:
            self.assertEqual("tenant-a", enqueued[0]["tenant_id"])
        else:
            self.assertEqual(403, code)
            self.assertEqual([], enqueued)


if __name__ == "__main__":
    unittest.main()
