"""Contract-only validation for the draft structured CV profile resource.

No AWS, backend, RIS handler, or private CV data is touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

pytest.importorskip("jsonschema")
from jsonschema import Draft7Validator, RefResolver  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "docs/api/openapi-structured-cv-profile-v1.draft.yaml"
CONTRACT_PATH = ROOT / "docs/contracts/STRUCTURED-CV-PROFILE-V1.md"


def load_openapi():
    return yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))


def validator_for(schema_name: str):
    document = load_openapi()
    resolver = RefResolver.from_schema(document)
    schema = document["components"]["schemas"][schema_name]
    return Draft7Validator(schema, resolver=resolver)


def synthetic_profile():
    return {
        "schemaVersion": 1,
        "profileId": "cvp-11111111-1111-4111-8111-111111111111",
        "name": "Synthetic durable CV",
        "template": "classic",
        "cvData": {
            "schemaVersion": 1,
            "personal": {"fullName": "Nora Beispiel", "email": "nora.beispiel@example.invalid"},
            "profile": {"headline": "Cloud Architect", "summary": "Synthetic profile."},
            "experience": [],
            "education": [],
            "skills": ["Synthetic Skill 01", "Synthetic Skill 02"],
            "projects": [],
            "certificates": [],
            "languages": [],
            "links": [],
        },
        "importReview": {
            "schemaVersion": 1,
            "sourceName": "synthetic-44-items.pdf",
            "pageCount": 3,
            "pendingAcknowledged": True,
            "selectedSections": ["personal", "experience"],
            "skills": {"total": 71, "selected": 58, "unselected": 13, "limited": True},
            "items": [
                {
                    "id": f"review-{index}-{index // 10 + 1}",
                    "index": index,
                    "text": f"Synthetic review item {index + 1}",
                    "original": f"Synthetic original item {index + 1}",
                    "edited": False,
                    "target": "experience",
                    "status": "pending",
                    "applied": False,
                    "page": index // 10 + 1,
                    "sectionHeading": "Synthetic Experience",
                    "reason": "incomplete-experience",
                    "suggestedTarget": "experience",
                }
                for index in range(44)
            ],
            "total": 44,
            "pending": 44,
            "accepted": 0,
            "ignored": 0,
        },
        "version": 1,
        "createdAt": "2026-11-12T12:00:00Z",
        "updatedAt": "2026-11-12T12:00:00Z",
    }


def errors_for(schema_name: str, value):
    return list(validator_for(schema_name).iter_errors(value))


def test_openapi_yaml_and_required_paths_parse():
    document = load_openapi()
    assert document["openapi"] == "3.0.3"
    assert set(document["paths"]) == {
        "/v1/partner/me/cv-builder-profiles",
        "/v1/partner/me/cv-builder-profiles/{profileId}",
        "/v1/partner/me/cv-builder-profiles/{profileId}/export",
    }
    assert document["components"]["parameters"]["IdempotencyKey"]["required"] is True
    assert document["components"]["parameters"]["IfMatchRequired"]["required"] is True
    assert "StructuredCvProfileV1" in document["components"]["schemas"]


def test_44_item_profile_roundtrip_schema_valid():
    profile = synthetic_profile()
    assert errors_for("StructuredCvProfileV1", profile) == []
    assert len(profile["importReview"]["items"]) == 44
    encoded = json.dumps(profile, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert len(encoded) <= 300_000
    assert "Nora Beispiel" in profile["cvData"]["personal"]["fullName"]
    assert "original" in profile["importReview"]["items"][0]
    assert "applied" in profile["importReview"]["items"][0]


def test_missing_applied_is_rejected_at_the_durable_boundary():
    profile = synthetic_profile()
    del profile["importReview"]["items"][0]["applied"]
    assert errors_for("StructuredCvProfileV1", profile)


def test_unknown_schema_versions_are_rejected():
    profile = synthetic_profile()
    profile["schemaVersion"] = 2
    assert errors_for("StructuredCvProfileV1", profile)
    profile = synthetic_profile()
    profile["importReview"]["schemaVersion"] = 2
    assert errors_for("StructuredCvProfileV1", profile)
    profile = synthetic_profile()
    profile["cvData"]["schemaVersion"] = 2
    assert errors_for("StructuredCvProfileV1", profile)


def test_unknown_fields_and_invalid_limits_are_rejected():
    profile = synthetic_profile()
    profile["ownerId"] = "must-not-be-client-owned"
    assert errors_for("StructuredCvProfileV1", profile)
    profile = synthetic_profile()
    profile["cvData"]["skills"] = ["Synthetic"] * 101
    assert errors_for("StructuredCvProfileV1", profile)
    profile = synthetic_profile()
    profile["template"] = "unknown"
    assert errors_for("StructuredCvProfileV1", profile)


def test_two_profiles_are_distinct_contract_resources():
    first = synthetic_profile()
    second = synthetic_profile()
    second["profileId"] = "cvp-22222222-2222-4222-8222-222222222222"
    second["name"] = "Synthetic second CV"
    assert first["profileId"] != second["profileId"]
    assert errors_for("StructuredCvProfileV1", first) == []
    assert errors_for("StructuredCvProfileV1", second) == []


def test_contract_documents_owner_version_idempotency_export_and_erasure_gates():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    for marker in [
        "ownerKey",
        "VERSION_CONFLICT",
        "Idempotency-Key",
        "/export",
        "cv-builder-profile-storage",
        "account erasure",
        "gsi-structured-owner",
        "UNKNOWN",
    ]:
        assert marker.lower() in text.lower()


def test_no_private_pdf_reference_in_contract_artifacts():
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in [OPENAPI_PATH, CONTRACT_PATH]
    )
    assert "/home/" not in text
    assert "may nowak" not in text.lower()
    assert "nowakbewerbung" not in text.lower()
