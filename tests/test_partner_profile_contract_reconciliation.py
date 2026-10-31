"""R05-G0: Jobsearch v1 <-> RIS R01-R04 contract reconciliation tests.

These tests do NOT claim v1 compliance. They:

- prove the current gaps as P0/P1 findings (schemaVersion type, missing
  ``searchConfig``/``skills``/``radiusKm``, CVDocument naming/status drift,
  missing CVSearchProfile ``description``/``origin``/``searchConfig``,
  ATS ``criteria`` drift), and
- guard the existing R01-R04 roundtrips that are already lossless.

Synthetic fixtures are copied from
``mays-jobsearch`` ``origin/main@ad9b5ed``
``docs/contracts/fixtures/profile-v1/``. No real user or CV data is used.
"""

import json
import os
import sys
import unittest
from dataclasses import fields

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
# P0-1: schemaVersion type/value
# --------------------------------------------------------------------------- #

class TestSchemaVersionGap(unittest.TestCase):
    def test_ris_uses_string_v1(self):
        self.assertEqual("v1", SCHEMA_VERSION)

    def test_contract_uses_integer_one(self):
        self.assertEqual(1, V1_CV_SEARCH_PROFILE["schemaVersion"])
        self.assertEqual(1, V1_MANUAL_PROFILE["schemaVersion"])

    def test_gap_is_currently_incompatible(self):
        # A strict JSON-Schema consumer rejects "v1" against const 1.
        self.assertNotEqual(V1_CV_SEARCH_PROFILE["schemaVersion"], SCHEMA_VERSION)
        for obj in (_cv(), _sp(), _ats(), _manual()):
            self.assertEqual("v1", obj.to_dict()["schemaVersion"])


# --------------------------------------------------------------------------- #
# P0-2: searchConfig / skills / radiusKm
# --------------------------------------------------------------------------- #

class TestSearchConfigGap(unittest.TestCase):
    def test_manual_profile_has_no_search_config(self):
        self.assertNotIn("searchConfig", _manual().to_dict())

    def test_matching_preferences_has_no_skills_string(self):
        self.assertNotIn("skills", MatchingPreferences().to_dict())

    def test_matching_preferences_has_no_radius_km(self):
        self.assertNotIn("radiusKm", MatchingPreferences().to_dict())

    def test_partial_mapping_roles_locations_workmodes_employment(self):
        sc = V1_CV_SEARCH_PROFILE["searchConfig"]
        mp = MatchingPreferences(
            roles=list(sc["targetRoles"]),
            locations=[sc["city"]] if sc["city"] else [],
            work_modes=list(sc["workModes"]),
            employment_types=list(sc["employmentTypes"]),
        ).to_dict()
        self.assertEqual(sc["targetRoles"], mp["roles"])
        self.assertEqual(sc["workModes"], mp["workModes"])
        self.assertEqual(sc["employmentTypes"], mp["employmentTypes"])
        self.assertEqual([sc["city"]], mp["locations"])

    def test_skills_and_radius_are_lost(self):
        # There is no destination field: this is the P0 data-loss proof.
        d = MatchingPreferences().to_dict()
        self.assertNotIn(V1_CV_SEARCH_PROFILE["searchConfig"]["skills"], json.dumps(d))
        self.assertNotIn("radiusKm", d)
        self.assertNotIn("radius", d)

    def test_matching_preferences_survives_losslessly(self):
        mp = MatchingPreferences.from_dict({
            "requiredSkills": ["AWS"],
            "preferredSkills": ["Cloud Architecture"],
            "excludedTerms": ["Schichtarbeit"],
        })
        out = mp.to_dict()
        self.assertEqual(["AWS"], out["requiredSkills"])
        self.assertEqual(["Cloud Architecture"], out["preferredSkills"])
        self.assertEqual(["Schichtarbeit"], out["excludedTerms"])


# --------------------------------------------------------------------------- #
# P1-1: CVDocument naming / status drift
# --------------------------------------------------------------------------- #

class TestCvDocumentGap(unittest.TestCase):
    def test_filename_vs_name(self):
        d = _cv().to_dict()
        self.assertIn("name", d)
        self.assertNotIn("filename", d)

    def test_sizebytes_vs_size(self):
        d = _cv().to_dict()
        self.assertIn("size", d)
        self.assertNotIn("sizeBytes", d)

    def test_processing_status_value_set_drift(self):
        contract = {"pending", "ready", "failed", "deleted"}
        self.assertFalse(CV_ALLOWED_STATUSES <= contract)
        self.assertIn("upload_pending", CV_ALLOWED_STATUSES)
        self.assertNotIn("failed", CV_ALLOWED_STATUSES)

    def test_content_type_contract_is_pdf_only(self):
        cv = CVDocument(cv_id="c", user_id="u", tenant_id="t", name="n",
                        content_type="application/msword")
        # RIS accepts more than the contract's application/pdf const.
        cv.validate()
        self.assertEqual("application/msword", cv.to_dict()["contentType"])

    def test_document_id_is_distinct_from_cv_id(self):
        cv = CVDocument(cv_id="c1", user_id="u", tenant_id="t", name="n",
                        document_id="d1")
        d = cv.to_dict()
        self.assertEqual("c1", d["cvId"])
        self.assertEqual("d1", d["documentId"])
        self.assertNotEqual(d["cvId"], d["documentId"])


# --------------------------------------------------------------------------- #
# P1-2/P1-3: CVSearchProfile and ATS shape
# --------------------------------------------------------------------------- #

class TestCvSearchProfileGap(unittest.TestCase):
    def test_missing_description_origin_search_config(self):
        d = _sp().to_dict()
        self.assertNotIn("description", d)
        self.assertNotIn("origin", d)
        self.assertNotIn("searchConfig", d)

    def test_has_dict_search_configuration(self):
        sp = CVSearchProfile(
            search_profile_id="sp1", cv_id="c1", user_id="u1", tenant_id="t1",
            name="sp", search_configuration={"targetRoles": ["X"]})
        self.assertEqual(["X"], sp.to_dict()["searchConfiguration"]["targetRoles"])


class TestAtsGap(unittest.TestCase):
    def test_missing_criteria(self):
        self.assertNotIn("criteria", _ats().to_dict())

    def test_has_non_contract_requirement_fields(self):
        ats = ATSSearchProfile(
            ats_profile_id="a1", search_profile_id="sp1", cv_id="c1",
            user_id="u1", tenant_id="t1", name="a",
            requirements=["r"], preferred_criteria=["p"], exclusions=["e"])
        d = ats.to_dict()
        self.assertEqual(["r"], d["requirements"])
        self.assertEqual(["p"], d["preferredCriteria"])
        self.assertEqual(["e"], d["exclusions"])


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
# Existing roundtrips (lossless today)
# --------------------------------------------------------------------------- #

class TestExistingRoundtrip(unittest.TestCase):
    def test_manual_profile_roundtrip_utf8_and_multi_values(self):
        mp = MatchingPreferences(
            roles=["Cloud Engineer", "Lösungsarchitekt"],
            work_modes=["remote", "hybrid"],
            employment_types=["full_time", "part_time"],
            locations=["Darmstadt", "Köln"],
            required_skills=['AWS, "Cloud Architecture"'],
        )
        man = ManualSearchProfile(
            manual_profile_id="m1", user_id="u1", tenant_id="t1",
            name="Independent", description="Ümlaut ✓",
            matching_preferences=mp)
        out = ManualSearchProfile.from_dict(man.to_dict())
        self.assertEqual("Ümlaut ✓", out.description)
        self.assertEqual(["Cloud Engineer", "Lösungsarchitekt"],
                         out.matching_preferences.roles)
        self.assertEqual(["Darmstadt", "Köln"],
                         out.matching_preferences.locations)
        self.assertEqual(['AWS, "Cloud Architecture"'],
                         out.matching_preferences.required_skills)

    def test_radius_null_is_not_coerced_because_field_is_absent(self):
        # The contract requires radiusKm=null preservation; RIS has no field.
        # This guards the finding: null must not silently become 0.
        d = MatchingPreferences().to_dict()
        self.assertNotIn("radiusKm", d)

    def test_quoted_phrase_is_not_split(self):
        phrase = 'AWS, "Cloud Architecture"'
        mp = MatchingPreferences(required_skills=[phrase])
        back = MatchingPreferences.from_dict(mp.to_dict())
        self.assertEqual([phrase], back.required_skills)


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
