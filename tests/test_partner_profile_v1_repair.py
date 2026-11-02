"""R05-P0 tests: persisted + reloaded v1 contract repair.

Exercises the REAL handler -> REAL R02 repository -> in-memory DynamoDB fake.
Asserts the persisted item, not only the DTO/validator.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

from tests.test_partner_manual_profiles_api import Harness, _meta, _profile, _registry  # noqa: E402

COLLECTION = "/v1/partner/me/manual-search-profiles"


V1_SEARCH_CONFIG = {
    "skills": 'AWS, Terraform, "Cloud Architecture"',
    "targetRoles": ["Cloud Engineer", "Solutions Architect"],
    "city": "Darmstadt",
    "radiusKm": 50,
    "workModes": ["remote", "hybrid"],
    "employmentTypes": ["full_time"],
}
V1_MATCHING = {
    "requiredSkills": ["AWS"],
    "preferredSkills": ["Cloud Architecture"],
    "excludedTerms": ["Schichtarbeit"],
}


class V1Harness(Harness):
    def create_v1(self, **overrides):
        payload = {
            "name": "Cloud Engineering",
            "description": "v1 profile",
            "searchConfig": dict(V1_SEARCH_CONFIG),
            "matchingPreferences": dict(V1_MATCHING),
        }
        payload.update(overrides)
        return self.call("POST", COLLECTION, body=payload)


# --------------------------------------------------------------------------- #
# schemaVersion
# --------------------------------------------------------------------------- #

class TestSchemaVersion(V1Harness):
    def test_create_response_integer_one(self):
        resp = self.create_v1()
        self.assertEqual(201, resp["statusCode"])
        b = self.body(resp)
        self.assertEqual(1, b["schemaVersion"])
        self.assertIsInstance(b["schemaVersion"], int)

    def test_persisted_item_integer_one(self):
        b = self.body(self.create_v1())
        stored = self.dynamo.resources[b["manualSearchProfileId"]]
        self.assertEqual(1, stored["schemaVersion"])
        self.assertEqual(1, stored["payload"]["schemaVersion"])

    def test_legacy_stored_record_reads_as_integer(self):
        legacy = {
            "resourceId": "legacy-1",
            "resourceType": "ManualSearchProfile",
            "schemaVersion": "v1",
            "userId": "user-1",
            "tenantId": "tenant-1",
            "partnerApplicationId": "app-1",
            "issuer": "https://cognito-idp.eu-central-1.amazonaws.com/pool-1",
            "parentId": "user-1",
            "version": 1,
            "createdAt": "2026-10-31T12:00:00+00:00",
            "updatedAt": "2026-10-31T12:00:00+00:00",
            "payload": {
                "resourceType": "ManualSearchProfile",
                "schemaVersion": "v1",
                "manualProfileId": "legacy-1",
                "userId": "user-1",
                "tenantId": "tenant-1",
                "name": "Legacy",
                "origin": "manual",
                "matchingPreferences": {
                    "requiredSkills": ["AWS"],
                    "roles": ["Cloud Engineer"],
                    "workModes": ["remote"],
                    "employmentTypes": ["full_time"],
                    "locations": ["Darmstadt"],
                },
            },
        }
        self.dynamo.resources["legacy-1"] = legacy
        resp = self.call("GET", f"{COLLECTION}/legacy-1")
        self.assertEqual(200, resp["statusCode"])
        b = self.body(resp)
        self.assertEqual(1, b["schemaVersion"])
        self.assertEqual(["Cloud Engineer"], b["searchConfig"]["targetRoles"])
        self.assertEqual("Darmstadt", b["searchConfig"]["city"])
        self.assertEqual(["AWS"], b["matchingPreferences"]["requiredSkills"])

    def test_legacy_metadata_survives_update(self):
        legacy = {
            "resourceId": "legacy-2", "resourceType": "ManualSearchProfile",
            "schemaVersion": "v1", "userId": "user-1", "tenantId": "tenant-1",
            "partnerApplicationId": "app-1",
            "issuer": "https://cognito-idp.eu-central-1.amazonaws.com/pool-1",
            "parentId": "user-1", "version": 1,
            "createdAt": "2026-10-31T12:00:00+00:00",
            "updatedAt": "2026-10-31T12:00:00+00:00",
            "payload": {
                "resourceType": "ManualSearchProfile", "schemaVersion": "v1",
                "manualProfileId": "legacy-2", "userId": "user-1",
                "tenantId": "tenant-1", "name": "Legacy", "origin": "manual",
                "matchingPreferences": {
                    "requiredSkills": ["AWS"], "roles": ["Cloud Engineer"],
                    "workModes": ["remote"], "employmentTypes": ["full_time"],
                    "locations": ["Darmstadt"], "query": "python",
                },
            },
        }
        self.dynamo.resources["legacy-2"] = legacy
        resp = self.call("PUT", f"{COLLECTION}/legacy-2",
                         body={"name": "Legacy renamed", "version": 1})
        self.assertEqual(200, resp["statusCode"])
        stored = self.dynamo.resources["legacy-2"]["payload"]
        self.assertEqual("Legacy renamed", stored["name"])
        self.assertEqual(1, stored["schemaVersion"])
        self.assertEqual("python",
                         stored["metadata"]["legacy"]["matchingPreferences"]["query"])
        self.assertEqual(["Cloud Engineer"], stored["searchConfig"]["targetRoles"])

    def test_client_cannot_override_schema_version(self):
        # schemaVersion is server-owned; a client-sent value is ignored and the
        # canonical response is still integer 1.
        resp = self.create_v1(schemaVersion=2)
        self.assertEqual(201, resp["statusCode"])
        self.assertEqual(1, self.body(resp)["schemaVersion"])


# --------------------------------------------------------------------------- #
# searchConfig persisted roundtrip
# --------------------------------------------------------------------------- #

class TestSearchConfigPersisted(V1Harness):
    def test_all_six_fields_persist_and_reload(self):
        b = self.body(self.create_v1())
        stored = self.dynamo.resources[b["manualSearchProfileId"]]
        sc = stored["payload"]["searchConfig"]
        self.assertEqual(V1_SEARCH_CONFIG["skills"], sc["skills"])
        self.assertEqual(V1_SEARCH_CONFIG["targetRoles"], sc["targetRoles"])
        self.assertEqual(V1_SEARCH_CONFIG["city"], sc["city"])
        self.assertEqual(V1_SEARCH_CONFIG["radiusKm"], sc["radiusKm"])
        self.assertEqual(V1_SEARCH_CONFIG["workModes"], sc["workModes"])
        self.assertEqual(V1_SEARCH_CONFIG["employmentTypes"], sc["employmentTypes"])
        reloaded = self.body(self.call("GET", f"{COLLECTION}/{b['manualSearchProfileId']}"))
        self.assertEqual(sc, reloaded["searchConfig"])

    def test_quoted_skills_preserved(self):
        b = self.body(self.create_v1())
        got = self.body(self.call("GET", f"{COLLECTION}/{b['manualSearchProfileId']}"))
        self.assertEqual('AWS, Terraform, "Cloud Architecture"',
                         got["searchConfig"]["skills"])

    def test_radius_null_preserved(self):
        sc = dict(V1_SEARCH_CONFIG)
        sc["radiusKm"] = None
        b = self.body(self.create_v1(searchConfig=sc))
        got = self.body(self.call("GET", f"{COLLECTION}/{b['manualSearchProfileId']}"))
        self.assertIsNone(got["searchConfig"]["radiusKm"])
        stored = self.dynamo.resources[b["manualSearchProfileId"]]
        self.assertIsNone(stored["payload"]["searchConfig"]["radiusKm"])

    def test_multi_values_preserved(self):
        sc = dict(V1_SEARCH_CONFIG)
        sc["targetRoles"] = ["Cloud Engineer", "Solutions Architect", "Platform Engineer"]
        sc["workModes"] = ["remote", "hybrid", "onsite"]
        sc["employmentTypes"] = ["full_time", "part_time"]
        b = self.body(self.create_v1(searchConfig=sc))
        got = self.body(self.call("GET", f"{COLLECTION}/{b['manualSearchProfileId']}"))
        self.assertEqual(sc["targetRoles"], got["searchConfig"]["targetRoles"])
        self.assertEqual(sc["workModes"], got["searchConfig"]["workModes"])
        self.assertEqual(sc["employmentTypes"], got["searchConfig"]["employmentTypes"])

    def test_city_preserved(self):
        sc = dict(V1_SEARCH_CONFIG)
        sc["city"] = "Köln"
        b = self.body(self.create_v1(searchConfig=sc))
        got = self.body(self.call("GET", f"{COLLECTION}/{b['manualSearchProfileId']}"))
        self.assertEqual("Köln", got["searchConfig"]["city"])


# --------------------------------------------------------------------------- #
# Independence of searchConfig and matchingPreferences
# --------------------------------------------------------------------------- #

class TestIndependence(V1Harness):
    def test_search_config_change_does_not_touch_matching(self):
        b = self.body(self.create_v1())
        pid = b["manualSearchProfileId"]
        new_sc = dict(V1_SEARCH_CONFIG)
        new_sc["city"] = "Berlin"
        resp = self.call("PUT", f"{COLLECTION}/{pid}", body={
            "searchConfig": new_sc, "version": 1})
        self.assertEqual(200, resp["statusCode"])
        got = self.body(self.call("GET", f"{COLLECTION}/{pid}"))
        self.assertEqual("Berlin", got["searchConfig"]["city"])
        self.assertEqual(V1_MATCHING, got["matchingPreferences"])

    def test_matching_change_does_not_touch_search(self):
        b = self.body(self.create_v1())
        pid = b["manualSearchProfileId"]
        resp = self.call("PUT", f"{COLLECTION}/{pid}", body={
            "matchingPreferences": {"requiredSkills": ["Go"]}, "version": 1})
        self.assertEqual(200, resp["statusCode"])
        got = self.body(self.call("GET", f"{COLLECTION}/{pid}"))
        self.assertEqual(V1_SEARCH_CONFIG, got["searchConfig"])
        self.assertEqual(["Go"], got["matchingPreferences"]["requiredSkills"])

    def test_both_objects_stored_separately(self):
        b = self.body(self.create_v1())
        stored = self.dynamo.resources[b["manualSearchProfileId"]]["payload"]
        self.assertIn("searchConfig", stored)
        self.assertIn("matchingPreferences", stored)
        self.assertNotIn("roles", stored["matchingPreferences"])
        self.assertNotIn("workModes", stored["matchingPreferences"])


# --------------------------------------------------------------------------- #
# CRUD / alias still works
# --------------------------------------------------------------------------- #

class TestCrudAndAlias(V1Harness):
    def test_crud_lifecycle_and_alias(self):
        b = self.body(self.create_v1())
        pid = b["manualSearchProfileId"]
        # lossless alias: API id and persisted R01 id are the same value
        stored = self.dynamo.resources[pid]["payload"]
        self.assertEqual(pid, stored["manualProfileId"])
        self.assertEqual(200, self.call("GET", f"{COLLECTION}/{pid}")["statusCode"])
        self.assertEqual(1, len(self.body(self.call("GET", COLLECTION))["items"]))
        self.assertEqual(200, self.call("PUT", f"{COLLECTION}/{pid}", body={
            "name": "Renamed", "version": 1})["statusCode"])
        self.assertEqual(204, self.call("DELETE", f"{COLLECTION}/{pid}")["statusCode"])
        self.assertEqual(404, self.call("GET", f"{COLLECTION}/{pid}")["statusCode"])

    def test_version_conflict(self):
        b = self.body(self.create_v1())
        pid = b["manualSearchProfileId"]
        resp = self.call("PUT", f"{COLLECTION}/{pid}", body={
            "name": "X", "version": 99})
        self.assertEqual(409, resp["statusCode"])


# --------------------------------------------------------------------------- #
# Security regression (v1 shape must not weaken isolation)
# --------------------------------------------------------------------------- #

class TestSecurityRegression(V1Harness):
    def test_cross_user(self):
        b = self.body(self.create_v1())
        pid = b["manualSearchProfileId"]
        self.assertEqual(404, self.call("GET", f"{COLLECTION}/{pid}", sub="user-2")["statusCode"])

    def test_cross_tenant(self):
        self.assertEqual(403, self.call("GET", COLLECTION, tenant="tenant-other")["statusCode"])

    def test_cross_partner(self):
        self.registry = None
        self.assertEqual(403, self.call("GET", COLLECTION)["statusCode"])

    def test_cross_issuer(self):
        b = self.body(self.create_v1())
        pid = b["manualSearchProfileId"]
        self.assertEqual(404, self.call("GET", f"{COLLECTION}/{pid}",
                                        issuer="https://other/pool")["statusCode"])

    def test_no_agent_or_model_call(self):
        self.create_v1()
        self.assertEqual([], self.enqueued)


if __name__ == "__main__":
    unittest.main()
