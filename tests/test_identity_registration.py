"""Tests Gates 10/12: Identity-Provisionierung + Profile-v1 (Gate 12).

NUR explizites Provisionieren (POST), nie via Read. Fake-Tabelle mit
Conditional-Write-Semantik. Keine Netz-/AWS-Abhaengigkeit.
"""

import importlib.util
import json
import os
import sys
import unittest

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


class TestProvision(unittest.TestCase):
    def test_create_returns_201_with_v1_fields(self):
        table = FakeTable()
        resp = handler._provision_user_profile(
            table, ctx(), {"nickname": "GT", "firstName": "Gate", "lastName": "Ten"})
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
        handler._provision_user_profile(table, ctx(), {"nickname": "Alt"})
        resp = handler._provision_user_profile(table, ctx(), {"nickname": "Neu"})
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(table.items["user-111"].get("nickname"), "Alt")
        self.assertEqual(table.puts, 1)

    def test_userid_spoofing_ignored(self):
        """Body-userId/tenantId duerfen nie uebernommen werden."""
        table = FakeTable()
        resp = handler._provision_user_profile(
            table, ctx(), {"userId": "user-FREMD", "tenantId": "tenant-FREMD",
                           "nickname": "X"})
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

    def test_missing_tenant_falls_back_to_default(self):
        """GSI tenantId duldet kein NULL (live belegt)."""
        table = FakeTable()
        no_tenant = dict(ctx())
        no_tenant["tenantId"] = None
        resp = handler._provision_user_profile(table, no_tenant, {})
        self.assertEqual(resp["statusCode"], 201)
        self.assertEqual(json.loads(resp["body"])["tenantId"], "default")

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
            table, ctx(), {"nickname": "Alt", "firstName": "A", "lastName": "B"})
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
