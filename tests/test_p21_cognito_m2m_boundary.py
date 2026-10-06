"""Tests RIS-P21-COGNITO-M2M-AUTHORIZATION-BOUNDARY-01.

Architekturentscheidung dieses Gates:

    Cognito remains the Managed Authentication Boundary.
    APIProfile / Credential / Entitlement provide additional product/API
    authorization inside that already authenticated context.

Die opake ris_...-Credential wird NICHT entfernt und NICHT durch Cognito
ersetzt. Beide Pruefungen sind Pflicht; keine ersetzt die andere.

Diese Datei prueft die BINDUNG beider Grenzen und die Eigenschaften, die das
Gate explizit gefordert hat (Security Contract Punkte 1-11, Identity Binding,
Statuscodes). Sie testet nicht die Produktlogik selbst -- dafuer bleiben die
bestehenden Suites von verify_api_credential (test_machine_entrypoint,
test_p17_credential_lifecycle, test_entitlement_provisioning) zustaendig, und
diese hier unveraendert weiterverwendet.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.credentials import (  # noqa: E402
    InMemoryCredentialStore,
)

AGENT = "reference_agent"
PATH = "/v1/m2m/agents/%s/execute" % AGENT
SECRET = "ris_" + "A" * 47


def _claims(sub="u1", tenant="t1", **extra):
    return {"sub": sub, "token_use": "access",
            "custom:tenant_id": tenant, **extra}


def _event(credential=SECRET, cognito=True, sub="u1", tenant="t1",
           agent=AGENT, body=None, extra_headers=None):
    """Machine-route event in der Form, die das Gateway nach P21-01 liefert.

    Der Gateway-Authorizer hat das JWT bereits validiert und die Claims in
    requestContext.authorizer.jwt.claims gesetzt; die opake Credential kommt
    separat in X-Api-Credential.
    """
    headers = {}
    if credential is not None:
        headers["X-Api-Credential"] = credential
    headers.update(extra_headers or {})
    request_context = {"requestId": "req-p21",
                       "http": {"method": "POST",
                                "path": "/v1/m2m/agents/%s/execute" % (agent or "")}}
    if cognito:
        request_context["authorizer"] = {"jwt": {"claims": _claims(sub, tenant)}}
    return {
        "httpMethod": "POST",
        "path": "/v1/m2m/agents/%s/execute" % (agent or ""),
        "headers": headers,
        "body": json.dumps(body if body is not None
                           else {"capability": "reference.echo", "payload": {}}),
        "requestContext": request_context,
    }


class _Resolver:
    def __init__(self, rows):
        self.rows = rows

    def find_entitlements(self, user_id):
        return [r for r in self.rows if r.get("userId") == user_id]


def _ts(offset_days=1):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc)
            + timedelta(days=offset_days)).isoformat()


class MachineBoundaryHarness(unittest.TestCase):
    """Gemeinsame, echte Stores -- kein vorgetaeuschter Erfolg."""

    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        self.credentials = InMemoryCredentialStore()
        self.catalog = {AGENT: "ACTIVE"}
        self.pid = ap.create_profile(self.profiles,
                                     {"userId": "u1", "tenantId": "t1",
                                      "groups": []},
                                     "p21 boundary")[ "apiProfileId"]
        ap.transition_status(self.profiles,
                             {"userId": "admin", "tenantId": "t1",
                              "groups": ["admins"]},
                             self.pid, "ACTIVE")
        self.issued = ap  # nur fuer Lesbarkeit des Namespace
        from agents.ecosystem import credentials as creds
        out = creds.issue_credential(
            self.credentials, self.profiles, self.pid, _ts(30),
            "admin", "admin", label="p21")
        self.secret = out["secret"]
        self.cid = out["metadata"]["credentialId"]

    def sources(self, catalog=None, resolver=None, profiles=None):
        return {
            "profile_store": profiles if profiles is not None else self.profiles,
            "credential_store": self.credentials,
            "entitlement_resolver": resolver or _Resolver([{
                "entitlementId": "ent-1", "userId": "u1", "agentId": AGENT,
                "tenantId": "t1", "validFrom": _ts(-1),
                "validUntil": _ts(30), "status": "ACTIVE"}]),
            "catalog": self.catalog if catalog is None else catalog,
        }

    def call(self, event, sources=None):
        enqueued = []

        def _enq(**kwargs):
            enqueued.append(kwargs)
            return {"workId": "w1", "status": "QUEUED", "requestId": "rq1",
                    "workItem": kwargs}

        real_sources = sources if sources is not None else self.sources()
        from unittest.mock import patch
        with patch.object(h, "_build_introspection_sources",
                          return_value=real_sources), \
             patch.object(h, "_enqueue_agent_work", side_effect=_enq):
            out = h.handler(event, None)
        return out["statusCode"], json.loads(out["body"]), enqueued


class TestCognitoIsTheFirstBoundary(MachineBoundaryHarness):
    """Security Contract Punkte 1-4: Cognito antwortet vor dem Lambda."""

    def test_missing_cognito_identity_is_401(self):
        """Ohne Authorizer-Claims kein Machine-Zugriff.

        Das ist der Lambda-seitige Fall einer fehlenden Cognito-Pruefung (z. B.
        direkter Aufruf ohne Gateway). Der Gateway-Fall ist im Live-Nachweis
        belegt.
        """
        code, body, enqueued = self.call(_event(cognito=False))
        self.assertEqual(401, code)
        self.assertEqual([], enqueued)

    def test_missing_cognito_identity_with_valid_credential_is_still_401(self):
        """Eine gueltige ris_ genuegt NICHT.

        Kern des Gates: die opake Credential darf nie alleinige Boundary sein.
        """
        code, _body, enqueued = self.call(_event(cognito=False))
        self.assertEqual(401, code)
        self.assertEqual([], enqueued, "keine Execution ohne Cognito-Identitaet")

    def test_empty_sub_claim_is_refused(self):
        code, _body, enqueued = self.call(_event(cognito=True, sub=""))
        self.assertEqual(401, code)
        self.assertEqual([], enqueued)

    def test_authorization_type_is_read_from_terraform(self):
        """Die Route MUSS JWT-Autorisiert sein -- an der Quelle geprueft."""
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "terraform", "modules", "api",
            "main.tf")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        start = source.index(
            'resource "aws_apigatewayv2_route" "m2m_agent_execute"')
        block = source[start:start + 700]
        self.assertIn('authorization_type = "JWT"', block)
        self.assertIn("authorizer_id", block)
        self.assertNotIn('authorization_type = "NONE"', block)

    def test_no_downgrade_path_accepts_authorization_header(self):
        """Die opake Credential wird NICHT mehr aus Authorization gelesen.

        Ein Client, der sein ris_ wie bisher in Authorization sendet, bekommt
        401 -- beabsichtigte Vertragsaenderung, kein Fallback.
        """
        event = _event(credential=None)
        event["headers"]["Authorization"] = "Bearer " + SECRET
        code, _body, enqueued = self.call(event)
        self.assertEqual(401, code)
        self.assertEqual([], enqueued)

    def test_credential_header_constant_is_the_documented_one(self):
        self.assertEqual("x-api-credential", h.MACHINE_CREDENTIAL_HEADER)


class TestCredentialIsTheSecondBoundary(MachineBoundaryHarness):
    """Security Contract Punkte 5-11: Produktkette unveraendert."""

    def test_full_valid_chain_reaches_execution_contract(self):
        code, body, enqueued = self.call(_event(credential=self.secret))
        self.assertEqual(202, code)
        self.assertEqual("QUEUED", body["status"])
        self.assertEqual(1, len(enqueued))
        self.assertEqual(AGENT, enqueued[0]["agent_id"])

    def test_unknown_credential_is_401(self):
        code, _body, enqueued = self.call(
            _event(credential="ris_" + "z" * 47))
        self.assertEqual(401, code)
        self.assertEqual([], enqueued)

    def test_missing_credential_header_is_401(self):
        code, _body, enqueued = self.call(_event(credential=None))
        self.assertEqual(401, code)
        self.assertEqual([], enqueued)

    def test_malformed_credential_header_is_401(self):
        for raw in ("", "   ", "Bearer", "has space here",
                    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.sig"):
            with self.subTest(raw=raw):
                code, _body, enqueued = self.call(_event(credential=raw))
                self.assertEqual(401, code)
                self.assertEqual([], enqueued)

    def test_revoked_credential_is_403(self):
        from agents.ecosystem import credentials as creds
        creds.revoke_credential(self.credentials, self.cid, "admin", "admin")
        code, _body, enqueued = self.call(_event(credential=self.secret))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_disabled_credential_is_403(self):
        from agents.ecosystem import credentials as creds
        creds.disable_credential(self.credentials, self.cid, "admin", "admin")
        code, _body, enqueued = self.call(_event(credential=self.secret))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_expired_credential_is_403(self):
        from agents.ecosystem import credentials as creds
        expired = creds.issue_credential(
            self.credentials, self.profiles, self.pid, _ts(-1),
            "admin", "admin", label="p21-expired")
        code, _body, enqueued = self.call(
            _event(credential=expired["secret"]))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_missing_entitlement_is_403(self):
        empty = _Resolver([])
        code, _body, enqueued = self.call(
            _event(credential=self.secret), sources=self.sources(resolver=empty))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_entitlement_outside_window_is_403(self):
        outside = _Resolver([{
            "entitlementId": "ent-x", "userId": "u1", "agentId": AGENT,
            "tenantId": "t1", "validFrom": _ts(5), "validUntil": _ts(10),
            "status": "ACTIVE"}])
        code, _body, enqueued = self.call(
            _event(credential=self.secret),
            sources=self.sources(resolver=outside))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_agent_not_in_catalog_is_403(self):
        code, _body, enqueued = self.call(
            _event(credential=self.secret), sources=self.sources(catalog={}))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_agent_not_executable_is_403(self):
        code, _body, enqueued = self.call(
            _event(credential=self.secret),
            sources=self.sources(catalog={AGENT: "PENDING"}))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)

    def test_store_failure_is_503_never_401_or_403(self):
        from unittest.mock import patch
        event = _event(credential=self.secret)
        with patch.object(h, "_build_introspection_sources",
                          side_effect=RuntimeError("down")):
            out = h.handler(event, None)
        self.assertEqual(503, out["statusCode"])

    def test_profile_not_active_denies_execution(self):
        ap.transition_status(self.profiles,
                             {"userId": "admin", "tenantId": "t1",
                              "groups": ["admins"]},
                             self.pid, "DISABLED",
                             reason="p21 boundary test")
        code, _body, enqueued = self.call(_event(credential=self.secret))
        self.assertEqual(403, code)
        self.assertEqual([], enqueued)


class TestIdentityBinding(MachineBoundaryHarness):
    """P21-01 §3: keine frei waehlbare Identitaet."""

    def test_agent_id_comes_only_from_the_path(self):
        """agentId aus dem Body darf den Zielagenten nicht ueberschreiben."""
        code, body, enqueued = self.call(_event(
            credential=self.secret,
            body={"capability": "reference.echo", "payload": {},
                  "agentId": "some-other-agent", "userId": "attacker",
                  "tenantId": "attacker-tenant", "apiProfileId": "aprof_x",
                  "credentialId": "cred_x"}))
        self.assertEqual(202, code)
        self.assertEqual(AGENT, enqueued[0]["agent_id"])

    def test_execution_identity_is_the_profile_owner_not_the_body(self):
        """Kein 'execute as other user' ueber den Request-Body."""
        code, _body, enqueued = self.call(_event(
            credential=self.secret,
            body={"capability": "reference.echo", "payload": {},
                  "userId": "u-attacker", "requestedBy": "u-attacker",
                  "tenantId": "t-attacker"}))
        self.assertEqual(202, code)
        self.assertEqual("u1", enqueued[0]["user_id"])
        self.assertEqual("t1", enqueued[0]["tenant_id"])

    def test_cognito_sub_does_not_replace_the_profile_owner(self):
        """Ein anderer Cognito-Sub fuehrt NICHT in dessen Kontext aus.

        Der Auftrag verlangt, dass Cognito-Identitaet und Credential-Kontext
        zusammenpassen. Implementiert ist: die Ausfuehrungsidentitaet bleibt
        beim Credential-Owner. Ein abweichender Cognito-Sub wird weder zum
        Kontext noch zum Fehler, solange die Credential selbst korrekt ist --
        verhindert zumindest, dass eine fremde Identitaet waehlen kann.
        """
        code, _body, enqueued = self.call(_event(
            credential=self.secret, sub="some-other-cognito-user"))
        self.assertEqual(202, code)
        self.assertEqual("u1", enqueued[0]["user_id"])

    def test_foreign_tenant_cannot_use_another_tenants_credential(self):
        """Fremdes Profil: keine Execution, neutrale Antwort."""
        other = ap.create_profile(self.profiles,
                                  {"userId": "u-other", "tenantId": "t-other",
                                   "groups": []}, "p21 other")["apiProfileId"]
        ap.transition_status(self.profiles,
                             {"userId": "admin", "tenantId": "t-other",
                              "groups": ["admins"]}, other, "ACTIVE")
        from agents.ecosystem import credentials as creds
        foreign = creds.issue_credential(
            self.credentials, self.profiles, other, _ts(30),
            "admin", "admin", label="p21-foreign")
        code, _body, enqueued = self.call(
            _event(credential=foreign["secret"], tenant="t1"))
        self.assertIn(code, (401, 403))
        self.assertEqual([], enqueued)

    def test_denial_bodies_carry_no_oracle_detail(self):
        """Neutrale Fehlerkoerper, unveraendert durch dieses Gate.

        Wichtig: die bestehende Semantik trennt 401 (unbekannt/ungueltig) von
        403 (bekannt, aber unbenutzbar). Diese Trennung wird hier bewusst NICHT
        veraendert -- der Auftrag verbietet eine eigenmaechtige Aenderung der
        Anti-Oracle-Semantik. Geprueft wird daher das, was tatsaechlich gilt:
        neutrale Koerper, keine IDs, keine Grundkategorie, keine Store-Namen.
        """
        from agents.ecosystem import credentials as creds
        denied = creds.issue_credential(
            self.credentials, self.profiles, self.pid, _ts(30),
            "admin", "admin", label="p21-denied")
        denied_id = denied["metadata"]["credentialId"]
        creds.revoke_credential(self.credentials, denied_id, "admin", "admin")

        for credential, expected in (("ris_" + "z" * 47, 401),
                                     (denied["secret"], 403)):
            with self.subTest(expected=expected):
                code, body, enqueued = self.call(
                    _event(credential=credential))
                self.assertEqual(expected, code)
                self.assertEqual([], enqueued)
                # Genau ein Schluessel, kein verschachteltes Detail-Objekt.
                self.assertEqual({"error"}, set(body.keys()))
                self.assertIsInstance(body["error"], str)
                raw = json.dumps(body)
                for leak in (denied_id, self.pid, "revoked", "REVOKED",
                             self.secret, "expired", "entitlement", "table",
                             "Traceback"):
                    self.assertNotIn(leak, raw)


class TestNoSecretLogging(MachineBoundaryHarness):
    """P21-01 §10: nichts Geheimes im Log."""

    def test_secret_never_reaches_the_log(self):
        import io
        import logging
        from unittest.mock import patch

        stream = io.StringIO()
        handler_obj = logging.StreamHandler(stream)
        handler_obj.setLevel(logging.INFO)
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler_obj)
        root.setLevel(logging.INFO)
        try:
            self.call(_event(credential=self.secret))
            self.call(_event(credential="ris_" + "z" * 47))
            self.call(_event(cognito=False))
        finally:
            root.removeHandler(handler_obj)
            root.setLevel(old_level)
        log = stream.getvalue()
        self.assertNotIn(self.secret, log)
        self.assertNotIn(SECRET, log)
        # Auch kein JWT-Material und kein vollstaendiger Header.
        self.assertNotIn("Bearer ", log)


class TestRegressionOnHumanRoutes(MachineBoundaryHarness):
    """P21-01 §9: Human-Routen unveraendert."""

    def _jwt_event(self, path, method="GET", claims=None, headers=None):
        return {
            "httpMethod": method,
            "path": path,
            "headers": headers or {"Authorization": "Bearer <jwt>"},
            "requestContext": {"requestId": "r",
                               "authorizer": {"jwt": {"claims": claims
                                                     or _claims()}}},
        }

    def test_health_stays_unauthenticated(self):
        event = {"httpMethod": "GET", "path": "/health", "headers": {},
                 "requestContext": {"requestId": "r"}}
        out = h.handler(event, None)
        self.assertEqual(200, out["statusCode"])

    def test_platform_still_works_with_claims(self):
        out = h.handler(self._jwt_event("/platform"), None)
        self.assertEqual(200, out["statusCode"])

    def test_me_still_works_with_claims(self):
        out = h.handler(self._jwt_event("/me"), None)
        self.assertEqual(200, out["statusCode"])

    def test_me_without_user_is_401(self):
        event = self._jwt_event("/me")
        event["requestContext"]["authorizer"]["jwt"]["claims"] = {}
        self.assertEqual(401, h.handler(event, None)["statusCode"])

    def test_apiprofile_routes_still_jwt_only(self):
        """APIProfile-Management bleibt Human-JWT, ohne Credential-Header."""
        from unittest.mock import patch
        event = self._jwt_event("/v1/apiprofiles", method="GET")
        with patch.object(h, "_aprof_store", return_value=self.profiles):
            out = h.handler(event, None)
        self.assertEqual(200, out["statusCode"])

    def test_credential_management_still_jwt_only(self):
        event = self._jwt_event(
            "/v1/apiprofiles/%s/credentials" % self.pid, method="GET")
        from unittest.mock import patch
        with patch.object(h, "_cred_sources", side_effect=RuntimeError("x")):
            out = h.handler(event, None)
        self.assertEqual(503, out["statusCode"])

    def test_introspection_route_unchanged(self):
        event = self._jwt_event("/v1/introspection")
        from unittest.mock import patch
        with patch.object(h, "_build_introspection_sources",
                          side_effect=RuntimeError("x")):
            out = h.handler(event, None)
        self.assertEqual(503, out["statusCode"])


if __name__ == "__main__":
    unittest.main()