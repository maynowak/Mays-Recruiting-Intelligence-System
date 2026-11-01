"""Focused UserProfileV1 PATCH and optimistic-concurrency coverage."""

import importlib.util
import json
import os
import sys
import threading
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "user_profile_versioning_handler", os.path.join(ROOT, "lambda", "handler.py"))
handler = importlib.util.module_from_spec(spec)
sys.modules["user_profile_versioning_handler"] = handler
spec.loader.exec_module(handler)


class ConditionalFailure(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class AtomicProfileTable:
    """Small DynamoDB Local equivalent for the conditional update contract."""

    def __init__(self, item=None):
        self.item = dict(item) if item else None
        self.lock = threading.Lock()
        self.update_calls = 0

    def get_item(self, Key):
        with self.lock:
            if not self.item or self.item.get("userId") != Key["userId"]:
                return {}
            return {"Item": dict(self.item)}

    def update_item(self, Key, UpdateExpression, ConditionExpression,
                    ExpressionAttributeNames, ExpressionAttributeValues,
                    ReturnValues):
        with self.lock:
            self.update_calls += 1
            item = self.item
            names = ExpressionAttributeNames
            values = ExpressionAttributeValues
            if not item or item.get("userId") != Key["userId"]:
                raise ConditionalFailure()
            if item.get(names["#tenantId"]) != values[":tenantId"]:
                raise ConditionalFailure()
            expected = values[":expectedVersion"]
            if "version" in item and item["version"] != expected:
                raise ConditionalFailure()
            for assignment in UpdateExpression[len("SET "):].split(","):
                left, right = (part.strip() for part in assignment.split("=", 1))
                item[names[left]] = values[right]
            return {"Attributes": dict(item)}


def context(tenant="tenant-a"):
    return {"userId": "user-a", "tenantId": tenant,
            "email": "jwt@example.test", "groups": []}


def event(method="PATCH", body=None, tenant="tenant-a", headers=None):
    claims = {"sub": "user-a", "email": "jwt@example.test",
              "custom:tenant_id": tenant}
    return {
        "httpMethod": method,
        "path": "/me/profile",
        "headers": headers or {},
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {"authorizer": {"jwt": {"claims": claims}}},
    }


def profile(version=1, **overrides):
    value = {
        "userId": "user-a", "tenantId": "tenant-a", "email": "stored@example.test",
        "status": "ACTIVE", "nickname": "Old", "firstName": "Ada",
        "lastName": "Lovelace", "createdAt": "2026-11-01T00:00:00",
        "updatedAt": "2026-11-01T00:00:00", "version": version,
    }
    value.update(overrides)
    return value


class TestUserProfileVersioning(unittest.TestCase):
    def test_get_patch_get_roundtrip_and_partial_update(self):
        table = AtomicProfileTable(profile())
        with patch.object(handler, "_get_dynamodb", return_value=type(
                "DDB", (), {"Table": lambda self, name: table})()), \
                patch.dict(os.environ, {"USER_PROFILE_TABLE": "profiles"}):
            before = handler._handle_me_profile(event("GET"), None)
            updated = handler.handler(event(body={"nickname": "New", "expectedVersion": 1}), None)
            after = handler._handle_me_profile(event("GET"), None)

        self.assertEqual(before["statusCode"], 200)
        self.assertEqual(updated["statusCode"], 200)
        self.assertEqual(after["statusCode"], 200)
        body = json.loads(updated["body"])
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["version"], 2)
        self.assertEqual(body["email"], "stored@example.test")
        self.assertEqual(body["firstName"], "Ada")
        self.assertEqual(json.loads(after["body"])["nickname"], "New")

    def test_legacy_missing_version_is_atomically_migrated(self):
        table = AtomicProfileTable(profile())
        del table.item["version"]
        result = handler._update_user_profile(
            table, context(), {"lastName": "Byron"}, expected_version=1,
            tenant_id="tenant-a")
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(table.item["version"], 2)
        self.assertEqual(json.loads(result["body"])["lastName"], "Byron")

    def test_stale_version_is_conflict_and_does_not_write(self):
        table = AtomicProfileTable(profile(version=2))
        result = handler._update_user_profile(
            table, context(), {"nickname": "Rejected"}, expected_version=1,
            tenant_id="tenant-a")
        self.assertEqual(result["statusCode"], 409)
        self.assertEqual(table.item["nickname"], "Old")
        self.assertEqual(table.update_calls, 1)

    def test_parallel_updates_have_one_winner(self):
        table = AtomicProfileTable(profile())
        results = []

        def update(value):
            results.append(handler._update_user_profile(
                table, context(), {"nickname": value}, expected_version=1,
                tenant_id="tenant-a")["statusCode"])

        threads = [threading.Thread(target=update, args=("A",)),
                   threading.Thread(target=update, args=("B",))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(table.item["version"], 2)

    def test_identity_fields_and_invalid_payloads_are_rejected(self):
        table = AtomicProfileTable(profile())
        with patch.object(handler, "_get_dynamodb", return_value=type(
                "DDB", (), {"Table": lambda self, name: table})()), \
                patch.dict(os.environ, {"USER_PROFILE_TABLE": "profiles"}):
            forged = handler.handler(event(body={
                "nickname": "x", "expectedVersion": 1, "email": "evil@test",
                "userId": "other", "status": "disabled"}), None)
            malformed = handler.handler(event(body=["not", "an", "object"]), None)
        self.assertEqual(forged["statusCode"], 400)
        self.assertEqual(malformed["statusCode"], 400)
        self.assertEqual(table.item["email"], "stored@example.test")

    def test_if_match_and_missing_token_semantics(self):
        table = AtomicProfileTable(profile())
        with patch.object(handler, "_get_dynamodb", return_value=type(
                "DDB", (), {"Table": lambda self, name: table})()), \
                patch.dict(os.environ, {"USER_PROFILE_TABLE": "profiles"}):
            missing = handler.handler(event(body={"nickname": "x"}), None)
            updated = handler.handler(event(body={"nickname": "x"},
                                            headers={"If-Match": '"1"'}), None)
        self.assertEqual(missing["statusCode"], 428)
        self.assertEqual(updated["statusCode"], 200)

    def test_tenant_mismatch_cannot_update_profile(self):
        table = AtomicProfileTable(profile())
        result = handler._update_user_profile(
            table, context(tenant="tenant-b"), {"nickname": "x"},
            expected_version=1, tenant_id="tenant-b")
        self.assertEqual(result["statusCode"], 404)
        self.assertEqual(table.item["nickname"], "Old")


if __name__ == "__main__":
    unittest.main()
