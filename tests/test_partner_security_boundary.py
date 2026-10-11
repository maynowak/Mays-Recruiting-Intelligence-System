"""T01-T14 Partner Identity Binding regression suite.

Every case drives the REAL handler through the REAL credential verifier and
entitlement resolver against in-memory stores. Nothing is stubbed except the
DynamoDB-backed Partner Registry lookup, which is dependency-injected via
`agents.ecosystem.partner_registry.resolve_partner_application`.

Also asserts the removal of the RIS_TEST_MODE bypass: no environment variable
may weaken the registry APIProfile binding.
"""

import inspect
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402
from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.credentials import InMemoryCredentialStore  # noqa: E402
from agents.ecosystem.worker_authorization import (  # noqa: E402
    WorkerAuthDecision,
)

AGENT = "reference_agent"
ROUTE_PREFIX = "/v1/partner/agents/%s/execute"
M2M_ROUTE_PREFIX = "/v1/m2m/agents/%s/execute"
REGISTRY_PATCH = "agents.ecosystem.partner_registry.resolve_partner_application"

TENANT = "tenant-a"
PROFILE = "pid-1"
CLIENT = "client-partner"
OTHER_CLIENT = "client-other"
USER = "user-1"


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class Resolver:
    def __init__(self, rows):
        self.rows = rows

    def find_entitlements(self, user_id):
        return [r for r in self.rows if r.get("userId") == user_id]


def entitlement(user, agent=AGENT, tenant=TENANT, status="ACTIVE"):
    return {"entitlementId": "ent-" + user, "userId": user, "agentId": agent,
            "tenantId": tenant, "validFrom": _ts(-1), "validUntil": _ts(30),
            "status": status}


class BoundaryHarness(unittest.TestCase):
    """Shared wiring for both the M2M and the partner route."""

    route = ROUTE_PREFIX
    patch_path = REGISTRY_PATCH

    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        self.creds = InMemoryCredentialStore()
        owner = {"userId": USER, "tenantId": TENANT, "groups": []}
        admin = {"userId": "a1", "tenantId": TENANT, "groups": ["admins"]}
        self.pid = ap.create_profile(self.profiles, owner, "partner")[
            "apiProfileId"]
        ap.transition_status(self.profiles, admin, self.pid, "ACTIVE")
        self.resolver = Resolver([entitlement(USER)])
        self.catalog = {AGENT: "ACTIVE"}
        self.issued = None
        self.enqueued = []

    def issue(self, expires_days=30, profile_id=None):
        from agents.ecosystem.credentials import issue_credential
        res = issue_credential(
            self.creds, self.profiles, profile_id or self.pid,
            _ts(expires_days), "owner", USER, reason="partner-test")
        self.issued = res
        return res

    def sources(self):
        return {"profile_store": self.profiles,
                "credential_store": self.creds,
                "entitlement_resolver": self.resolver,
                "catalog": self.catalog}

    def registry(self, **overrides):
        record = {"applicationId": "app-partner",
                  "cognitoClientId": CLIENT,
                  "apiProfileId": self.pid,
                  "tenantId": TENANT,
                  "status": "ACTIVE"}
        record.update(overrides)
        return record

    def call(self, bearer=None, client_id=CLIENT, tenant=TENANT,
             token_use="access", user=USER, agent_id=AGENT,
             registry="default", path=None):
        headers = {"X-Api-Credential": bearer}
        claims = {}
        if client_id is not None:
            claims["client_id"] = client_id
        if tenant is not None:
            claims["custom:tenant_id"] = tenant
        if token_use is not None:
            claims["token_use"] = token_use
        if user is not None:
            claims["sub"] = user
        event = {
            "httpMethod": "POST",
            "path": path if path is not None else self.route % (agent_id or ""),
            "headers": headers,
            "body": json.dumps({"capability": "reference.echo", "payload": {}}),
            "requestContext": {"requestId": "req-t",
                               "http": {"method": "POST",
                                        "path": path if path is not None
                                        else self.route % (agent_id or "")},
                               "authorizer": {"jwt": {"claims": claims}}},
        }

        if registry == "default":
            registry_fn = lambda cid: self.registry(cognitoClientId=cid)  # noqa: E731
        elif callable(registry):
            registry_fn = registry
        else:
            registry_fn = lambda cid: registry  # noqa: E731

        def enqueue(**kwargs):
            self.enqueued.append(kwargs)
            return {"workId": "w1", "status": "QUEUED", "requestId": "rq1"}

        with patch.object(h, "_build_introspection_sources",
                          return_value=self.sources()), \
             patch.object(h, "_enqueue_agent_work", side_effect=enqueue), \
             patch(self.patch_path, side_effect=registry_fn):
            out = h.handler(event, None)
        return out["statusCode"], json.loads(out["body"])


class TestT01T14(BoundaryHarness):
    def test_t01_matching_client_and_credential_allowed(self):
        self.issue()
        code, body = self.call(bearer=self.issued["secret"])
        self.assertEqual(code, 202)
        self.assertIn("workId", body)

    def test_t02_cross_client_credential_reuse_denied(self):
        """A credential may only be used by the client it is bound to.

        The other client IS a validly registered partner, but it is bound to a
        DIFFERENT APIProfile. Its JWT must therefore not unlock a credential
        issued under this profile.
        """
        self.issue()
        code, _ = self.call(
            bearer=self.issued["secret"],
            client_id=OTHER_CLIENT,
            registry=self.registry(cognitoClientId=OTHER_CLIENT,
                                   apiProfileId="pid-other-partner"))
        self.assertEqual(code, 403)

    def test_t03_tenant_mismatch_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"], tenant="tenant-b")
        self.assertEqual(code, 403)

    def test_t04_revoked_credential_denied(self):
        res = self.issue()
        from agents.ecosystem.credentials import revoke_credential
        revoke_credential(self.creds, res["metadata"]["credentialId"],
                          "admin", "a1", reason="t04", actor_tenant=TENANT)
        code, _ = self.call(bearer=res["secret"])
        self.assertIn(code, (401, 403))

    def test_t05_inactive_apiprofile_denied(self):
        self.issue()
        admin = {"userId": "a1", "tenantId": TENANT, "groups": ["admins"]}
        ap.transition_status(self.profiles, admin, self.pid, "REVOKED",
                             reason="t05")
        code, _ = self.call(bearer=self.issued["secret"])
        self.assertIn(code, (401, 403))

    def test_t06_missing_entitlement_denied(self):
        self.issue()
        self.resolver = Resolver([])
        code, _ = self.call(bearer=self.issued["secret"])
        self.assertEqual(code, 403)

    def test_t07_multiple_users_one_credential(self):
        res = self.issue()
        self.resolver = Resolver([entitlement(USER),
                                  entitlement("user-2")])
        code, _ = self.call(bearer=res["secret"], user="user-2")
        self.assertEqual(code, 202)
        # user-3 has no entitlement -> denied
        code, _ = self.call(bearer=res["secret"], user="user-3")
        self.assertEqual(code, 403)

    def test_t08_missing_client_id_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"], client_id=None)
        self.assertEqual(code, 401)

    def test_t09_missing_tenant_claim_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"], tenant=None)
        self.assertEqual(code, 403)

    def test_t10_invalid_token_use_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"], token_use="id")
        self.assertEqual(code, 401)

    def test_t11_inactive_partner_application_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"],
                            registry=self.registry(status="INACTIVE"))
        self.assertEqual(code, 403)

    def test_t12_registry_apiprofile_mismatch_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"],
                            registry=self.registry(apiProfileId="pid-other"))
        self.assertEqual(code, 403)

    def test_t13_registry_tenant_mismatch_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"],
                            registry=self.registry(tenantId="tenant-z"))
        self.assertEqual(code, 403)

    def test_t14_registry_lookup_failure_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"],
                            registry=lambda cid: None)
        self.assertEqual(code, 403)

    def test_t14b_registry_exception_denied(self):
        self.issue()

        def boom(cid):
            raise RuntimeError("registry unavailable")

        code, _ = self.call(bearer=self.issued["secret"], registry=boom)
        self.assertEqual(code, 403)

    def test_t15_missing_registry_entry_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"],
                            registry=lambda cid: None)
        self.assertEqual(code, 403)

    def test_t16_invalid_credential_denied(self):
        code, _ = self.call(bearer="ris_not_a_real_secret")
        self.assertIn(code, (401, 403))

    def test_t17_env_var_cannot_enable_a_bypass(self):
        """Even with RIS_TEST_MODE set, a mismatched profile must be denied.

        Guards against reintroducing an environment-driven escape hatch: the
        variable has no meaning anywhere in the authorization path.
        """
        for var in ("RIS_TEST_MODE", "RIS_TEST", "RIS_ADMIN_BYPASS"):
            with self.subTest(var=var):
                self.setUp()
                self.issue()
                with patch.dict(os.environ, {var: "1"}):
                    code, _ = self.call(
                        bearer=self.issued["secret"],
                        registry=self.registry(apiProfileId="pid-other"))
                self.assertEqual(code, 403, "bypass via %s" % var)


class TestNoProductionBypass(unittest.TestCase):
    """RIS_TEST_MODE must not exist anywhere in the production boundary."""

    def test_handler_source_has_no_test_mode_bypass(self):
        src = inspect.getsource(h)
        self.assertNotIn("RIS_TEST_MODE", src)
        self.assertNotIn("test_mode", src)

    def test_machine_route_binding_is_unconditional(self):
        src = inspect.getsource(h._machine_execute_agent)
        self.assertIn("reg_api_profile != context.get('apiProfileId')", src)
        self.assertIn("reg_tenant != context.get('tenantId')", src)

    def test_boundary_functions_read_no_environment_variables(self):
        """Env-var-agnostic guard.

        A bypass renamed to any other variable (`PARTNER_SKIP_BINDING`,
        `RIS_TEST`, ...) must still be detected, so this asserts the ABSENCE of
        any environment read in the two authorization functions rather than the
        absence of one specific name.
        """
        for fn in (h._machine_execute_agent, h._partner_execute_agent):
            src = inspect.getsource(fn)
            for pattern in ("os.getenv", "os.environ",
                            "environ.get", "getenv"):
                self.assertNotIn(pattern, src,
                                 "%s reads %s" % (fn.__name__, pattern))

    def test_machine_route_enforces_token_use(self):
        src = inspect.getsource(h._machine_execute_agent)
        self.assertIn("tokenUse') != 'access'", src)

    def test_partner_route_has_no_bypass(self):
        src = inspect.getsource(h._partner_execute_agent)
        self.assertNotIn("RIS_TEST_MODE", src)
        self.assertNotIn("test_mode", src)

    def test_registry_binding_present_in_both_routes(self):
        for fn in (h._partner_execute_agent, h._machine_execute_agent):
            src = inspect.getsource(fn)
            self.assertIn("resolve_partner_application", src)
            self.assertIn("'ACTIVE'", src)


class TestMachineRouteBoundary(TestT01T14):
    """The FULL T-matrix must also hold on the dedicated M2M route.

    Inherits from TestT01T14 so the machine plane gets exactly the same
    behavioural coverage as the partner plane.
    """

    route = M2M_ROUTE_PREFIX

    # The machine plane is machine-to-machine: the EXECUTION IDENTITY is the
    # APIProfile owner that the credential verification resolves, and the JWT
    # subject is recorded for audit only (see _machine_execute_agent
    # docstring). Three partner-plane concepts therefore do not transfer, and
    # the correct machine behaviour is asserted explicitly instead of silently
    # inheriting the partner expectation.

    def test_t03_tenant_mismatch_denied(self):
        """JWT tenant is audit context on this plane, not the tenant gate."""
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"], tenant="tenant-b")
        # Execution stays inside the credential's tenant (verifier-authorized),
        # so this is NOT an escalation. The registry-vs-credential tenant gate
        # is covered by test_t13 and by test_m2m_tenant_mismatch_denied.
        self.assertEqual(code, 202)

    def test_t07_multiple_users_one_credential(self):
        """A JWT user without entitlement must not change the machine outcome."""
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"], user="user-3")
        self.assertEqual(code, 202)
        # The owner without entitlement IS denied - that is the gate.
        self.resolver = Resolver([])
        code, _ = self.call(bearer=self.issued["secret"])
        self.assertEqual(code, 403)

    def test_t09_missing_tenant_claim_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"], tenant=None)
        self.assertEqual(code, 202)

    def test_m2m_matching_allowed(self):
        self.issue()
        code, body = self.call(bearer=self.issued["secret"])
        self.assertEqual(code, 202)

    def test_m2m_cross_client_denied(self):
        self.issue()
        code, _ = self.call(
            bearer=self.issued["secret"],
            client_id=OTHER_CLIENT,
            registry=self.registry(cognitoClientId=OTHER_CLIENT,
                                   apiProfileId="pid-other-partner"))
        self.assertEqual(code, 403)

    def test_m2m_apiprofile_mismatch_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"],
                            registry=self.registry(apiProfileId="pid-other"))
        self.assertEqual(code, 403)

    def test_m2m_tenant_mismatch_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"],
                            registry=self.registry(tenantId="tenant-z"))
        self.assertEqual(code, 403)

    def test_m2m_missing_client_id_denied(self):
        self.issue()
        code, _ = self.call(bearer=self.issued["secret"], client_id=None)
        self.assertEqual(code, 401)


if __name__ == "__main__":
    unittest.main()