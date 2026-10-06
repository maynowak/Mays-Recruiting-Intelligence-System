"""Tests RIS-P20-API-CONTRACT-AND-HEALTH-01, Scope 1: GET /health.

P20-Discovery-01 finding H: the route and its integration already existed in
terraform/modules/api/main.tf, but lambda/handler.py had no branch for
/health, so every probe fell through to the generic 404 at the end of
_handle_api_event. Live proof before the fix: HTTP 404 three times.

These tests pin the repaired contract and the two properties that make it
usable as an infrastructure probe:

  * it answers 200 with the documented minimal body, and
  * it answers WITHOUT touching DynamoDB, Cognito or SQS, so a dependency
    outage cannot mark a startable Lambda as unhealthy.

The second point is a design decision, not an accident. /platform stays the
JWT-protected dependency-aware endpoint; /health is liveness only.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402


def _event(method="GET", path="/health"):
    """API Gateway HTTP API (payload 2.0) event, as the live route delivers."""
    return {
        "routeKey": "%s %s" % (method, path),
        "path": path,
        "httpMethod": method,
        "headers": {},
        "requestContext": {
            "http": {"method": method, "path": path},
            "requestId": "req-health-test",
        },
    }


class TestHealthContract(unittest.TestCase):
    """The repaired contract of GET /health."""

    def test_health_returns_200(self):
        response = h._handle_api_event(_event(), None)
        self.assertEqual(200, response["statusCode"])

    def test_health_body_is_minimal_and_json(self):
        response = h._handle_api_event(_event(), None)
        body = json.loads(response["body"])
        self.assertEqual("ok", body["status"])
        # Every documented key must be present, and nothing beyond the
        # documented minimum -- otherwise an operator starts depending on
        # fields this endpoint never promised.
        self.assertEqual(
            {"status", "service", "version", "environment"},
            set(body.keys()))

    def test_health_service_identity_matches_platform_endpoint(self):
        """The probe must be attributable to this service, so an operator
        hitting a misrouted endpoint sees who answered."""
        body = json.loads(h._handle_api_event(_event(), None)["body"])
        platform = json.loads(h._handle_api_event(
            _event(path="/platform"), None)["body"])["platform"]
        self.assertEqual(platform["name"], body["service"])
        self.assertEqual(platform["version"], body["version"])
        self.assertEqual(platform["environment"], body["environment"])

    def test_health_never_reveals_secrets(self):
        """Anonymous endpoint: the body must not carry configuration."""
        raw = h._handle_api_event(_event(), None)["body"]
        for forbidden in ("table", "Table", "secret", "Secret", "token",
                          "pool", "Pool", "arn", "Arn", "AWS_"):
            self.assertNotIn(forbidden, raw)


class TestHealthIsDependencyFree(unittest.TestCase):
    """/health must stay answerable while a dependency is down.

    A probe that reads DynamoDB would report the target unhealthy whenever
    the table is unreachable -- even though the Lambda is startable and would
    serve correctly. That is the wrong signal for a load balancer.
    """

    def _boom(self, *args, **kwargs):
        raise AssertionError(
            "GET /health must not perform I/O; it is a liveness probe")

    def test_health_survives_missing_store_configuration(self):
        # Unset every store variable the handler consults elsewhere.
        for var in ("API_PROFILES_TABLE", "CREDENTIALS_TABLE",
                    "ENTITLEMENTS_TABLE", "AGENT_CATALOG_TABLE",
                    "USER_PROFILE_TABLE", "WORK_ITEMS_TABLE"):
            os.environ.pop(var, None)
        self.assertEqual(
            200, h._handle_api_event(_event(), None)["statusCode"])

    def test_health_survives_unavailable_dynamodb(self):
        original = h._get_dynamodb
        h._get_dynamodb = self._boom
        try:
            response = h._handle_api_event(_event(), None)
        finally:
            h._get_dynamodb = original
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("ok", json.loads(response["body"])["status"])

    def test_health_is_first_dispatch_branch(self):
        """Ordering matters: /health must be matched before any prefix
        dispatch, otherwise a future refactor could route it elsewhere."""
        source = (
            open(h.__file__, encoding="utf-8").read()
        )
        dispatch = source[source.index("def _handle_api_event"):
                          source.index("def _handle_health")]
        self.assertLess(dispatch.index("'/health'"),
                        dispatch.index("'/v1/apiprofiles'"))


class TestHealthRouteBoundary(unittest.TestCase):
    """The repair must not widen the auth boundary."""

    def test_health_needs_no_authentication(self):
        """AuthorizationType NONE in Terraform, so the handler must not
        demand a JWT."""
        response = h._handle_api_event(_event(), None)
        self.assertEqual(200, response["statusCode"])

    def test_health_ignores_a_foreign_bearer(self):
        """An unrelated token must neither authorize nor break the probe."""
        event = _event()
        event["headers"] = {"Authorization": "Bearer not-a-real-token"}
        self.assertEqual(200, h._handle_api_event(event, None)["statusCode"])

    def test_platform_relies_on_the_gateway_authorizer(self):
        """Guard against the repair accidentally changing /platform.

        /platform authenticates at the API Gateway JWT authorizer, not in the
        Lambda: _handle_platform intentionally performs no claim check, which
        is why it answers 200 even without claims. Its protection is
        authorization_type = "JWT" in terraform/modules/api. Asserting 401
        here would assert behaviour the code does not have.
        """
        response = h._handle_api_event(_event(path="/platform"), None)
        self.assertEqual(200, response["statusCode"])

    def test_machine_route_rejects_jwt_as_credential(self):
        """Two NONE routes exist; the machine one stays credential-bound.

        A Cognito JWT is a syntactically well-formed Bearer, so it passes the
        transport shape check and is then refused by the central verifier
        (verify_api_credential), which finds no matching digest. This is the
        real production path, exercised against the real verifier with
        in-memory stores -- no simplified stand-in is used here.
        """
        from agents.ecosystem import api_profiles as ap
        from agents.ecosystem.credentials import InMemoryCredentialStore

        class _EmptyResolver:
            def find_entitlements(self, user_id):
                return []

        sources = {
            "credential_store": InMemoryCredentialStore(),
            "profile_store": ap.InMemoryApiProfileStore(),
            "entitlement_resolver": _EmptyResolver(),
            "catalog": {},
        }
        original = h._build_introspection_sources
        h._build_introspection_sources = lambda: sources
        try:
            for header in ("Bearer eyJhbGciOi.eyJzdWIi.sig", "Bearer nope",
                           "Bearer "):
                event = _event(
                    "POST", "/v1/m2m/agents/reference_agent/execute")
                event["headers"] = {"Authorization": header}
                response = h._handle_api_event(event, None)
                self.assertNotEqual(202, response["statusCode"], header)
                self.assertIn(response["statusCode"], (401, 403), header)
        finally:
            h._build_introspection_sources = original

    def test_machine_route_rejects_missing_authorization(self):
        event = _event("POST", "/v1/m2m/agents/reference_agent/execute")
        response = h._handle_api_event(event, None)
        # No Authorization header at all: refused outright, before any store
        # is needed. Never an execution.
        self.assertEqual(401, response["statusCode"])


if __name__ == "__main__":
    unittest.main()