"""R06-G0/R06: ATS v1 contract and parent-semantics tests.

The former PLANNED (skipped) cases are now real contract tests because R06
implemented ATSCriteriaV1 and the v1 API shape. Repository/concurrency tests
remain transaction-logic only (real DynamoDB is R07).

Jobsearch reference: origin/main @ 0129559. ``excludedTerms`` IS present in
``contractTypes.ts`` at that commit (the earlier R06-G0 note was wrong).
"""

import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402
from tests.test_partner_cv_document_api import CvHarness  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    USER, TENANT, ISSUER, PARTNER_APP,
)
from jobsearch.partner_profile_contract import (  # noqa: E402
    ATSCriteria, ATSSearchProfile, CVSearchProfile, ProfileContractError,
    SearchConfiguration,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileConflictError,
)

IDENTITY = {
    "user_id": USER, "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP, "issuer": ISSUER,
}

ATS_FIXTURE = {
    "schemaVersion": 1,
    "atsSearchProfileId": "ats_01EXAMPLE",
    "searchProfileId": "sp_01EXAMPLE",
    "name": "DevOps ATS variant",
    "targetRoles": ["DevOps Engineer"],
    "skills": ["Terraform", "Kubernetes", "Cloud Architecture"],
    "criteria": {
        "schemaVersion": 1,
        "requiredSkills": ["Terraform"],
        "preferredSkills": ["Kubernetes"],
        "excludedTerms": ["night shift"],
    },
    "createdAt": "2026-10-31T12:00:00Z",
    "updatedAt": "2026-10-31T12:00:00Z",
    "version": 1,
}
ATS_INVALID_CRITERIA = {
    "name": "Invalid ATS criteria",
    "targetRoles": ["DevOps Engineer"],
    "skills": ["Terraform"],
    "criteria": {"schemaVersion": 1, "overallScore": 91,
                 "modelExplanation": "must never be persisted"},
}


def _sp(cv_id, sp_id="sp-1"):
    return CVSearchProfile(
        search_profile_id=sp_id, cv_id=cv_id, user_id=USER,
        tenant_id=TENANT, name="sp", origin="cv",
        search_config=SearchConfiguration(
            skills="AWS", target_roles=["Cloud Engineer"], city="Berlin",
            radius_km=25, work_modes=["remote"],
            employment_types=["full_time"]))


def _ats(cv_id="cv-1", sp_id="sp-1", ats_id="ats-1"):
    return ATSSearchProfile(
        ats_profile_id=ats_id, search_profile_id=sp_id, cv_id=cv_id,
        user_id=USER, tenant_id=TENANT, name="ats",
        target_roles=["DevOps Engineer"],
        skills=["Terraform", "Cloud Architecture"])


# --------------------------------------------------------------------------- #
# Canonical ATSSearchProfileV1 / ATSCriteriaV1
# --------------------------------------------------------------------------- #

class TestAtsV1Contract(unittest.TestCase):
    def test_schema_version_is_integer_one(self):
        self.assertEqual(1, _ats().to_dict()["schemaVersion"])

    def test_parent_id_is_required(self):
        ats = ATSSearchProfile(
            ats_profile_id="a", search_profile_id="", cv_id="c",
            user_id="u", tenant_id="t", name="n")
        with self.assertRaises(ProfileContractError):
            ats.validate()

    def test_unassigned_null_parent_rejected(self):
        with self.assertRaises(ProfileContractError):
            ATSSearchProfile(
                ats_profile_id="a", search_profile_id=None, cv_id="c",
                user_id="u", tenant_id="t", name="n").validate()

    def test_criteria_is_optional(self):
        self.assertNotIn("criteria", _ats().to_dict())

    def test_criteria_three_lists(self):
        criteria = ATSCriteria(required_skills=["A"], preferred_skills=["B"],
                               excluded_terms=["C"])
        ats = _ats()
        ats.criteria = criteria
        self.assertEqual(criteria.to_dict(), ats.to_dict()["criteria"])

    def test_criteria_empty_lists(self):
        criteria = ATSCriteria.from_dict({
            "schemaVersion": 1, "requiredSkills": [],
            "preferredSkills": [], "excludedTerms": []})
        self.assertEqual([], criteria.required_skills)
        self.assertEqual([], criteria.preferred_skills)
        self.assertEqual([], criteria.excluded_terms)

    def test_criteria_schema_version_required(self):
        with self.assertRaises(ProfileContractError):
            ATSCriteria.from_dict({"requiredSkills": ["A"]})

    def test_criteria_schema_version_must_be_integer_one(self):
        for sv in ("v1", 2, True):
            with self.assertRaises(ProfileContractError):
                ATSCriteria.from_dict({"schemaVersion": sv})

    def test_criteria_unknown_fields_rejected(self):
        with self.assertRaises(ProfileContractError):
            ATSCriteria.from_dict({"schemaVersion": 1, "foo": "bar"})

    def test_criteria_score_and_model_fields_rejected(self):
        with self.assertRaises(ProfileContractError):
            ATSCriteria.from_dict({
                "schemaVersion": 1, "overallScore": 91,
                "modelExplanation": "no"})

    def test_quoted_phrases_preserved(self):
        criteria = ATSCriteria(required_skills=['"Cloud Architecture"'])
        self.assertEqual(['"Cloud Architecture"'], criteria.to_dict()["requiredSkills"])

    def test_api_uses_ats_search_profile_id(self):
        out = h._serialize_ats_profile(_ats())
        self.assertIn("atsSearchProfileId", out)
        self.assertNotIn("atsProfileId", out)

    def test_api_omits_cv_id(self):
        out = h._serialize_ats_profile(_ats())
        self.assertNotIn("cvId", out)

    def test_api_omits_legacy_fields(self):
        out = h._serialize_ats_profile(_ats())
        for legacy in ("atsKeywords", "requirements", "preferredCriteria",
                       "exclusions", "location", "radius", "workMode"):
            self.assertNotIn(legacy, out)

    def test_v1_fixture_roundtrip(self):
        payload = dict(ATS_FIXTURE)
        payload.update({"userId": USER, "tenantId": TENANT,
                        "cvId": "cv-synthetic"})
        ats = ATSSearchProfile.from_dict(payload, strict=True)
        self.assertEqual("ats_01EXAMPLE", ats.ats_profile_id)
        self.assertEqual(1, ats.schema_version)
        self.assertEqual(["DevOps Engineer"], ats.target_roles)
        self.assertEqual(["Terraform", "Kubernetes", "Cloud Architecture"],
                         ats.skills)
        self.assertEqual(["Terraform"], ats.criteria.required_skills)
        self.assertEqual(["Kubernetes"], ats.criteria.preferred_skills)
        self.assertEqual(["night shift"], ats.criteria.excluded_terms)

    def test_invalid_criteria_fixture_rejected(self):
        payload = dict(ATS_INVALID_CRITERIA)
        payload.update({"atsSearchProfileId": "a", "searchProfileId": "sp",
                        "cvId": "cv", "userId": USER, "tenantId": TENANT,
                        "schemaVersion": 1})
        with self.assertRaises(ProfileContractError):
            ATSSearchProfile.from_dict(payload, strict=True)

    def test_legacy_criteria_lists_migrate(self):
        ats = ATSSearchProfile.from_dict({
            "resourceType": "ATSSearchProfile", "schemaVersion": "v1",
            "atsProfileId": "a", "searchProfileId": "sp", "cvId": "cv",
            "userId": USER, "tenantId": TENANT, "name": "legacy",
            "targetRoles": ["A"], "skills": ["B"],
            "requirements": ["R"], "preferredCriteria": ["P"],
            "exclusions": ["E"],
        }, strict=False)
        self.assertEqual(["R"], ats.criteria.required_skills)
        self.assertEqual(["P"], ats.criteria.preferred_skills)
        self.assertEqual(["E"], ats.criteria.excluded_terms)
        self.assertTrue(ats.metadata.get("legacyIncomplete"))


# --------------------------------------------------------------------------- #
# Existing repository mechanisms (R05-A) used by R06
# --------------------------------------------------------------------------- #

class AtsRepoHarness(CvHarness):
    def cv(self):
        return self.body(self.create_cv())["cvId"]

    def make_sp(self, cv_id, sp_id="sp-1"):
        return self.repo.create(_sp(cv_id, sp_id), **IDENTITY)

    def make_ats(self, cv_id, sp_id="sp-1", ats_id="ats-1"):
        return self.repo.create(_ats(cv_id, sp_id, ats_id), **IDENTITY)


class TestAtsParentMechanisms(AtsRepoHarness):
    def test_five_ats_capacity(self):
        cv_id = self.cv()
        self.make_sp(cv_id)
        for i in range(5):
            self.make_ats(cv_id, ats_id=f"ats-{i}")
        with self.assertRaises(PartnerProfileConflictError):
            self.make_ats(cv_id, ats_id="ats-6")

    def test_parent_must_exist(self):
        cv_id = self.cv()
        self.make_sp(cv_id)
        with self.assertRaises(ProfileContractError):
            self.repo.create(_ats(cv_id, sp_id="missing"), **IDENTITY)

    def test_parent_cv_chain_must_match(self):
        cv_id = self.cv()
        self.make_sp(cv_id)
        with self.assertRaises(ProfileContractError):
            self.repo.create(_ats("other-cv"), **IDENTITY)

    def test_parent_deleting_guard_blocks_create(self):
        cv_id = self.cv()
        self.make_sp(cv_id)
        reservation = self.repo.reserve_parent_delete(
            "sp-1", **IDENTITY, child_type="ATSSearchProfile")
        with self.assertRaises(PartnerProfileConflictError):
            self.make_ats(cv_id)
        self.repo.release_parent_delete(reservation, **IDENTITY)

    def test_search_profile_delete_with_ats_children_refused(self):
        cv_id = self.cv()
        self.make_sp(cv_id)
        self.make_ats(cv_id)
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.delete("sp-1", **IDENTITY,
                             child_type="ATSSearchProfile")

    def test_delete_vs_ats_create_no_orphan(self):
        cv_id = self.cv()
        self.make_sp(cv_id)
        results = []
        barrier = threading.Barrier(2)

        def child():
            barrier.wait()
            try:
                self.make_ats(cv_id)
                results.append("child")
            except Exception:
                pass

        def delete():
            barrier.wait()
            try:
                self.repo.delete("sp-1", **IDENTITY,
                                 child_type="ATSSearchProfile")
                results.append("delete")
            except PartnerProfileConflictError:
                pass

        t1 = threading.Thread(target=child)
        t2 = threading.Thread(target=delete)
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(1, len(results))
        parent = self.repo.get("sp-1", **IDENTITY)
        children, _ = self.repo.list_by_parent(
            "sp-1", USER, TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER)
        if parent is None:
            self.assertEqual([], children)


# --------------------------------------------------------------------------- #
# ATS override semantics (synthetic, mirrors Jobsearch cvSearchConfig.ts)
# --------------------------------------------------------------------------- #

def _effective_search_config(parent_sc, ats_skills, ats_target_roles):
    effective = parent_sc.to_dict()
    effective["skills"] = ", ".join(ats_skills)
    effective["targetRoles"] = list(ats_target_roles)
    return effective


class TestAtsOverrideSemantics(unittest.TestCase):
    def setUp(self):
        self.parent = SearchConfiguration(
            skills="AWS, Terraform", target_roles=["Cloud Engineer"],
            city="Darmstadt", radius_km=50, work_modes=["remote", "hybrid"],
            employment_types=["full_time"])

    def test_ats_skills_and_roles_override_parent(self):
        eff = _effective_search_config(
            self.parent, ["Kubernetes", "Terraform"], ["DevOps Engineer"])
        self.assertEqual("Kubernetes, Terraform", eff["skills"])
        self.assertEqual(["DevOps Engineer"], eff["targetRoles"])

    def test_parent_location_and_filters_survive(self):
        eff = _effective_search_config(
            self.parent, ["Kubernetes"], ["DevOps Engineer"])
        self.assertEqual("Darmstadt", eff["city"])
        self.assertEqual(50, eff["radiusKm"])
        self.assertEqual(["remote", "hybrid"], eff["workModes"])
        self.assertEqual(["full_time"], eff["employmentTypes"])

    def test_parent_object_is_not_mutated(self):
        before = self.parent.to_dict()
        _effective_search_config(self.parent, ["Kubernetes"], ["DevOps"])
        self.assertEqual(before, self.parent.to_dict())

    def test_multiple_target_roles_are_not_reduced(self):
        eff = _effective_search_config(
            self.parent, ["AWS"], ["DevOps", "SRE", "Platform"])
        self.assertEqual(["DevOps", "SRE", "Platform"], eff["targetRoles"])


if __name__ == "__main__":
    unittest.main()
