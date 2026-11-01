"""R08-P1-1 P0-1 canonical UserProfile/CVDocument contract tests."""

import json
from pathlib import Path

import pytest

from jobsearch.partner_profile_contract import (
    CVDocument,
    DocumentUploadTicketV1,
    ProfileContractError,
    UserProfile,
    UserProfilePatchV1,
    parse_expected_version,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "r08_p1_1"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_user_profile_v1_fixture_and_server_authoritative_fields():
    profile = UserProfile.from_dict(fixture("user-profile-v1.json"))
    assert profile.canonical_dict() == fixture("user-profile-v1.json")
    with pytest.raises(ProfileContractError):
        UserProfilePatchV1.from_dict({"userId": "client-controlled"})


def test_user_profile_patch_and_optimistic_lock_tokens():
    patch = UserProfilePatchV1.from_dict({"nickname": "New name", "expectedVersion": 3})
    assert patch.nickname == "New name"
    assert patch.expected_version == 3
    assert parse_expected_version({"expectedVersion": 3}) == 3
    assert parse_expected_version({}, '"3"') == 3
    with pytest.raises(ProfileContractError):
        parse_expected_version({"expectedVersion": 3}, "4")
    with pytest.raises(ProfileContractError):
        parse_expected_version({})


def test_cv_document_v1_maps_legacy_names_and_statuses():
    raw = fixture("cv-document-v1.json")
    cv = CVDocument(
        cv_id=raw["cvId"], user_id="user-synthetic-001",
        tenant_id="tenant-synthetic-001", name=raw["filename"],
        size=raw["sizeBytes"], content_type=raw["contentType"],
        document_id=raw["documentId"], processing_status=raw["processingStatus"],
        metadata=raw["metadata"], created_at=raw["createdAt"],
        updated_at=raw["updatedAt"], version=raw["version"],
    )
    assert cv.canonical_dict() == raw

    legacy = dict(raw)
    legacy.update({"userId": "user-synthetic-001", "tenantId": "tenant-synthetic-001"})
    legacy.pop("filename")
    legacy["name"] = "resume.pdf"
    legacy.pop("sizeBytes")
    legacy["size"] = 2048
    legacy["processingStatus"] = "upload_pending"
    parsed = CVDocument.from_dict(legacy)
    assert parsed.name == "resume.pdf"
    assert parsed.size == 2048
    assert parsed.canonical_dict()["processingStatus"] == "pending"


@pytest.mark.parametrize("field,value", [
    ("contentType", "text/plain"),
    ("sizeBytes", 0),
    ("documentId", None),
    ("processingStatus", "unknown"),
])
def test_cv_document_v1_rejects_noncanonical_public_shape(field, value):
    raw = fixture("cv-document-v1.json")
    raw[field] = value
    cv = CVDocument(
        cv_id=raw["cvId"], user_id="u", tenant_id="t", name=raw["filename"],
        size=raw["sizeBytes"], content_type=raw["contentType"],
        document_id=raw["documentId"], processing_status=raw["processingStatus"],
        metadata=raw.get("metadata", {}), version=raw["version"],
    )
    with pytest.raises(ProfileContractError):
        cv.canonical_dict()


def test_upload_ticket_has_no_internal_s3_key():
    ticket = DocumentUploadTicketV1.from_legacy(fixture("upload-ticket-v1.json"))
    assert ticket.to_dict() == fixture("upload-ticket-v1.json")
    with pytest.raises(ProfileContractError):
        DocumentUploadTicketV1.from_legacy({**fixture("upload-ticket-v1.json"), "key": "tenant/t/users/u/doc"})
