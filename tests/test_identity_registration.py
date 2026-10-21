"""Tests Gates 10/12: Identity-Provisionierung + Profile-v1 (Gate 12).

NUR explizites Provisionieren (POST), nie via Read. Fake-Tabelle mit
Conditional-Write-Semantik. Keine Netz-/AWS-Abhaengigkeit.
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "gw_handler_10", os.path.join(REPO_ROOT, "lambda", "handler.py"))
handler = importlib.util.module_from_spec(_SPEC)
sys.modules["gw_handler_10"] = handler
_SPEC.loader.exec_module(handler)


def jwt_event(body=None, method="POST", path="/me/profile", claims=None):
    claims = claims if claims is not None else {
        "sub": "user-111", "email": "gate10@example.com",
        "preferred_username": "gate10user", "cognito:groups": ["user-user"],
    }
    return {
        "httpMethod": method, "path": path,
        "requestContext": {"authorizer": {"jwt": {"claims": claims}}},
        "body": json.dumps(body) if body is not None else None,
    }


class FakeTable:
    class ConditionalFailed(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "ConditionalCheckFailedException"}}

    def __init__(self):
        self.items = {}
        self.puts = 0

    def put_item(self, Item, ConditionExpression=None):
        if ConditionExpression == "attribute_not_exists(userId)" \
                and Item["userId"] in self.items:
            raise FakeTable.ConditionalFailed()
        self.items[Item["userId"]] = dict(Item)
        self.puts += 1

    def get_item(self, Key):
        item = self.items.get(Key["userId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None, ExpressionAttributeValues=None,
                    **kwargs):
        if "attribute_exists(userId)" in (ConditionExpression or "") \
                and Key["userId"] not in self.items:
            raise FakeTable.ConditionalFailed()
        item = self.items[Key["userId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        set_part = UpdateExpression[len("SET "):]
        for assign in set_part.split(","):
            left, right = [s.strip() for s in assign.split("=", 1)]
            item[names.get(left, left)] = values[right]
        return {"Attributes": dict(item)}


def ctx():
    return {"userId": "user-111", "tenantId": "tenant-gate10",
            "username": "gate10user", "email": "gate10@example.com", "groups": []}


TENANT = "tenant-gate10"


class TestTenantResolution(unittest.TestCase):
    """L03 — der Tenant ist eine Server-Zustandsgroesse.

    Der Claim `custom:tenant_id` bleibt autoritativ, WENN er vorhanden ist.
    Fehlt er, wird der Tenant serverseitig aus der Partner-Registry (JWT
    client_id -> Application -> tenantId) aufgeloest. Ein Widerspruch ist
    ein Cross-Tenant-Versuch -> deny. Es gibt keinen "default"-Fallback.
    """

    REGISTRY = "agents.ecosystem.partner_registry.resolve_partner_application"

    def _ctx(self, tenant=None, client_id="client-partner"):
        return {"userId": "user-111", "tenantId": tenant, "clientId": client_id}

    def test_claim_wins_and_registry_is_not_consulted(self):
        def boom(_client_id):
            raise AssertionError("registry must not be consulted")

        with patch(self.REGISTRY, side_effect=boom):
            tenant, conflict = handler._resolve_tenant(self._ctx(tenant=TENANT))
        self.assertEqual(tenant, TENANT)
        self.assertFalse(conflict)

    def test_missing_claim_resolves_via_registry(self):
        with patch(self.REGISTRY, return_value={"applicationId": "app-1",
                                                "tenantId": TENANT,
                                                "status": "ACTIVE"}):
            tenant, conflict = handler._resolve_tenant(self._ctx())
        self.assertEqual(tenant, TENANT)
        self.assertFalse(conflict)

    def test_contradicting_claim_is_a_conflict(self):
        with patch(self.REGISTRY, return_value={"applicationId": "app-1",
                                                "tenantId": TENANT,
                                                "status": "ACTIVE"}):
            tenant, conflict = handler._resolve_tenant(self._ctx(tenant="tenant-fremd"))
        self.assertIsNone(tenant)
        self.assertTrue(conflict)

    def test_unresolvable_tenant_is_not_guessed(self):
        with patch(self.REGISTRY, return_value=None):
            tenant, conflict = handler._resolve_tenant(self._ctx())
        self.assertIsNone(tenant)
        self.assertFalse(conflict)

    def test_inactive_registry_entry_resolves_nothing(self):
        with patch(self.REGISTRY, return_value={"applicationId": "app-1",
                                                "tenantId": TENANT,
                                                "status": "INACTIVE"}):
            tenant, conflict = handler._resolve_tenant(self._ctx())
        self.assertIsNone(tenant)
        self.assertFalse(conflict)

    def test_expected_tenant_is_authoritative_in_the_partner_route(self):
        """Partnerroute: Tenant kommt aus dem Credential (serverseitig)."""
        with patch(self.REGISTRY, side_effect=AssertionError("no registry")):
            tenant, conflict = handler._resolve_tenant(
                self._ctx(tenant=TENANT), expected_tenant=TENANT)
            self.assertEqual(tenant, TENANT)
            self.assertFalse(conflict)

            # Fehlender Claim ist kein Fehler: der Server kennt den Tenant.
            tenant, conflict = handler._resolve_tenant(
                self._ctx(), expected_tenant=TENANT)
            self.assertEqual(tenant, TENANT)
            self.assertFalse(conflict)

            # Widerspruch -> Cross-Tenant-Versuch.
            tenant, conflict = handler._resolve_tenant(
                self._ctx(tenant="tenant-fremd"), expected_tenant=TENANT)
            self.assertIsNone(tenant)
            self.assertTrue(conflict)

    def test_handler_has_no_default_tenant_fallback(self):
        """Es gibt keinen stillen "default"-Tenant mehr."""
        import ast
        import inspect

        def code_strings(fn):
            """String-Konstanten des Codes (ohne Docstring)."""
            tree = ast.parse(inspect.getsource(fn))
            fn_node = tree.body[0]
            body = list(fn_node.body)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]  # Docstring aussortieren
            found = []
            for node in body:
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Constant)
                            and isinstance(sub.value, str)):
                        found.append(sub.value)
            return found

        for fn in (handler._provision_user_profile, handler._resolve_tenant,
                   handler._registry_tenant):
            self.assertNotIn("default", code_strings(fn),
                             "%s still contains a default tenant" % fn.__name__)


class TestProvision(unittest.TestCase):
    def test_create_returns_201_with_v1_fields(self):
        table = FakeTable()
        resp = handler._provision_user_profile(
            table, ctx(), {"nickname": "GT", "firstName": "Gate", "lastName": "Ten"},
            tenant_id=TENANT)
        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["userId"], "user-111")
        self.assertEqual(body["tenantId"], "tenant-gate10")
        self.assertEqual(body["nickname"], "GT")
        self.assertEqual(body["firstName"], "Gate")
        self.assertEqual(body["lastName"], "Ten")
        self.assertEqual(body["email"], "gate10@example.com")
        self.assertEqual(body["status"], "ACTIVE")
        self.assertTrue(body["createdAt"])
        self.assertNotIn("username", body)
        self.assertNotIn("displayName", body)

    def test_duplicate_returns_409_no_overwrite(self):
        table = FakeTable()
        handler._provision_user_profile(table, ctx(), {"nickname": "Alt"},
                                        tenant_id=TENANT)
        resp = handler._provision_user_profile(table, ctx(), {"nickname": "Neu"},
                                               tenant_id=TENANT)
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(table.items["user-111"].get("nickname"), "Alt")
        self.assertEqual(table.puts, 1)

    def test_userid_spoofing_ignored(self):
        """Body-userId/tenantId duerfen nie uebernommen werden."""
        table = FakeTable()
        resp = handler._provision_user_profile(
            table, ctx(), {"userId": "user-FREMD", "tenantId": "tenant-FREMD",
                           "nickname": "X"}, tenant_id=TENANT)
        body = json.loads(resp["body"])
        self.assertEqual(resp["statusCode"], 201)
        self.assertEqual(body["userId"], "user-111")
        self.assertEqual(body["tenantId"], "tenant-gate10")

    def test_username_extraction_prefers_preferred(self):
        claims = {"sub": "u-1", "cognito:username": "legacy",
                  "preferred_username": "neu"}
        out = handler._extract_user_context(
            {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}})
        self.assertEqual(out["username"], "neu")
        self.assertIsNone(out["tenantId"])

    def test_unauthenticated_create_401(self):
        resp = handler._handle_me_profile_create(
            jwt_event(claims={"sub": None}), None)
        # kein sub -> userId None -> 401 (kein Tabellenkontakt noetig)
        self.assertEqual(resp["statusCode"], 401)

    def test_missing_tenant_is_refused(self):
        """Kein stiller "default"-Tenant: ohne aufgeloesten Tenant wird
        nicht geschrieben (GSI tenantId duldet kein NULL, live belegt)."""
        table = FakeTable()
        with self.assertRaises(ValueError):
            handler._provision_user_profile(table, ctx(), {})
        self.assertEqual(table.puts, 0)
        self.assertEqual(table.items, {})

    def test_dispatch_api_event_without_records(self):
        """Gate-10-Befund: API-Events duerfen nicht mit KeyError crashen."""
        resp = handler.handler(
            {"httpMethod": "GET", "path": "/platform",
             "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "u-1"}}}}},
            None)
        self.assertEqual(resp["statusCode"], 200)


class TestUpdate(unittest.TestCase):
    def _seeded(self):
        table = FakeTable()
        handler._provision_user_profile(
            table, ctx(), {"nickname": "Alt", "firstName": "A", "lastName": "B"},
            tenant_id=TENANT)
        return table

    def test_update_changes_only_v1_fields(self):
        table = self._seeded()
        before = dict(table.items["user-111"])
        resp = handler._update_user_profile(
            table, ctx(), {"nickname": "Neu", "userId": "user-FREMD",
                           "tenantId": "tenant-FREMD", "createdAt": "2000-01-01",
                           "email": "fremd@x.io", "status": "BLOCKED"})
        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["nickname"], "Neu")
        self.assertEqual(body["userId"], "user-111")
        self.assertEqual(body["tenantId"], "tenant-gate10")
        self.assertEqual(body["createdAt"], before["createdAt"])
        self.assertEqual(body["email"], "gate10@example.com")
        self.assertEqual(body["status"], "ACTIVE")
        self.assertNotEqual(body["updatedAt"], before["updatedAt"])

    def test_update_missing_profile_404(self):
        table = FakeTable()
        resp = handler._update_user_profile(table, ctx(), {"nickname": "X"})
        self.assertEqual(resp["statusCode"], 404)

    def test_update_empty_body_400(self):
        table = self._seeded()
        resp = handler._update_user_profile(table, ctx(), {})
        self.assertEqual(resp["statusCode"], 400)

    def test_update_unauthenticated_401(self):
        resp = handler._handle_me_profile_update(
            jwt_event(body={}, method="PUT", claims={"sub": None}), None)
        self.assertEqual(resp["statusCode"], 401)


if __name__ == "__main__":
    unittest.main()
