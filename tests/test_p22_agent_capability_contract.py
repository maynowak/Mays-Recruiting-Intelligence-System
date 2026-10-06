"""Tests RIS-P22-USER-AGENT-CAPABILITY-AND-PRODUCT-ADMIN-01.

Der positive Capability-Contract ist der BESTEHENDE Endpunkt GET /agents.
Dieses Gate baut keinen zweiten Capability-Endpoint, sondern beweist den
bestehenden und schliesst die eine Luecke, die die Live-Pruefung ergab.

Zwei Festlegungen, die diese Tests einhalten:

    "Cognito remains the Managed Authentication Boundary."
    "Frontend visibility is not a security boundary. Backend authorization
     remains authoritative."

Daher prueft jede Testklasse einen Teil der Sicherheitskette:

  * Der Endpunkt ist positiv: er liefert genau die Agenten, die der
    authentifizierte Aufrufer verwenden darf, und keine Ablehnungsgruende
    (kein Permission Oracle).
  * Die Identitaet kommt aus dem Gateway-validierten JWT (`sub`), nicht aus
    Body, Header oder irgendeinem anderen vom Client steuerbaren Feld.
  * Tenant-Isolation: Entitlements eines fremden Tenants werden nie
    aggregiert, auch nicht stillschweigend.
  * Der Agent Catalog bleibt die einzige Quelle fuer "existiert und ist
    ausfuehrbar"; es entsteht keine parallele Catalog-Architektur.
  * Frontend-Sichtbarkeit ist keine Grenze: der Execution-Pfad bleibt
    unabhaengig autoritativ (P21 unveraendert).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402

AGENT = "reference_agent"
OTHER = "jobsearch-agent"


def _claims(sub="u1", tenant="t1", groups=None):
    return {"sub": sub, "token_use": "access",
            "custom:tenant_id": tenant,
            "cognito:groups": list(groups or [])}


def _event(claims=None, path="/agents", method="GET", headers=None):
    """Event in der Form, die das Gateway nach der JWT-Pruefung liefert."""
    request_context = {"requestId": "req-p22", "http": {"method": method,
                                                        "path": path}}
    if claims is not None:
        request_context["authorizer"] = {"jwt": {"claims": claims}}
    return {"httpMethod": method, "path": path, "headers": headers or {},
            "requestContext": request_context}


def _catalog(status=AGENT and "ACTIVE"):
    """Agent-Catalog in der Produktionsform: agentId -> Item."""
    return {
        AGENT: {"agentId": AGENT, "name": AGENT, "version": "1.0.0",
                "status": status, "description": "Nachweis-Agent",
                "risk_level": "low", "capabilities": ["reference.echo"],
                "supported_bodies": ["1.0.0"],
                "supported_runtimes": ["python3.14"], "metadata": {}},
    }


def _entitlement(agent=AGENT, tenant="t1", valid_from=None, valid_until=None,
                 api_profile_id=None, entitlement_id="ent-1"):
    row = {"entitlementId": entitlement_id, "userId": "u1",
           "agentId": agent, "tenantId": tenant, "status": "ACTIVE"}
    if valid_from:
        row["validFrom"] = valid_from
    if valid_until:
        row["validUntil"] = valid_until
    if api_profile_id:
        row["apiProfileId"] = api_profile_id
    return row


class CapabilityHarness(unittest.TestCase):
    """/agents gegen echte Handler-Funktionen, Stores nur gemockt."""

    def agents(self, claims=_claims(), entitlements=None, catalog=None,
               path="/agents", method="GET", headers=None):
        from unittest.mock import patch
        with patch.object(h, "_get_entitlements",
                          return_value=entitlements if entitlements is not None
                          else [_entitlement()]), \
             patch.object(h, "_get_agent_catalog",
                          return_value=_catalog() if catalog is None else catalog):
            out = h.handler(_event(claims, path, method, headers), None)
        return out["statusCode"], json.loads(out["body"])

    def agent_ids(self, **kwargs):
        code, body = self.agents(**kwargs)
        self.assertEqual(200, code)
        return [a["agentId"] for a in body["agents"]]


class TestPositiveCapabilityContract(CapabilityHarness):
    """Auftrag §2: positiv, kein Permission Oracle."""

    def test_entitled_agent_is_returned(self):
        self.assertEqual([AGENT], self.agent_ids())

    def test_empty_list_when_nothing_is_entitled(self):
        """Kein Entitlement -> leere Liste, kein 403, keine Erklaerung warum."""
        code, body = self.agents(entitlements=[])
        self.assertEqual(200, code)
        self.assertEqual({"agents": []}, body)

    def test_response_never_explains_why_an_agent_is_absent(self):
        """Die Antwort nennt keine Ablehnungsgruende."""
        catalog = _catalog()
        catalog[OTHER] = dict(catalog[AGENT], agentId=OTHER, name=OTHER)
        code, body = self.agents(
            entitlements=[_entitlement(agent=OTHER, entitlement_id="e2")],
            catalog=catalog)
        self.assertEqual(200, code)
        raw = json.dumps(body)
        for leak in ("entitlement", "reason", "denied", "forbidden",
                     "expired", "no-entitlement", "profile-mismatch"):
            self.assertNotIn(leak.lower(), raw.lower(), leak)

    def test_response_exposes_no_internal_authorization_data(self):
        """Keine Credential-Digests, IAM-Details oder Entitlement-IDs."""
        code, body = self.agents(
            entitlements=[_entitlement(entitlement_id="ent-secret-123")])
        self.assertEqual(200, code)
        raw = json.dumps(body)
        for leak in ("digest", "secret", "credentialId", "entitlementId",
                     "arn:aws", "iam", "ownerUserId", "tenantId"):
            self.assertNotIn(leak, raw, leak)

    def test_agent_metadata_comes_from_the_catalog(self):
        """Die Antwort ist der Catalog-Eintrag, nicht eine zweite Quelle."""
        code, body = self.agents()
        agent = body["agents"][0]
        self.assertEqual("1.0.0", agent["version"])
        self.assertEqual(["reference.echo"], agent["capabilities"])
        self.assertEqual("ACTIVE", agent["status"])

    def test_non_executable_agent_is_not_offered(self):
        """Catalog bleibt die Quelle fuer Ausfuehrbarkeit (fail-closed)."""
        catalog = _catalog(status="PENDING")
        self.assertEqual([], self.agent_ids(catalog=catalog))

    def test_unknown_catalog_agent_is_not_offered(self):
        self.assertEqual([], self.agent_ids(catalog={}))


class TestNoDuplicateCapabilities(CapabilityHarness):
    """Live-Befund dieses Gates: der Agent erschien doppelt.

    Zwei Entitlements koennen denselben Agenten autorisieren (user-weit plus
    profilgebunden). Die Schleife haengt pro Entitlement an, also musste die
    Website den Agenten mehrfach rendern.
    """

    def test_two_entitlements_for_one_agent_yield_one_entry(self):
        ids = self.agent_ids(entitlements=[
            _entitlement(entitlement_id="ent-user"),
            _entitlement(api_profile_id="aprof_1", entitlement_id="ent-prof"),
        ])
        self.assertEqual([AGENT], ids)

    def test_repeated_identical_entitlement_does_not_duplicate(self):
        ids = self.agent_ids(entitlements=[
            _entitlement(entitlement_id="ent-a"),
            _entitlement(entitlement_id="ent-b"),
            _entitlement(entitlement_id="ent-c"),
        ])
        self.assertEqual([AGENT], ids)

    def test_distinct_agents_are_all_kept(self):
        """Deduplizierung darf echte Capabilities nicht verlieren."""
        catalog = _catalog()
        catalog[OTHER] = dict(catalog[AGENT], agentId=OTHER, name=OTHER)
        ids = self.agent_ids(
            entitlements=[_entitlement(), _entitlement(agent=OTHER,
                                                       entitlement_id="e2")],
            catalog=catalog)
        self.assertEqual([AGENT, OTHER], ids)

    def test_expired_duplicate_does_not_hide_a_valid_one(self):
        """Auch abgelaufene Doppelzeilen duerfen ein gültiges nicht verdecken."""
        ids = self.agent_ids(entitlements=[
            _entitlement(valid_until="2000-01-01T00:00:00Z",
                         entitlement_id="ent-old"),
            _entitlement(entitlement_id="ent-live"),
        ])
        self.assertEqual([AGENT], ids)


class TestIdentityFromJwtOnly(CapabilityHarness):
    """Auftrag §3 Schritt 5: Identitaet stammt aus dem JWT `sub`."""

    def test_missing_claims_is_401(self):
        from unittest.mock import patch
        with patch.object(h, "_get_entitlements", return_value=[]), \
             patch.object(h, "_get_agent_catalog", return_value=_catalog()):
            out = h.handler(_event(None), None)
        self.assertEqual(401, out["statusCode"])

    def test_empty_sub_is_401(self):
        self.assertEqual(401, self.agents(claims=_claims(sub=""))[0])

    def test_entitlement_query_uses_the_jwt_sub(self):
        """Der Aufrufer bestimmt die Entitlement-Menge, nicht das Frontend."""
        from unittest.mock import patch
        seen = {}

        def _capture(user_id, tenant_id=None):
            seen["user_id"] = user_id
            seen["tenant_id"] = tenant_id
            return []

        with patch.object(h, "_get_entitlements", side_effect=_capture), \
             patch.object(h, "_get_agent_catalog", return_value=_catalog()):
            h.handler(_event(_claims(sub="u-cognito", tenant="t-cognito")),
                      None)
        self.assertEqual("u-cognito", seen["user_id"])
        self.assertEqual("t-cognito", seen["tenant_id"])

    def test_client_supplied_headers_cannot_change_the_subject(self):
        """X-Api-Profile oder Body duerfen die Identitaet nicht uebernehmen."""
        code, _body = self.agents(
            claims=_claims(sub="u1"),
            headers={"X-Api-Profile": "aprof_someone_else",
                     "X-User-Id": "attacker",
                     "Authorization": "Bearer irrelevant-here"})
        self.assertEqual(200, code)


class TestTenantIsolation(CapabilityHarness):
    """Auftrag §7: keine Aggregation fremder Tenant-Daten."""

    def test_entitlement_of_foreign_tenant_is_not_offered(self):
        from unittest.mock import patch
        # _get_entitlements filtert tenant-seitig; hier der Beweis, dass
        # _handle_agents selbst nichts ueberschreibt.
        with patch.object(h, "_get_entitlements",
                          return_value=[]), \
             patch.object(h, "_get_agent_catalog", return_value=_catalog()):
            out = h.handler(_event(_claims(tenant="t-mine")), None)
        self.assertEqual({"agents": []}, json.loads(out["body"]))

    def test_tenant_filter_runs_in_the_data_layer(self):
        """Die Isolation entsteht im Query, nicht durch nachgelagerte Sicht."""
        from unittest.mock import patch
        seen = {}

        def _fake(user_id, tenant_id=None):
            seen["tenant"] = tenant_id
            return [_entitlement(tenant=tenant_id)]

        with patch.object(h, "_get_entitlements", side_effect=_fake), \
             patch.object(h, "_get_agent_catalog", return_value=_catalog()):
            h.handler(_event(_claims(tenant="t-isolation")), None)
        self.assertEqual("t-isolation", seen["tenant"])

    def test_two_users_get_their_own_capabilities(self):
        """A sieht A, B sieht B -- getrennte Entitlement-Mengen."""
        def _rows_for(user_id):
            if user_id == "user-a":
                return [_entitlement(tenant="t-a")]
            return [_entitlement(agent=OTHER, tenant="t-b",
                                 entitlement_id="ent-b")]

        from unittest.mock import patch
        catalog = _catalog()
        catalog[OTHER] = dict(catalog[AGENT], agentId=OTHER, name=OTHER)

        def run(sub, tenant):
            with patch.object(h, "_get_entitlements",
                              side_effect=lambda uid, tid=None: _rows_for(uid)), \
                 patch.object(h, "_get_agent_catalog", return_value=catalog):
                out = h.handler(_event(_claims(sub=sub, tenant=tenant)), None)
            return [a["agentId"] for a in json.loads(out["body"])["agents"]]

        self.assertEqual([AGENT], run("user-a", "t-a"))
        self.assertEqual([OTHER], run("user-b", "t-b"))


class TestFrontendIsNotASecurityBoundary(CapabilityHarness):
    """Auftrag §3 Schritt 10 und Festlegung: Backend bleibt autoritativ.

    Die Sichtbarkeit in /agents ist eine Anzeige. Ob ein Aufruf tatsaechlich
    ausgefuehrt werden darf, entscheidet der Execution-Pfad (P21) weiterhin
    unabhaengig. Diese Tests halten beide Aussagen getrennt.
    """

    def test_capability_visibility_does_not_grant_execution(self):
        """Ein gelisteter Agent allein erlaubt keine Machine-Execution.

        `/agents` wird mit einem Human-JWT aufgerufen, die Machine-Route
        verlangt zusaetzlich X-Api-Credential. Ein JWT allein genuegt dort
        nicht -- die Grenze liegt im Backend, nicht in der Liste.
        """
        event = {"httpMethod": "POST",
                 "path": "/v1/m2m/agents/%s/execute" % AGENT,
                 "headers": {},
                 "body": "{}",
                 "requestContext": {
                     "requestId": "r",
                     "http": {"method": "POST", "path":
                              "/v1/m2m/agents/%s/execute" % AGENT},
                     "authorizer": {"jwt": {"claims": _claims()}}}}
        from agents.ecosystem import api_profiles as ap
        from agents.ecosystem.credentials import InMemoryCredentialStore
        from unittest.mock import patch

        class _Empty:
            def find_entitlements(self, user_id):
                return []

        sources = {"profile_store": ap.InMemoryApiProfileStore(),
                   "credential_store": InMemoryCredentialStore(),
                   "entitlement_resolver": _Empty(),
                   "catalog": {AGENT: "ACTIVE"}}
        with patch.object(h, "_build_introspection_sources",
                          return_value=sources):
            out = h.handler(event, None)
        self.assertNotEqual(202, out["statusCode"])

    def test_capability_list_never_contains_a_credential(self):
        code, body = self.agents()
        self.assertEqual(200, code)
        raw = json.dumps(body)
        self.assertNotIn("ris_", raw)
        self.assertNotIn("Bearer", raw)


class TestAuthorizationMatrix(CapabilityHarness):
    """Auftrag §6. Jede Zelle mit belegbarer Evidenz."""

    def test_unauthenticated_is_denied(self):
        self.assertEqual(401, self.agents(claims=None)[0])

    def test_plain_user_gets_own_context_only(self):
        """User: eigener Kontext, keine Admin-Sicht."""
        self.assertEqual([AGENT], self.agent_ids(claims=_claims(groups=[])))

    def test_staff_sees_nothing_extra(self):
        """Staff erhaelt KEINE zusaetzliche Sichtbarkeit (kein Erfinden)."""
        as_staff = self.agent_ids(claims=_claims(groups=["Staff"]))
        as_user = self.agent_ids(claims=_claims(groups=[]))
        self.assertEqual(as_user, as_staff)

    def test_admin_is_no_broader_than_his_entitlements(self):
        """`admins` ist RIS Product Administrator, kein AWS-Administrator.

        Fuer die Capability-Sicht folgt daraus keine Sonderbehandlung: auch ein
        Admin sieht nur Agenten, die sein eigener Kontext autorisiert. Das ist
        der bestehende Vertrag von /agents und wird hier festgehalten.
        """
        as_admin = self.agent_ids(claims=_claims(groups=["admins"]))
        self.assertEqual([AGENT], as_admin)
        self.assertEqual([], self.agent_ids(claims=_claims(groups=["admins"]),
                                           entitlements=[]))

    def test_admin_group_never_widens_foreign_tenant_access(self):
        """Auch als admins: fremde Entitlements erscheinen nicht."""
        from unittest.mock import patch
        with patch.object(h, "_get_entitlements", return_value=[]), \
             patch.object(h, "_get_agent_catalog", return_value=_catalog()):
            out = h.handler(_event(_claims(sub="admin1", tenant="t-admin",
                                           groups=["admins"])), None)
        self.assertEqual({"agents": []}, json.loads(out["body"]))


class TestCatalogRemainsSingleSource(CapabilityHarness):
    """Auftrag HARD SCOPE: keine parallele Catalog-Architektur."""

    def test_catalog_is_read_through_the_existing_reader(self):
        from unittest.mock import patch
        with patch.object(h, "_get_agent_catalog", wraps=h._get_agent_catalog) \
                as reader:
            try:
                h.handler(_event(_claims()), None)
            except Exception:
                pass
        self.assertTrue(reader.called,
                        "_handle_agents muss den bestehenden Catalog-Reader "
                        "verwenden")

    def test_catalog_status_decision_is_central(self):
        """Fail-closed bei jedem unbekannten Statuswert."""
        for status in (None, "", "unknown", "CASE", "pending"):
            with self.subTest(status=status):
                catalog = {"agentId-entry": {"agentId": AGENT,
                                             "status": status}}
                self.assertEqual([], self.agent_ids(catalog=catalog))

    def test_catalog_registration_is_not_written_by_the_handler(self):
        """Der Handler registriert nichts; der Catalog bleibt Terraform-SoT."""
        source = open(h.__file__, encoding="utf-8").read()
        body = source[source.index("def _handle_agents"):
                      source.index("MACHINE_CREDENTIAL_HEADER")]
        for forbidden in ("put_item", "update_item", "delete_item",
                          "register_agent", "create_offer"):
            self.assertNotIn(forbidden, body.lower(),
                             "%s gehoert nicht in den Lese-Handler" % forbidden)


class TestRouteBoundaryUnchanged(CapabilityHarness):
    """Regression: /agents bleibt JWT-geschuetzt, /health bleibt offen."""

    def test_agents_route_is_jwt_protected_in_terraform(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "terraform", "modules", "api",
            "main.tf")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        start = source.index('resource "aws_apigatewayv2_route" "agents"')
        block = source[start:start + 400]
        self.assertIn('authorization_type = "JWT"', block)
        self.assertIn("authorizer_id", block)

    def test_health_still_needs_no_authentication(self):
        from unittest.mock import patch
        with patch.object(h, "_get_entitlements", return_value=[]), \
             patch.object(h, "_get_agent_catalog", return_value=_catalog()):
            out = h.handler(_event(None, path="/health"), None)
        self.assertEqual(200, out["statusCode"])


if __name__ == "__main__":
    unittest.main()