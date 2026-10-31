"""Tests for the partner profile DynamoDB repository (R02)."""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from jobsearch.partner_profile_contract import (
    SCHEMA_VERSION,
    ProfileContractError,
    CVDocument,
    CVSearchProfile,
    ATSSearchProfile,
    ManualSearchProfile,
    MatchingPreferences,
)
from jobsearch.partner_profile_repository import (
    PartnerProfileRepository,
    PartnerProfileConflictError,
)


def _repo(table=None):
    r = PartnerProfileRepository(table_name="test-table")
    r._table = table if table is not None else MagicMock()
    return r


class TestCreateGetListUpdateDelete(unittest.TestCase):
    def test_create_returns_id_and_calls_put(self):
        table = MagicMock()
        table.put_item.return_value = {}
        repo = _repo(table)
        cv = CVDocument(cv_id="cv1", user_id="u1", tenant_id="t1", name="r.pdf", size=10)
        rid = repo.create(cv, user_id="u1", tenant_id="t1")
        assert rid == "cv1"
        table.put_item.assert_called_once()
        item = table.put_item.call_args.kwargs["Item"]
        assert item["resourceType"] == "CVDocument"
        assert item["version"] == 1
        assert item["schemaVersion"] == SCHEMA_VERSION

    def test_create_duplicate_raises_conflict(self):
        table = MagicMock()
        err = Exception("ConditionalCheckFailedException")
        table.put_item.side_effect = err
        repo = _repo(table)
        cv = CVDocument(cv_id="cv1", user_id="u1", tenant_id="t1", name="r.pdf", size=10)
        with self.assertRaises(PartnerProfileConflictError):
            repo.create(cv, user_id="u1", tenant_id="t1")

    def test_get_returns_typed_object(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": "p1", "issuer": "iss",
            "parentId": "u1", "version": 1, "createdAt": "2026-01-01T00:00:00+00:00",
            "updatedAt": "2026-01-01T00:00:00+00:00",
            "payload": {
                "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "r.pdf", "size": 10,
            },
        }}
        repo = _repo(table)
        obj = repo.get("cv1", "u1", "t1", "p1", "iss")
        assert isinstance(obj, CVDocument)
        assert obj.cv_id == "cv1"

    def test_get_wrong_user_returns_none(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u2", "tenantId": "t1", "partnerApplicationId": "p1", "issuer": "iss",
            "parentId": "u2", "version": 1, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                        "cvId": "cv1", "userId": "u2", "tenantId": "t1", "name": "r.pdf", "size": 10},
        }}
        repo = _repo(table)
        assert repo.get("cv1", "u1", "t1", "p1", "iss") is None

    def test_get_wrong_tenant_returns_none(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t2", "partnerApplicationId": "p1", "issuer": "iss",
            "parentId": "u1", "version": 1, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                        "cvId": "cv1", "userId": "u1", "tenantId": "t2", "name": "r.pdf", "size": 10},
        }}
        repo = _repo(table)
        assert repo.get("cv1", "u1", "t1", "p1", "iss") is None

    def test_list_by_user_filters(self):
        table = MagicMock()
        table.query.return_value = {"Items": [
            {"resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
             "userId": "u1", "tenantId": "t1", "partnerApplicationId": "p1", "issuer": "iss",
             "parentId": "u1", "version": 1, "createdAt": "x", "updatedAt": "x",
             "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                         "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "r.pdf", "size": 10}},
        ], "LastEvaluatedKey": None}
        repo = _repo(table)
        items, cursor = repo.list_by_user("u1", "t1", "CVDocument", partner_app_id="p1", issuer="iss")
        assert len(items) == 1
        assert isinstance(items[0], CVDocument)

    def test_delete_success(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": "p1", "issuer": "iss",
            "parentId": "u1", "version": 2, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                        "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "r.pdf", "size": 10},
        }}
        table.delete_item.return_value = {}
        repo = _repo(table)
        assert repo.delete("cv1", "u1", "t1", "p1", "iss") is True

    def test_delete_wrong_version_raises(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": "p1", "issuer": "iss",
            "parentId": "u1", "version": 2, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                        "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "r.pdf", "size": 10},
        }}
        repo = _repo(table)
        with self.assertRaises(PartnerProfileConflictError):
            repo.delete("cv1", "u1", "t1", "p1", "iss", expected_version=1)


class TestIsolation(unittest.TestCase):
    def test_partner_app_mismatch_returns_none(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": "p2", "issuer": "iss",
            "parentId": "u1", "version": 1, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                        "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "r.pdf", "size": 10},
        }}
        repo = _repo(table)
        assert repo.get("cv1", "u1", "t1", "p1", "iss") is None

    def test_issuer_mismatch_returns_none(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": "p1", "issuer": "iss2",
            "parentId": "u1", "version": 1, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                        "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "r.pdf", "size": 10},
        }}
        repo = _repo(table)
        assert repo.get("cv1", "u1", "t1", "p1", "iss") is None


class TestHierarchyAndCapacity(unittest.TestCase):
    def test_create_cv_search_profile_requires_parent_cv(self):
        table = MagicMock()
        # parent get returns None
        table.get_item.return_value = {}
        repo = _repo(table)
        sp = CVSearchProfile(search_profile_id="sp1", cv_id="cv1", user_id="u1", tenant_id="t1", name="sp")
        with self.assertRaises(ProfileContractError):
            repo.create(sp, user_id="u1", tenant_id="t1")

    def test_create_ats_requires_parent_search_profile(self):
        table = MagicMock()
        table.get_item.return_value = {}
        repo = _repo(table)
        ats = ATSSearchProfile(ats_profile_id="a1", search_profile_id="sp1", cv_id="cv1",
                               user_id="u1", tenant_id="t1", name="a")
        with self.assertRaises(ProfileContractError):
            repo.create(ats, user_id="u1", tenant_id="t1")

    def test_create_ats_validates_assignment(self):
        table = MagicMock()
        # parent search profile exists with matching identity
        table.get_item.return_value = {"Item": {
            "resourceId": "sp1", "resourceType": "CVSearchProfile", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": None, "issuer": None,
            "parentId": "cv1", "version": 1, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVSearchProfile", "schemaVersion": SCHEMA_VERSION,
                        "searchProfileId": "sp1", "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "sp"},
        }}
        table.put_item.return_value = {}
        repo = _repo(table)
        ats = ATSSearchProfile(ats_profile_id="a1", search_profile_id="sp1", cv_id="cv1",
                               user_id="u1", tenant_id="t1", name="a")
        rid = repo.create(ats, user_id="u1", tenant_id="t1")
        assert rid == "a1"

    def test_manual_profile_no_parent_required(self):
        table = MagicMock()
        table.put_item.return_value = {}
        repo = _repo(table)
        m = ManualSearchProfile(manual_profile_id="m1", user_id="u1", tenant_id="t1", name="m",
                                matching_preferences=MatchingPreferences(roles=["Dev"]))
        rid = repo.create(m, user_id="u1", tenant_id="t1")
        assert rid == "m1"

    def test_cv_capacity_enforced(self):
        table = MagicMock()
        # list returns MAX+1 existing
        many = []
        for i in range(11):
            many.append({"resourceId": f"cv{i}", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                         "userId": "u1", "tenantId": "t1", "partnerApplicationId": None, "issuer": None,
                         "parentId": "u1", "version": 1, "createdAt": "x", "updatedAt": "x",
                         "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                                     "cvId": f"cv{i}", "userId": "u1", "tenantId": "t1", "name": "r", "size": 1}})
        table.query.return_value = {"Items": many, "LastEvaluatedKey": None}
        table.put_item.return_value = {}
        repo = _repo(table)
        cv = CVDocument(cv_id="cv-new", user_id="u1", tenant_id="t1", name="r.pdf", size=10)
        with self.assertRaises(ProfileContractError):
            repo.create(cv, user_id="u1", tenant_id="t1")

    def test_update_version_conflict(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": None, "issuer": None,
            "parentId": "u1", "version": 3, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                        "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "r.pdf", "size": 10},
        }}
        repo = _repo(table)
        cv = CVDocument(cv_id="cv1", user_id="u1", tenant_id="t1", name="r.pdf", size=10)
        with self.assertRaises(PartnerProfileConflictError):
            repo.update(cv, user_id="u1", tenant_id="t1", expected_version=1)

    def test_update_identity_mutation_rejected(self):
        table = MagicMock()
        table.get_item.return_value = {"Item": {
            "resourceId": "cv1", "resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": None, "issuer": None,
            "parentId": "u1", "version": 1, "createdAt": "x", "updatedAt": "x",
            "payload": {"resourceType": "CVDocument", "schemaVersion": SCHEMA_VERSION,
                        "cvId": "cv1", "userId": "u1", "tenantId": "t1", "name": "r.pdf", "size": 10},
        }}
        repo = _repo(table)
        cv = CVDocument(cv_id="cv1", user_id="evil", tenant_id="t1", name="r.pdf", size=10)
        with self.assertRaises(ProfileContractError):
            repo.update(cv, user_id="u1", tenant_id="t1")

    def test_roundtrip_no_field_loss(self):
        table = MagicMock()
        table.put_item.return_value = {}
        table.get_item.return_value = {"Item": {
            "resourceId": "m1", "resourceType": "ManualSearchProfile", "schemaVersion": SCHEMA_VERSION,
            "userId": "u1", "tenantId": "t1", "partnerApplicationId": None, "issuer": None,
            "parentId": "u1", "version": 1, "createdAt": "x", "updatedAt": "x",
            "payload": {
                "resourceType": "ManualSearchProfile", "schemaVersion": SCHEMA_VERSION,
                "manualProfileId": "m1", "userId": "u1", "tenantId": "t1", "name": "m",
                "matchingPreferences": {
                    "resourceType": "MatchingPreferences", "schemaVersion": SCHEMA_VERSION,
                    "roles": ["Dev", "Lead"], "workModes": ["remote"], "employmentTypes": ["full_time"],
                    "locations": ["Berlin"], "remoteOnly": False,
                },
            },
        }}
        repo = _repo(table)
        m = ManualSearchProfile(manual_profile_id="m1", user_id="u1", tenant_id="t1", name="m",
                                matching_preferences=MatchingPreferences(roles=["Dev", "Lead"], work_modes=["remote"],
                                                                           employment_types=["full_time"], locations=["Berlin"]))
        repo.create(m, user_id="u1", tenant_id="t1")
        got = repo.get("m1", "u1", "t1")
        assert isinstance(got, ManualSearchProfile)
        assert got.matching_preferences.roles == ["Dev", "Lead"]
        assert got.matching_preferences.locations == ["Berlin"]

    def test_pagination_cursor_passthrough(self):
        table = MagicMock()
        table.query.return_value = {"Items": [], "LastEvaluatedKey": {"resourceId": "x"}}
        repo = _repo(table)
        items, cursor = repo.list_by_user("u1", "t1", limit=5)
        assert cursor == {"resourceId": "x"}


class TestConcurrency(unittest.TestCase):
    def test_concurrent_create_capacity_race_documented(self):
        # Repository relies on count+conditional put; concurrent over-limit
        # writes are mitigated by conditional put on resourceId only.
        # This test documents that capacity is checked before write.
        table = MagicMock()
        table.query.return_value = {"Items": [], "LastEvaluatedKey": None}
        table.put_item.return_value = {}
        repo = _repo(table)
        cv = CVDocument(cv_id="cv-race", user_id="u1", tenant_id="t1", name="r.pdf", size=1)
        rid = repo.create(cv, user_id="u1", tenant_id="t1")
        assert rid == "cv-race"
        table.put_item.assert_called()


if __name__ == "__main__":
    unittest.main()
