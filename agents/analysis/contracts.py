"""Versioned contracts for the RIS analysis pipeline (CV/job/ATS/comparison)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

REQUEST_SCHEMA_VERSION = "1.0"
RESULT_BODY_SCHEMA_VERSION = "1.0"
ALLOWED_RESULTS = ("cv.tags", "job.tags", "ats.tags", "comparison")
RESULT_CAPABILITY = {
    "cv.tags": "parse.cv",
    "job.tags": "parse.job",
    "ats.tags": "analyze.job",
    "comparison": "compare.tags",
}
MAX_INLINE_JOB_CHARS = 32 * 1024
ANALYSIS_CONSENT_PURPOSE = "analysis-processing"
ANALYSIS_NOTICE_VERSION = "1.0"


class ContractError(ValueError):
    """Invalid request or result contract; ``code`` is stable for callers."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_digest(value: Any) -> str:
    return _digest(value)


def validate_request(payload: Any) -> Dict[str, Any]:
    """Validate and normalize the versioned analysis request."""
    if not isinstance(payload, dict):
        raise ContractError("invalid_request", "request must be an object")
    if payload.get("schemaVersion") != REQUEST_SCHEMA_VERSION:
        raise ContractError("schema_version_unsupported",
                            f"schemaVersion must be {REQUEST_SCHEMA_VERSION}")
    requested = payload.get("requestedResults")
    if not isinstance(requested, list) or not requested:
        raise ContractError("invalid_requested_results",
                            "requestedResults must be a non-empty list")
    if len(set(requested)) != len(requested):
        raise ContractError("invalid_requested_results",
                            "requestedResults must not contain duplicates")
    unknown = [item for item in requested if item not in ALLOWED_RESULTS]
    if unknown:
        raise ContractError("invalid_requested_results",
                            f"unsupported result(s): {', '.join(unknown)}")

    inputs = payload.get("input")
    if not isinstance(inputs, dict):
        raise ContractError("invalid_input", "input must be an object")
    cv = inputs.get("cv")
    job = inputs.get("job")
    profile = inputs.get("profile")
    if cv is not None and not isinstance(cv, dict):
        raise ContractError("invalid_input", "input.cv must be an object")
    if job is not None and not isinstance(job, dict):
        raise ContractError("invalid_input", "input.job must be an object")
    if profile is not None and not isinstance(profile, dict):
        raise ContractError("invalid_input", "input.profile must be an object")

    if "cv.tags" in requested or "comparison" in requested:
        if not cv or not (cv.get("cvId") or isinstance(cv.get("structured"), dict)):
            raise ContractError("missing_cv",
                                "cvId or structured CV data is required")
    if "job.tags" in requested or "ats.tags" in requested or "comparison" in requested:
        if not job or not (job.get("text") or job.get("jobRef")):
            raise ContractError("missing_job",
                                "job text or jobRef is required")
    if job and isinstance(job.get("text"), str):
        if len(job["text"]) > MAX_INLINE_JOB_CHARS:
            raise ContractError(
                "job_text_too_large",
                f"inline job text exceeds {MAX_INLINE_JOB_CHARS} characters; "
                "use jobRef")
    if "ats.tags" in requested:
        cv_available = bool(cv and (cv.get("cvId")
                                    or isinstance(cv.get("structured"), dict)))
        if not cv_available and not isinstance(profile, dict):
            raise ContractError("missing_ats_inputs",
                                "ATS requires CV data or input.profile")
    return {
        "schemaVersion": REQUEST_SCHEMA_VERSION,
        "requestedResults": list(requested),
        "input": {"cv": cv, "job": job, "profile": profile},
        "idempotencyKey": payload.get("idempotencyKey"),
        "digest": _digest(payload),
    }


@dataclass(frozen=True)
class Identity:
    tenant_id: str
    user_id: str
    entitlements: frozenset
    consent: bool = True
    partner_application_id: Optional[str] = None
    issuer: Optional[str] = None
    caller_partner_id: Optional[str] = None
    consent_purpose: Optional[str] = None
    consent_notice_version: Optional[str] = None
    consent_notice_approved: bool = False
    synthetic: bool = False

    def entitled(self, capability: str) -> bool:
        return capability in self.entitlements


def require_capabilities(requested: Iterable[str], identity: Identity) -> None:
    if not identity.consent:
        raise ContractError("consent_required",
                            "analysis processing consent is required")
    if identity.consent_purpose != ANALYSIS_CONSENT_PURPOSE:
        raise ContractError("consent_purpose_mismatch",
                            f"consent for {ANALYSIS_CONSENT_PURPOSE} is required")
    if not identity.consent_notice_approved and not identity.synthetic:
        raise ContractError(
            "consent_notice_not_approved",
            "the analysis-processing notice is a draft; legal approval is required")
    needed = {RESULT_CAPABILITY[item] for item in requested}
    if "comparison" in requested:
        needed.update({"parse.cv", "parse.job"})
    missing = sorted(cap for cap in needed if not identity.entitled(cap))
    if missing:
        raise ContractError("entitlement_denied",
                            f"missing entitlement(s): {', '.join(missing)}")


def _provenance(parser_version: str, source: str) -> Dict[str, Any]:
    return {"source": source, "parserVersion": parser_version,
            "contractVersion": RESULT_BODY_SCHEMA_VERSION}


def build_cv_result(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schemaVersion": RESULT_BODY_SCHEMA_VERSION,
        "bodyType": "CVParserResultBody",
        "bodyVersion": "1.0",
        "stableId": data.get("stableId"),
        "cvTags": data.get("cvTags", []),
        "skills": data.get("skills", []),
        "experience": data.get("experience", []),
        "education": data.get("education", []),
        "languages": data.get("languages", []),
        "location": data.get("location", ""),
        "confidence": data.get("confidence", "uncertain"),
        "parserVersion": data.get("parserVersion", "unknown"),
        "provenance": data.get("provenance")
        or _provenance(data.get("parserVersion", "unknown"), "mays-jobsearch"),
    }


def build_job_result(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schemaVersion": RESULT_BODY_SCHEMA_VERSION,
        "bodyType": "JobParserResultBody",
        "bodyVersion": "1.0",
        "stableId": data.get("stableId"),
        "jobTags": data.get("jobTags", []),
        "requiredSkills": data.get("requiredSkills", []),
        "preferredSkills": data.get("preferredSkills", []),
        "experienceRequirements": data.get("experienceRequirements", []),
        "workMode": data.get("workMode", "unknown"),
        "location": data.get("location", []),
        "confidence": data.get("confidence", "uncertain"),
        "analysisStatus": data.get("analysisStatus", ""),
        "parserVersion": data.get("parserVersion", "unknown"),
        "provenance": data.get("provenance")
        or _provenance(data.get("parserVersion", "unknown"), "mays-jobsearch"),
    }


def build_ats_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """Additive projection: keeps ATSAnalysisResultBody 2.0 compatible."""
    return {
        "schemaVersion": RESULT_BODY_SCHEMA_VERSION,
        "bodyType": "ATSAnalysisResultBody",
        "bodyVersion": "2.0",
        "stableId": data.get("stableId"),
        "atsTags": data.get("atsTags", []),
        "analysis": {
            "score": data.get("score"),
            "analysisStatus": data.get("analysisStatus", ""),
            "requirements": data.get("requirements", []),
            "matches": data.get("matches", []),
            "criticalGaps": data.get("criticalGaps", []),
        },
        "provenance": data.get("provenance")
        or _provenance("ats.mjs", "mays-jobsearch"),
    }


def build_comparison_result(cv: Dict[str, Any], job: Dict[str, Any],
                            comparison: Dict[str, Any],
                            ats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = {
        "schemaVersion": RESULT_BODY_SCHEMA_VERSION,
        "bodyType": "ComparisonResultBody",
        "bodyVersion": "1.0",
        "cvTags": cv.get("cvTags", []),
        "jobTags": job.get("jobTags", []),
        "matched": comparison.get("matched", []),
        "missingInCv": comparison.get("missingInCv", []),
        "missingInJob": comparison.get("missingInJob", []),
        "extraInCv": comparison.get("extraInCv", []),
        "coverage": comparison.get("coverage", {}),
        "weightedScore": comparison.get("weightedScore"),
        "aliasMapVersion": comparison.get("aliasMapVersion"),
        "unknown": comparison.get("unknown", False),
        "provenance": {
            "cvStableId": cv.get("stableId"),
            "jobStableId": job.get("stableId"),
            "source": "ris-deterministic",
            "atsScore": (ats or {}).get("analysis", {}).get("score"),
        },
    }
    if ats is not None:
        body["atsTags"] = ats.get("atsTags", [])
    return body


def build_response(request_id: str, results: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schemaVersion": REQUEST_SCHEMA_VERSION,
        "requestId": request_id,
        "results": results,
    }
