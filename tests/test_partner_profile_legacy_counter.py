"""R07-FIX-03: legacy capacity counter integrity and safe deletion.

Synthetic legacy resources are modelled by removing the counter items created
by the modern path. No counter is ever inferred as zero.
"""

import os
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

from tests.test_partner_cv_document_api import CVS, CvHarness  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    FakeDynamo, USER, TENANT, ISSUER, PARTNER_APP,
)
from jobsearch.partner_profile_contract import (  # noqa: E402
    ATSSearchProfile, CVDocument, CVSearchProfile,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    LEGACY_SCAN_MAX_PAGES, PartnerProfileConflictError,
    PartnerProfileIntegrityError, PartnerProfileNotFoundError,
    PartnerProfileReadError, PartnerProfileRepository,
)

IDENTITY = {
    "user_id": USER, "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP, "issuer": ISSUER,
}


def _cv(cv_id="cv-1"):
    return CVDocument(cv_id=cv_id, user_id=USER, tenant_id=TENANT,
                      name="cv.pdf", content_type="application/pdf")


def _sp(sp_id="sp-1", cv_id="cv-1"):
    return CVSearchProfile(search_profile_id=sp_id, cv_id=cv_id,
                           user_id=USER, tenant_id=TENANT, name="sp",
                           origin="cv")


def _ats(ats_id="ats-1", sp_id="sp-1", cv_id="cv-1"):
    return ATSSearchProfile(ats_profile_id=ats_id, search_profile_id=sp_id,
                            cv_id=cv_id, user_id=USER, tenant_id=TENANT,
                            name="ats", target_roles=["DevOps"],
                            skills=["Terraform"])


class LegacyHarness(unittest.TestCase):
    def setUp(self):
        self.dynamo = FakeDynamo()
        self.repo = PartnerProfileRepository(table_name="ris-legacy")
        self.repo._table = self.dynamo
        self.repo._client = self.dynamo

    def make_cv(self, cv_id="cv-1"):
        self.repo.create(_cv(cv_id), **IDENTITY)
        return cv_id

    def make_sp(self, cv_id="cv-1", sp_id="sp-1"):
        self.repo.create(_sp(sp_id, cv_id), **IDENTITY)
        return sp_id

    def make_ats(self, sp_id="sp-1", cv_id="cv-1", ats_id="ats-1"):
        self.repo.create(_ats(ats_id, sp_id, cv_id), **IDENTITY)
        return ats_id

    def drop(self, *keys):
        for key in keys:
            self.dynamo.resources.pop(key, None)

    def counter(self, rt, parent):
        return self.dynamo.resources[f"capacity#{rt}#{parent}"]["count"]


class TestLegacyDelete(LegacyHarness):
    def test_cv_without_counters_and_without_children(self):
        cv_id = self.make_cv()
        self.drop("capacity#CV#user-1", "capacity#CVSP#cv-1")
        reservation = self.repo.reserve_parent_delete(
            cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertTrue(reservation["legacy_scan_verified"])
        self.assertTrue(reservation["own_counter_missing"])
        self.assertEqual("deleting", self.dynamo.resources[
            "lifecycle#CVDocument#cv-1"]["state"])
        self.assertTrue(self.repo.finalize_parent_delete(
            reservation, **IDENTITY))
        self.assertNotIn("cv-1", self.dynamo.resources)
        self.assertNotIn("lifecycle#CVDocument#cv-1", self.dynamo.resources)
        self.assertNotIn("capacity#CVSP#cv-1", self.dynamo.resources)

    def test_cv_without_counters_but_with_child_is_refused(self):
        cv_id = self.make_cv()
        self.make_sp()
        self.drop("capacity#CV#user-1", "capacity#CVSP#cv-1")
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.reserve_parent_delete(
                cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertIn("cv-1", self.dynamo.resources)
        self.assertIn("sp-1", self.dynamo.resources)
        self.assertEqual("active", self.dynamo.resources["lifecycle#CVDocument#cv-1"]["state"])

    def test_cvsp_without_counters_and_without_children(self):
        self.make_cv()
        self.make_sp()
        self.drop("capacity#CVSP#cv-1", "capacity#ATS#sp-1")
        self.assertTrue(self.repo.delete(
            "sp-1", **IDENTITY, child_type="ATSSearchProfile"))
        self.assertNotIn("sp-1", self.dynamo.resources)
        self.assertNotIn("capacity#ATS#sp-1", self.dynamo.resources)

    def test_cvsp_without_counter_but_with_ats_child_is_refused(self):
        self.make_cv()
        self.make_sp()
        self.make_ats()
        self.drop("capacity#CVSP#cv-1", "capacity#ATS#sp-1")
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.delete("sp-1", **IDENTITY,
                             child_type="ATSSearchProfile")
        self.assertIn("sp-1", self.dynamo.resources)
        self.assertIn("ats-1", self.dynamo.resources)
        self.assertEqual("active", self.dynamo.resources[
            "lifecycle#CVSearchProfile#sp-1"]["state"])

    def test_leaf_ats_without_counter_deletes_without_creating_one(self):
        self.make_cv()
        self.make_sp()
        self.make_ats()
        self.drop("capacity#ATS#sp-1")
        self.assertTrue(self.repo.delete("ats-1", **IDENTITY))
        self.assertNotIn("ats-1", self.dynamo.resources)
        self.assertNotIn("capacity#ATS#sp-1", self.dynamo.resources)

    def test_zero_counter_for_existing_resource_is_integrity_error(self):
        cv_id = self.make_cv()
        self.dynamo.resources["capacity#CV#user-1"]["count"] = 0
        with self.assertRaises(PartnerProfileIntegrityError):
            self.repo.reserve_parent_delete(
                cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertIn("cv-1", self.dynamo.resources)
        self.assertNotIn("lifecycle#CVDocument#cv-1", self.dynamo.resources)

    def test_non_numeric_counter_is_integrity_error(self):
        cv_id = self.make_cv()
        self.dynamo.resources["capacity#CV#user-1"]["count"] = "oops"
        with self.assertRaises(PartnerProfileIntegrityError):
            self.repo.reserve_parent_delete(
                cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertIn("cv-1", self.dynamo.resources)

    def test_non_numeric_child_counter_is_integrity_error(self):
        cv_id = self.make_cv()
        self.dynamo.resources["capacity#CVSP#cv-1"]["count"] = "oops"
        with self.assertRaises(PartnerProfileIntegrityError):
            self.repo.reserve_parent_delete(
                cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertIn("cv-1", self.dynamo.resources)

    def test_positive_child_counter_blocks_without_scan(self):
        cv_id = self.make_cv()
        self.make_sp()
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.reserve_parent_delete(
                cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertEqual(0, self.dynamo.scan_calls)

    def test_zero_child_counter_with_existing_child_legacy_is_detected(self):
        cv_id = self.make_cv()
        self.make_sp()
        # Legacy parent: own counter is missing; the child counter wrongly
        # says zero. The guarded scan must catch the contradiction.
        self.drop("capacity#CV#user-1")
        self.dynamo.resources["capacity#CVSP#cv-1"]["count"] = 0
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.reserve_parent_delete(
                cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertIn("sp-1", self.dynamo.resources)
        self.assertEqual("active", self.dynamo.resources["lifecycle#CVDocument#cv-1"]["state"])

    def test_scan_error_releases_guard_and_can_be_retried(self):
        cv_id = self.make_cv()
        self.drop("capacity#CV#user-1", "capacity#CVSP#cv-1")
        self.dynamo.scan_error = RuntimeError("scan unavailable")
        with self.assertRaises(PartnerProfileReadError):
            self.repo.reserve_parent_delete(
                cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertEqual("active", self.dynamo.resources["lifecycle#CVDocument#cv-1"]["state"])
        self.dynamo.scan_error = None
        reservation = self.repo.reserve_parent_delete(
            cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertTrue(self.repo.finalize_parent_delete(
            reservation, **IDENTITY))
        self.assertNotIn("cv-1", self.dynamo.resources)

    def test_scan_bound_fails_closed_and_releases_guard(self):
        cv_id = self.make_cv()
        self.drop("capacity#CV#user-1", "capacity#CVSP#cv-1")
        self.dynamo.scan_infinite = True
        with self.assertRaises(PartnerProfileIntegrityError):
            self.repo.reserve_parent_delete(
                cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertIn("cv-1", self.dynamo.resources)
        self.assertEqual("active", self.dynamo.resources["lifecycle#CVDocument#cv-1"]["state"])
        self.assertEqual(LEGACY_SCAN_MAX_PAGES, self.dynamo.scan_calls)

    def test_legacy_scan_walks_multiple_pages(self):
        cv_id = self.make_cv()
        # Unrelated items force several scan pages; the repository must follow
        # LastEvaluatedKey to completion.
        for i in range(4):
            self.dynamo.resources[f"unrelated-{i}"] = {
                "resourceId": f"unrelated-{i}", "resourceType": "X"}
        self.drop("capacity#CV#user-1", "capacity#CVSP#cv-1")
        self.dynamo.scan_page_size = 1
        reservation = self.repo.reserve_parent_delete(
            cv_id, **IDENTITY, child_type="CVSearchProfile")
        self.assertGreater(self.dynamo.scan_calls, 1)
        self.assertTrue(self.repo.finalize_parent_delete(
            reservation, **IDENTITY))

    def test_modern_delete_does_not_scan(self):
        cv_id = self.make_cv()
        self.assertTrue(self.repo.delete(cv_id, **IDENTITY))
        self.assertEqual(0, self.dynamo.scan_calls)

    def test_legacy_owner_isolation(self):
        cv_id = self.make_cv()
        self.drop("capacity#CV#user-1", "capacity#CVSP#cv-1")
        with self.assertRaises(PartnerProfileNotFoundError):
            self.repo.reserve_parent_delete(
                cv_id, user_id="other", tenant_id=TENANT,
                partner_app_id=PARTNER_APP, issuer=ISSUER,
                child_type="CVSearchProfile")

    def test_legacy_reserve_and_finalize_transactions_are_well_formed(self):
        cv_id = self.make_cv()
        self.drop("capacity#CV#user-1", "capacity#CVSP#cv-1")
        self.dynamo.calls.clear()
        reservation = self.repo.reserve_parent_delete(
            cv_id, **IDENTITY, child_type="CVSearchProfile")
        for call in self.dynamo.calls:
            keys = []
            for action in call:
                body = action.get("Put") or action.get("Update") or \
                    action.get("Delete") or action.get("ConditionCheck")
                keys.append(body["Key"]["resourceId"]["S"]
                            if "Key" in body else body["Item"]["resourceId"]["S"])
            self.assertEqual(len(keys), len(set(keys)), keys)
        self.assertTrue(self.repo.finalize_parent_delete(
            reservation, **IDENTITY))

    def test_concurrent_legacy_deletes_have_one_winner(self):
        cv_id = self.make_cv()
        self.drop("capacity#CV#user-1", "capacity#CVSP#cv-1")
        outcome = []
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait()
            try:
                reservation = self.repo.reserve_parent_delete(
                    cv_id, **IDENTITY, child_type="CVSearchProfile")
                outcome.append(self.repo.finalize_parent_delete(
                    reservation, **IDENTITY))
            except Exception:
                outcome.append(False)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(1, outcome.count(True), outcome)
        self.assertNotIn("cv-1", self.dynamo.resources)


# --------------------------------------------------------------------------- #
# CV / S3 handler path
# --------------------------------------------------------------------------- #

class TestLegacyCvS3(CvHarness):
    def _legacy_cv(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.dynamo.resources.pop(f"capacity#CV#user-1", None)
        self.dynamo.resources.pop(f"capacity#CVSP#{cv_id}", None)
        return cv_id

    def test_legacy_cv_without_children_deletes_without_s3_document(self):
        cv_id = self._legacy_cv()
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(200, resp["statusCode"])
        self.assertTrue(self.body(resp)["deleted"])
        self.assertNotIn(cv_id, self.dynamo.resources)
        self.assertEqual([], self.s3.deleted)

    def test_legacy_cv_with_child_does_not_touch_s3(self):
        cv_id = self._legacy_cv()
        self.call("POST", f"{CVS}/{cv_id}/search-profiles",
                  body={"name": "sp", "searchConfig": {
                      "skills": "AWS", "targetRoles": ["Dev"],
                      "city": "Berlin", "radiusKm": 25,
                      "workModes": ["remote"],
                      "employmentTypes": ["full_time"]}})
        self.dynamo.resources.pop(f"capacity#CVSP#{cv_id}", None)
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(409, resp["statusCode"])
        self.assertEqual([], self.s3.deleted)
        self.assertIn(cv_id, self.dynamo.resources)

    def test_scan_error_returns_5xx_and_does_not_touch_s3(self):
        cv_id = self._legacy_cv()
        self.dynamo.scan_error = RuntimeError("scan unavailable")
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertGreaterEqual(resp["statusCode"], 500)
        self.assertEqual([], self.s3.deleted)
        self.assertIn(cv_id, self.dynamo.resources)

    def test_s3_failure_keeps_metadata_and_allows_retry(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id)
        self.assertEqual(200, self.complete(cv_id)["statusCode"])
        # Simulate legacy counters after the document is READY.
        self.dynamo.resources.pop("capacity#CV#user-1", None)
        self.dynamo.resources.pop(f"capacity#CVSP#{cv_id}", None)
        with patch("documents.delete_document_report",
                   side_effect=RuntimeError("s3 down")):
            resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(502, resp["statusCode"])
        self.assertIn(cv_id, self.dynamo.resources)
        self.assertEqual("active", self.dynamo.resources[
            f"lifecycle#CVDocument#{cv_id}"]["state"])
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(200, resp["statusCode"])
        self.assertNotIn(cv_id, self.dynamo.resources)


if __name__ == "__main__":
    unittest.main()

