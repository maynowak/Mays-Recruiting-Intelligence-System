"""R06 tests: ATSSearchProfileV1 CRUD API.

Real handler -> real R02/R05-A repository -> in-memory DynamoDB fake.
Concurrency is transaction-logic, not real DynamoDB (reserved for R07).
"""

import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

from tests.test_partner_cv_document_api import CvHarness  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    USER, TENANT, ISSUER, PARTNER_APP,
)
from jobsearch.partner_profile_contract import (  # noqa: E402
    ATSSearchProfile, ProfileContractError,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileConflictError,
)

CVS = "/v1/partner/me/cvs"
MANUAL = "/v1/partner/me/manual-search-profiles"
IDENTITY = {
    "user_id": USER, "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP, "issuer": ISSUER,
}
SEARCH_CONFIG = {
    "skills": "AWS, Terraform", "targetRoles": ["Cloud Engineer"],
    "city": "Darmstadt", "radiusKm": 50, "workModes": ["remote"],
    "employmentTypes": ["full_time"],
}
# Synthetic Jobsearch fixture (origin/main @ 0129559)
ATS_CREATE_FIXTURE = {
    "name": "Created ATS Variant",
    "targetRoles": ["Cloud Engineer"],
    "skills": ["AWS", "Cloud Architecture"],
    "criteria": {"schemaVersion": 1, "requiredSkills": ["AWS"],
                 "preferredSkills": [], "excludedTerms": []},
}


class AtsHarness(CvHarness):
    def cv(self):
        return self.body(self.create_cv())["cvId"]

    def make_sp(self, cv_id, name="sp"):
        r = self.call("POST", f"{CVS}/{cv_id}/search-profiles",
                      body={"name": name, "searchConfig": SEARCH_CONFIG})
        return self.body(r)["searchProfileId"]

    def ats_url(self, sp_id, ats_id=None):
        base = f"/v1/partner/me/search-profiles/{sp_id}/ats-profiles"
        return base if ats_id is None else f"{base}/{ats_id}"

    def create_ats(self, sp_id, name="ATS", target_roles=None, skills=None,
                   criteria="OMIT", **overrides):
        payload = {
            "name": name,
            "targetRoles": (target_roles if target_roles is not None
                            else ["DevOps Engineer"]),
            "skills": (skills if skills is not None
                       else ["Terraform", "Cloud Architecture"]),
        }
        if criteria != "OMIT":
            payload["criteria"] = criteria
        payload.update(overrides)
        return self.call("POST", self.ats_url(sp_id), body=payload)

    def parent(self):
        cv_id = self.cv()
        return cv_id, self.make_sp(cv_id)


# --------------------------------------------------------------------------- #
# Contract + CRUD
# --------------------------------------------------------------------------- #

class TestCrud(AtsHarness):
    def test_create_201_v1_shape(self):
        _, sp_id = self.parent()
        resp = self.create_ats(sp_id)
        self.assertEqual(201, resp["statusCode"])
        b = self.body(resp)
        self.assertEqual(1, b["schemaVersion"])
        self.assertTrue(b["atsSearchProfileId"])
        self.assertEqual(sp_id, b["searchProfileId"])
        self.assertEqual("ATS", b["name"])
        self.assertEqual(["DevOps Engineer"], b["targetRoles"])
        self.assertEqual(["Terraform", "Cloud Architecture"], b["skills"])
        self.assertEqual(1, b["version"])
        self.assertNotIn("cvId", b)
        self.assertNotIn("atsProfileId", b)
        self.assertNotIn("criteria", b)

    def test_get_200(self):
        _, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        resp = self.call("GET", self.ats_url(sp_id, ats_id))
        self.assertEqual(200, resp["statusCode"])
        self.assertEqual(ats_id, self.body(resp)["atsSearchProfileId"])

    def test_list_200(self):
        _, sp_id = self.parent()
        self.create_ats(sp_id)
        b = self.body(self.call("GET", self.ats_url(sp_id)))
        self.assertEqual(1, len(b["items"]))
        self.assertIsNone(b["nextCursor"])

    def test_update_200(self):
        _, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        resp = self.call("PUT", self.ats_url(sp_id, ats_id), body={
            "name": "Updated", "targetRoles": ["SRE"],
            "skills": ['"Site Reliability"', "Linux"], "version": 1})
        self.assertEqual(200, resp["statusCode"])
        b = self.body(resp)
        self.assertEqual("Updated", b["name"])
        self.assertEqual(["SRE"], b["targetRoles"])
        self.assertEqual(['"Site Reliability"', "Linux"], b["skills"])
        self.assertEqual(2, b["version"])

    def test_delete_204_then_404(self):
        _, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        self.assertEqual(204, self.call(
            "DELETE", self.ats_url(sp_id, ats_id))["statusCode"])
        self.assertEqual(404, self.call(
            "GET", self.ats_url(sp_id, ats_id))["statusCode"])

    def test_criteria_three_lists(self):
        _, sp_id = self.parent()
        criteria = {"schemaVersion": 1, "requiredSkills": ["Terraform"],
                    "preferredSkills": ["Kubernetes"],
                    "excludedTerms": ["night shift"]}
        b = self.body(self.create_ats(sp_id, criteria=criteria))
        self.assertEqual(criteria, b["criteria"])

    def test_criteria_empty_lists(self):
        _, sp_id = self.parent()
        criteria = {"schemaVersion": 1, "requiredSkills": [],
                    "preferredSkills": [], "excludedTerms": []}
        b = self.body(self.create_ats(sp_id, criteria=criteria))
        self.assertEqual(criteria, b["criteria"])

    def test_criteria_update_merges_one_list(self):
        _, sp_id = self.parent()
        criteria = {"schemaVersion": 1, "requiredSkills": ["A"],
                    "preferredSkills": ["B"], "excludedTerms": ["C"]}
        ats_id = self.body(self.create_ats(sp_id, criteria=criteria))["atsSearchProfileId"]
        b = self.body(self.call("PUT", self.ats_url(sp_id, ats_id), body={
            "criteria": {"schemaVersion": 1, "requiredSkills": ["X"]},
            "version": 1}))
        self.assertEqual(["X"], b["criteria"]["requiredSkills"])
        self.assertEqual(["B"], b["criteria"]["preferredSkills"])
        self.assertEqual(["C"], b["criteria"]["excludedTerms"])

    def test_criteria_explicit_removal(self):
        _, sp_id = self.parent()
        criteria = {"schemaVersion": 1, "requiredSkills": ["A"]}
        ats_id = self.body(self.create_ats(sp_id, criteria=criteria))["atsSearchProfileId"]
        b = self.body(self.call("PUT", self.ats_url(sp_id, ats_id), body={
            "criteria": None, "version": 1}))
        self.assertNotIn("criteria", b)
        self.assertNotIn("criteria", self.body(self.call(
            "GET", self.ats_url(sp_id, ats_id))))

    def test_unknown_criteria_field_422(self):
        _, sp_id = self.parent()
        resp = self.create_ats(sp_id, criteria={
            "schemaVersion": 1, "foo": "bar"})
        self.assertEqual(422, resp["statusCode"])

    def test_score_and_model_fields_422(self):
        _, sp_id = self.parent()
        resp = self.create_ats(sp_id, criteria={
            "schemaVersion": 1, "overallScore": 91,
            "modelExplanation": "no"})
        self.assertEqual(422, resp["statusCode"])

    def test_invalid_criteria_schema_version_422(self):
        _, sp_id = self.parent()
        for sv in ("v1", 2, True):
            resp = self.create_ats(sp_id, criteria={"schemaVersion": sv})
            self.assertEqual(422, resp["statusCode"], f"sv={sv!r}")

    def test_fixture_roundtrip(self):
        _, sp_id = self.parent()
        resp = self.create_ats(
            sp_id, name=ATS_CREATE_FIXTURE["name"],
            target_roles=ATS_CREATE_FIXTURE["targetRoles"],
            skills=ATS_CREATE_FIXTURE["skills"],
            criteria=ATS_CREATE_FIXTURE["criteria"])
        self.assertEqual(201, resp["statusCode"])
        b = self.body(resp)
        self.assertEqual(ATS_CREATE_FIXTURE["name"], b["name"])
        self.assertEqual(ATS_CREATE_FIXTURE["targetRoles"], b["targetRoles"])
        self.assertEqual(ATS_CREATE_FIXTURE["skills"], b["skills"])
        self.assertEqual(ATS_CREATE_FIXTURE["criteria"], b["criteria"])
        self.assertNotIn("cvId", b)

    def test_parent_search_config_unchanged(self):
        cv_id, sp_id = self.parent()
        self.create_ats(sp_id, skills=["Kubernetes"], target_roles=["DevOps"])
        sp = self.body(self.call("GET", f"{CVS}/{cv_id}/search-profiles/{sp_id}"))
        self.assertEqual(SEARCH_CONFIG, sp["searchConfig"])
        ats = self.body(self.call("GET", self.ats_url(sp_id)))["items"][0]
        self.assertNotIn("searchConfig", ats)


# --------------------------------------------------------------------------- #
# Parent / security
# --------------------------------------------------------------------------- #

class TestSecurity(AtsHarness):
    def test_missing_parent_404(self):
        self.assertEqual(404, self.call(
            "GET", self.ats_url("does-not-exist"))["statusCode"])
        self.assertEqual(404, self.create_ats("does-not-exist")["statusCode"])

    def test_foreign_parent_404(self):
        _, sp_id = self.parent()
        r = self.call("POST", self.ats_url(sp_id), body={
            "name": "X", "targetRoles": ["A"], "skills": ["B"]}, sub="user-2")
        self.assertEqual(404, r["statusCode"])

    def test_manual_profile_is_not_parent(self):
        r = self.call("POST", MANUAL, body={
            "name": "manual", "searchConfig": SEARCH_CONFIG,
            "matchingPreferences": {}})
        self.assertEqual(201, r["statusCode"])
        manual_id = self.body(r)["manualSearchProfileId"]
        self.assertEqual(404, self.create_ats(manual_id)["statusCode"])

    def test_wrong_parent_on_item(self):
        cv_id = self.cv()
        sp1 = self.make_sp(cv_id, "sp1")
        sp2 = self.make_sp(cv_id, "sp2")
        ats_id = self.body(self.create_ats(sp1))["atsSearchProfileId"]
        self.assertEqual(404, self.call("GET", self.ats_url(sp2, ats_id))["statusCode"])
        self.assertEqual(404, self.call("PUT", self.ats_url(sp2, ats_id),
                                        body={"name": "x", "version": 1})["statusCode"])
        self.assertEqual(404, self.call("DELETE", self.ats_url(sp2, ats_id))["statusCode"])

    def test_cross_user(self):
        _, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        self.assertEqual(404, self.call("GET", self.ats_url(sp_id, ats_id),
                                        sub="user-2")["statusCode"])

    def test_cross_tenant(self):
        _, sp_id = self.parent()
        self.assertEqual(403, self.call("GET", self.ats_url(sp_id),
                                        tenant="tenant-other")["statusCode"])

    def test_cross_partner(self):
        _, sp_id = self.parent()
        self.registry = None
        self.assertEqual(403, self.call("GET", self.ats_url(sp_id))["statusCode"])

    def test_cross_issuer(self):
        _, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        self.assertEqual(404, self.call("GET", self.ats_url(sp_id, ats_id),
                                        issuer="https://other/pool")["statusCode"])

    def test_identity_forgery(self):
        _, sp_id = self.parent()
        resp = self.create_ats(sp_id, userId="victim", tenantId="other")
        self.assertEqual(400, resp["statusCode"])

    def test_missing_credential(self):
        _, sp_id = self.parent()
        self.assertEqual(401, self.call("GET", self.ats_url(sp_id),
                                        credential=None)["statusCode"])

    def test_null_parent_contract_rejected(self):
        with self.assertRaises(ProfileContractError):
            ATSSearchProfile(
                ats_profile_id="a", search_profile_id=None,
                user_id="u", tenant_id="t", name="n").validate()


# --------------------------------------------------------------------------- #
# Capacity / idempotency / lifecycle
# --------------------------------------------------------------------------- #

class TestCapacityAndLifecycle(AtsHarness):
    def test_five_allowed_sixth_409(self):
        _, sp_id = self.parent()
        for i in range(5):
            self.assertEqual(201, self.create_ats(sp_id, name=f"A{i}")["statusCode"])
        self.assertEqual(409, self.create_ats(sp_id, name="A6")["statusCode"])

    def test_concurrent_last_slot(self):
        _, sp_id = self.parent()
        for i in range(4):
            self.assertEqual(201, self.create_ats(sp_id, name=f"A{i}")["statusCode"])
        results = []
        lock = threading.Lock()

        def one(i):
            r = self.create_ats(sp_id, name=f"R{i}")
            with lock:
                results.append(r["statusCode"])

        threads = [threading.Thread(target=one, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(1, results.count(201))
        self.assertEqual(1, results.count(409))

    def test_idempotent_retry(self):
        _, sp_id = self.parent()
        body = {"name": "Idem", "targetRoles": ["A"], "skills": ["B"]}
        r1 = self.call("POST", self.ats_url(sp_id), body=body,
                       extra_headers={"Idempotency-Key": "ats-key"})
        r2 = self.call("POST", self.ats_url(sp_id), body=body,
                       extra_headers={"Idempotency-Key": "ats-key"})
        self.assertEqual(201, r1["statusCode"])
        self.assertEqual(201, r2["statusCode"])
        self.assertEqual(self.body(r1)["atsSearchProfileId"],
                         self.body(r2)["atsSearchProfileId"])
        self.assertEqual(1, len(self.body(self.call("GET", self.ats_url(sp_id)))["items"]))

    def test_idempotency_different_payload_409(self):
        _, sp_id = self.parent()
        r1 = self.call("POST", self.ats_url(sp_id), body={
            "name": "A", "targetRoles": ["A"], "skills": ["B"]},
            extra_headers={"Idempotency-Key": "ats-key-2"})
        self.assertEqual(201, r1["statusCode"])
        r2 = self.call("POST", self.ats_url(sp_id), body={
            "name": "B", "targetRoles": ["A"], "skills": ["B"]},
            extra_headers={"Idempotency-Key": "ats-key-2"})
        self.assertEqual(409, r2["statusCode"])

    def test_delete_frees_capacity(self):
        _, sp_id = self.parent()
        ids = [self.body(self.create_ats(sp_id, name=f"A{i}"))["atsSearchProfileId"]
               for i in range(5)]
        self.assertEqual(204, self.call("DELETE", self.ats_url(sp_id, ids[0]))["statusCode"])
        self.assertEqual(201, self.create_ats(sp_id, name="A6")["statusCode"])

    def test_stale_update_409(self):
        _, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        self.assertEqual(409, self.call("PUT", self.ats_url(sp_id, ats_id),
                                        body={"name": "x", "version": 99})["statusCode"])

    def test_stale_delete_409(self):
        _, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        self.assertEqual(409, self.call("DELETE", self.ats_url(sp_id, ats_id),
                                        query={"version": "99"})["statusCode"])

    def test_parent_delete_with_ats_409(self):
        cv_id, sp_id = self.parent()
        self.create_ats(sp_id)
        r = self.call("DELETE", f"{CVS}/{cv_id}/search-profiles/{sp_id}")
        self.assertEqual(409, r["statusCode"])

    def test_parent_delete_vs_child_create_no_orphan(self):
        cv_id = self.cv()
        sp_id = self.make_sp(cv_id)
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def child():
            barrier.wait()
            try:
                self.repo.create(ATSSearchProfile(
                    ats_profile_id="ats-race", search_profile_id=sp_id,
                    cv_id=cv_id, user_id=USER, tenant_id=TENANT, name="race",
                    target_roles=["A"], skills=["B"]), **IDENTITY)
                results.append("child")
            except Exception:
                errors.append("child")

        def delete():
            barrier.wait()
            try:
                self.repo.delete(sp_id, **IDENTITY,
                                 child_type="ATSSearchProfile")
                results.append("delete")
            except PartnerProfileConflictError:
                errors.append("delete")

        t1 = threading.Thread(target=child)
        t2 = threading.Thread(target=delete)
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(1, len(results))
        parent = self.repo.get(sp_id, **IDENTITY)
        children, _ = self.repo.list_by_parent(
            sp_id, USER, TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER)
        if parent is None:
            self.assertEqual([], children)

    def test_counter_no_drift(self):
        _, sp_id = self.parent()
        ids = [self.body(self.create_ats(sp_id, name=f"A{i}"))["atsSearchProfileId"]
               for i in range(5)]
        self.assertEqual(5, self.dynamo.resources[f"capacity#ATS#{sp_id}"]["count"])
        self.call("DELETE", self.ats_url(sp_id, ids[0]))
        self.assertEqual(4, self.dynamo.resources[f"capacity#ATS#{sp_id}"]["count"])

    def test_legacy_record_readable(self):
        cv_id, sp_id = self.parent()
        legacy = {
            "resourceId": "ats-legacy", "resourceType": "ATSSearchProfile",
            "schemaVersion": "v1", "userId": USER, "tenantId": TENANT,
            "partnerApplicationId": PARTNER_APP, "issuer": ISSUER,
            "parentId": sp_id, "version": 1,
            "createdAt": "2026-10-31T12:00:00+00:00",
            "updatedAt": "2026-10-31T12:00:00+00:00",
            "payload": {
                "resourceType": "ATSSearchProfile", "schemaVersion": "v1",
                "atsProfileId": "ats-legacy", "searchProfileId": sp_id,
                "cvId": cv_id, "userId": USER, "tenantId": TENANT,
                "name": "Legacy", "targetRoles": ["A"], "skills": ["B"],
                "requirements": ["R"], "preferredCriteria": ["P"],
                "exclusions": ["E"],
            },
        }
        self.dynamo.resources["ats-legacy"] = legacy
        b = self.body(self.call("GET", self.ats_url(sp_id, "ats-legacy")))
        self.assertEqual(1, b["schemaVersion"])
        self.assertEqual(["R"], b["criteria"]["requiredSkills"])
        self.assertEqual(["P"], b["criteria"]["preferredSkills"])
        self.assertEqual(["E"], b["criteria"]["excludedTerms"])
        put = self.call("PUT", self.ats_url(sp_id, "ats-legacy"),
                        body={"name": "Renamed", "version": 1})
        self.assertEqual(200, put["statusCode"])
        stored = self.dynamo.resources["ats-legacy"]["payload"]
        self.assertTrue(stored["metadata"].get("legacyIncomplete"))


if __name__ == "__main__":
    unittest.main()
