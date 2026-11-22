"""Deterministic tag normalization and CV↔job comparison."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

ALIAS_MAP_VERSION = "1.0.0"

#: Versioned alias map. Extend deliberately; the version is part of the result.
ALIASES: Dict[str, str] = {
    "k8s": "kubernetes",
    "amazon web services": "aws",
    "nodejs": "node.js",
    "node js": "node.js",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "postgres": "postgresql",
    "postgre sql": "postgresql",
    "ci/cd": "ci-cd",
    "cicd": "ci-cd",
    "ml": "machine learning",
    "nlp": "natural language processing",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    "ms azure": "azure",
    "microsoft azure": "azure",
}

_SPLIT = re.compile(r"[;,/|•·]+")
_SPACE = re.compile(r"\s+")


def normalize_tag(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = _SPACE.sub(" ", text).strip(" .,:;()[]{}")
    return ALIASES.get(text, text)


def normalize_tags(values: Iterable[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for raw in values or []:
        for part in _SPLIT.split(str(raw or "")):
            tag = normalize_tag(part)
            if tag and tag not in seen:
                seen.add(tag)
                out.append(tag)
    return sorted(out)


def _pct(hit: int, total: int):
    if total <= 0:
        return None
    return round(100.0 * hit / total, 1)


def compare_tags(cv: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    """Compare parsed CV and job bodies deterministically.

    Required tags weight 2, preferred 1. The ATS score is never mixed in here.
    """
    cv_source = cv.get("skills") or cv.get("cvTags") or []
    cv_tags = set(normalize_tags(cv_source))
    required = normalize_tags(job.get("requiredSkills") or [])
    preferred = normalize_tags(job.get("preferredSkills") or [])
    assumed_priority = False
    if not required and not preferred:
        preferred = normalize_tags(job.get("jobTags") or [])
        assumed_priority = True

    required_set = set(required)
    preferred_set = set(preferred) - required_set
    job_tags = required_set | preferred_set

    matched_required = sorted(required_set & cv_tags)
    matched_preferred = sorted(preferred_set & cv_tags)
    matched = sorted(required_set & cv_tags) + sorted(
        tag for tag in (preferred_set & cv_tags) if tag not in required_set)

    missing_in_cv = sorted(job_tags - cv_tags)
    extra_in_cv = sorted(cv_tags - job_tags)
    missing_in_job = list(extra_in_cv)

    required_hits = len(matched_required)
    preferred_hits = len(matched_preferred)
    weighted = 2 * required_hits + preferred_hits
    weight_total = 2 * len(required_set) + len(preferred_set)
    unknown = weight_total == 0

    return {
        "matched": matched,
        "missingInCv": missing_in_cv,
        "missingInJob": missing_in_job,
        "extraInCv": extra_in_cv,
        "coverage": {
            "required": _pct(required_hits, len(required_set)),
            "preferred": _pct(preferred_hits, len(preferred_set)),
            "overall": _pct(weighted, weight_total),
            "requiredTotal": len(required_set),
            "preferredTotal": len(preferred_set),
            "matchedTotal": len(matched),
        },
        "weightedScore": None if unknown else round(100.0 * weighted / weight_total, 1),
        "unknown": unknown,
        "assumedPriority": assumed_priority,
        "aliasMapVersion": ALIAS_MAP_VERSION,
    }
