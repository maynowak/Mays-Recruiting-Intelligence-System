"""Tests for the partner profile v1 contract foundation."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import unittest

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - local fallback only
    import contextlib

    class _Raises:
        def __init__(self, exc):
            self.exc = exc
            self.value = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc_type is None:
                raise AssertionError(f"Expected {self.exc.__name__} to be raised")
            if not issubclass(exc_type, self.exc):
                return False
            self.value = exc
            return True

    class _PytestShim:
        raises = _Raises

    pytest = _PytestShim()

from jobsearch.partner_profile_contract import (
    SCHEMA_VERSION,
    RESOURCE_TYPES,
    MAX_CVS_PER_USER,
    MAX_SEARCH_PROFILES_PER_CV,
    MAX_ATS_PROFILES_PER_SEARCH_PROFILE,
    ProfileContractError,
    UserProfile,
    CVDocument,
    CVSearchProfile,
    ATSSearchProfile,
    ManualSearchProfile,
    MatchingPreferences,
    reject_client_identity,
    parse_resource,
    build_from_client_payload,
    validate_cv_capacity,
    validate_search_profile_capacity,
    validate_ats_profile_capacity,
    validate_ats_assignment,
)


def _user():
    return UserProfile(user_id="u1", tenant_id="t1", display_name="Alice", email="a@b.com")


def _cv(cv_id="cv1"):
    return CVDocument(cv_id=cv_id, user_id="u1", tenant_id="t1", name="resume.pdf", size=1024, content_hash="abc")


def _sp(sp_id="sp1", cv_id="cv1"):
    return CVSearchProfile(search_profile_id=sp_id, cv_id=cv_id, user_id="u1", tenant_id="t1", name="Senior Dev",
                          profile={"skills": "python", "targetRoles": ["Dev"]},
                          search_configuration={"targetRoles": ["Dev", "Lead"], "workModes": ["remote", "hybrid"]})


def _ats(ats_id="ats1", sp_id="sp1", cv_id="cv1"):
    return ATSSearchProfile(ats_profile_id=ats_id, search_profile_id=sp_id, cv_id=cv_id,
                            user_id="u1", tenant_id="t1", name="ATS1",
                            target_roles=["Dev"], skills=["python"], work_mode="remote")


class TestValidObjects(unittest.TestCase):
    def test_user_profile_roundtrip(self):
        u = _user()
        d = u.to_dict()
        u2 = UserProfile.from_dict(d)
        assert u2.user_id == "u1"
        assert u2.tenant_id == "t1"
        assert d["resourceType"] == "UserProfile"
        assert d["schemaVersion"] == SCHEMA_VERSION

    def test_cv_document_roundtrip(self):
        c = _cv()
        d = c.to_dict()
        c2 = CVDocument.from_dict(d)
        assert c2.cv_id == "cv1"
        assert c2.size == 1024

    def test_cv_search_profile_roundtrip(self):
        sp = _sp()
        d = sp.to_dict()
        sp2 = CVSearchProfile.from_dict(d)
        assert sp2.search_profile_id == "sp1"
        assert sp2.search_configuration["targetRoles"] == ["Dev", "Lead"]

    def test_ats_roundtrip(self):
        a = _ats()
        d = a.to_dict()
        a2 = ATSSearchProfile.from_dict(d)
        assert a2.ats_profile_id == "ats1"
        assert a2.target_roles == ["Dev"]

    def test_manual_profile_roundtrip(self):
        mp = MatchingPreferences(roles=["Dev"], work_modes=["remote"], employment_types=["full_time"],
                                 locations=["Berlin"], salary_min=50000, remote_only=True, sources=["arbeitsagentur"],
                                 query="python")
        m = ManualSearchProfile(manual_profile_id="m1", user_id="u1", tenant_id="t1", name="Manual1",
                                matching_preferences=mp)
        d = m.to_dict()
        m2 = ManualSearchProfile.from_dict(d)
        assert m2.manual_profile_id == "m1"
        assert m2.matching_preferences.roles == ["Dev"]
        assert m2.matching_preferences.salary_min == 50000


class TestInvalidFields(unittest.TestCase):
    def test_missing_required_user_id(self):
        with pytest.raises(ProfileContractError) as ei:
            UserProfile.from_dict({"resourceType": "UserProfile", "schemaVersion": SCHEMA_VERSION, "tenantId": "t1"})
        assert ei.value.code == "MISSING_FIELD"

    def test_unknown_field_rejected(self):
        with pytest.raises(ProfileContractError) as ei:
            UserProfile.from_dict({"resourceType": "UserProfile", "schemaVersion": SCHEMA_VERSION,
                                   "userId": "u1", "tenantId": "t1", "foo": "bar"})
        assert ei.value.code == "UNKNOWN_FIELD"

    def test_invalid_size(self):
        with pytest.raises(ProfileContractError):
            CVDocument(cv_id="c", user_id="u", tenant_id="t", name="n", size=-1).validate()

    def test_empty_name(self):
        with pytest.raises(ProfileContractError):
            CVDocument(cv_id="c", user_id="u", tenant_id="t", name="").validate()


class TestHierarchy(unittest.TestCase):
    def test_ats_assignment_valid(self):
        sp = _sp()
        ats = _ats()
        validate_ats_assignment(ats, sp)  # no raise

    def test_ats_assignment_invalid_search_profile(self):
        sp = _sp()
        ats = _ats(sp_id="other")
        with pytest.raises(ProfileContractError):
            validate_ats_assignment(ats, sp)

    def test_ats_assignment_invalid_cv(self):
        sp = _sp()
        ats = _ats(cv_id="other")
        with pytest.raises(ProfileContractError):
            validate_ats_assignment(ats, sp)

    def test_ats_assignment_invalid_identity(self):
        sp = _sp()
        ats = _ats()
        ats.user_id = "other"
        with pytest.raises(ProfileContractError):
            validate_ats_assignment(ats, sp)


class TestManualIndependent(unittest.TestCase):
    def test_manual_profile_no_cv_dependency(self):
        m = ManualSearchProfile(manual_profile_id="m1", user_id="u1", tenant_id="t1", name="Manual")
        assert m.matching_preferences is not None
        d = m.to_dict()
        assert "cvId" not in d
        assert "searchProfileId" not in d


class TestMultiValueSearchConfig(unittest.TestCase):
    def test_preserves_multiple_roles_workmodes_employment(self):
        sp = CVSearchProfile(
            search_profile_id="sp", cv_id="cv", user_id="u", tenant_id="t", name="n",
            search_configuration={
                "targetRoles": ["Dev", "Lead", "Architect"],
                "workModes": ["remote", "hybrid", "onsite"],
                "employmentTypes": ["full_time", "part_time", "contract"],
            },
        )
        d = sp.to_dict()
        sp2 = CVSearchProfile.from_dict(d)
        assert sp2.search_configuration["targetRoles"] == ["Dev", "Lead", "Architect"]
        assert sp2.search_configuration["workModes"] == ["remote", "hybrid", "onsite"]
        assert sp2.search_configuration["employmentTypes"] == ["full_time", "part_time", "contract"]


class TestSchemaVersion(unittest.TestCase):
    def test_default_schema_version(self):
        u = UserProfile(user_id="u", tenant_id="t")
        assert u.schema_version == SCHEMA_VERSION
        assert u.to_dict()["schemaVersion"] == SCHEMA_VERSION

    def test_wrong_schema_version_rejected(self):
        with pytest.raises(ProfileContractError) as ei:
            UserProfile.from_dict({"resourceType": "UserProfile", "schemaVersion": "v2",
                                   "userId": "u", "tenantId": "t"})
        assert ei.value.code == "INVALID_SCHEMA_VERSION"

    def test_missing_resource_type_rejected(self):
        with pytest.raises(ProfileContractError):
            parse_resource({"schemaVersion": SCHEMA_VERSION, "userId": "u", "tenantId": "t"})


class TestClientIdentityForbidden(unittest.TestCase):
    def test_reject_client_identity(self):
        with pytest.raises(ProfileContractError) as ei:
            reject_client_identity({"userId": "evil", "tenantId": "t"})
        assert ei.value.code == "CLIENT_IDENTITY_FORBIDDEN"

    def test_build_from_client_injects_identity(self):
        obj = build_from_client_payload(
            "UserProfile",
            {"displayName": "Alice"},
            server_user_id="server-u",
            server_tenant_id="server-t",
        )
        assert obj.user_id == "server-u"
        assert obj.tenant_id == "server-t"

    def test_build_from_client_rejects_client_identity(self):
        with pytest.raises(ProfileContractError):
            build_from_client_payload(
                "UserProfile",
                {"userId": "evil", "tenantId": "t", "displayName": "Alice"},
                server_user_id="server-u",
                server_tenant_id="server-t",
            )


class TestCapacity(unittest.TestCase):
    def test_cv_capacity_ok(self):
        cvs = [_cv(f"cv{i}") for i in range(MAX_CVS_PER_USER)]
        validate_cv_capacity(cvs)  # no raise

    def test_cv_capacity_exceeded(self):
        cvs = [_cv(f"cv{i}") for i in range(MAX_CVS_PER_USER + 1)]
        with pytest.raises(ProfileContractError):
            validate_cv_capacity(cvs)

    def test_search_profile_capacity(self):
        sps = [_sp(f"sp{i}") for i in range(MAX_SEARCH_PROFILES_PER_CV)]
        validate_search_profile_capacity(sps)
        with pytest.raises(ProfileContractError):
            validate_search_profile_capacity(sps + [_sp("extra")])

    def test_ats_capacity(self):
        ats = [_ats(f"ats{i}") for i in range(MAX_ATS_PROFILES_PER_SEARCH_PROFILE)]
        validate_ats_profile_capacity(ats)
        with pytest.raises(ProfileContractError):
            validate_ats_profile_capacity(ats + [_ats("extra")])


class TestForbiddenContent(unittest.TestCase):
    def test_no_file_object(self):
        with pytest.raises(ProfileContractError):
            CVDocument(cv_id="c", user_id="u", tenant_id="t", name="n", metadata={"file": "obj"}).validate()

    def test_no_cv_text(self):
        with pytest.raises(ProfileContractError):
            CVDocument(cv_id="c", user_id="u", tenant_id="t", name="n", metadata={"cvText": "text"}).validate()

    def test_no_original_text(self):
        with pytest.raises(ProfileContractError):
            CVDocument(cv_id="c", user_id="u", tenant_id="t", name="n", metadata={"originalText": "text"}).validate()


class TestResourceTypes(unittest.TestCase):
    def test_all_resource_types_present(self):
        assert "UserProfile" in RESOURCE_TYPES
        assert "CVDocument" in RESOURCE_TYPES
        assert "CVSearchProfile" in RESOURCE_TYPES
        assert "ATSSearchProfile" in RESOURCE_TYPES
        assert "ManualSearchProfile" in RESOURCE_TYPES
        assert "MatchingPreferences" in RESOURCE_TYPES

    def test_parse_resource(self):
        u = parse_resource({"resourceType": "UserProfile", "schemaVersion": SCHEMA_VERSION,
                            "userId": "u", "tenantId": "t"})
        assert isinstance(u, UserProfile)

    def test_matching_preferences_multi_values_preserved(self):
        mp = MatchingPreferences(roles=["Dev", "Lead"], work_modes=["remote", "hybrid"],
                                 employment_types=["full_time", "part_time"], locations=["Berlin", "Munich"])
        d = mp.to_dict()
        mp2 = MatchingPreferences.from_dict(d)
        assert mp2.roles == ["Dev", "Lead"]
        assert mp2.work_modes == ["remote", "hybrid"]
        assert mp2.employment_types == ["full_time", "part_time"]
        assert mp2.locations == ["Berlin", "Munich"]

    def test_ats_criteria_separate_from_matching_preferences(self):
        ats = _ats()
        # ATS has target_roles/skills; MatchingPreferences has roles/work_modes
        assert hasattr(ats, "target_roles")
        assert not hasattr(ats, "matching_preferences")
        mp = MatchingPreferences(roles=["X"])
        assert mp.roles == ["X"]


class TestFixtureCompatibility(unittest.TestCase):
    def test_synthetic_cv_profile_fixture(self):
        # Synthetic fixture mimicking a CV search profile payload
        payload = {
            "resourceType": "CVSearchProfile",
            "schemaVersion": SCHEMA_VERSION,
            "searchProfileId": "sp-synth",
            "cvId": "cv-synth",
            "userId": "u-synth",
            "tenantId": "t-synth",
            "name": "Synthetic",
            "profile": {"skills": "python,java", "targetRoles": ["Dev"]},
            "searchConfiguration": {
                "targetRoles": ["Dev", "Lead"],
                "workModes": ["remote", "hybrid"],
                "employmentTypes": ["full_time"],
            },
        }
        sp = CVSearchProfile.from_dict(payload)
        assert sp.search_profile_id == "sp-synth"
        assert sp.search_configuration["targetRoles"] == ["Dev", "Lead"]

    def test_synthetic_ats_fixture(self):
        payload = {
            "resourceType": "ATSSearchProfile",
            "schemaVersion": SCHEMA_VERSION,
            "atsProfileId": "ats-synth",
            "searchProfileId": "sp-synth",
            "cvId": "cv-synth",
            "userId": "u-synth",
            "tenantId": "t-synth",
            "name": "ATS Synth",
            "targetRoles": ["Dev"],
            "skills": ["python"],
            "workMode": "remote",
        }
        ats = ATSSearchProfile.from_dict(payload)
        assert ats.ats_profile_id == "ats-synth"
        assert ats.work_mode == "remote"
        matching_sp = CVSearchProfile(search_profile_id="sp-synth", cv_id="cv-synth", user_id="u-synth", tenant_id="t-synth", name="sp")
        validate_ats_assignment(ats, matching_sp)
        # identity mismatch should fail
        ats2 = ATSSearchProfile.from_dict({**payload, "userId": "other"})
        with pytest.raises(ProfileContractError):
            validate_ats_assignment(ats2, matching_sp)

    def test_synthetic_manual_fixture(self):
        payload = {
            "resourceType": "ManualSearchProfile",
            "schemaVersion": SCHEMA_VERSION,
            "manualProfileId": "m-synth",
            "userId": "u-synth",
            "tenantId": "t-synth",
            "name": "Manual Synth",
            "matchingPreferences": {
                "resourceType": "MatchingPreferences",
                "schemaVersion": SCHEMA_VERSION,
                "roles": ["Dev"],
                "workModes": ["remote"],
                "employmentTypes": ["full_time"],
                "locations": ["Berlin"],
            },
        }
        m = ManualSearchProfile.from_dict(payload)
        assert m.manual_profile_id == "m-synth"
        assert m.matching_preferences.locations == ["Berlin"]
        assert "cvId" not in m.to_dict()
