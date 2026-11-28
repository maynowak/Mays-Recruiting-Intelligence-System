"""Versioned, capability-scoped privacy declarations and evidence checks.

Declarations describe policy; evidence records independently produced test and
build provenance. A declaration alone is never sufficient for execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional


PRIVACY_CONTRACT_VERSION = "RIS-CAPABILITY-PRIVACY/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


@dataclass(frozen=True)
class CapabilityPrivacyDeclaration:
    capability: str
    processing_purpose: str
    technical_inputs: tuple[str, ...]
    business_inputs: tuple[str, ...]
    allowed_input_fields: tuple[str, ...]
    prohibited_inline_categories: tuple[str, ...]
    actor_identity: str
    requester_identity: str
    tenant_identity: str
    authorization_requirements: tuple[str, ...]
    storage_locations: tuple[str, ...]
    external_recipients: tuple[str, ...]
    result_categories: tuple[str, ...]
    order_result_disposition: str
    allowed_order_result_fields: tuple[str, ...]
    lifecycle_phases: tuple[str, ...]
    cleanup_mechanism: str


@dataclass(frozen=True)
class PrivacyEvidence:
    agent_id: str
    agent_version: str
    capability: str
    contract_version: str
    contract_sha256: str
    source_sha: str
    test_report_sha256: str
    artifact_sha256: str
    tests_passed: bool
    required_tests_skipped: bool = False
    source_commit: str = ""
    test_selection_sha256: str = ""
    build_tool_version: str = ""


@dataclass(frozen=True)
class PrivacyValidation:
    valid: bool
    reason: str


_TUPLE_FIELDS = (
    "technical_inputs", "business_inputs", "prohibited_inline_categories",
    "allowed_input_fields", "allowed_order_result_fields",
    "authorization_requirements", "storage_locations", "external_recipients",
    "result_categories", "lifecycle_phases",
)


def declaration_from_mapping(value: Mapping[str, Any]) -> CapabilityPrivacyDeclaration:
    """Parse JSON/YAML-shaped policy data into the immutable typed contract."""
    if not isinstance(value, Mapping):
        raise ValueError("privacy declaration must be an object")
    fields = dict(value)
    for name in _TUPLE_FIELDS:
        if name in fields and isinstance(fields[name], list):
            fields[name] = tuple(fields[name])
    return CapabilityPrivacyDeclaration(**fields)


def declaration_digest(declaration: CapabilityPrivacyDeclaration) -> str:
    payload = json.dumps(asdict(declaration), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_capability_privacy(
    *, agent_id: str, agent_version: str, capability: str,
    declaration: Optional[CapabilityPrivacyDeclaration],
    evidence: Optional[PrivacyEvidence],
    source_sha: Optional[str] = None,
    artifact_sha256: Optional[str] = None,
) -> PrivacyValidation:
    """Fail closed unless declaration and exact-source evidence agree."""
    if declaration is None or evidence is None:
        return PrivacyValidation(False, "PRIVACY_EVIDENCE_MISSING")
    if not isinstance(declaration, CapabilityPrivacyDeclaration):
        return PrivacyValidation(False, "PRIVACY_CONTRACT_INVALID")
    if declaration.capability != capability or not declaration.capability.strip():
        return PrivacyValidation(False, "PRIVACY_CAPABILITY_MISMATCH")
    if declaration.order_result_disposition not in {
        "forbidden", "reference-only", "allowlisted"
    }:
        return PrivacyValidation(False, "PRIVACY_CONTRACT_INVALID")
    if (declaration.order_result_disposition == "allowlisted"
            and not declaration.allowed_order_result_fields):
        return PrivacyValidation(False, "PRIVACY_CONTRACT_INVALID")
    if (declaration.order_result_disposition == "forbidden"
            and declaration.allowed_order_result_fields):
        return PrivacyValidation(False, "PRIVACY_CONTRACT_INVALID")
    if (declaration.order_result_disposition == "reference-only"
            and declaration.allowed_order_result_fields):
        return PrivacyValidation(False, "PRIVACY_CONTRACT_INVALID")
    required_text = (
        declaration.processing_purpose, declaration.actor_identity,
        declaration.requester_identity, declaration.tenant_identity,
        declaration.cleanup_mechanism,
    )
    if any(not isinstance(value, str) or not value.strip()
           for value in required_text):
        return PrivacyValidation(False, "PRIVACY_CONTRACT_INVALID")
    collections = (
        declaration.technical_inputs, declaration.business_inputs,
        declaration.prohibited_inline_categories,
        declaration.authorization_requirements,
        declaration.storage_locations, declaration.external_recipients,
        declaration.result_categories, declaration.lifecycle_phases,
    )
    if any(not isinstance(values, tuple)
           or any(not isinstance(value, str) or not value.strip()
                  for value in values)
           or len(set(values)) != len(values)
           for values in collections):
        return PrivacyValidation(False, "PRIVACY_CONTRACT_INVALID")
    if evidence.contract_version != PRIVACY_CONTRACT_VERSION:
        return PrivacyValidation(False, "PRIVACY_EVIDENCE_STALE")
    if (evidence.agent_id != agent_id
            or evidence.agent_version != agent_version
            or evidence.capability != capability
            or evidence.contract_sha256 != declaration_digest(declaration)):
        return PrivacyValidation(False, "PRIVACY_EVIDENCE_MISMATCH")
    if (not _SHA256.fullmatch(evidence.contract_sha256)
            or not _SOURCE_SHA.fullmatch(evidence.source_sha)
            or not _SHA256.fullmatch(evidence.test_report_sha256)
            or not _SHA256.fullmatch(evidence.artifact_sha256)):
        return PrivacyValidation(False, "PRIVACY_EVIDENCE_INVALID")
    if (evidence.source_commit
            and not re.fullmatch(r"[0-9a-f]{40}", evidence.source_commit)):
        return PrivacyValidation(False, "PRIVACY_EVIDENCE_INVALID")
    if (evidence.test_selection_sha256
            and not _SHA256.fullmatch(evidence.test_selection_sha256)):
        return PrivacyValidation(False, "PRIVACY_EVIDENCE_INVALID")
    if source_sha is not None and evidence.source_sha != source_sha:
        return PrivacyValidation(False, "PRIVACY_EVIDENCE_STALE")
    if artifact_sha256 is not None and evidence.artifact_sha256 != artifact_sha256:
        return PrivacyValidation(False, "PRIVACY_EVIDENCE_STALE")
    if not evidence.tests_passed or evidence.required_tests_skipped:
        return PrivacyValidation(False, "PRIVACY_TEST_EVIDENCE_INCOMPLETE")
    return PrivacyValidation(True, "PRIVACY_EVIDENCE_VALID")
