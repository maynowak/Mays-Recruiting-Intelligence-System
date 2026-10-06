"""Tests RIS-P23-OFFER-PRODUCT-ADMIN-PROVISIONING-01.

Offer ist das beschlossene RIS-Produktobjekt (P23-01). Diese Tests pruefen die
HTTP-Verdrahtung ueber der bestehenden Offer-Domaene -- nicht die Domaene
selbst, die in tests/test_offer_entitlement_grant.py bereits umfassend getestet
wird und hier unveraendert wiederverwendet wird.

  * Rollenpruefung kommt aus der Domaene (offers._is_admin liest
    actor["groups"]); diese Schicht leitet die Gruppe ausschliesslich aus dem
    Gateway-validierten JWT ab.
  * Agent-Validierung, Namenseindeutigkeit, reason-Pflichten, Idempotenz,
    Overlap-Erkennung und all-or-nothing bleiben in der Domaene. Hier wird nur
    die HTTP-Abbildung geprueft.
  * Kein direkter DynamoDB-Write: jede Mutation laeuft ueber eine
    Domaenenfunktion.

Zusaetzlich wird die Capability-Wirkung belegt (Auftrag §14/§16): nach einem
Grant erscheint der Offer-Agent in /agents, nach dem Entzug nicht mehr.
"""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.offers import (  # noqa: E402
    InMemoryEntitlementStore,
    InMemoryOfferStore,
)

AGENT = "reference_agent"
OTHER = "jobsearch-agent"
ADMIN = "admins"
STAFF = "Staff"


def _claims(sub="admin1", tenant="t1", groups=(ADMIN,)):
    return {"sub": sub, "token_use": "access", "custom:tenant_id": tenant,
            "cognito:groups": list(groups)}


def _event(path, method="GET", claims=_claims(), body=None, headers=None):
    request_context = {"requestId": "req-p23",
                       "http": {"method": method, "path": path}}
    if claims is not None:
        request_context["authorizer"] = {"jwt": {"claims": claims}}
    return {"httpMethod": method, "path": path, "headers": headers or {},
            "body": json.dumps(body) if body is not None else "{}",
            "requestContext": request_context}


def _catalog(*agent_ids):
    return {agent_id: {"agentId": agent_id, "name": agent_id,
                       "status": "ACTIVE", "version": "1.0.0",
                       "capabilities": ["reference.echo"]}
            for agent_id in agent_ids}


class OfferHarness(unittest.TestCase):
    """Echte Offer-/Entitlement-Stores, gemockte AWS-Handles."""

    def setUp(self):
        self.offers = InMemoryOfferStore()
        self.entitlements = InMemoryEntitlementStore()
        self.profiles = ap.InMemoryApiProfileStore()
        self.catalog = _catalog(AGENT)
        self.pid = ap.create_profile(
            self.profiles,
            {"userId": "u1", "tenantId": "t1", "groups": []},
            "p23 profile")["apiProfileId"]
        ap.transition_status(self.profiles,
                             {"userId": "admin1", "tenantId": "t1",
                              "groups": [ADMIN]}, self.pid, "ACTIVE")

    def sources(self):
        return {"offers": self.offers, "entitlements": self.entitlements}

    def call(self, path, method="GET", claims=_claims(), body=None,
             catalog=None, headers=None):
        from unittest.mock import patch
        with patch.object(h, "_offer_sources", return_value=self.sources()), \
             patch.object(h, "_get_agent_catalog",
                          return_value=self.catalog if catalog is None
                          else catalog):
            out = h.handler(_event(path, method, claims, body, headers), None)
        return out["statusCode"], json.loads(out["body"])

    def create_offer(self, name="P23 Basispaket", agents=(AGENT,),
                     claims=_claims(), **kwargs):
        code, body = self.call(
            "/v1/offers", "POST", claims,
            {"name": name, "agentIds": list(agents)}, **kwargs)
        return code, body

    def grant(self, offer_id, user="u1", tenant="t1", claims=_claims(),
              reason="P23 E2E", valid_from=None, valid_until=None):
        """Grant mit Fenster -- die Domaene verlangt es zwingend."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        return self.call("/v1/offers/%s/grant" % offer_id, "POST", claims,
                         {"userId": user, "tenantId": tenant, "reason": reason,
                          "validFrom": valid_from
                          or (now - timedelta(days=1)).isoformat(),
                          "validUntil": valid_until
                          or (now + timedelta(days=30)).isoformat()})


class TestOfferManagementRequiresAdmin(OfferHarness):
    """Auftrag §5/§15: nur Product Admin, Staff und User niemals."""

    def test_admin_may_create(self):
        code, body = self.create_offer()
        self.assertEqual(201, code)
        self.assertTrue(body["offerId"].startswith("off_"))
        self.assertEqual([AGENT], body["agentIds"])

    def test_unauthenticated_is_401(self):
        code, _body = self.call("/v1/offers", "POST", claims=None,
                                body={"name": "x", "agentIds": [AGENT]})
        self.assertEqual(401, code)

    def test_plain_user_is_denied(self):
        code, _body = self.create_offer(claims=_claims(groups=()))
        self.assertEqual(403, code)

    def test_staff_is_denied(self):
        """Staff erhaelt KEIN Offer-Management (kein Erfinden)."""
        code, _body = self.create_offer(claims=_claims(groups=(STAFF,)))
        self.assertEqual(403, code)

    def test_staff_reads_only_active_display_offers(self):
        """Bestehender Contract, nicht von P23 geaendert.

        list_offers gibt Nicht-Admins ausschliesslich ACTIVE-Angebote zurueck
        (offers.py:399-408). Staff ist also kein Management-Leser, sieht aber
        das aktive Angebot als Display-Information. Verwaltung (Schreiben) bleibt
        Admin-only.
        """
        self.create_offer(name="Aktiv", claims=_claims())
        _code, inactive = self.create_offer(name="Inaktiv")
        self.call("/v1/offers/%s/status" % inactive["offerId"], "POST",
                  body={"status": "INACTIVE", "reason": "P23 test"})
        code, body = self.call("/v1/offers", "GET", _claims(groups=(STAFF,)))
        self.assertEqual(200, code)
        names = [o["name"] for o in body["offers"]]
        self.assertEqual(["Aktiv"], names,
                         "Staff sieht nur ACTIVE, kein INACTIVE")
        # Verwaltung bleibt verweigert.
        code, _b = self.call("/v1/offers", "POST", _claims(groups=(STAFF,)),
                             body={"name": "Neu", "agentIds": [AGENT]})
        self.assertEqual(403, code)

    def test_role_cannot_be_faked_by_header(self):
        """Kein Header und kein Body kann `admins` vortaeuschen."""
        code, _body = self.call(
            "/v1/offers", "POST", _claims(groups=()),
            {"name": "x", "agentIds": [AGENT]},
            headers={"X-Role": "admin", "X-Groups": ADMIN,
                     "Cognito-Groups": ADMIN})
        self.assertEqual(403, code)
        self.assertEqual([], self.offers.list_offers())

    def test_role_cannot_be_faked_by_body_groups(self):
        """Ein Body-Feld `role` ist unbekannt -> 400, und es entsteht kein Offer.

        Wichtig ist die Wirkung, nicht die Statusziffer: keine Rolle, kein Offer.
        """
        code, _body = self.call(
            "/v1/offers", "POST", _claims(groups=()),
            {"name": "x", "agentIds": [AGENT], "role": "admin"})
        self.assertEqual(400, code)
        self.assertEqual([], self.offers.list_offers())


class TestOfferAgentValidation(OfferHarness):
    """Auftrag §6: nur Catalog-Agenten, kein Unknown persistiert."""

    def test_unknown_agent_is_refused(self):
        code, _body = self.create_offer(agents=("no-such-agent",))
        self.assertEqual(400, code)
        self.assertEqual([], self.offers.list_offers(),
                         "kein partielles Persistieren")

    def test_non_executable_agent_is_refused(self):
        catalog = {"agentId-entry": {"agentId": AGENT, "status": "PENDING"}}
        code, _body = self.create_offer(catalog=catalog)
        self.assertEqual(400, code)
        self.assertEqual([], self.offers.list_offers())

    def test_empty_agent_list_is_refused(self):
        code, _body = self.create_offer(agents=())
        self.assertEqual(400, code)

    def test_duplicate_offer_name_is_conflict(self):
        self.create_offer(name="Doppelt")
        code, _body = self.create_offer(name="Doppelt")
        self.assertEqual(409, code)

    def test_all_agents_must_be_known(self):
        """Gemischte Liste: ein unbekannter Agent blockiert das ganze Offer."""
        code, _body = self.create_offer(agents=(AGENT, "no-such-agent"))
        self.assertEqual(400, code)
        self.assertEqual([], self.offers.list_offers())


class TestOfferLifecycle(OfferHarness):
    """§10: nur Routen, die der bestehende Lifecycle wirklich traegt."""

    def test_list_and_get(self):
        _code, created = self.create_offer()
        code, body = self.call("/v1/offers", "GET")
        self.assertEqual(200, code)
        self.assertEqual(1, len(body["offers"]))
        code, body = self.call("/v1/offers/%s" % created["offerId"], "GET")
        self.assertEqual(200, code, body)
        self.assertEqual(created["offerId"], body["offerId"])

    def test_unknown_offer_is_404(self):
        code, _body = self.call("/v1/offers/off_missing", "GET")
        self.assertEqual(404, code)

    def test_update_rejects_unknown_field(self):
        _code, created = self.create_offer()
        code, _body = self.call("/v1/offers/%s" % created["offerId"], "PATCH",
                                body={"pricing": "free"})
        self.assertEqual(400, code)

    def test_update_changes_agents_for_future_grants(self):
        _code, created = self.create_offer(agents=(AGENT,))
        self.assertEqual([AGENT], created["agentIds"])
        catalog = _catalog(AGENT, OTHER)
        code, body = self.call("/v1/offers/%s" % created["offerId"], "PATCH",
                               body={"agentIds": [AGENT, OTHER],
                                     "description": "erweitert"},
                               catalog=catalog)
        self.assertEqual(200, code)
        self.assertEqual([AGENT, OTHER], body["agentIds"])
        self.assertEqual("erweitert", body["description"])

    def test_status_change_requires_reason(self):
        _code, created = self.create_offer()
        code, _body = self.call("/v1/offers/%s/status" % created["offerId"],
                                "POST", body={"status": "INACTIVE"})
        self.assertEqual(400, code)

    def test_status_can_be_deactivated_and_reactivated(self):
        _code, created = self.create_offer()
        path = "/v1/offers/%s/status" % created["offerId"]
        code, body = self.call(path, "POST",
                               body={"status": "INACTIVE", "reason": "P23 test"})
        self.assertEqual(200, code)
        self.assertEqual("INACTIVE", body["status"])
        code, body = self.call(path, "POST",
                               body={"status": "ACTIVE", "reason": "P23 test"})
        self.assertEqual(200, code)
        self.assertEqual("ACTIVE", body["status"])

    def test_invalid_status_value_is_refused(self):
        _code, created = self.create_offer()
        code, _body = self.call("/v1/offers/%s/status" % created["offerId"],
                                "POST", body={"status": "GONE",
                                              "reason": "x"})
        self.assertEqual(400, code)

    def test_unknown_sub_action_is_404(self):
        code, _body = self.call("/v1/offers/off_x/frobnicate", "POST")
        self.assertEqual(404, code)

    def test_unknown_body_field_on_create_is_refused(self):
        code, _body = self.call("/v1/offers", "POST",
                                body={"name": "x", "agentIds": [AGENT],
                                      "price": 10})
        self.assertEqual(400, code)


class TestOfferGrant(OfferHarness):
    """§7/§11: grant_offer wiederverwendet, all-or-nothing erhalten."""

    def test_grant_creates_one_entitlement_per_agent(self):
        _code, created = self.create_offer()
        code, body = self.grant(created["offerId"])
        self.assertEqual(200, code)
        self.assertEqual(1, len(body["entitlementIds"]))
        rows = self.entitlements.find_by_user("u1")
        self.assertEqual(1, len(rows))
        self.assertEqual(AGENT, rows[0]["agentId"])
        self.assertEqual(created["offerId"], rows[0]["offerId"])
        self.assertEqual("t1", rows[0]["tenantId"])

    def test_grant_requires_reason(self):
        _code, created = self.create_offer()
        code, _body = self.grant(created["offerId"], reason=None)
        self.assertEqual(400, code)
        self.assertEqual([], self.entitlements.find_by_user("u1"))

    def test_grant_requires_a_validity_window(self):
        """_windows_ok verlangt validFrom < validUntil (Domaene)."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        _code, created = self.create_offer()
        for kwargs in ({"valid_from": None},
                       {"valid_until": None},
                       {"valid_from": (now + timedelta(days=10)).isoformat(),
                        "valid_until": (now + timedelta(days=1)).isoformat()}):
            with self.subTest(kwargs=sorted(kwargs)):
                body = {"userId": "u1", "tenantId": "t1", "reason": "r",
                        "validFrom": (now - timedelta(days=1)).isoformat(),
                        "validUntil": (now + timedelta(days=30)).isoformat()}
                body.update({k: v for k, v in kwargs.items() if v is not None})
                if "valid_from" in kwargs:
                    body.pop("validFrom")
                if "valid_until" in kwargs:
                    body.pop("validUntil")
                code, _b = self.call("/v1/offers/%s/grant" % created["offerId"],
                                     "POST", body=body)
                self.assertEqual(400, code)
        self.assertEqual([], self.entitlements.find_by_user("u1"))

    def test_grant_requires_user_and_tenant(self):
        _code, created = self.create_offer()
        for missing in ("userId", "tenantId", "reason"):
            with self.subTest(missing=missing):
                body = {"userId": "u1", "tenantId": "t1", "reason": "r"}
                body.pop(missing)
                code, _b = self.call("/v1/offers/%s/grant" % created["offerId"],
                                     "POST", body=body)
                self.assertEqual(400, code)

    def test_grant_of_inactive_offer_is_refused(self):
        _code, created = self.create_offer()
        self.call("/v1/offers/%s/status" % created["offerId"], "POST",
                  body={"status": "INACTIVE", "reason": "P23 test"})
        code, _body = self.grant(created["offerId"])
        self.assertEqual(400, code)
        self.assertEqual([], self.entitlements.find_by_user("u1"))

    def test_grant_of_unknown_offer_is_400(self):
        """grant_offer wirft GrantDenied("offer missing") -> 400.

        Bestehender Vertrag: im Grant-Vertrag ist ein fehlendes Offer ein
        abgelehnter Grant, kein 404. Nicht eigenmaechtig umgedeutet.
        """
        code, _body = self.grant("off_missing")
        self.assertEqual(400, code)
        self.assertEqual([], self.entitlements.find_by_user("u1"))

    def test_grant_requires_admin(self):
        _code, created = self.create_offer()
        for groups in ((), (STAFF,)):
            with self.subTest(groups=groups):
                code, _b = self.grant(created["offerId"],
                                      claims=_claims(groups=groups))
                self.assertEqual(403, code)
        self.assertEqual([], self.entitlements.find_by_user("u1"))

    def test_grant_writes_no_partial_on_conflict(self):
        """Overlap blockiert den GANZEN Grant (kein Teilwrite)."""
        _code, created = self.create_offer(agents=(AGENT,))
        self.grant(created["offerId"])
        # Zweites Offer mit demselben Agenten, anderes Fenster -> Konflikt.
        _code, other = self.create_offer(name="Anderes Fenster", agents=(AGENT,))
        code, _body = self.grant(other["offerId"])
        self.assertEqual(409, code)
        rows = self.entitlements.find_by_user("u1")
        self.assertEqual(1, len(rows), "kein zusaetzlicher Write")

    def test_grant_is_user_wide_in_this_gate(self):
        """FALL A aus Auftrag §9: user-wide, also ohne apiProfileId.

        Genau diese Form behandelt check_worker_entitlement als user-wide, weshalb
        OPEN-1 fuer diesen Pfad nicht angefasst werden musste.
        """
        _code, created = self.create_offer()
        self.grant(created["offerId"])
        row = self.entitlements.find_by_user("u1")[0]
        self.assertIsNone(row.get("apiProfileId"))

    def test_grant_window_is_honoured(self):
        _code, created = self.create_offer()
        code, _body = self.grant(created["offerId"])
        self.assertEqual(200, code)
        row = self.entitlements.find_by_user("u1")[0]
        self.assertIn("validUntil", row)
        self.assertIn("expiresAt", row)


class TestWithdrawAndTenantIsolation(OfferHarness):
    """§8/§11: Entzug, Tenant-Bindung, keine Fremdgriffe."""

    def _grant_to(self, user, tenant, claims=_claims(tenant="t1")):
        _code, created = self.create_offer()
        code, body = self.grant(created["offerId"], user=user,
                                tenant=tenant, claims=claims)
        return created, body

    def test_withdraw_removes_the_entitlement(self):
        created, granted = self._grant_to("u1", "t1")
        code, body = self.call(
            "/v1/offers/%s/withdraw" % created["offerId"], "POST",
            body={"entitlementId": granted["entitlementIds"][0],
                  "reason": "P23 cleanup"})
        self.assertEqual(200, code)
        self.assertTrue(body["withdrawn"])
        self.assertEqual([], self.entitlements.find_by_user("u1"))

    def test_withdraw_requires_reason(self):
        created, granted = self._grant_to("u1", "t1")
        code, _body = self.call(
            "/v1/offers/%s/withdraw" % created["offerId"], "POST",
            body={"entitlementId": granted["entitlementIds"][0]})
        self.assertEqual(400, code)
        self.assertEqual(1, len(self.entitlements.find_by_user("u1")))

    def test_withdraw_from_wrong_offer_is_404(self):
        """Die Path-Offer muss die Zeile wirklich beschreiben."""
        created, granted = self._grant_to("u1", "t1")
        _code, other = self.create_offer(name="Fremdes Offer")
        code, _body = self.call(
            "/v1/offers/%s/withdraw" % other["offerId"], "POST",
            body={"entitlementId": granted["entitlementIds"][0],
                  "reason": "x"})
        self.assertEqual(404, code)
        self.assertEqual(1, len(self.entitlements.find_by_user("u1")))

    def test_cross_tenant_grant_needs_reason_from_the_admin(self):
        """Der Admin muss den Tenant-Wechsel begruenden."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        _code, created = self.create_offer()
        code, _body = self.call("/v1/offers/%s/grant" % created["offerId"],
                                 "POST",
                                 body={"userId": "u1", "tenantId": "t-fremd",
                                       "reason": "",
                                       "validFrom": (now - timedelta(
                                           days=1)).isoformat(),
                                       "validUntil": (now + timedelta(
                                           days=30)).isoformat()})
        self.assertEqual(400, code)
        self.assertEqual([], self.entitlements.find_by_user("u1"))

    def test_cross_tenant_grant_with_reason_is_allowed(self):
        """Admin in t1 darf nach t-fremd vergeben, wenn er es begruendet."""
        code, _body = self.grant(created_id := self.create_offer()[1]["offerId"],
                                 tenant="t-fremd",
                                 reason="P23 cross-tenant support")
        self.assertEqual(200, code)
        self.assertEqual("t-fremd",
                         self.entitlements.find_by_user("u1")[0]["tenantId"])

    def test_entitlement_carries_offer_provenance(self):
        created, granted = self._grant_to("u1", "t1")
        row = self.entitlements.find_by_user("u1")[0]
        self.assertEqual(created["offerId"], row["offerId"])
        self.assertEqual(granted["grantId"], row["grantId"])


class TestCapabilityEffect(OfferHarness):
    """§14/§16: der Grant muss die positive Capability-Liste aendern."""

    def agents(self, user="u1", tenant="t1"):
        from unittest.mock import patch
        with patch.object(h, "_get_entitlements",
                          side_effect=lambda uid, tid=None: self.entitlements.find_by_user(uid)), \
             patch.object(h, "_get_agent_catalog", return_value=self.catalog):
            out = h.handler(_event("/agents", "GET", _claims(sub=user)), None)
        return [a["agentId"] for a in json.loads(out["body"])["agents"]]

    def test_before_grant_agent_is_not_visible(self):
        self.assertEqual([], self.agents())

    def test_after_grant_agent_is_visible(self):
        _code, created = self.create_offer()
        self.assertEqual([], self.agents())
        self.grant(created["offerId"])
        self.assertEqual([AGENT], self.agents())

    def test_after_withdraw_agent_is_gone(self):
        _code, created = self.create_offer()
        granted = self.grant(created["offerId"])[1]
        self.assertEqual([AGENT], self.agents())
        self.call("/v1/offers/%s/withdraw" % created["offerId"], "POST",
                  body={"entitlementId": granted["entitlementIds"][0],
                        "reason": "P23 cleanup"})
        self.assertEqual([], self.agents())

    def test_other_user_does_not_see_the_granted_agent(self):
        _code, created = self.create_offer()
        self.grant(created["offerId"])
        self.assertEqual([AGENT], self.agents(user="u1"))
        self.assertEqual([], self.agents(user="u2"))

    def test_deactivating_the_offer_does_not_retroactively_revoke(self):
        """Bestehender Contract: INACTIVE wirkt nur auf KÜNFTIGE Grants."""
        _code, created = self.create_offer()
        self.grant(created["offerId"])
        self.call("/v1/offers/%s/status" % created["offerId"], "POST",
                  body={"status": "INACTIVE", "reason": "P23 test"})
        self.assertEqual([AGENT], self.agents())

    def test_backend_stays_authoritative_after_grant(self):
        """Sichtbarkeit ersetzt keine serverseitige Pruefung (P21 unveraendert)."""
        _code, created = self.create_offer()
        self.grant(created["offerId"])
        self.assertEqual([AGENT], self.agents())
        event = _event("/v1/m2m/agents/%s/execute" % AGENT, "POST", body={})
        from agents.ecosystem.credentials import InMemoryCredentialStore
        from unittest.mock import patch

        sources = {"profile_store": self.profiles,
                   "credential_store": InMemoryCredentialStore(),
                   "entitlement_resolver": self,
                   "catalog": {AGENT: "ACTIVE"}}
        with patch.object(h, "_build_introspection_sources",
                          return_value=sources):
            out = h.handler(event, None)
        self.assertNotEqual(202, out["statusCode"],
                            "ohne ris_-Credential keine Execution")


class TestAuditAndSecretHygiene(OfferHarness):
    """§13: nachvollziehbar, ohne Secrets."""

    def test_offer_audit_actions_are_emitted(self):
        import io
        import logging
        import re
        from unittest.mock import patch

        stream = io.StringIO()
        sink = logging.StreamHandler(stream)
        sink.setLevel(logging.INFO)
        logger = logging.getLogger("agents.ecosystem.offers")
        logger.addHandler(sink)
        old = logger.level
        logger.setLevel(logging.INFO)
        try:
            _code, created = self.create_offer(name="Audit Offer")
            self.grant(created["offerId"])
        finally:
            logger.removeHandler(sink)
            logger.setLevel(old)
        text = stream.getvalue()
        self.assertIn("offer-created", text)
        self.assertIn("grant-authorized", text)

    def test_denied_action_is_audited(self):
        import io
        import logging

        stream = io.StringIO()
        sink = logging.StreamHandler(stream)
        sink.setLevel(logging.INFO)
        logger = logging.getLogger("agents.ecosystem.offers")
        logger.addHandler(sink)
        old = logger.level
        logger.setLevel(logging.INFO)
        try:
            self.create_offer(claims=_claims(groups=(STAFF,)))
        finally:
            logger.removeHandler(sink)
            logger.setLevel(old)
        self.assertIn("unauthorized-offer-action", stream.getvalue())

    def test_response_never_contains_secrets(self):
        import base64

        _code, created = self.create_offer()
        code, body = self.call("/v1/offers/%s" % created["offerId"], "GET")
        raw = json.dumps(body)
        for leak in ("digest", "secret", "Bearer", "eyJ"):
            self.assertNotIn(leak, raw)


class TestRouteAndIamContract(OfferHarness):
    """§12/§20: Routen JWT-geschuetzt, IAM minimal begruendet."""

    def test_all_offer_routes_are_jwt_protected_in_terraform(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "terraform", "modules", "api",
            "main.tf")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        blocks = re.findall(
            r'resource "aws_apigatewayv2_route" "offers[^"]*" \{(.*?)\n\}',
            source, re.S)
        self.assertEqual(7, len(blocks), "erwartet: 7 offer-Routen")
        for block in blocks:
            with self.subTest(block=block.split("\n")[0]):
                self.assertIn('authorization_type = "JWT"', block)
                self.assertIn("authorizer_id", block)
                self.assertNotIn('"NONE"', block)

    def test_every_protected_route_reuses_the_one_authorizer(self):
        """Nur /health ist bewusst ohne Authorizer; alle anderen 34 nutzen
        denselben Cognito-Authorizer. Es gibt keinen zweiten."""
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "terraform", "modules", "api",
            "main.tf")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        blocks = re.findall(
            r'resource "aws_apigatewayv2_route" "([^"]+)" \{(.*?)\n\}',
            source, re.S)
        without = [name for name, block in blocks
                   if "authorizer_id" not in block]
        self.assertEqual(["health"], without,
                         "nur /health ist unauthentifiziert")
        for name, block in blocks:
            if name == "health":
                continue
            with self.subTest(route=name):
                self.assertIn("aws_apigatewayv2_authorizer.jwt.id", block)
        self.assertEqual(1, source.count(
            'resource "aws_apigatewayv2_authorizer"'))

    def test_entitlements_admin_policy_is_scoped_to_one_table(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "terraform", "modules", "lambda",
            "main.tf")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        start = source.index(
            'resource "aws_iam_role_policy" "lambda_dynamodb_entitlements_admin"')
        block = source[start:start + 900]
        for action in ("dynamodb:TransactWriteItems", "dynamodb:Scan",
                       "dynamodb:DeleteItem"):
            self.assertIn(action, block)
        # Kein pauschales Wildcard-Recht.
        self.assertNotIn("dynamodb:*", block)
        self.assertNotIn('"*"', block)
        # Nur die Entitlements-Tabelle, keine weitere.
        self.assertEqual(1, block.count("var.entitlements_table_arn"))

    def test_handler_never_writes_dynamodb_directly_for_offers(self):
        """Kein DDB-Workaround: die Route nutzt ausschliesslich die Domaene."""
        source = open(h.__file__, encoding="utf-8").read()
        body = source[source.index("def _handle_offer_routes"):
                      source.index("# P19: APIProfile management HTTP")]
        for forbidden in ("put_item(", "update_item(", "delete_item(",
                          "transact_write_items(", "boto3.resource"):
            self.assertNotIn(forbidden, body.lower(),
                             "%s waere ein DDB-Workaround" % forbidden)
        for domain_fn in ("create_offer", "grant_offer", "set_offer_status",
                          "update_offer", "withdraw_entitlement"):
            self.assertIn(domain_fn, body)


class TestRegressionBoundaries(OfferHarness):
    """§17: P21, P22 und /health unveraendert."""

    def test_health_stays_unauthenticated(self):
        with patch_catalog(self):
            out = h.handler(_event("/health", "GET", claims=None), None)
        self.assertEqual(200, out["statusCode"])

    def test_agents_route_still_jwt_only(self):
        code, _body = self.call("/agents", "GET", claims=None)
        self.assertEqual(401, code)

    def test_offer_paths_are_not_captured_by_other_routes(self):
        with patch_catalog(self):
            out = h.handler(_event("/v1/offers", "GET", claims=None), None)
        self.assertEqual(401, out["statusCode"])

    def test_machine_route_still_requires_credential(self):
        from agents.ecosystem.credentials import InMemoryCredentialStore
        from unittest.mock import patch

        class _Empty:
            def find_entitlements(self, user_id):
                return []

        sources = {"profile_store": self.profiles,
                   "credential_store": InMemoryCredentialStore(),
                   "entitlement_resolver": _Empty(),
                   "catalog": {AGENT: "ACTIVE"}}
        event = _event("/v1/m2m/agents/%s/execute" % AGENT, "POST", body={})
        with patch.object(h, "_build_introspection_sources",
                          return_value=sources):
            out = h.handler(event, None)
        self.assertEqual(401, out["statusCode"])

    def test_api_profile_routes_are_untouched(self):
        """Der neue Prefix /v1/offers darf bestehende Routen nicht fressen."""
        with patch_catalog(self):
            out = h.handler(_event("/v1/apiprofiles", "GET",
                                   _claims(groups=())), None)
        self.assertIn(out["statusCode"], (200, 503))


def patch_catalog(harness):
    from unittest.mock import patch
    return patch.object(h, "_get_agent_catalog", return_value=harness.catalog)


if __name__ == "__main__":
    unittest.main()