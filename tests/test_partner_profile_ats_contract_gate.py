"""R06-G0: ATS v1 contract / parent-semantics gate.

PASS tests document the CURRENT RIS model and the repository mechanisms that
already exist. PLANNED (skipped) tests describe the target ATSSearchProfileV1
contract that R06 CRUD must implement. No production code is changed here.

Jobsearch reference: origin/main @ 0129559 (ATS data shape unchanged since
c6137b3; only session-capacity documentation changed).
"""

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
    ATSSearchProfile, CVSearchProfile, ProfileContractError,
    SearchConfiguration,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileConflictError,
)

IDENTITY = {
    "user_id": USER, "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP, "issuer": ISSUER,
}

# Synthetic fixtures from mays-jobsearch docs/contracts/fixtures/profile-v1/
# (origin/main @ 0129559). No real data.
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
ATS_CREATE_FIXTURE = {
    "name": "Created ATS Variant",
    "targetRoles": ["Cloud Engineer"],
    "skills": ["AWS", "Cloud Architecture"],
    "criteria": {"schemaVersion": 1, "requiredSkills": ["AWS"],
                 "preferredSkills": [], "excludedTerms": []},
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


def _ats(cv_id, sp_id="sp-1", ats_id="ats-1"):
    return ATSSearchProfile(
        ats_profile_id=ats_id, search_profile_id=sp_id, cv_id=cv_id,
        user_id=USER, tenant_id=TENANT, name="ats",
        target_roles=["DevOps Engineer"],
        skills=["Terraform", "Cloud Architecture"])


# --------------------------------------------------------------------------- #
# Current RIS model (documented gaps, not v1 compliance)
# --------------------------------------------------------------------------- #

class TestCurrentAtsModel(unittest.TestCase):
    def test_schema_version_is_integer_one(self):
        self.assertEqual(1, _ats("cv-1").to_dict()["schemaVersion"])

    def test_parent_id_is_required(self):
        ats = ATSSearchProfile(
            ats_profile_id="a", search_profile_id="", cv_id="c",
            user_id="u", tenant_id="t", name="n")
        with self.assertRaises(ProfileContractError):
            ats.validate()

    def test_unassigned_null_parent_rejected(self):
        # Persistent v1 must never carry searchProfileId = null.
        with self.assertRaises(ProfileContractError):
            ATSSearchProfile(
                ats_profile_id="a", search_profile_id=None, cv_id="c",
                user_id="u", tenant_id="t", name="n").validate()

    def test_current_model_has_no_criteria(self):
        self.assertNotIn("criteria", _ats("cv-1").to_dict())

    def test_current_model_emits_legacy_cv_id(self):
        # v1 ATSSearchProfileV1 has no cvId; the current RIS model does.
        self.assertIn("cvId", _ats("cv-1").to_dict())

    def test_current_model_uses_ats_profile_id_name(self):
        d = _ats("cv-1").to_dict()
        self.assertIn("atsProfileId", d)
        self.assertNotIn("atsSearchProfileId", d)

    def test_strict_parser_rejects_v1_fixture(self):
        # The v1 fixture uses atsSearchProfileId + criteria; neither is in the
        # current strict field set. This is the P1-3 gap.
        with self.assertRaises(ProfileContractError):
            ATSSearchProfile.from_dict(ATS_FIXTURE, strict=True)

    def test_legacy_criteria_fields_are_separate(self):
        ats = ATSSearchProfile(
            ats_profile_id="a", search_profile_id="sp", cv_id="c",
            user_id="u", tenant_id="t", name="n",
            requirements=["r"], preferred_criteria=["p"], exclusions=["e"])
        d = ats.to_dict()
        self.assertEqual(["r"], d["requirements"])
        self.assertEqual(["p"], d["preferredCriteria"])
        self.assertEqual(["e"], d["exclusions"])
        self.assertNotIn("criteria", d)

    def test_skills_and_target_roles_are_lists(self):
        d = _ats("cv-1").to_dict()
        self.assertEqual(["DevOps Engineer"], d["targetRoles"])
        self.assertEqual(["Terraform", "Cloud Architecture"], d["skills"])


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
        self.assertIsNotNone(self.repo.get("sp-1", **IDENTITY))

    def test_delete_vs_ats_create_no_orphan(self):
        cv_id = self.cv()
        self.make_sp(cv_id)
        results = []
        errors = []
        barrier = threading.Barrier(2)

        def child():
            barrier.wait()
            try:
                self.make_ats(cv_id)
                results.append("child")
            except Exception:
                errors.append("child")

        def delete():
            barrier.wait()
            try:
                self.repo.delete("sp-1", **IDENTITY,
                                 child_type="ATSSearchProfile")
                results.append("delete")
            except PartnerProfileConflictError:
                errors.append("delete")

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

    def test_cross_user_get_is_empty(self):
        cv_id = self.cv()
        self.make_sp(cv_id)
        self.make_ats(cv_id)
        self.assertIsNone(self.repo.get(
            "ats-1", "user-2", TENANT, PARTNER_APP, ISSUER))


# --------------------------------------------------------------------------- #
# ATS override semantics (synthetic, mirrors Jobsearch cvSearchConfig.ts)
# --------------------------------------------------------------------------- #

def _effective_search_config(parent_sc, ats_skills, ats_target_roles):
    """Test-only mirror of buildCvSearchProfile (no production helper)."""
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


# --------------------------------------------------------------------------- #
# PLANNED: target v1 CRUD / criteria (R06)
# --------------------------------------------------------------------------- #

@unittest.skip("PLANNED R06-CRUD: ATSCriteriaV1 is not yet modelled in RIS")
class TestPlannedAtsV1(unittest.TestCase):
    def test_valid_v1_fixture_roundtrip(self):
        raise AssertionError("R06 must implement ATSSearchProfileV1")

    def test_criteria_absent_is_valid(self):
        raise AssertionError("R06 must allow criteria to be omitted")

    def test_criteria_v1_with_three_lists(self):
        raise AssertionError("R06 must model required/preferred/excluded")

    def test_empty_criteria_lists(self):
        raise AssertionError("R06 must allow empty criteria lists")

    def test_quoted_phrases_preserved(self):
        raise AssertionError("R06 must preserve phrase arrays")

    def test_invalid_criteria_fields_rejected(self):
        raise AssertionError("R06 must reject unknown criteria fields")

    def test_score_and_model_fields_rejected(self):
        raise AssertionError("R06 must reject scores/model output")

    def test_unknown_schema_version_rejected(self):
        raise AssertionError("R06 must reject non-1 schemaVersion")

    def test_v1_response_has_no_cv_id(self):
        raise AssertionError("R06 must derive cvId from the parent chain")


if __name__ == "__main__":
    unittest.main()
