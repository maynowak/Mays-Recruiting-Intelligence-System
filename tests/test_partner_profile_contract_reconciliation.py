"""R05-G0/R05-P0: Jobsearch v1 <-> RIS contract reconciliation.

After R05-P0 the two P0 blockers are repaired:

- canonical ``schemaVersion`` is the integer ``1`` (legacy ``"v1"`` is
  accepted on read and normalised to ``1``);
- ``searchConfig`` (six fields, phrase-preserving ``skills``, nullable
  ``radiusKm``) is a distinct object, separate from ``matchingPreferences``.

Remaining P1 gaps (CVDocument naming/status, CVSearchProfile shape, ATS
``criteria``) are still asserted here as explicit findings.

Synthetic fixtures are copied from ``mays-jobsearch`` ``origin/main@ad9b5ed``
``docs/contracts/fixtures/profile-v1/``. No real user or CV data is used.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobsearch.partner_profile_contract import (  # noqa: E402
    ATSSearchProfile,
    CV_ALLOWED_STATUSES,
    CVDocument,
    CVSearchProfile,
    MAX_ATS_PROFILES_PER_SEARCH_PROFILE,
    MAX_CVS_PER_USER,
    MAX_SEARCH_PROFILES_PER_CV,
    MatchingPreferences,
    ManualSearchProfile,
    SCHEMA_VERSION,
    SearchConfiguration,
)
from jobsearch.partner_profile_repository import CAPACITY_RULES  # noqa: E402

# --------------------------------------------------------------------------- #
# Synthetic Jobsearch v1 fixtures (source commit ad9b5ed)
# --------------------------------------------------------------------------- #

V1_CV_SEARCH_PROFILE = {
    "schemaVersion": 1,
    "searchProfileId": "sp_01EXAMPLE",
    "cvId": "cv_01EXAMPLE",
    "name": "Cloud Engineering",
    "description": "Search profile derived from the selected CV",
    "origin": "cv",
    "searchConfig": {
        "skills": 'AWS, Terraform, "Cloud Architecture"',
        "targetRoles": ["Cloud Engineer", "Solutions Architect"],
        "city": "Darmstadt",
        "radiusKm": 50,
        "workModes": ["remote", "hybrid"],
        "employmentTypes": ["full_time"],
    },
    "createdAt": "2026-10-31T12:00:00Z",
    "updatedAt": "2026-10-31T12:00:00Z",
    "version": 1,
}

V1_ROUNDTRIP = {
    "skills": 'AWS, Terraform, "Cloud Architecture", "Machine Learning"',
    "targetRoles": ["Cloud Engineer", "Solutions Architect"],
    "city": "",
    "radiusKm": None,
    "workModes": ["remote", "hybrid"],
    "employmentTypes": ["full_time", "part_time"],
}

V1_MANUAL_PROFILE = {
    "schemaVersion": 1,
    "manualSearchProfileId": "msp_01EXAMPLE",
    "name": "Independent Cloud Search",
    "description": "No CV required",
    "origin": "manual",
    "searchConfig": {
        "skills": 'AWS, Terraform, "Cloud Architecture"',
        "targetRoles": ["Cloud Engineer"],
        "city": "",
        "radiusKm": None,
        "workModes": ["remote", "hybrid"],
        "employmentTypes": ["full_time", "part_time"],
    },
    "matchingPreferences": {
        "requiredSkills": ["AWS"],
        "preferredSkills": ["Cloud Architecture"],
        "excludedTerms": ["Schichtarbeit"],
    },
    "createdAt": "2026-10-31T12:00:00Z",
    "updatedAt": "2026-10-31T12:00:00Z",
    "version": 1,
}


def _manual():
    return ManualSearchProfile(
        manual_profile_id="m1", user_id="u1", tenant_id="t1", name="n")


def _cv():
    return CVDocument(cv_id="c1", user_id="u1", tenant_id="t1", name="f.pdf")


def _sp():
    return CVSearchProfile(
        search_profile_id="sp1", cv_id="c1", user_id="u1", tenant_id="t1",
        name="sp")


def _ats():
    return ATSSearchProfile(
        ats_profile_id="a1", search_profile_id="sp1", cv_id="c1",
        user_id="u1", tenant_id="t1", name="a")


# --------------------------------------------------------------------------- #
# P0-1 (repaired): integer schemaVersion + legacy read
# --------------------------------------------------------------------------- #

class TestSchemaVersionRepair(unittest.TestCase):
    def test_ris_uses_integer_one(self):
        self.assertEqual(1, SCHEMA_VERSION)

    def test_contract_uses_integer_one(self):
        self.assertEqual(1, V1_CV_SEARCH_PROFILE["schemaVersion"])
        self.assertEqual(1, V1_MANUAL_PROFILE["schemaVersion"])

    def test_canonical_responses_emit_integer_one(self):
        for obj in (_cv(), _sp(), _ats(), _manual()):
            self.assertEqual(1, obj.to_dict()["schemaVersion"])
            self.assertIsInstance(obj.to_dict()["schemaVersion"], int)

    def test_legacy_string_is_accepted_and_normalised(self):
        legacy = ManualSearchProfile.from_dict({
            "resourceType": "ManualSearchProfile",
            "schemaVersion": "v1",
            "manualProfileId": "m1", "userId": "u1", "tenantId": "t1",
            "name": "legacy", "origin": "manual",
            "matchingPreferences": {"requiredSkills": ["AWS"]},
        })
        self.assertEqual(1, legacy.schema_version)
        self.assertEqual(1, legacy.to_dict()["schemaVersion"])

    def test_unknown_version_rejected(self):
        from jobsearch.partner_profile_contract import ProfileContractError
        with self.assertRaises(ProfileContractError):
            ManualSearchProfile.from_dict({
                "resourceType": "ManualSearchProfile", "schemaVersion": 2,
                "manualProfileId": "m1", "userId": "u1", "tenantId": "t1",
                "name": "x", "origin": "manual",
                "matchingPreferences": {},
            })

    def test_bool_is_not_an_integer_version(self):
        from jobsearch.partner_profile_contract import ProfileContractError
        with self.assertRaises(ProfileContractError):
            ManualSearchProfile.from_dict({
                "resourceType": "ManualSearchProfile", "schemaVersion": True,
                "manualProfileId": "m1", "userId": "u1", "tenantId": "t1",
                "name": "x", "origin": "manual",
                "matchingPreferences": {},
            })


# --------------------------------------------------------------------------- #
# P0-2 (repaired): searchConfig roundtrip
# --------------------------------------------------------------------------- #

class TestSearchConfigRepair(unittest.TestCase):
    def test_manual_profile_has_search_config(self):
        self.assertIn("searchConfig", _manual().to_dict())

    def test_all_six_fields_roundtrip(self):
        sc = SearchConfiguration.from_dict(V1_ROUNDTRIP)
        out = sc.to_dict()
        self.assertEqual(V1_ROUNDTRIP["skills"], out["skills"])
        self.assertEqual(V1_ROUNDTRIP["targetRoles"], out["targetRoles"])
        self.assertEqual(V1_ROUNDTRIP["city"], out["city"])
        self.assertIsNone(out["radiusKm"])
        self.assertEqual(V1_ROUNDTRIP["workModes"], out["workModes"])
        self.assertEqual(V1_ROUNDTRIP["employmentTypes"], out["employmentTypes"])

    def test_quoted_phrases_preserved(self):
        sc = SearchConfiguration.from_dict(V1_CV_SEARCH_PROFILE["searchConfig"])
        self.assertEqual('AWS, Terraform, "Cloud Architecture"', sc.skills)
        self.assertIn('"Cloud Architecture"', sc.to_dict()["skills"])

    def test_radius_null_stays_null(self):
        sc = SearchConfiguration.from_dict(V1_ROUNDTRIP)
        self.assertIsNone(sc.radius_km)
        self.assertIsNone(sc.to_dict()["radiusKm"])

    def test_radius_values_restricted(self):
        from jobsearch.partner_profile_contract import ProfileContractError
        for value in (10, 25, 50, 100):
            self.assertEqual(value, SearchConfiguration(radius_km=value).to_dict()["radiusKm"])
        with self.assertRaises(ProfileContractError):
            SearchConfiguration(radius_km=7).validate()

    def test_multiple_work_modes_and_employment_types(self):
        sc = SearchConfiguration.from_dict(V1_ROUNDTRIP)
        self.assertEqual(["remote", "hybrid"], sc.work_modes)
        self.assertEqual(["full_time", "part_time"], sc.employment_types)

    def test_matching_preferences_is_separate_and_lossless(self):
        mp = MatchingPreferences.from_dict(V1_MANUAL_PROFILE["matchingPreferences"])
        out = mp.to_dict()
        self.assertEqual(["AWS"], out["requiredSkills"])
        self.assertEqual(["Cloud Architecture"], out["preferredSkills"])
        self.assertEqual(["Schichtarbeit"], out["excludedTerms"])
        self.assertNotIn("roles", out)
        self.assertNotIn("workModes", out)

    def test_manual_profile_roundtrip_with_both_objects(self):
        sc = SearchConfiguration.from_dict(V1_MANUAL_PROFILE["searchConfig"])
        mp = MatchingPreferences.from_dict(V1_MANUAL_PROFILE["matchingPreferences"])
        man = ManualSearchProfile(
            manual_profile_id="m1", user_id="u1", tenant_id="t1",
            name="Independent", description="Ümlaut ✓",
            search_config=sc, matching_preferences=mp)
        back = ManualSearchProfile.from_dict(man.to_dict())
        self.assertEqual(1, back.to_dict()["schemaVersion"])
        self.assertEqual(sc.to_dict(), back.search_config.to_dict())
        self.assertEqual(mp.to_dict(), back.matching_preferences.to_dict())

    def test_legacy_matching_preferences_are_migrated_not_dropped(self):
        legacy = ManualSearchProfile.from_dict({
            "resourceType": "ManualSearchProfile", "schemaVersion": "v1",
            "manualProfileId": "m1", "userId": "u1", "tenantId": "t1",
            "name": "legacy", "origin": "manual",
            "matchingPreferences": {
                "requiredSkills": ["AWS"],
                "roles": ["Cloud Engineer"],
                "workModes": ["remote"],
                "employmentTypes": ["full_time"],
                "locations": ["Darmstadt"],
                "query": "python",
            },
        })
        self.assertEqual(["Cloud Engineer"], legacy.search_config.target_roles)
        self.assertEqual("Darmstadt", legacy.search_config.city)
        self.assertEqual(["remote"], legacy.search_config.work_modes)
        self.assertEqual(["full_time"], legacy.search_config.employment_types)
        self.assertEqual(["AWS"], legacy.matching_preferences.required_skills)
        # no silent loss: the query has no v1 slot and is preserved in metadata
        self.assertIn("legacy", legacy.metadata)
        self.assertEqual("python",
                         legacy.metadata["legacy"]["matchingPreferences"]["query"])
        self.assertTrue(legacy.metadata.get("legacyIncomplete"))


# --------------------------------------------------------------------------- #
# Remaining P1 gaps (documented, not repaired in R05-P0)
# --------------------------------------------------------------------------- #

class TestRemainingP1Gaps(unittest.TestCase):
    def test_cvdocument_naming_drift(self):
        d = _cv().to_dict()
        self.assertIn("name", d)
        self.assertNotIn("filename", d)
        self.assertIn("size", d)
        self.assertNotIn("sizeBytes", d)

    def test_cvdocument_status_set_drift(self):
        contract = {"pending", "ready", "failed", "deleted"}
        self.assertFalse(CV_ALLOWED_STATUSES <= contract)
        self.assertIn("upload_pending", CV_ALLOWED_STATUSES)

    def test_content_type_contract_is_pdf_only(self):
        cv = CVDocument(cv_id="c", user_id="u", tenant_id="t", name="n",
                        content_type="application/msword")
        cv.validate()
        self.assertEqual("application/msword", cv.to_dict()["contentType"])

    def test_cv_search_profile_shape_gap(self):
        d = _sp().to_dict()
        self.assertNotIn("description", d)
        self.assertNotIn("origin", d)
        self.assertNotIn("searchConfig", d)

    def test_ats_criteria_gap(self):
        self.assertNotIn("criteria", _ats().to_dict())


# --------------------------------------------------------------------------- #
# Capacity contract
# --------------------------------------------------------------------------- #

class TestCapacityContract(unittest.TestCase):
    def test_limits(self):
        self.assertEqual(10, MAX_CVS_PER_USER)
        self.assertEqual(2, MAX_SEARCH_PROFILES_PER_CV)
        self.assertEqual(5, MAX_ATS_PROFILES_PER_SEARCH_PROFILE)

    def test_capacity_rules_cover_children(self):
        self.assertEqual(10, CAPACITY_RULES["CVDocument"])
        self.assertEqual(2, CAPACITY_RULES["CVSearchProfile"])
        self.assertEqual(5, CAPACITY_RULES["ATSSearchProfile"])

    def test_no_manual_limit(self):
        self.assertNotIn("ManualSearchProfile", CAPACITY_RULES)


# --------------------------------------------------------------------------- #
# P1-5: delete integrity precondition (specified, not implemented)
# --------------------------------------------------------------------------- #

class TestDeleteIntegrityGap(unittest.TestCase):
    def test_repository_delete_has_no_child_guard_yet(self):
        import inspect
        from jobsearch.partner_profile_repository import PartnerProfileRepository
        src = inspect.getsource(PartnerProfileRepository.delete)
        self.assertNotIn("CVSearchProfile", src)
        self.assertNotIn("list_by_parent", src)

    def test_no_cascade_helper(self):
        import jobsearch.partner_profile_repository as repo
        self.assertFalse(hasattr(repo, "cascade_delete"))


# --------------------------------------------------------------------------- #
# No model / agent coupling
# --------------------------------------------------------------------------- #

class TestNoModelOrAgentCoupling(unittest.TestCase):
    def test_contract_module_has_no_agent_or_model_import(self):
        import jobsearch.partner_profile_contract as contract
        with open(contract.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for forbidden in ("import agents", "from agents", "openai",
                          "bedrock", "anthropic"):
            self.assertNotIn(forbidden, src)

    def test_repository_module_has_no_agent_or_model_import(self):
        import jobsearch.partner_profile_repository as repo
        with open(repo.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for forbidden in ("import agents", "from agents", "openai",
                          "bedrock", "anthropic"):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
