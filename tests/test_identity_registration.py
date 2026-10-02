"""Tests Gate 10: Identity-Provisionierung (Gate 10).

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


def ctx():
    return {"userId": "user-111", "tenantId": "tenant-gate10",
            "username": "gate10user", "email": "gate10@example.com", "groups": []}


class TestProvision(unittest.TestCase):
    def test_create_returns_201_with_identity_fields(self):
        table = FakeTable()
        resp = handler._provision_user_profile(table, ctx(), {"displayName": "Gate Ten"})
        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertEqual(body["userId"], "user-111")
        self.assertEqual(body["tenantId"], "tenant-gate10")
        self.assertEqual(body["username"], "gate10user")
        self.assertEqual(body["email"], "gate10@example.com")
        self.assertEqual(body["displayName"], "Gate Ten")
        self.assertEqual(body["status"], "ACTIVE")
        self.assertTrue(body["createdAt"])

    def test_duplicate_returns_409_no_overwrite(self):
        table = FakeTable()
        handler._provision_user_profile(table, ctx(), {})
        resp = handler._provision_user_profile(table, ctx(), {"displayName": "Neu"})
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(table.items["user-111"].get("displayName"), None)
        self.assertEqual(table.puts, 1)

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


if __name__ == "__main__":
    unittest.main()
