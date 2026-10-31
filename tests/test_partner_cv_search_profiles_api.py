"""R05-B tests: CVSearchProfileV1 CRUD API.

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
    ATSSearchProfile, CVSearchProfile, SearchConfiguration,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileConflictError,
)

CVS = "/v1/partner/me/cvs"
IDENTITY = {
    "user_id": USER, "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP, "issuer": ISSUER,
}
SEARCH_CONFIG = {
    "skills": 'AWS, Terraform, "Cloud Architecture"',
    "targetRoles": ["Cloud Engineer", "Solutions Architect"],
    "city": "Darmstadt",
    "radiusKm": 50,
    "workModes": ["remote", "hybrid"],
    "employmentTypes": ["full_time"],
}


def _sp(cv_id, sp_id="sp-1", user_id=USER, tenant_id=TENANT, name="Cloud"):
    return CVSearchProfile(
        search_profile_id=sp_id, cv_id=cv_id, user_id=user_id,
        tenant_id=tenant_id, name=name, origin="cv",
        search_config=SearchConfiguration(
            skills="AWS", target_roles=["Cloud Engineer"], city="Berlin",
            radius_km=25, work_modes=["remote"],
            employment_types=["full_time"]))


def _ats(sp_id, cv_id, ats_id="ats-1"):
    return ATSSearchProfile(
        ats_profile_id=ats_id, search_profile_id=sp_id, cv_id=cv_id,
        user_id=USER, tenant_id=TENANT, name="ats")


class CvSpHarness(CvHarness):
    def cv(self):
        return self.body(self.create_cv())["cvId"]

    def url(self, cv_id, sp_id=None):
        base = f"{CVS}/{cv_id}/search-profiles"
        return base if sp_id is None else f"{base}/{sp_id}"

    def create_sp(self, cv_id, name="Cloud", search_config=None, **overrides):
        payload = {
            "name": name,
            "description": "derived",
            "searchConfig": dict(search_config or SEARCH_CONFIG),
        }
        payload.update(overrides)
        return self.call("POST", self.url(cv_id), body=payload)

    def body_of(self, resp):
        return json.loads(resp["body"]) if resp.get("body") else None


# --------------------------------------------------------------------------- #
# CRUD + contract
# --------------------------------------------------------------------------- #

class TestCrud(CvSpHarness):
    def test_create_201_v1_shape(self):
        cv_id = self.cv()
        resp = self.create_sp(cv_id)
        self.assertEqual(201, resp["statusCode"])
        b = self.body_of(resp)
        self.assertEqual(1, b["schemaVersion"])
        self.assertTrue(b["searchProfileId"])
        self.assertEqual(cv_id, b["cvId"])
        self.assertEqual("cv", b["origin"])
        self.assertEqual("derived", b["description"])
        self.assertEqual(1, b["version"])
        self.assertEqual(SEARCH_CONFIG, b["searchConfig"])

    def test_get_200(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        resp = self.call("GET", self.url(cv_id, sp_id))
        self.assertEqual(200, resp["statusCode"])
        self.assertEqual(sp_id, self.body_of(resp)["searchProfileId"])

    def test_list_200(self):
        cv_id = self.cv()
        self.create_sp(cv_id)
        resp = self.call("GET", self.url(cv_id))
        self.assertEqual(200, resp["statusCode"])
        b = self.body_of(resp)
        self.assertEqual(1, len(b["items"]))
        self.assertIsNone(b["nextCursor"])

    def test_update_200_full_roundtrip(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        new_cfg = {
            "skills": '"Machine Learning" Python',
            "targetRoles": ["ML Engineer", "Data Scientist"],
            "city": "Köln",
            "radiusKm": None,
            "workModes": ["hybrid", "onsite"],
            "employmentTypes": ["full_time", "part_time"],
        }
        resp = self.call("PUT", self.url(cv_id, sp_id), body={
            "name": "ML", "description": "new", "searchConfig": new_cfg,
            "version": 1})
        self.assertEqual(200, resp["statusCode"])
        b = self.body_of(resp)
        self.assertEqual("ML", b["name"])
        self.assertEqual(2, b["version"])
        self.assertEqual(new_cfg, b["searchConfig"])
        self.assertIsNone(b["searchConfig"]["radiusKm"])

    def test_delete_204_then_404(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        self.assertEqual(204, self.call("DELETE", self.url(cv_id, sp_id))["statusCode"])
        self.assertEqual(404, self.call("GET", self.url(cv_id, sp_id))["statusCode"])

    def test_quoted_skills_and_multi_values(self):
        cv_id = self.cv()
        cfg = dict(SEARCH_CONFIG)
        cfg["targetRoles"] = ["A", "B", "C"]
        cfg["workModes"] = ["remote", "hybrid", "onsite"]
        cfg["employmentTypes"] = ["full_time", "part_time"]
        b = self.body_of(self.create_sp(cv_id, search_config=cfg))
        self.assertEqual('AWS, Terraform, "Cloud Architecture"', b["searchConfig"]["skills"])
        self.assertEqual(cfg["targetRoles"], b["searchConfig"]["targetRoles"])
        self.assertEqual(cfg["workModes"], b["searchConfig"]["workModes"])
        self.assertEqual(cfg["employmentTypes"], b["searchConfig"]["employmentTypes"])

    def test_invalid_search_config_422(self):
        cv_id = self.cv()
        resp = self.create_sp(cv_id, search_config={
            "skills": "AWS", "targetRoles": ["Dev"], "city": "",
            "radiusKm": 7, "workModes": ["remote"],
            "employmentTypes": ["full_time"]})
        self.assertEqual(422, resp["statusCode"])

    def test_missing_name_422(self):
        cv_id = self.cv()
        resp = self.create_sp(cv_id, name="")
        self.assertEqual(422, resp["statusCode"])

    def test_pagination(self):
        cv_id = self.cv()
        self.create_sp(cv_id, name="A")
        self.create_sp(cv_id, name="B")
        items = []
        cursor = None
        while True:
            query = {"limit": "1"}
            if cursor:
                query["cursor"] = cursor
            b = self.body_of(self.call("GET", self.url(cv_id), query=query))
            items.extend(b["items"])
            cursor = b["nextCursor"]
            if not cursor:
                break
        self.assertEqual(2, len(items))
        self.assertEqual(2, len({i["searchProfileId"] for i in items}))


# --------------------------------------------------------------------------- #
# Security + parent isolation
# --------------------------------------------------------------------------- #

class TestSecurity(CvSpHarness):
    def test_cross_user(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        self.assertEqual(404, self.call("GET", self.url(cv_id, sp_id), sub="user-2")["statusCode"])
        # the foreign CV is not visible at all -> 404, never an empty oracle
        self.assertEqual(404, self.call("GET", self.url(cv_id), sub="user-2")["statusCode"])

    def test_cross_tenant(self):
        cv_id = self.cv()
        self.assertEqual(403, self.call("GET", self.url(cv_id), tenant="tenant-other")["statusCode"])

    def test_cross_partner(self):
        cv_id = self.cv()
        self.registry = None
        self.assertEqual(403, self.call("GET", self.url(cv_id))["statusCode"])

    def test_cross_issuer(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        self.assertEqual(404, self.call("GET", self.url(cv_id, sp_id),
                                        issuer="https://other/pool")["statusCode"])

    def test_forged_identity_rejected(self):
        cv_id = self.cv()
        resp = self.create_sp(cv_id, userId="victim", tenantId="other")
        self.assertEqual(400, resp["statusCode"])
        self.assertEqual("CLIENT_IDENTITY_FORBIDDEN", self.body_of(resp)["code"])

    def test_foreign_or_missing_parent_cv(self):
        self.assertEqual(404, self.call("GET", self.url("does-not-exist"))["statusCode"])
        self.assertEqual(404, self.create_sp("does-not-exist")["statusCode"])

    def test_wrong_parent_id_on_item_access(self):
        cv_a = self.cv()
        cv_b = self.cv()
        sp_id = self.body_of(self.create_sp(cv_a))["searchProfileId"]
        self.assertEqual(404, self.call("GET", self.url(cv_b, sp_id))["statusCode"])

    def test_no_agent_or_model_call(self):
        cv_id = self.cv()
        self.create_sp(cv_id)
        self.assertEqual([], self.enqueued)


# --------------------------------------------------------------------------- #
# Capacity, idempotency, versions, delete guard
# --------------------------------------------------------------------------- #

class TestCapacityAndVersions(CvSpHarness):
    def test_max_two_per_cv(self):
        cv_id = self.cv()
        self.assertEqual(201, self.create_sp(cv_id, name="A")["statusCode"])
        self.assertEqual(201, self.create_sp(cv_id, name="B")["statusCode"])
        self.assertEqual(409, self.create_sp(cv_id, name="C")["statusCode"])

    def test_concurrent_creates_last_slot(self):
        cv_id = self.cv()
        self.repo.create(_sp(cv_id, sp_id="sp-existing"), **IDENTITY)
        results = []
        lock = threading.Lock()

        def create_one(i):
            try:
                self.repo.create(_sp(cv_id, sp_id=f"sp-race-{i}", name=f"r{i}"),
                                 **IDENTITY)
                with lock:
                    results.append(201)
            except PartnerProfileConflictError:
                with lock:
                    results.append(409)

        threads = [threading.Thread(target=create_one, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(1, results.count(201))
        self.assertEqual(1, results.count(409))
        counter = self.dynamo.resources[f"capacity#CVSP#{cv_id}"]
        self.assertEqual(2, counter["count"])

    def test_idempotent_retry(self):
        cv_id = self.cv()
        body = {"name": "Idem", "description": "d", "searchConfig": SEARCH_CONFIG}
        r1 = self.call("POST", self.url(cv_id), body=body,
                       extra_headers={"Idempotency-Key": "sp-key"})
        r2 = self.call("POST", self.url(cv_id), body=body,
                       extra_headers={"Idempotency-Key": "sp-key"})
        self.assertEqual(201, r1["statusCode"])
        self.assertEqual(201, r2["statusCode"])
        self.assertEqual(self.body_of(r1)["searchProfileId"],
                         self.body_of(r2)["searchProfileId"])
        self.assertEqual(1, len(self.body_of(self.call("GET", self.url(cv_id)))["items"]))
        self.assertEqual(1, self.dynamo.resources[f"capacity#CVSP#{cv_id}"]["count"])

    def test_idempotency_key_different_payload_conflict(self):
        cv_id = self.cv()
        r1 = self.call("POST", self.url(cv_id),
                       body={"name": "A", "searchConfig": SEARCH_CONFIG},
                       extra_headers={"Idempotency-Key": "sp-key-2"})
        self.assertEqual(201, r1["statusCode"])
        r2 = self.call("POST", self.url(cv_id),
                       body={"name": "B", "searchConfig": SEARCH_CONFIG},
                       extra_headers={"Idempotency-Key": "sp-key-2"})
        self.assertEqual(409, r2["statusCode"])

    def test_stale_update_409(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        resp = self.call("PUT", self.url(cv_id, sp_id), body={
            "name": "X", "version": 99})
        self.assertEqual(409, resp["statusCode"])

    def test_stale_delete_409(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        resp = self.call("DELETE", self.url(cv_id, sp_id), query={"version": "99"})
        self.assertEqual(409, resp["statusCode"])

    def test_delete_with_ats_child_409(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        # Simulate an existing ATS child via its capacity counter.
        self.dynamo.resources[f"capacity#ATS#{sp_id}"] = {
            "resourceId": f"capacity#ATS#{sp_id}",
            "resourceType": "CapacityCounter", "count": 1,
            "userId": USER, "tenantId": TENANT, "parentId": sp_id,
            "createdAt": "x", "updatedAt": "x",
        }
        resp = self.call("DELETE", self.url(cv_id, sp_id))
        self.assertEqual(409, resp["statusCode"])
        self.assertEqual(200, self.call("GET", self.url(cv_id, sp_id))["statusCode"])

    def test_parent_cv_deleting_refuses_create(self):
        cv_id = self.cv()
        reservation = self.repo.reserve_parent_delete(
            cv_id, **IDENTITY, child_type="CVSearchProfile")
        resp = self.create_sp(cv_id)
        self.assertEqual(409, resp["statusCode"])
        self.repo.release_parent_delete(reservation, **IDENTITY)

    def test_delete_vs_ats_create_no_orphan(self):
        cv_id = self.cv()
        sp_id = self.body_of(self.create_sp(cv_id))["searchProfileId"]
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def child():
            barrier.wait()
            try:
                self.repo.create(_ats(sp_id, cv_id), **IDENTITY)
                results.append("child")
            except Exception:
                errors.append("child")

        def delete():
            barrier.wait()
            try:
                self.repo.delete(sp_id, **IDENTITY, child_type="ATSSearchProfile")
                results.append("delete")
            except PartnerProfileConflictError:
                errors.append("delete")

        t1 = threading.Thread(target=child)
        t2 = threading.Thread(target=delete)
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(1, len(results))
        parent = self.repo.get(sp_id, USER, TENANT, PARTNER_APP, ISSUER)
        children, _ = self.repo.list_by_parent(
            sp_id, USER, TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER)
        if parent is None:
            self.assertEqual([], children)


# --------------------------------------------------------------------------- #
# Legacy protection
# --------------------------------------------------------------------------- #

class TestLegacy(CvSpHarness):
    def test_legacy_record_reads_and_update_preserves_incomplete(self):
        cv_id = self.cv()
        legacy = {
            "resourceId": "sp-legacy", "resourceType": "CVSearchProfile",
            "schemaVersion": "v1", "userId": USER, "tenantId": TENANT,
            "partnerApplicationId": PARTNER_APP, "issuer": ISSUER,
            "parentId": cv_id, "version": 1,
            "createdAt": "2026-10-31T12:00:00+00:00",
            "updatedAt": "2026-10-31T12:00:00+00:00",
            "payload": {
                "resourceType": "CVSearchProfile", "schemaVersion": "v1",
                "searchProfileId": "sp-legacy", "cvId": cv_id,
                "userId": USER, "tenantId": TENANT, "name": "Legacy",
                "profile": {"skills": "AWS", "targetRoles": ["Dev"]},
                "searchConfiguration": {"targetRoles": ["Dev"],
                                        "query": "python"},
            },
        }
        self.dynamo.resources["sp-legacy"] = legacy
        resp = self.call("GET", self.url(cv_id, "sp-legacy"))
        self.assertEqual(200, resp["statusCode"])
        b = self.body_of(resp)
        self.assertEqual(1, b["schemaVersion"])
        self.assertEqual("cv", b["origin"])
        self.assertEqual(["Dev"], b["searchConfig"]["targetRoles"])
        put = self.call("PUT", self.url(cv_id, "sp-legacy"),
                        body={"name": "Renamed", "version": 1})
        self.assertEqual(200, put["statusCode"])
        stored = self.dynamo.resources["sp-legacy"]["payload"]
        self.assertTrue(stored["metadata"].get("legacyIncomplete"))
        self.assertEqual("python",
                         stored["metadata"]["legacy"]["searchConfiguration"]["query"])


if __name__ == "__main__":
    unittest.main()
