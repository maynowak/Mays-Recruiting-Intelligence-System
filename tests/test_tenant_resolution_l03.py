"""L03 — Tenant-Auflösung (serverseitig) für die Profil-Routen.

Kernthese des L03-Vertrags:

* Der Tenant ist eine **Server-Zustandsgröße**. Er kommt aus dem
  `custom:tenant_id`-Claim, wenn dieser vorhanden ist, sonst aus der
  **Partner-Registry** (JWT-Client → Partner Application → tenantId).
* Ein Claim, der der serverseitigen Auflösung widerspricht, ist ein
  Cross-Tenant-Versuch → deny (403).
* Ein **fehlender** Claim ist kein Fehler: ein Self-Signup-User der
  Partneranwendung trägt keinen Tenant-Claim. Ihn zu verweigern würde
  die Anbindung unbrauchbar machen, ohne etwas zu schützen.
* Es gibt **keinen** stillen `default`-Tenant. Ohne auflösbaren Tenant
  wird verweigert (403), nicht geraten.
* Der Browser liefert den Tenant **nie**: Body-/Header-Tenant werden
  ignoriert.

Die Tests fahren den echten Handler gegen eine In-Memory-Tabelle; nur
der DynamoDB-Zugriff und der Registry-Lookup werden ersetzt.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402

REGISTRY = "agents.ecosystem.partner_registry.resolve_partner_application"
TENANT = "tenant-partner"
CLIENT = "client-partner"
SUB = "user-l03"


class FakeTable:
    """Minimaler UserProfile-Store mit Conditional-Write-Semantik."""

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
        for assign in UpdateExpression[len("SET "):].split(","):
            left, right = [s.strip() for s in assign.split("=", 1)]
            item[names.get(left, left)] = values[right]
        return {"Attributes": dict(item)}

    def delete_item(self, Key, ConditionExpression=None):
        if ConditionExpression == "attribute_exists(userId)" \
                and Key["userId"] not in self.items:
            raise FakeTable.ConditionalFailed()
        self.items.pop(Key["userId"], None)
        return {}


class FakeDdb:
    def __init__(self, table):
        self.table = table

    def Table(self, name):  # noqa: N802  (boto3 casing)
        return self.table


def _event(method="POST", path="/me/profile", tenant=None, client_id=None,
           audience=None, body=None):
    claims = {"sub": SUB, "email": "l03@example.com",
              "preferred_username": "l03user"}
    if tenant is not None:
        claims["custom:tenant_id"] = tenant
    if client_id is not None:
        claims["client_id"] = client_id
    if audience is not None:
        claims["aud"] = audience
    return {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {"authorizer": {"jwt": {"claims": claims}}},
    }


class L03Harness(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.registry = {"applicationId": "app-partner",
                         "cognitoClientId": CLIENT,
                         "tenantId": TENANT,
                         "status": "ACTIVE"}
        self._env = patch.dict(os.environ, {"USER_PROFILE_TABLE": "profile"})
        self._env.start()
        self._ddb = patch.object(h, "_get_dynamodb",
                                 return_value=FakeDdb(self.table))
        self._ddb.start()

    def tearDown(self):
        self._ddb.stop()
        self._env.stop()

    def _with_registry(self, value):
        return patch(REGISTRY, return_value=value)


class TestProfileTenantResolution(L03Harness):
    def test_claim_is_used_when_present(self):
        with self._with_registry(self.registry):
            res = h._handle_me_profile_create(
                _event(tenant=TENANT, body={"nickname": "N"}), None)
        self.assertEqual(res["statusCode"], 201)
        body = json.loads(res["body"])
        self.assertEqual(body["tenantId"], TENANT)

    def test_registry_resolves_the_tenant_when_the_claim_is_missing(self):
        """Self-Signup-User: kein Tenant-Claim -> Registry (serverseitig)."""
        with self._with_registry(self.registry):
            res = h._handle_me_profile_create(
                _event(client_id=CLIENT, body={"nickname": "N"}), None)
        self.assertEqual(res["statusCode"], 201)
        self.assertEqual(json.loads(res["body"])["tenantId"], TENANT)

    def test_audience_claim_resolves_the_tenant(self):
        """ID-Token (kein `client_id`-Claim): `aud` ist der Client."""
        with self._with_registry(self.registry):
            res = h._handle_me_profile_create(
                _event(audience=CLIENT, body={"nickname": "N"}), None)
        self.assertEqual(res["statusCode"], 201)
        self.assertEqual(json.loads(res["body"])["tenantId"], TENANT)

    def test_unresolvable_tenant_is_refused_on_create(self):
        with self._with_registry(None):
            res = h._handle_me_profile_create(
                _event(body={"nickname": "N"}), None)
        self.assertEqual(res["statusCode"], 403)
        self.assertEqual(json.loads(res["body"])["error"], "Tenant not resolvable")
        self.assertEqual(self.table.puts, 0)

    def test_contradicting_claim_is_refused_on_create(self):
        """Der Authorizer hat den Client festgelegt (`aud`); ein Claim, der
        dem Registry-Tenant widerspricht, ist ein Cross-Tenant-Versuch."""
        with self._with_registry(self.registry):
            res = h._handle_me_profile_create(
                _event(tenant="tenant-fremd", audience=CLIENT,
                       body={"nickname": "N"}), None)
        self.assertEqual(res["statusCode"], 403)
        self.assertEqual(json.loads(res["body"])["error"], "Tenant not resolvable")
        self.assertEqual(self.table.puts, 0)

    def test_unresolvable_tenant_is_refused_on_read(self):
        with self._with_registry(None):
            res = h._handle_me_profile(
                _event(method="GET", path="/me/profile"), None)
        self.assertEqual(res["statusCode"], 403)
        self.assertEqual(json.loads(res["body"])["error"], "Tenant not resolvable")

    def test_unresolvable_tenant_is_refused_on_update(self):
        with self._with_registry(None):
            res = h._handle_me_profile_update(
                _event(method="PUT", path="/me/profile", body={"nickname": "X"}),
                None)
        self.assertEqual(res["statusCode"], 403)
        self.assertEqual(json.loads(res["body"])["error"], "Tenant not resolvable")

    def test_read_returns_the_profile_of_the_resolved_tenant(self):
        with self._with_registry(self.registry):
            h._handle_me_profile_create(
                _event(client_id=CLIENT, body={"nickname": "N"}), None)
            res = h._handle_me_profile(
                _event(method="GET", path="/me/profile", client_id=CLIENT), None)
        self.assertEqual(res["statusCode"], 200)
        self.assertEqual(json.loads(res["body"])["tenantId"], TENANT)

    def test_body_tenant_is_ignored(self):
        """Der Browser darf den Tenant nicht waehlen."""
        with self._with_registry(self.registry):
            res = h._handle_me_profile_create(
                _event(client_id=CLIENT,
                       body={"nickname": "N", "tenantId": "tenant-fremd"}), None)
        self.assertEqual(res["statusCode"], 201)
        self.assertEqual(json.loads(res["body"])["tenantId"], TENANT)

    def test_delete_needs_no_tenant(self):
        """Privacy-Recht: Loeschen bleibt ohne Tenant-Aufloesung moeglich."""
        with self._with_registry(self.registry):
            h._handle_me_profile_create(
                _event(client_id=CLIENT, body={"nickname": "N"}), None)
            res = h._handle_me_profile_delete(
                _event(method="DELETE", path="/me/profile"), None)
        self.assertEqual(res["statusCode"], 204)
        self.assertEqual(self.table.items, {})


class TestNoDefaultTenant(unittest.TestCase):
    def test_handler_contains_no_default_tenant_fallback(self):
        """Kein stiller "default"-Tenant in einem Schreibpfad."""
        import ast
        import inspect

        fns = [h._provision_user_profile, h._resolve_tenant,
               h._registry_tenant, h._handle_me_profile,
               h._handle_me_profile_create, h._handle_me_profile_update]
        for fn in fns:
            tree = ast.parse(inspect.getsource(fn))
            fn_node = tree.body[0]
            body = list(fn_node.body)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]
            for node in body:
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Constant)
                            and sub.value == "default"):
                        self.fail("%s still falls back to 'default'" % fn.__name__)


if __name__ == "__main__":
    unittest.main()
