"""Versioned, capability-scoped privacy declarations and evidence checks.

Declarations describe policy; evidence records independently produced test and
build provenance. A declaration alone is never sufficient for execution.
"""

from __future__ import annotations

import hashlib
import json
import math
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
    input_field_types: tuple[tuple[str, str], ...]
    prohibited_inline_categories: tuple[str, ...]
    actor_identity: str
    requester_identity: str
    tenant_identity: str
    authorization_requirements: tuple[str, ...]
    storage_locations: tuple[str, ...]
    external_recipients: tuple[str, ...]
    result_categories: tuple[str, ...]
    allowed_result_fields: tuple[str, ...]
    order_result_disposition: str
    allowed_order_result_fields: tuple[str, ...]
    result_field_types: tuple[tuple[str, str], ...]
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
    "allowed_result_fields",
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
    for name in ("input_field_types", "result_field_types"):
        if name in fields and isinstance(fields[name], list):
            fields[name] = tuple(tuple(pair) if isinstance(pair, list) else pair
                                 for pair in fields[name])
    return CapabilityPrivacyDeclaration(**fields)


def _valid_typed_fields(fields: tuple[tuple[str, str], ...], allowed: tuple[str, ...]) -> bool:
    kinds = {"number", "integer", "string", "opaque-reference", "boolean"}
    if not isinstance(fields, tuple):
        return False
    if any(not isinstance(pair, tuple) or len(pair) != 2
           or not all(isinstance(item, str) and item for item in pair)
           or pair[1] not in kinds for pair in fields):
        return False
    names = [pair[0] for pair in fields]
    return len(names) == len(set(names)) and set(names) == set(allowed)


def _value_matches(value: Any, kind: str) -> bool:
    if kind == "number":
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and (not isinstance(value, float) or math.isfinite(value)))
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "opaque-reference":
        return isinstance(value, str) and bool(value.strip())
    if kind == "boolean":
        return isinstance(value, bool)
    return False


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
    if not set(declaration.allowed_order_result_fields).issubset(
            declaration.allowed_result_fields):
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
        declaration.allowed_input_fields, declaration.allowed_result_fields,
        declaration.allowed_order_result_fields,
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
    if (not _valid_typed_fields(declaration.input_field_types,
                                declaration.allowed_input_fields)
            or not _valid_typed_fields(declaration.result_field_types,
                                       declaration.allowed_result_fields)):
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


def validate_capability_input(declaration: CapabilityPrivacyDeclaration,
                              payload: Any) -> bool:
    """Allow only declared payload fields and primitive types."""
    if not isinstance(payload, dict):
        return False
    allowed = set(declaration.allowed_input_fields)
    if set(payload) != allowed:
        return False
    kinds = dict(declaration.input_field_types)
    return all(_value_matches(value, kinds[key]) for key, value in payload.items())


def validate_capability_result(declaration: CapabilityPrivacyDeclaration,
                               result: Any, *, order_transport: bool = False) -> bool:
    """Check result payload before WorkItem persistence or ORDER_RESULT."""
    if not isinstance(result, dict):
        return False
    data = result.get("data")
    if not isinstance(data, dict):
        return False
    allowed = set(declaration.allowed_order_result_fields if order_transport
                  else declaration.allowed_result_fields)
    if not set(data).issubset(allowed):
        return False
    kinds = dict(declaration.result_field_types)
    return all(_value_matches(value, kinds[key]) for key, value in data.items())
