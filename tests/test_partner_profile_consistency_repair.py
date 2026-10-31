"""R07-FIX-01: consistent reads and fail-closed GSI queries.

Covers F-1 (authoritative GetItem reads must be strongly consistent and read
failures must never become 404/409) and F-7 (a failed parent-GSI query must
not be replaced by a truncated user-level fallback).
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402
from tests.test_partner_ats_profiles_api import AtsHarness  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    FakeDynamo, USER, TENANT, ISSUER, PARTNER_APP,
)
from jobsearch.partner_profile_contract import (  # noqa: E402
    ATSSearchProfile, CVDocument, CVSearchProfile, ManualSearchProfile,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileConflictError, PartnerProfileReadError,
    PartnerProfileRepository,
)

IDENTITY = {
    "user_id": USER, "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP, "issuer": ISSUER,
}
MANUAL = "/v1/partner/me/manual-search-profiles"
CVS = "/v1/partner/me/cvs"


class RecordingDynamo(FakeDynamo):
    def __init__(self):
        super().__init__()
        self.get_calls = []
        self.query_calls = []

    def get_item(self, Key, ConsistentRead=False):
        self.get_calls.append((Key["resourceId"], ConsistentRead))
        return super().get_item(Key, ConsistentRead=ConsistentRead)

    def query(self, **kwargs):
        self.query_calls.append(dict(kwargs))
        return super().query(**kwargs)


class ReadFailingDynamo(FakeDynamo):
    def get_item(self, Key, ConsistentRead=False):
        raise RuntimeError("ddb read unavailable")


class ParentQueryFailingDynamo(FakeDynamo):
    def query(self, **kwargs):
        if kwargs.get("IndexName") == "gsi-parent":
            raise RuntimeError("gsi-parent unavailable")
        return super().query(**kwargs)


def _repo(dynamo):
    repo = PartnerProfileRepository(table_name="ris-r07fix-unittest")
    repo._table = dynamo
    repo._client = dynamo
    return repo


def _cv(cv_id="cv-1"):
    return CVDocument(cv_id=cv_id, user_id=USER, tenant_id=TENANT,
                      name="cv.pdf", content_type="application/pdf")


def _sp(cv_id="cv-1", sp_id="sp-1"):
    return CVSearchProfile(search_profile_id=sp_id, cv_id=cv_id,
                           user_id=USER, tenant_id=TENANT, name="sp",
                           origin="cv")


def _ats(sp_id="sp-1", ats_id="ats-1", cv_id="cv-1"):
    return ATSSearchProfile(ats_profile_id=ats_id, search_profile_id=sp_id,
                            cv_id=cv_id, user_id=USER, tenant_id=TENANT,
                            name="ats", target_roles=["DevOps"],
                            skills=["Terraform"])


# --------------------------------------------------------------------------- #
# F-1: consistent authoritative reads
# --------------------------------------------------------------------------- #

class TestConsistentReads(unittest.TestCase):
    def test_all_get_item_calls_are_consistent(self):
        dynamo = RecordingDynamo()
        repo = _repo(dynamo)
        repo.create(_cv(), **IDENTITY)
        repo.create(_sp(), **IDENTITY)
        repo.create(_ats(), **IDENTITY)
        repo.get("ats-1", **IDENTITY)
        repo._get_raw("ats-1")
        self.assertTrue(dynamo.get_calls)
        self.assertTrue(all(flag is True for _, flag in dynamo.get_calls),
                        dynamo.get_calls)

    def test_gsi_queries_are_not_forced_consistent(self):
        dynamo = RecordingDynamo()
        repo = _repo(dynamo)
        repo.create(_cv(), **IDENTITY)
        repo.create(_sp(), **IDENTITY)
        repo.create(_ats(), **IDENTITY)
        repo.list_by_parent("sp-1", USER, TENANT, "ATSSearchProfile",
                            partner_app_id=PARTNER_APP, issuer=ISSUER)
        repo.list_by_user(USER, TENANT, "CVDocument",
                          partner_app_id=PARTNER_APP, issuer=ISSUER)
        self.assertTrue(dynamo.query_calls)
        for call in dynamo.query_calls:
            self.assertNotIn("ConsistentRead", call)

    def test_get_returns_none_only_for_missing_item(self):
        repo = _repo(FakeDynamo())
        self.assertIsNone(repo.get("missing", **IDENTITY))

    def test_unparseable_item_raises_read_error(self):
        dynamo = FakeDynamo()
        dynamo.resources["cv-bad"] = {
            "resourceId": "cv-bad", "resourceType": "CVDocument",
            "userId": USER, "tenantId": TENANT,
            "partnerApplicationId": PARTNER_APP, "issuer": ISSUER,
            "version": 1,
            "payload": {"resourceType": "CVDocument", "schemaVersion": 1},
        }
        repo = _repo(dynamo)
        with self.assertRaises(PartnerProfileReadError):
            repo.get("cv-bad", **IDENTITY)

    def test_read_error_is_not_none(self):
        repo = _repo(ReadFailingDynamo())
        with self.assertRaises(PartnerProfileReadError):
            repo.get("cv-1", **IDENTITY)

    def test_read_error_is_not_delete_404(self):
        repo = _repo(ReadFailingDynamo())
        with self.assertRaises(PartnerProfileReadError):
            repo.delete("ats-1", **IDENTITY)

    def test_counter_read_error_is_not_capacity_conflict(self):
        repo = _repo(ReadFailingDynamo())
        with self.assertRaises(PartnerProfileReadError):
            repo.create(_cv(), **IDENTITY)

    def test_parent_read_error_is_not_contract_or_conflict(self):
        repo = _repo(ReadFailingDynamo())
        with self.assertRaises(PartnerProfileReadError):
            repo.create(_ats(), **IDENTITY)

    def test_stale_update_keeps_optimistic_locking(self):
        repo = _repo(FakeDynamo())
        repo.create(_cv(), **IDENTITY)
        with self.assertRaises(PartnerProfileConflictError):
            repo.update(_cv(), **IDENTITY, expected_version=99)

    def test_idempotency_replay_read_error_is_not_conflict(self):
        repo = _repo(FakeDynamo())
        repo.create(ManualSearchProfile(
            manual_profile_id="m-1", user_id=USER, tenant_id=TENANT,
            name="m"), **IDENTITY, idempotency_key="k-1")
        with patch.object(repo, "_get_raw",
                          side_effect=PartnerProfileReadError("read failed")):
            with self.assertRaises(PartnerProfileReadError):
                repo.create(ManualSearchProfile(
                    manual_profile_id="m-2", user_id=USER, tenant_id=TENANT,
                    name="m"), **IDENTITY, idempotency_key="k-1")


# --------------------------------------------------------------------------- #
# F-1: API responses must not be built from a stale/missing read
# --------------------------------------------------------------------------- #

class TestApiFailClosed(AtsHarness):
    def test_ats_get_read_error_is_500_not_404(self):
        cv_id, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        bad = ReadFailingDynamo()
        self.repo._table = bad
        self.repo._client = bad
        resp = self.call("GET", self.ats_url(sp_id, ats_id))
        self.assertEqual(500, resp["statusCode"])
        self.assertEqual("Internal error", self.body(resp)["error"])

    def test_manual_get_read_error_is_500_not_404(self):
        bad = ReadFailingDynamo()
        self.repo._table = bad
        self.repo._client = bad
        resp = self.call("GET", f"{MANUAL}/p-1")
        self.assertEqual(500, resp["statusCode"])
        self.assertNotEqual("Not found", self.body(resp)["error"])

    def test_cv_get_read_error_is_500_not_404(self):
        bad = ReadFailingDynamo()
        self.repo._table = bad
        self.repo._client = bad
        resp = self.call("GET", f"{CVS}/cv-1")
        self.assertEqual(500, resp["statusCode"])
        self.assertNotEqual("Not found", self.body(resp)["error"])

    def test_ats_list_gsi_error_is_500_not_empty_page(self):
        cv_id, sp_id = self.parent()
        self.create_ats(sp_id)
        bad = ParentQueryFailingDynamo()
        bad.resources = self.dynamo.resources
        self.repo._table = bad
        self.repo._client = bad
        resp = self.call("GET", self.ats_url(sp_id))
        self.assertEqual(500, resp["statusCode"])
        self.assertNotIn("items", self.body(resp))

    def test_create_without_post_write_read_is_500_not_null_version(self):
        _, sp_id = self.parent()
        real_get = self.repo.get

        def flaky(rid, *a, **kw):
            obj = real_get(rid, *a, **kw)
            return None if isinstance(obj, ATSSearchProfile) else obj

        with patch.object(self.repo, "get", side_effect=flaky):
            resp = self.create_ats(sp_id)
        self.assertEqual(500, resp["statusCode"])
        self.assertNotIn("version", self.body(resp))

    def test_all_post_write_responses_use_guarded_read(self):
        src = open(h.__file__, encoding="utf-8").read()
        self.assertNotIn("stored or", src)
        self.assertIn("_post_write_response", src)
        self.assertIn("_partner_storage_guard", src)

    def test_ats_create_response_version_is_integer(self):
        _, sp_id = self.parent()
        body = self.body(self.create_ats(sp_id))
        self.assertIsInstance(body["version"], int)
        self.assertGreaterEqual(body["version"], 1)


# --------------------------------------------------------------------------- #
# F-7: no fallback, fail closed
# --------------------------------------------------------------------------- #

class TestNoFallback(unittest.TestCase):
    def test_parent_query_error_raises_and_never_falls_back(self):
        dynamo = RecordingDynamo()
        repo = _repo(dynamo)
        repo.create(_cv(), **IDENTITY)
        repo.create(_sp(), **IDENTITY)
        repo.create(_ats(), **IDENTITY)
        dynamo.query = lambda **kw: (_ for _ in ()).throw(
            RuntimeError("gsi-parent down"))
        with patch.object(repo, "list_by_user") as fallback:
            with self.assertRaises(PartnerProfileReadError):
                repo.list_by_parent("sp-1", USER, TENANT, "ATSSearchProfile",
                                    partner_app_id=PARTNER_APP, issuer=ISSUER)
            fallback.assert_not_called()

    def test_user_query_error_is_not_an_empty_list(self):
        dynamo = RecordingDynamo()
        repo = _repo(dynamo)
        dynamo.query = lambda **kw: (_ for _ in ()).throw(
            RuntimeError("gsi-user down"))
        with self.assertRaises(PartnerProfileReadError):
            repo.list_by_user(USER, TENANT, "CVDocument",
                              partner_app_id=PARTNER_APP, issuer=ISSUER)

    def test_parent_query_still_pages_normally(self):
        repo = _repo(FakeDynamo())
        repo.create(_cv(), **IDENTITY)
        repo.create(_sp(), **IDENTITY)
        for i in range(3):
            repo.create(_ats(ats_id=f"ats-{i}"), **IDENTITY)
        first, cursor = repo.list_by_parent(
            "sp-1", USER, TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER, limit=1)
        self.assertEqual(1, len(first))
        self.assertIsNotNone(cursor)
        rest, _ = repo.list_by_parent(
            "sp-1", USER, TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER, limit=10,
            cursor=cursor)
        self.assertEqual(2, len(rest))


if __name__ == "__main__":
    unittest.main()
