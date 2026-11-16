"""Fail-closed validation of the pinned Mays-Jobsearch ATS response.

The ATS implementation stays in Mays-Jobsearch. RIS validates only the
interface it consumes (``docs/contracts/JOBSEARCH-ATS-ANALYSIS-V1.md``). No
analysis logic is duplicated here.
"""

from __future__ import annotations

from typing import Any, Dict

CONTRACT_VERSION = "1.1"
CONTRACT_PROTOCOL = "MAYS-JOBSEARCH-ATS-ANALYSIS-V1"

ANALYSIS_STATUSES = frozenset({"complete", "limited", "insufficient"})
MATCH_STATUSES = frozenset({"MATCHED", "PARTIAL", "UNKNOWN"})
IMPORTANCE_LEVELS = frozenset({"critical", "high", "medium", "low"})


class ATSContractError(ValueError):
    """The upstream response does not match the pinned contract."""

    code = "ATS_CONTRACT_MISMATCH"

    def __init__(self, message: str):
        super().__init__(message)
        self.code = "ATS_CONTRACT_MISMATCH"


def _require(mapping: Any, path: str) -> Dict[str, Any]:
    if not isinstance(mapping, dict):
        raise ATSContractError(f"{path}: expected object, got {type(mapping).__name__}")
    return mapping


def _require_key(mapping: Dict[str, Any], key: str, path: str) -> Any:
    if key not in mapping:
        raise ATSContractError(f"{path}.{key}: missing")
    return mapping[key]


def _int_0_100(value: Any, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ATSContractError(f"{path}: expected integer, got {type(value).__name__}")
    if not 0 <= value <= 100:
        raise ATSContractError(f"{path}: expected 0..100, got {value}")


def _bool(value: Any, path: str) -> None:
    if not isinstance(value, bool):
        raise ATSContractError(f"{path}: expected boolean, got {type(value).__name__}")


def _list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise ATSContractError(f"{path}: expected array, got {type(value).__name__}")
    return value


def _str(value: Any, path: str, allow_empty: bool = True) -> None:
    if not isinstance(value, str):
        raise ATSContractError(f"{path}: expected string, got {type(value).__name__}")
    if not allow_empty and not value:
        raise ATSContractError(f"{path}: must not be empty")


def validate_analysis_response(payload: Any) -> Dict[str, Any]:
    """Validate a ``POST /api/ats-analysis`` response; return it unchanged.

    Unknown additional fields are allowed (additive upstream changes). Required
    fields, types, ranges and status values are checked fail-closed.
    """
    response = _require(payload, "$")

    analysis = _require(_require_key(response, "analysis", "$"), "$.analysis")
    _int_0_100(_require_key(analysis, "score", "$.analysis"), "$.analysis.score")

    coverage = _require(
        _require_key(analysis, "keywordCoverage", "$.analysis"),
        "$.analysis.keywordCoverage",
    )
    _int_0_100(
        _require_key(coverage, "overall", "$.analysis.keywordCoverage"),
        "$.analysis.keywordCoverage.overall",
    )

    _int_0_100(
        _require_key(analysis, "requirementCoverage", "$.analysis"),
        "$.analysis.requirementCoverage",
    )
    _int_0_100(
        _require_key(analysis, "profileEvidenceCoverage", "$.analysis"),
        "$.analysis.profileEvidenceCoverage",
    )

    role_match = _require_key(analysis, "roleMatch", "$.analysis")
    if role_match is not None:
        _int_0_100(role_match, "$.analysis.roleMatch")

    status = _require_key(analysis, "analysisStatus", "$.analysis")
    if status not in ANALYSIS_STATUSES:
        raise ATSContractError(
            f"$.analysis.analysisStatus: expected one of {sorted(ANALYSIS_STATUSES)}, got {status!r}"
        )

    basis = _require(_require_key(analysis, "basis", "$.analysis"), "$.analysis.basis")
    for key in ("requirementCount", "titleRequirementCount"):
        value = _require_key(basis, key, "$.analysis.basis")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ATSContractError(
                f"$.analysis.basis.{key}: expected non-negative integer, got {value!r}"
            )
    _bool(
        _require_key(basis, "hasDescription", "$.analysis.basis"),
        "$.analysis.basis.hasDescription",
    )
    _bool(
        _require_key(basis, "roleMatchAvailable", "$.analysis.basis"),
        "$.analysis.basis.roleMatchAvailable",
    )

    _list(_require_key(analysis, "criticalGaps", "$.analysis"), "$.analysis.criticalGaps")

    requirements = _list(
        _require_key(analysis, "requirements", "$.analysis"), "$.analysis.requirements"
    )
    for index, requirement in enumerate(requirements):
        path = f"$.analysis.requirements[{index}]"
        item = _require(requirement, path)
        for key in ("id", "text", "category"):
            _str(_require_key(item, key, path), f"{path}.{key}")
        importance = _require_key(item, "importance", path)
        if importance not in IMPORTANCE_LEVELS:
            raise ATSContractError(
                f"{path}.importance: expected one of {sorted(IMPORTANCE_LEVELS)}, got {importance!r}"
            )

    matches = _list(_require_key(analysis, "matches", "$.analysis"), "$.analysis.matches")
    for index, match in enumerate(matches):
        path = f"$.analysis.matches[{index}]"
        item = _require(match, path)
        _str(_require_key(item, "requirementId", path), f"{path}.requirementId")
        status_value = _require_key(item, "status", path)
        if status_value not in MATCH_STATUSES:
            raise ATSContractError(
                f"{path}.status: expected one of {sorted(MATCH_STATUSES)}, got {status_value!r}"
            )
        _str(_require_key(item, "confidence", path), f"{path}.confidence")

    recommendations = _list(
        _require_key(response, "recommendations", "$"), "$.recommendations"
    )
    for index, recommendation in enumerate(recommendations):
        path = f"$.recommendations[{index}]"
        item = _require(recommendation, path)
        for key in (
            "requirementId",
            "changeType",
            "priority",
            "proposedChange",
            "rationale",
        ):
            _str(_require_key(item, key, path), f"{path}.{key}")
        _list(_require_key(item, "evidence", path), f"{path}.evidence")

    ai = _require(_require_key(response, "ai", "$"), "$.ai")
    for key in ("requested", "executed", "consentRequired", "consentGiven"):
        _bool(_require_key(ai, key, "$.ai"), f"$.ai.{key}")

    return response
