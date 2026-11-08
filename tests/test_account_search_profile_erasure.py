"""P3: account erasure must remove persisted partner search profiles.

Synthetic in-memory repository; no AWS, S3, Cognito or deployment mutation.
The adapter reuses the existing R08-C1A executor; these tests pin ordering,
identity scoping, pagination, partial-failure/resume, version conflicts and
the account-erasure integration.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

from agents.ecosystem.privacy_erasure import PrivacyErasure  # noqa: E402
from agents.ecosystem.privacy_profile_erasure import (  # noqa: E402
    AccountSearchProfileErasure,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileConflictError,
)


class Resource:
    def __init__(self, rid, resource_type, **extra):
        self.resource_id = rid
        self.resource_type = resource_type
        self.ats_profile_id = extra.get("ats_profile_id")
        self.search_profile_id = extra.get("search_profile_id")
        self.manual_profile_id = extra.get("manual_profile_id")
        self.cv_id = extra.get("cv_id")
        self.user_id = extra.get("user_id", "u1")
        self.tenant_id = extra.get("tenant_id", "t1")
        self.partner_application_id = extra.get("partner_application_id", "p1")
        self.issuer = extra.get("issuer", "issuer")
        self.version = extra.get("version", 1)


class Repo:
    table = object()

    def __init__(self, items, page_size=2, fail_on=None,
                 conflict_on=None, enabled=True):
        self.items = {item.resource_id: item for item in items}
        self.page_size = page_size
        self.fail_on = fail_on
        self.conflict_on = conflict_on
        self.enabled = enabled
        self.deleted = []

    def list_by_user(self, user_id, tenant_id, *, resource_type,
                     partner_app_id=None, issuer=None, limit=50, cursor=None):
        if not self.enabled:
            raise RuntimeError("storage unavailable")
        values = [
            item for item in self.items.values()
            if item.resource_type == resource_type
            and item.user_id == user_id and item.tenant_id == tenant_id
            and (partner_app_id is None
                 or item.partner_application_id == partner_app_id)
            and (issuer is None or item.issuer == issuer)
        ]
        values.sort(key=lambda item: item.resource_id)
        start = 0
        if cursor and cursor.get("after"):
            for index, item in enumerate(values):
                if item.resource_id == cursor["after"]:
                    start = index + 1
                    break
        page = values[start:start + min(limit, self.page_size)]
        next_cursor = ({"after": page[-1].resource_id}
                       if start + len(page) < len(values) else None)
        return page, next_cursor

    def delete(self, resource_id, user_id, tenant_id, partner_app_id=None,
               issuer=None, expected_version=None):
        item = self.items.get(resource_id)
        if item is None:
            return False
        if (item.user_id != user_id or item.tenant_id != tenant_id
                or item.partner_application_id != partner_app_id
                or item.issuer != issuer):
            return False
        if self.conflict_on == resource_id:
            raise PartnerProfileConflictError("Version conflict")
        if expected_version is not None and item.version != expected_version:
            raise PartnerProfileConflictError("Version conflict")
        if self.fail_on == resource_id:
            raise RuntimeError("synthetic delete failure")
        self.deleted.append(resource_id)
        self.items.pop(resource_id, None)
        return True


def profile(rid, rt, **extra):
    return Resource(rid, rt, **extra)


class AccountSearchProfileErasureTests(unittest.TestCase):
    def test_deletes_all_three_categories_in_child_first_order(self):
        repo = Repo([
            profile("manual1", "ManualSearchProfile", manual_profile_id="manual1"),
            profile("sp1", "CVSearchProfile", search_profile_id="sp1", cv_id="cv1"),
            profile("ats1", "ATSSearchProfile", ats_profile_id="ats1", search_profile_id="sp1"),
            profile("manual-other", "ManualSearchProfile", manual_profile_id="manual-other", user_id="u2"),
            profile("sp-other", "CVSearchProfile", search_profile_id="sp-other", cv_id="cv9", user_id="u2"),
        ], page_size=1)
        result = AccountSearchProfileErasure(repo, page_size=1).erase(
            user_id="u1", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(["ats1", "sp1", "manual1"], repo.deleted)
        self.assertEqual({"atsSearchProfiles": 1, "cvSearchProfiles": 1,
                          "manualSearchProfiles": 1}, result.counts)
        self.assertIn("manual-other", repo.items)
        self.assertIn("sp-other", repo.items)

    def test_identity_scope_is_enforced(self):
        repo = Repo([
            profile("sp1", "CVSearchProfile", search_profile_id="sp1", cv_id="cv1"),
            profile("sp-p2", "CVSearchProfile", search_profile_id="sp-p2", cv_id="cv2", partner_application_id="p2"),
            profile("sp-t2", "CVSearchProfile", search_profile_id="sp-t2", cv_id="cv3", tenant_id="t2"),
            profile("sp-i2", "CVSearchProfile", search_profile_id="sp-i2", cv_id="cv4", issuer="issuer2"),
        ])
        result = AccountSearchProfileErasure(repo).erase(
            user_id="u1", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertTrue(result.ok)
        self.assertEqual(["sp1"], repo.deleted)
        self.assertEqual({"sp-p2", "sp-t2", "sp-i2"}, set(repo.items))

    def test_multiple_cvs_and_parents_are_paginated(self):
        items = []
        for i in range(1, 4):
            sp = f"sp{i}"
            items.append(profile(sp, "CVSearchProfile", search_profile_id=sp, cv_id=f"cv{i}"))
            items.append(profile(f"ats{i}a", "ATSSearchProfile", ats_profile_id=f"ats{i}a", search_profile_id=sp))
            items.append(profile(f"ats{i}b", "ATSSearchProfile", ats_profile_id=f"ats{i}b", search_profile_id=sp))
        repo = Repo(items, page_size=1)
        result = AccountSearchProfileErasure(repo, page_size=1).erase(
            user_id="u1", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(9, result.deleted)
        self.assertEqual(9, len(repo.deleted))
        # Every ATS item precedes every CV search item.
        first_cv = next(i for i, rid in enumerate(repo.deleted) if rid.startswith("sp"))
        self.assertTrue(all(not rid.startswith("ats") for rid in repo.deleted[first_cv:]))

    def test_partial_failure_is_reported_and_retry_resumes(self):
        repo = Repo([
            profile("manual1", "ManualSearchProfile", manual_profile_id="manual1"),
            profile("sp1", "CVSearchProfile", search_profile_id="sp1", cv_id="cv1"),
            profile("ats1", "ATSSearchProfile", ats_profile_id="ats1", search_profile_id="sp1"),
        ], page_size=1, fail_on="sp1")
        first = AccountSearchProfileErasure(repo, page_size=1).erase(
            user_id="u1", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertFalse(first.ok)
        self.assertEqual("SEARCH_PROFILE_ERASURE_FAILED", first.error)
        self.assertIn("ats1", repo.deleted)
        self.assertIn("manual1", repo.items)
        self.assertIn("sp1", repo.items)
        repo.fail_on = None
        second = AccountSearchProfileErasure(repo, page_size=1).erase(
            user_id="u1", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertTrue(second.ok, second.error)
        self.assertEqual({}, repo.items)
        third = AccountSearchProfileErasure(repo, page_size=1).erase(
            user_id="u1", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertTrue(third.ok)
        self.assertEqual(0, third.deleted)

    def test_version_conflict_fails_closed(self):
        repo = Repo([
            profile("sp1", "CVSearchProfile", search_profile_id="sp1", cv_id="cv1"),
        ], conflict_on="sp1")
        result = AccountSearchProfileErasure(repo).erase(
            user_id="u1", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertFalse(result.ok)
        self.assertEqual("PROFILE_CONCURRENT_MUTATION", result.error)
        self.assertIn("sp1", repo.items)

    def test_missing_identity_or_storage_fails_closed(self):
        repo = Repo([])
        result = AccountSearchProfileErasure(repo).erase(
            user_id="", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertFalse(result.ok)
        self.assertEqual("SEARCH_PROFILE_IDENTITY_CONTEXT_REQUIRED", result.error)
        repo.table = None
        result = AccountSearchProfileErasure(repo).erase(
            user_id="u1", tenant_id="t1", partner_application_id="p1",
            issuer="issuer")
        self.assertFalse(result.ok)
        self.assertEqual("SEARCH_PROFILE_STORAGE_UNAVAILABLE", result.error)


class HandlerWiringTests(unittest.TestCase):
    def test_erasure_handler_constructs_and_passes_partner_profile_erasure(self):
        source = (ROOT / "lambda" / "handler.py").read_text(encoding="utf-8")
        body = source[source.index("def _handle_me_erasure"):
                      source.index("def _handle_me_erasure") + 9000]
        self.assertIn("AccountSearchProfileErasure", body)
        self.assertIn("partner_profile_erasure=partner_profile_erasure", body)
        self.assertIn("partner_application_id=partner_application_id", body)
        self.assertIn("issuer=issuer", body)
        self.assertIn("PARTNER_PROFILE_TABLE", body)


class DocumentPhaseTests(unittest.TestCase):
    def test_s3_list_failure_is_pending_not_success(self):
        import documents

        class S3:
            def list_objects_v2(self, **_kwargs):
                raise RuntimeError("S3 unavailable")

        deleted, pending = documents.delete_all_for_user_report(
            s3=S3(), user_id="u1")
        self.assertEqual(0, deleted)
        self.assertTrue(pending)

    def test_s3_delete_failure_is_pending(self):
        import documents

        class S3:
            def list_objects_v2(self, **_kwargs):
                return {"Contents": [{"Key": "tenant/t1/users/u1/documents/d1"}],
                        "IsTruncated": False}

            def delete_object(self, **_kwargs):
                raise RuntimeError("denied")

        deleted, pending = documents.delete_all_for_user_report(
            s3=S3(), user_id="u1")
        self.assertEqual(0, deleted)
        self.assertTrue(pending)


class PrivacyErasureIntegrationTests(unittest.TestCase):
    def test_search_profile_step_is_counted_and_complete(self):
        class Collaborator:
            def erase(self, **kwargs):
                from agents.ecosystem.privacy_profile_erasure import (
                    SearchProfileErasureResult)
                return SearchProfileErasureResult(True, 3, {
                    "atsSearchProfiles": 1, "cvSearchProfiles": 1,
                    "manualSearchProfiles": 1})
        result = PrivacyErasure(partner_profile_erasure=Collaborator()).erase(
            "u1", "t1", partner_application_id="p1", issuer="issuer")
        step = next(s for s in result.steps
                    if s.step == "erase-partner-search-profiles")
        self.assertTrue(step.ok)
        self.assertEqual(3, step.affected)
        self.assertEqual(3, result.search_profiles_deleted)
        self.assertTrue(result.complete)

    def test_search_profile_failure_keeps_run_incomplete(self):
        class Collaborator:
            def erase(self, **kwargs):
                from agents.ecosystem.privacy_profile_erasure import (
                    SearchProfileErasureResult)
                return SearchProfileErasureResult(False, 1, {}, "FAIL")
        result = PrivacyErasure(partner_profile_erasure=Collaborator()).erase(
            "u1", "t1", partner_application_id="p1", issuer="issuer")
        step = next(s for s in result.steps
                    if s.step == "erase-partner-search-profiles")
        self.assertFalse(step.ok)
        self.assertFalse(result.complete)

    def test_open_document_phase_is_not_success(self):
        result = PrivacyErasure(document_deleter=lambda _uid: (2, True)).erase(
            "u1", "t1")
        step = next(s for s in result.steps if s.step == "delete-documents")
        self.assertFalse(step.ok)
        self.assertFalse(result.complete)
        self.assertEqual(2, step.affected)

    def test_document_failure_is_not_success(self):
        def broken(_uid):
            raise RuntimeError("S3 unavailable")
        result = PrivacyErasure(document_deleter=broken).erase("u1", "t1")
        step = next(s for s in result.steps if s.step == "delete-documents")
        self.assertFalse(step.ok)
        self.assertFalse(result.complete)
        self.assertEqual("DOCUMENT_ERASURE_FAILED", step.error)


if __name__ == "__main__":
    unittest.main()
