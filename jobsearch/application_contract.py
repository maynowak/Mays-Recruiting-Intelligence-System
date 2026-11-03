"""Pure ApplicationV1 validation and state-transition contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

SCHEMA_VERSION = 1
STATUSES = frozenset({"DRAFT", "READY", "SUBMITTED", "WITHDRAWN", "ARCHIVED"})
JOBSEARCH_STAGES = frozenset({
    "draft", "submitted", "feedback", "interview", "offer", "rejected", "withdrawn",
})
TRANSITIONS = {
    "DRAFT": frozenset({"DRAFT", "READY", "ARCHIVED"}),
    "READY": frozenset({"READY", "DRAFT", "SUBMITTED", "ARCHIVED"}),
    "SUBMITTED": frozenset({"SUBMITTED", "WITHDRAWN", "ARCHIVED"}),
    "WITHDRAWN": frozenset({"WITHDRAWN", "ARCHIVED"}),
    "ARCHIVED": frozenset({"ARCHIVED"}),
}
STAGE_TRANSITIONS = {
    "draft": frozenset({"draft", "submitted"}),
    "submitted": frozenset({"submitted", "feedback", "interview", "rejected", "withdrawn"}),
    "feedback": frozenset({"feedback", "interview", "offer", "rejected", "withdrawn"}),
    "interview": frozenset({"interview", "offer", "rejected", "withdrawn"}),
    "offer": frozenset({"offer", "withdrawn"}),
    "rejected": frozenset({"rejected"}),
    "withdrawn": frozenset({"withdrawn"}),
}


def legacy_status_stage(status: str) -> str | None:
    """Project a legacy status without rewriting the stored legacy value."""
    return {
        "DRAFT": "draft",
        "SUBMITTED": "submitted",
        "WITHDRAWN": "withdrawn",
    }.get(status)
IDENTITY_FIELDS = frozenset({"applicationId", "ownerId", "userId", "tenantId", "partnerApplicationId", "issuer"})


class ApplicationContractError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def reject_client_identity(data: Mapping[str, Any]) -> None:
    found = sorted(IDENTITY_FIELDS.intersection(data))
    if found:
        raise ApplicationContractError("IDENTITY_FIELD_FORBIDDEN", "identity fields are server-owned")


def validate_job(job: Any) -> dict[str, str]:
    if not isinstance(job, Mapping):
        raise ApplicationContractError("INVALID_JOB", "job is required")
    allowed = {"jobId", "source", "title", "company", "location", "url"}
    unknown = set(job) - allowed
    if unknown:
        raise ApplicationContractError("UNKNOWN_FIELD", "unknown job fields")
    if not isinstance(job.get("jobId"), str) or not job["jobId"].strip():
        raise ApplicationContractError("INVALID_JOB", "job.jobId is required")
    return {k: str(v) for k, v in job.items() if v is not None}


def validate_create(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ApplicationContractError("INVALID_JSON", "request body must be an object")
    reject_client_identity(data)
    allowed = {"job", "profileRef", "cvRef", "idempotencyKey"}
    unknown = set(data) - allowed
    if unknown:
        raise ApplicationContractError("UNKNOWN_FIELD", "unknown application fields")
    result = {"job": validate_job(data.get("job"))}
    for name in ("profileRef", "cvRef"):
        if name in data:
            value = data[name]
            if not isinstance(value, Mapping) or not isinstance(value.get("id"), str):
                raise ApplicationContractError("INVALID_REFERENCE", f"{name} is invalid")
            result[name] = {"id": value["id"], "version": int(value.get("version", 0))}
    if "idempotencyKey" in data:
        key = data["idempotencyKey"]
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise ApplicationContractError("INVALID_IDEMPOTENCY_KEY", "idempotencyKey is invalid")
        result["idempotencyKey"] = key
    return result


def validate_patch(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ApplicationContractError("INVALID_JSON", "request body must be an object")
    reject_client_identity(data)
    if set(data) - {"job", "profileRef", "cvRef", "expectedVersion"}:
        raise ApplicationContractError("UNKNOWN_FIELD", "unknown application fields")
    if not isinstance(data.get("expectedVersion"), int) or data["expectedVersion"] < 1:
        raise ApplicationContractError("EXPECTED_VERSION_REQUIRED", "expectedVersion is required")
    result = {"expectedVersion": data["expectedVersion"]}
    if "job" in data:
        result["job"] = validate_job(data["job"])
    for name in ("profileRef", "cvRef"):
        if name in data:
            value = data[name]
            if not isinstance(value, Mapping) or not isinstance(value.get("id"), str):
                raise ApplicationContractError("INVALID_REFERENCE", f"{name} is invalid")
            result[name] = {"id": value["id"], "version": int(value.get("version", 0))}
    return result


def validate_transition(current: str, target: Any, confirm: bool = False) -> None:
    if target not in STATUSES or target not in TRANSITIONS.get(current, ()):
        raise ApplicationContractError("INVALID_STATUS_TRANSITION", "status transition is not allowed")
    if target == "SUBMITTED" and not confirm:
        raise ApplicationContractError("SUBMIT_CONFIRMATION_REQUIRED", "submit requires explicit confirmation")


def validate_stage_transition(current: str, target: Any, confirm: bool = False) -> None:
    """Validate the additive Jobsearch stage without changing legacy status."""
    if current not in JOBSEARCH_STAGES or target not in JOBSEARCH_STAGES:
        raise ApplicationContractError("INVALID_STAGE", "jobsearch stage is invalid")
    if target not in STAGE_TRANSITIONS[current]:
        raise ApplicationContractError("INVALID_STAGE_TRANSITION", "stage transition is not allowed")
    if target == "submitted" and not confirm:
        raise ApplicationContractError("SUBMIT_CONFIRMATION_REQUIRED", "submit requires explicit confirmation")


def validate_status_filter(value: Any) -> str:
    if value not in STATUSES:
        raise ApplicationContractError("INVALID_STATUS_FILTER", "status filter is invalid")
    return value


def validate_stage_filter(value: Any) -> str:
    if value not in JOBSEARCH_STAGES:
        raise ApplicationContractError("INVALID_STAGE_FILTER", "stage filter is invalid")
    return value


@dataclass(frozen=True)
class ApplicationContext:
    user_id: str
    tenant_id: str
    partner_application_id: str
    issuer: str

    def validate(self) -> "ApplicationContext":
        if not all(isinstance(v, str) and v for v in (self.user_id, self.tenant_id, self.partner_application_id, self.issuer)):
            raise ApplicationContractError("INVALID_CONTEXT", "verified application context is incomplete")
        return self
