"""Thin analysis orchestration over the existing Agent Body building blocks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol

from agents.analysis.contracts import (
    ContractError,
    Identity,
    build_ats_result,
    build_comparison_result,
    build_cv_result,
    build_job_result,
    build_response,
    require_capabilities,
    validate_request,
)
from agents.analysis.cv_bridge import CvInput, CvResolver, RequestCvResolver
from agents.analysis.job_store import JobStoreError
from agents.analysis.partner import assert_internal_partner
from agents.analysis.tags import compare_tags


class ParserPort(Protocol):
    def parse_cv(self, pdf_base64: str) -> Dict[str, Any]: ...
    def parse_job(self, job: Dict[str, Any]) -> Dict[str, Any]: ...
    def parse_ats(self, job: Dict[str, Any],
                  profile: Dict[str, Any]) -> Dict[str, Any]: ...


class NodeParser:
    """Adapter to the shared Node CLI (single JS execution boundary)."""

    def __init__(self, runner: Optional[Callable] = None):
        self._runner = runner

    def _call(self, capability: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from agents.parsers.node_adapter import parse_via_node

        result = parse_via_node(capability, payload, runner=self._runner)
        return result.data

    def parse_cv(self, pdf_base64: str) -> Dict[str, Any]:
        return self._call("parse.cv", {"pdfBase64": pdf_base64})

    def parse_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        return self._call("parse.job", {"job": job})

    def parse_ats(self, job: Dict[str, Any],
                  profile: Dict[str, Any]) -> Dict[str, Any]:
        return self._call("parse.ats", {"job": job, "profile": profile})


def job_from_text(text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = (lines[0] if lines else "Stellenanzeige")[:300]
    return {"title": title, "descriptionPlain": text}


@dataclass
class AnalysisOrchestrator:
    parser: ParserPort = field(default_factory=NodeParser)
    cv_resolver: CvResolver = field(default_factory=RequestCvResolver)
    job_store: Any = None
    idempotency: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cleanup_job: bool = False

    def run(self, payload: Dict[str, Any], identity: Identity,
            request_id: Optional[str] = None) -> Dict[str, Any]:
        request = validate_request(payload)
        assert_internal_partner(payload, identity)
        require_capabilities(request["requestedResults"], identity)

        key = None
        if request.get("idempotencyKey"):
            key = (f"{identity.tenant_id}\u0000{identity.user_id}\u0000"
                   f"{request['idempotencyKey']}")
            cached = self.idempotency.get(key)
            if cached is not None:
                response = dict(cached)
                response["idempotent"] = True
                return response

        requested = request["requestedResults"]
        inputs = request["input"]
        cv_input: Optional[CvInput] = None
        cv_data: Optional[Dict[str, Any]] = None
        job: Optional[Dict[str, Any]] = None
        job_data: Optional[Dict[str, Any]] = None
        ats_data: Optional[Dict[str, Any]] = None
        job_ref: Optional[str] = None

        needs_cv = any(item in requested for item in ("cv.tags", "comparison")) \
            or ("ats.tags" in requested and inputs.get("cv"))
        needs_job_input = any(item in requested for item in
                              ("job.tags", "ats.tags", "comparison"))
        needs_job_parse = any(item in requested for item in
                              ("job.tags", "comparison"))

        if needs_cv:
            cv_input = self.cv_resolver.resolve(inputs["cv"], identity)
            if cv_input.is_structured:
                cv_data = self._structured_cv(cv_input)
            else:
                cv_data = self.parser.parse_cv(cv_input.pdf_base64 or "")

        if needs_job_input:
            job_spec = inputs["job"]
            if job_spec.get("jobRef"):
                if self.job_store is None:
                    raise ContractError("job_ref_unavailable",
                                        "temporary job storage is not configured")
                job_ref = str(job_spec["jobRef"])
                try:
                    record = self.job_store.get(
                        job_ref, identity.tenant_id, identity.user_id)
                except JobStoreError as exc:
                    raise ContractError(getattr(exc, "code", "job_ref_error"),
                                        str(exc)) from exc
                text = record.text
            else:
                text = str(job_spec.get("text") or "")
            job = job_from_text(text)
            if needs_job_parse:
                job_data = self.parser.parse_job(job)

        if "ats.tags" in requested:
            if job is None:
                job = job_from_text(str(inputs["job"].get("text") or ""))
            profile = inputs.get("profile")
            if not isinstance(profile, dict):
                skills = (cv_data or {}).get("skills") or []
                profile = {"skills": ", ".join(str(item) for item in skills)}
            ats_data = self.parser.parse_ats(job, profile)

        results: Dict[str, Any] = {}
        cv_body = build_cv_result(cv_data) if cv_data is not None else None
        job_body = build_job_result(job_data) if job_data is not None else None
        ats_body = build_ats_result(ats_data) if ats_data is not None else None

        if "cv.tags" in requested and cv_body is not None:
            results["cv.tags"] = cv_body
        if "job.tags" in requested and job_body is not None:
            results["job.tags"] = job_body
        if "ats.tags" in requested and ats_body is not None:
            results["ats.tags"] = ats_body
        if "comparison" in requested:
            if cv_body is None or job_body is None:
                raise ContractError("missing_comparison_inputs",
                                    "comparison needs CV and job results")
            comparison = compare_tags(cv_body, job_body)
            results["comparison"] = build_comparison_result(
                cv_body, job_body, comparison, ats_body)

        response = build_response(request_id or str(uuid.uuid4()), results)
        response["requestedResults"] = list(requested)
        response["idempotent"] = False
        if key is not None:
            self.idempotency[key] = dict(response)

        if self.cleanup_job and job_ref and self.job_store is not None:
            try:
                self.job_store.delete(job_ref, identity.tenant_id,
                                      identity.user_id)
            except Exception:  # noqa: BLE001 - cleanup is best effort
                pass
        return response

    @staticmethod
    def _structured_cv(cv_input: CvInput) -> Dict[str, Any]:
        data = cv_input.structured or {}
        skills = [str(item) for item in data.get("skills") or []]
        languages = data.get("languages") or []
        education = data.get("education") or []
        degrees = [item.get("degree") if isinstance(item, dict) else item
                   for item in education]
        tags = [item for item in
                [*skills, *languages, *[d for d in degrees if d]] if item]
        return {
            "stableId": cv_input.sha256,
            "cvTags": tags,
            "skills": skills,
            "experience": data.get("experience") or [],
            "education": education,
            "languages": languages,
            "location": data.get("location") or "",
            "confidence": data.get("confidence") or "confirmed",
            "parserVersion": "structured-1.0",
            "provenance": {"source": "ris-structured", "parserVersion": "structured-1.0"},
        }
