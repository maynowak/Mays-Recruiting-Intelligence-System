"""R05-A tests: parent integrity, delete-vs-create races, create idempotency.

Real handler -> real R02 repository -> in-memory DynamoDB fake. The fake
serialises transactions with a lock, so this proves the transaction LOGIC,
not real DynamoDB concurrency. A real DynamoDB integration check is reserved
for R07.
"""

import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

from tests.test_partner_cv_document_api import CvHarness, BUCKET  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    Harness, USER, TENANT, ISSUER, PARTNER_APP,
)
from jobsearch.partner_profile_contract import (  # noqa: E402
    CVDocument, CVSearchProfile, MatchingPreferences, ManualSearchProfile,
    ProfileContractError,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileConflictError, PartnerProfileNotFoundError,
)

CVS = "/v1/partner/me/cvs"
MANUAL = "/v1/partner/me/manual-search-profiles"

IDENTITY = {
    "user_id": USER,
    "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP,
    "issuer": ISSUER,
}


def _sp(cv_id, sp_id="sp-1", user_id=USER, tenant_id=TENANT):
    return CVSearchProfile(
        search_profile_id=sp_id, cv_id=cv_id, user_id=user_id,
        tenant_id=tenant_id, name="sp")


def _cv(cv_id, name="f.pdf", size=10, user_id=USER, tenant_id=TENANT):
    return CVDocument(cv_id=cv_id, user_id=user_id, tenant_id=tenant_id,
                      name=name, size=size)


def _manual(mp_id, name="m", user_id=USER, tenant_id=TENANT):
    return ManualSearchProfile(
        manual_profile_id=mp_id, user_id=user_id, tenant_id=tenant_id,
        name=name, matching_preferences=MatchingPreferences())


def _action_key(action):
    for kind in ("ConditionCheck", "Put", "Update", "Delete"):
        if kind in action:
            body = action[kind]
            key = body.get("Key", {}).get("resourceId", {}).get("S")
            if key is None and kind == "Put":
                key = body.get("Item", {}).get("resourceId", {}).get("S")
            return key
    return None


# --------------------------------------------------------------------------- #
# P1-5: parent integrity
# --------------------------------------------------------------------------- #

class TestParentDeleteIntegrity(CvHarness):
    def test_cv_without_children_can_be_deleted(self):
        cv_id = self.body(self.create_cv())["cvId"]
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(200, resp["statusCode"])
        self.assertEqual(404, self.call("GET", f"{CVS}/{cv_id}")["statusCode"])

    def test_cv_with_search_profile_delete_409(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.repo.create(_sp(cv_id), **IDENTITY)
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(409, resp["statusCode"])
        self.assertEqual(200, self.call("GET", f"{CVS}/{cv_id}")["statusCode"])
        children, _ = self.repo.list_by_parent(
            cv_id, USER, TENANT, "CVSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER)
        self.assertEqual(1, len(children))

    def test_s3_untouched_when_children_refuse_delete(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        key = self.simulate_put(cv_id, doc_id)
        self.complete(cv_id)
        self.repo.create(_sp(cv_id), **IDENTITY)
        before_deleted = list(self.s3.deleted)
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(409, resp["statusCode"])
        self.assertIn((BUCKET, key), self.s3.objects)
        self.assertEqual(before_deleted, self.s3.deleted)
        self.assertEqual(200, self.call("GET", f"{CVS}/{cv_id}")["statusCode"])

    def test_cv_search_profile_with_ats_child_delete_409(self):
        cv_id = "cv-repo-1"
        self.repo.create(_cv(cv_id), **IDENTITY)
        self.repo.create(_sp(cv_id), **IDENTITY)
        # ATS child capacity counter > 0 (created through the child counter)
        self.dynamo.resources["capacity#ATS#sp-1"] = {
            "resourceId": "capacity#ATS#sp-1", "resourceType": "CapacityCounter",
            "count": 1, "userId": USER, "tenantId": TENANT,
            "parentId": "sp-1", "createdAt": "x", "updatedAt": "x",
        }
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.delete("sp-1", USER, TENANT, PARTNER_APP, ISSUER,
                             child_type="ATSSearchProfile")
        # parent still there, child counter unchanged
        self.assertIsNotNone(self.repo.get("sp-1", USER, TENANT,
                                           PARTNER_APP, ISSUER))

    def test_repeated_delete(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.assertEqual(200, self.call("DELETE", f"{CVS}/{cv_id}")["statusCode"])
        self.assertEqual(404, self.call("DELETE", f"{CVS}/{cv_id}")["statusCode"])

    def test_s3_failure_releases_guard_and_allows_retry(self):
        from unittest.mock import patch
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id)
        self.complete(cv_id)
        with patch("documents.delete_document_report",
                   side_effect=RuntimeError("s3 down")):
            resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(502, resp["statusCode"])
        self.assertTrue(self.body(resp)["metadataRetained"])
        guard = self.dynamo.resources.get(f"lifecycle#CVDocument#{cv_id}")
        self.assertIsNotNone(guard)
        self.assertEqual("active", guard["state"])
        # retry succeeds once S3 is reachable
        self.assertEqual(200, self.call("DELETE", f"{CVS}/{cv_id}")["statusCode"])

    def test_delete_reservation_and_finalize_are_atomic_per_item(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.call("DELETE", f"{CVS}/{cv_id}")
        for call in self.dynamo.calls if hasattr(self.dynamo, "calls") else []:
            keys = [_action_key(a) for a in call]
            self.assertEqual(len(keys), len(set(keys)))


class TestChildCreateVsParentDeleteRace(CvHarness):
    def _race(self, cv_id):
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def child():
            barrier.wait()
            try:
                self.repo.create(_sp(cv_id), **IDENTITY)
                results.append("child")
            except (PartnerProfileConflictError, ProfileContractError):
                errors.append("child")

        def delete():
            barrier.wait()
            try:
                reservation = self.repo.reserve_parent_delete(
                    cv_id, **IDENTITY, child_type="CVSearchProfile")
                self.repo.finalize_parent_delete(reservation, **IDENTITY)
                results.append("delete")
            except (PartnerProfileConflictError, PartnerProfileNotFoundError):
                errors.append("delete")

        t1 = threading.Thread(target=child)
        t2 = threading.Thread(target=delete)
        t1.start(); t2.start(); t1.join(); t2.join()
        return results, errors, cv_id

    def test_concurrent_child_create_and_cv_delete(self):
        for i in range(10):
            cv_id = f"cv-race-{i}"
            self.repo.create(_cv(cv_id), **IDENTITY)
            results, errors, _ = self._race(cv_id)
            self.assertEqual(1, len(results),
                             f"iteration {i}: exactly one must win, got {results}")
            self.assertEqual(1, len(errors))
            # invariant: no orphan child without a live parent
            parent = self.repo.get(cv_id, USER, TENANT, PARTNER_APP, ISSUER)
            children, _ = self.repo.list_by_parent(
                cv_id, USER, TENANT, "CVSearchProfile",
                partner_app_id=PARTNER_APP, issuer=ISSUER)
            if parent is None:
                self.assertEqual([], children)
            else:
                self.assertEqual(1, len(children))


# --------------------------------------------------------------------------- #
# P1-6: create idempotency
# --------------------------------------------------------------------------- #

class TestIdempotency(Harness):
    def test_identical_retry_returns_same_id(self):
        first = _manual("m-1", name="same")
        rid1 = self.repo.create(first, **IDENTITY, idempotency_key="key-1")
        second = _manual("m-2", name="same")
        rid2 = self.repo.create(second, **IDENTITY, idempotency_key="key-1")
        self.assertEqual(rid1, rid2)
        self.assertEqual("m-1", rid1)
        self.assertNotIn("m-2", self.dynamo.resources)

    def test_retry_after_simulated_timeout(self):
        # A timeout means the client retries without having seen the response;
        # the stored idempotency record returns the original identity.
        first = self.repo.create(_manual("m-1"), **IDENTITY,
                                 idempotency_key="timeout-key")
        retry = self.repo.create(_manual("m-2"), **IDENTITY,
                                 idempotency_key="timeout-key")
        self.assertEqual(first, retry)

    def test_same_key_different_payload_conflict(self):
        self.repo.create(_manual("m-1", name="same"), **IDENTITY,
                         idempotency_key="key-2")
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.create(_manual("m-2", name="different"), **IDENTITY,
                             idempotency_key="key-2")

    def test_no_double_capacity(self):
        self.repo.create(_cv("cv-idem-1"), **IDENTITY, idempotency_key="cv-key")
        self.repo.create(_cv("cv-idem-2"), **IDENTITY, idempotency_key="cv-key")
        counter = self.dynamo.resources.get(f"capacity#CV#{USER}")
        self.assertEqual(1, counter["count"])

    def test_same_key_other_user_is_isolated(self):
        rid_a = self.repo.create(_manual("m-a", user_id=USER),
                                 user_id=USER, tenant_id=TENANT,
                                 partner_app_id=PARTNER_APP, issuer=ISSUER,
                                 idempotency_key="shared")
        rid_b = self.repo.create(_manual("m-b", user_id="user-2"),
                                 user_id="user-2", tenant_id=TENANT,
                                 partner_app_id=PARTNER_APP, issuer=ISSUER,
                                 idempotency_key="shared")
        self.assertNotEqual(rid_a, rid_b)
        self.assertEqual("user-2", self.dynamo.resources[rid_b]["userId"])

    def test_expired_key_can_be_reused(self):
        rid1 = self.repo.create(_manual("m-1", name="first"), **IDENTITY,
                                idempotency_key="exp-key")
        # Force the idempotency record into the past.
        idem = [k for k in self.dynamo.resources if k.startswith("idem#")][0]
        self.dynamo.resources[idem]["expiresAt"] = 1
        rid2 = self.repo.create(_manual("m-2", name="second"), **IDENTITY,
                                idempotency_key="exp-key")
        self.assertNotEqual(rid1, rid2)
        self.assertIn("m-2", self.dynamo.resources)

    def test_handler_idempotency_header(self):
        payload = {"name": "H", "searchConfig": {
            "skills": "AWS", "targetRoles": ["Dev"], "city": "",
            "radiusKm": None, "workModes": ["remote"],
            "employmentTypes": ["full_time"]},
            "matchingPreferences": {"requiredSkills": ["AWS"]}}
        r1 = self.call("POST", MANUAL, body=payload,
                       extra_headers={"Idempotency-Key": "hdr-1"})
        r2 = self.call("POST", MANUAL, body=payload,
                       extra_headers={"Idempotency-Key": "hdr-1"})
        self.assertEqual(201, r1["statusCode"])
        self.assertEqual(201, r2["statusCode"])
        self.assertEqual(self.body(r1)["manualSearchProfileId"],
                         self.body(r2)["manualSearchProfileId"])
        self.assertEqual(1, len(self.body(self.call("GET", MANUAL))["items"]))
        r3 = self.call("POST", MANUAL, body={"name": "different", "searchConfig": {
            "skills": "Go", "targetRoles": ["Dev"], "city": "",
            "radiusKm": None, "workModes": ["remote"],
            "employmentTypes": ["full_time"]}},
            extra_headers={"Idempotency-Key": "hdr-1"})
        self.assertEqual(409, r3["statusCode"])


# --------------------------------------------------------------------------- #
# Legacy completeness
# --------------------------------------------------------------------------- #

class TestLegacyCompleteness(Harness):
    def test_legacy_incomplete_preserved_on_write(self):
        legacy = {
            "resourceId": "legacy-a", "resourceType": "ManualSearchProfile",
            "schemaVersion": "v1", "userId": USER, "tenantId": TENANT,
            "partnerApplicationId": PARTNER_APP, "issuer": ISSUER,
            "parentId": USER, "version": 1,
            "createdAt": "2026-10-31T12:00:00+00:00",
            "updatedAt": "2026-10-31T12:00:00+00:00",
            "payload": {
                "resourceType": "ManualSearchProfile", "schemaVersion": "v1",
                "manualProfileId": "legacy-a", "userId": USER,
                "tenantId": TENANT, "name": "Legacy", "origin": "manual",
                "matchingPreferences": {"requiredSkills": ["AWS"],
                                        "query": "python",
                                        "roles": ["Dev"]},
            },
        }
        self.dynamo.resources["legacy-a"] = legacy
        resp = self.call("PUT", f"{MANUAL}/legacy-a",
                         body={"name": "Renamed", "version": 1})
        self.assertEqual(200, resp["statusCode"])
        stored = self.dynamo.resources["legacy-a"]["payload"]
        self.assertTrue(stored["metadata"].get("legacyIncomplete"))
        self.assertEqual("python",
                         stored["metadata"]["legacy"]["matchingPreferences"]["query"])
        self.assertEqual(["Dev"], stored["searchConfig"]["targetRoles"])


if __name__ == "__main__":
    unittest.main()
