"""Versioned ATSAnalysisResultBody V1.

The body is the RIS-owned, versioned projection of the pinned Jobsearch ATS
response. It keeps only the fields RIS consumers need and drops transient
upstream internals (tokenizer artifacts, raw evidence, profile input).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from agents.ats_agent.contract import (
    CONTRACT_PROTOCOL,
    CONTRACT_VERSION,
    SOURCE_CONTRACT_COMMIT,
)

RESULT_BODY_TYPE = "ATSAnalysisResultBody"
RESULT_BODY_VERSION = "1.1"
SOURCE_SYSTEM = "mays-jobsearch"

_REQUIREMENT_FIELDS: Tuple[str, ...] = ("id", "text", "category", "importance", "source")
_MATCH_FIELDS: Tuple[str, ...] = ("requirementId", "status", "confidence")
_RECOMMENDATION_FIELDS: Tuple[str, ...] = (
    "requirementId",
    "changeType",
    "priority",
    "proposedChange",
    "rationale",
    "evidence",
)
_AI_FIELDS: Tuple[str, ...] = (
    "requested",
    "executed",
    "consentRequired",
    "consentGiven",
    "provider",
    "model",
    "externalProcessing",
    "dataMinimized",
    "privacyStatus",
    "dataCategories",
    "privacyPolicy",
    "formulations",
)
_BASIS_FIELDS: Tuple[str, ...] = (
    "requirementCount",
    "titleRequirementCount",
    "hasDescription",
    "roleMatchAvailable",
)
_METADATA_FIELDS: Tuple[str, ...] = (
    "title",
    "titleTokens",
    "language",
    "workMode",
    "jobTypes",
    "contractType",
    "contractTypeNoData",
)


def _project(mapping: Mapping[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    """Keep only known fields; omit absent optional ones."""
    return {key: mapping[key] for key in fields if key in mapping}


def _project_list(
    items: Iterable[Mapping[str, Any]], fields: Iterable[str]
) -> list:
    return [_project(item, fields) for item in items]


def build_ats_analysis_result_body(
    api_response: Mapping[str, Any],
    *,
    job_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Project a validated ATS response into ATSAnalysisResultBody V1.

    The caller must run ``validate_analysis_response`` first. Unknown fields are
    dropped so upstream additions never leak into the persisted result body.
    """
    analysis = api_response["analysis"]
    body: Dict[str, Any] = {
        "bodyType": RESULT_BODY_TYPE,
        "bodyVersion": RESULT_BODY_VERSION,
        "analysis": {
            "score": analysis["score"],
            "keywordCoverage": {"overall": analysis["keywordCoverage"]["overall"]},
            "requirementCoverage": analysis["requirementCoverage"],
            "profileEvidenceCoverage": analysis["profileEvidenceCoverage"],
            "roleMatch": analysis["roleMatch"],
            "analysisStatus": analysis["analysisStatus"],
            "basis": _project(analysis["basis"], _BASIS_FIELDS),
            "metadata": _project(analysis["metadata"], _METADATA_FIELDS),
            "criticalGaps": _project_list(
                analysis["criticalGaps"], _REQUIREMENT_FIELDS
            ),
            "requirements": _project_list(
                analysis["requirements"], _REQUIREMENT_FIELDS
            ),
            "matches": _project_list(analysis["matches"], _MATCH_FIELDS),
        },
        "recommendations": _project_list(
            api_response["recommendations"], _RECOMMENDATION_FIELDS
        ),
        "ai": _project(api_response["ai"], _AI_FIELDS),
        "source": {
            "system": SOURCE_SYSTEM,
            "contract": CONTRACT_PROTOCOL,
            "contractVersion": CONTRACT_VERSION,
            "contractCommit": SOURCE_CONTRACT_COMMIT,
        },
    }
    if job_title:
        body["jobTitle"] = job_title
    return body
