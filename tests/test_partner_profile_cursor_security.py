"""R07-FIX-04: secure pagination cursor tests (real production codec)."""

import base64
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402
import jobsearch.partner_profile_cursor as cursor_module  # noqa: E402
from tests.test_partner_ats_profiles_api import AtsHarness  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    FakeDynamo, USER, TENANT, ISSUER, PARTNER_APP,
)
from jobsearch.partner_profile_cursor import (  # noqa: E402
    CURSOR_PREFIX, CURSOR_TTL_SECONDS, CursorError, cursor_item_key,
    query_digest,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileRepository,
)

CTX = {"userId": USER, "tenantId": TENANT,
       "partnerApplicationId": PARTNER_APP, "issuer": ISSUER}
KEY = {"resourceId": "ats-1", "parentId": "sp-1"}
SCOPE = "ats-search-profiles"
RESOURCE_TYPE = "ATSSearchProfile"
PARENT = "sp-1"
LIMIT = 1


class CursorHarness(unittest.TestCase):
    def setUp(self):
        self.dynamo = FakeDynamo()
        self.repo = PartnerProfileRepository(table_name="ris-cursor")
        self.repo._table = self.dynamo
        self.repo._client = self.dynamo

    def issue(self, key=None, **overrides):
        params = dict(user_id=USER, tenant_id=TENANT,
                      partner_app_id=PARTNER_APP, issuer=ISSUER,
                      scope=SCOPE, resource_type=RESOURCE_TYPE,
                      parent_id=PARENT, limit=LIMIT)
        params.update(overrides)
        return self.repo.issue_cursor(key if key is not None else KEY,
                                      **params)

    def resolve(self, token, **overrides):
        params = dict(user_id=USER, tenant_id=TENANT,
                      partner_app_id=PARTNER_APP, issuer=ISSUER,
                      scope=SCOPE, resource_type=RESOURCE_TYPE,
                      parent_id=PARENT, limit=LIMIT)
        params.update(overrides)
        return self.repo.resolve_cursor(token, **params)

    def cursor_item(self):
        return next(v for v in self.dynamo.resources.values()
                    if v.get("resourceType") == "CursorToken")


class TestRoundtrip(CursorHarness):
    def test_issue_and_resolve(self):
        token = self.issue()
        self.assertTrue(token.startswith(CURSOR_PREFIX))
        self.assertEqual(KEY, self.resolve(token))

    def test_token_has_no_readable_internal_key(self):
        token = self.issue()
        self.assertNotIn("ats-1", token)
        self.assertNotIn("resourceId", token)
        self.assertNotIn("sp-1", token)

    def test_same_payload_gets_different_nonces(self):
        first = self.issue()
        second = self.issue()
        self.assertNotEqual(first, second)
        self.assertEqual(KEY, self.resolve(first))
        self.assertEqual(KEY, self.resolve(second))

    def test_cursor_item_has_ttl_and_version(self):
        self.issue()
        item = self.cursor_item()
        self.assertEqual(1, item["version"])
        self.assertGreater(item["expiresAt"], int(time.time()))
        self.assertEqual(item["issuedAt"] + CURSOR_TTL_SECONDS,
                         item["expiresAt"])
        self.assertEqual(query_digest(
            scope=SCOPE, resource_type=RESOURCE_TYPE, parent_id=PARENT),
            item["queryHash"])


class TestRejection(CursorHarness):
    def test_tampered_token(self):
        token = self.issue()
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with self.assertRaises(CursorError):
            self.resolve(tampered)

    def test_missing_cursor_item(self):
        token = CURSOR_PREFIX + "A" * 43
        with self.assertRaises(CursorError):
            self.resolve(token)

    def test_empty_and_malformed(self):
        for token in (None, "", "not-a-token", "rp1_short", "rp1_" + "!" * 43):
            with self.assertRaises(CursorError):
                self.resolve(token)

    def test_too_large(self):
        with self.assertRaises(CursorError):
            self.resolve(CURSOR_PREFIX + "A" * 300)

    def test_legacy_base64_json_cursor(self):
        legacy = base64.urlsafe_b64encode(
            json.dumps({"resourceId": "ats-1"}).encode()).decode()
        with self.assertRaises(CursorError):
            self.resolve(legacy)

    def test_expired_cursor_is_deleted(self):
        token = self.issue()
        item = self.cursor_item()
        item["expiresAt"] = int(time.time()) - 1
        with self.assertRaises(CursorError):
            self.resolve(token)
        self.assertNotIn(cursor_item_key(token), self.dynamo.resources)

    def test_unknown_version(self):
        token = self.issue()
        self.cursor_item()["version"] = 2
        with self.assertRaises(CursorError):
            self.resolve(token)

    def test_wrong_user(self):
        token = self.issue()
        with self.assertRaises(CursorError):
            self.resolve(token, user_id="other-user")

    def test_wrong_tenant(self):
        token = self.issue()
        with self.assertRaises(CursorError):
            self.resolve(token, tenant_id="other-tenant")

    def test_wrong_partner(self):
        token = self.issue()
        with self.assertRaises(CursorError):
            self.resolve(token, partner_app_id="other-partner")

    def test_wrong_issuer(self):
        token = self.issue()
        with self.assertRaises(CursorError):
            self.resolve(token, issuer="https://other/pool")

    def test_wrong_parent(self):
        token = self.issue()
        with self.assertRaises(CursorError):
            self.resolve(token, parent_id="sp-2")

    def test_wrong_resource_type(self):
        token = self.issue()
        with self.assertRaises(CursorError):
            self.resolve(token, resource_type="CVSearchProfile")

    def test_wrong_scope(self):
        token = self.issue()
        with self.assertRaises(CursorError):
            self.resolve(token, scope="cv-search-profiles")

    def test_page_size_is_not_part_of_query_binding(self):
        token = self.issue()
        self.assertEqual(KEY, self.resolve(token, limit=50))

    def test_foreign_store_cannot_resolve(self):
        token = self.issue()
        other = PartnerProfileRepository(table_name="ris-cursor")
        other._table = FakeDynamo()
        other._client = other._table
        with self.assertRaises(CursorError):
            other.resolve_cursor(
                token, user_id=USER, tenant_id=TENANT,
                partner_app_id=PARTNER_APP, issuer=ISSUER, scope=SCOPE,
                resource_type=RESOURCE_TYPE, parent_id=PARENT, limit=LIMIT)

    def test_store_read_failure_is_not_a_400(self):
        token = self.issue()
        with patch.object(self.dynamo, "get_item",
                          side_effect=RuntimeError("store down")):
            with self.assertRaises(RuntimeError):
                self.resolve(token)

    def test_issue_rejects_empty_or_oversized_key(self):
        with self.assertRaises(ValueError):
            self.issue(key={})
        with self.assertRaises(ValueError):
            self.issue(key={"resourceId": "x" * 5000})

    def test_no_logging_of_token_material(self):
        source = Path(cursor_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("print(", source)
        self.assertNotIn("logger.", source)


class TestApiCursorBinding(AtsHarness):
    def _three(self):
        _, sp_id = self.parent()
        ids = []
        for i in range(3):
            ids.append(self.body(self.create_ats(
                sp_id, name=f"A{i}"))["atsSearchProfileId"])
        return sp_id, ids

    def test_two_page_roundtrip(self):
        sp_id, ids = self._three()
        first = self.body(self.call(
            "GET", self.ats_url(sp_id), query={"limit": "1"}))
        self.assertEqual(1, len(first["items"]))
        token = first["nextCursor"]
        self.assertTrue(token.startswith(CURSOR_PREFIX))
        second = self.body(self.call(
            "GET", self.ats_url(sp_id),
            query={"cursor": token}))
        self.assertEqual(2, len(second["items"]))
        self.assertNotEqual(first["items"][0]["atsSearchProfileId"],
                            second["items"][0]["atsSearchProfileId"])
        self.assertIn(first["items"][0]["atsSearchProfileId"], ids)
        self.assertIn(second["items"][0]["atsSearchProfileId"], ids)

    def test_tampered_cursor_is_400(self):
        sp_id, _ = self._three()
        token = self.body(self.call(
            "GET", self.ats_url(sp_id), query={"limit": "1"}))["nextCursor"]
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        resp = self.call("GET", self.ats_url(sp_id),
                         query={"limit": "1", "cursor": tampered})
        self.assertEqual(400, resp["statusCode"])

    def test_foreign_user_cursor_is_400(self):
        sp_id, _ = self._three()
        token = self.body(self.call(
            "GET", self.ats_url(sp_id), query={"limit": "1"}))["nextCursor"]
        resp = self.call("GET", self.ats_url(sp_id),
                         query={"limit": "1", "cursor": token}, sub="user-2")
        # The parent is hidden from user-2 before the cursor can be used.
        self.assertIn(resp["statusCode"], (400, 404))

    def test_wrong_parent_cursor_is_400(self):
        cv_id, sp1 = self.parent()
        sp2 = self.make_sp(cv_id, "sp-2")
        self.create_ats(sp1, name="one")
        self.create_ats(sp1, name="two")
        token = self.body(self.call(
            "GET", self.ats_url(sp1), query={"limit": "1"}))["nextCursor"]
        self.assertIsNotNone(token)
        resp = self.call("GET", self.ats_url(sp2),
                         query={"limit": "1", "cursor": token})
        self.assertEqual(400, resp["statusCode"])

    def test_legacy_cursor_is_400(self):
        sp_id, _ = self._three()
        legacy = base64.urlsafe_b64encode(
            json.dumps({"resourceId": "internal"}).encode()).decode()
        resp = self.call("GET", self.ats_url(sp_id),
                         query={"limit": "1", "cursor": legacy})
        self.assertEqual(400, resp["statusCode"])

    def test_expired_api_cursor_is_400(self):
        sp_id, _ = self._three()
        token = self.body(self.call(
            "GET", self.ats_url(sp_id), query={"limit": "1"}))["nextCursor"]
        item = next(v for v in self.dynamo.resources.values()
                    if v.get("resourceType") == "CursorToken")
        item["expiresAt"] = int(time.time()) - 1
        resp = self.call("GET", self.ats_url(sp_id),
                         query={"limit": "1", "cursor": token})
        self.assertEqual(400, resp["statusCode"])

    def test_store_failure_is_500(self):
        sp_id, _ = self._three()
        token = self.body(self.call(
            "GET", self.ats_url(sp_id), query={"limit": "1"}))["nextCursor"]
        real_get = self.dynamo.get_item

        def flaky(Key, ConsistentRead=False):
            if Key["resourceId"].startswith("cursor#"):
                raise RuntimeError("cursor store unavailable")
            return real_get(Key, ConsistentRead=ConsistentRead)

        with patch.object(self.dynamo, "get_item", side_effect=flaky):
            resp = self.call("GET", self.ats_url(sp_id),
                             query={"limit": "1", "cursor": token})
        self.assertEqual(500, resp["statusCode"])
        self.assertNotIn(token, json.dumps(self.body(resp)))


class TestManualCursor(AtsHarness):
    def test_manual_list_cursor_roundtrip_and_legacy_rejection(self):
        for i in range(2):
            self.assertEqual(201, self.create(name=f"M{i}")["statusCode"])
        first = self.body(self.call(
            "GET", "/v1/partner/me/manual-search-profiles",
            query={"limit": "1"}))
        self.assertEqual(1, len(first["items"]))
        token = first["nextCursor"]
        second = self.body(self.call(
            "GET", "/v1/partner/me/manual-search-profiles",
            query={"limit": "1", "cursor": token}))
        self.assertEqual(1, len(second["items"]))
        legacy = base64.urlsafe_b64encode(b'{"a":1}').decode()
        resp = self.call("GET", "/v1/partner/me/manual-search-profiles",
                         query={"limit": "1", "cursor": legacy})
        self.assertEqual(400, resp["statusCode"])


if __name__ == "__main__":
    unittest.main()
