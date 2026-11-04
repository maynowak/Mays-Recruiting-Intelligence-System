"""Pure ApplicationV1 validation and state-transition contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

SCHEMA_VERSION = 1
STATUSES = frozenset({"DRAFT", "READY", "SUBMITTED", "WITHDRAWN", "ARCHIVED"})
JOBSEARCH_STAGES = frozenset({
    "draft", "submitted", "feedback", "interview", "offer", "rejected", "withdrawn",
})
APPLICATION_CHANNELS = frozenset({"online", "email", "portal", "postal", "other"})
SALARY_PERIODS = frozenset({"year", "month", "hour"})
DOCUMENT_STATUSES = frozenset({"missing", "draft", "ready"})
LETTER_SOURCES = frozenset({"generated", "revised", "manual"})
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


def _optional_text(value: Any, field: str, maximum: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value.strip()):
        raise ApplicationContractError("INVALID_FIELD", f"{field} is invalid")
    return value


def validate_application_date(value: Any) -> str:
    if not isinstance(value, str):
        raise ApplicationContractError("INVALID_APPLICATION_DATE", "applicationDate is invalid")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApplicationContractError("INVALID_APPLICATION_DATE", "applicationDate is invalid") from exc
    return value


def validate_contact(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ApplicationContractError("INVALID_CONTACT", "contact is invalid")
    allowed = {"name", "email", "phone"}
    if set(value) - allowed:
        raise ApplicationContractError("UNKNOWN_FIELD", "unknown contact field")
    result: dict[str, str] = {}
    for field in allowed:
        if field not in value or value[field] is None:
            continue
        text = _optional_text(value[field], f"contact.{field}", 500, allow_empty=True)
        if field == "email" and text.strip() and ("@" not in text or text.startswith("@") or text.endswith("@")):
            raise ApplicationContractError("INVALID_CONTACT", "contact.email is invalid")
        if field == "phone" and any(ord(char) < 32 for char in text):
            raise ApplicationContractError("INVALID_CONTACT", "contact.phone is invalid")
        result[field] = text
    return result


def validate_salary(value: Any, field: str = "salary") -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ApplicationContractError("INVALID_SALARY", f"{field} is invalid")
    if set(value) - {"amount", "currency", "period"}:
        raise ApplicationContractError("UNKNOWN_FIELD", f"unknown {field} field")
    if not isinstance(value.get("amount"), (int, float)) or isinstance(value.get("amount"), bool) or value["amount"] <= 0:
        raise ApplicationContractError("INVALID_SALARY", f"{field}.amount is invalid")
    if not isinstance(value.get("currency"), str) or len(value["currency"]) != 3 or not value["currency"].isupper():
        raise ApplicationContractError("INVALID_SALARY", f"{field}.currency is invalid")
    if value.get("period") not in SALARY_PERIODS:
        raise ApplicationContractError("INVALID_SALARY", f"{field}.period is invalid")
    return {"amount": value["amount"], "currency": value["currency"], "period": value["period"]}


def validate_salary_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"expectation", "offer"}:
        raise ApplicationContractError("INVALID_SALARY", "salary is invalid")
    result: dict[str, Any] = {}
    for name in ("expectation", "offer"):
        if name in value and value[name] is not None:
            result[name] = validate_salary(value[name], f"salary.{name}")
    return result


def validate_follow_up(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"dueOn", "note", "status", "completedAt"}:
        raise ApplicationContractError("INVALID_FOLLOW_UP", "followUp is invalid")
    due_on = value.get("dueOn")
    if not isinstance(due_on, str) or not _is_calendar_date(due_on):
        raise ApplicationContractError("INVALID_FOLLOW_UP", "followUp.dueOn must be YYYY-MM-DD")
    status = value.get("status")
    if status not in {"open", "completed"}:
        raise ApplicationContractError("INVALID_FOLLOW_UP", "followUp.status is invalid")
    note = value.get("note")
    if note is not None:
        _optional_text(note, "followUp.note", 2000, allow_empty=True)
    completed_at = value.get("completedAt")
    if status == "completed":
        if not isinstance(completed_at, str):
            raise ApplicationContractError("INVALID_FOLLOW_UP", "completedAt is required when completed")
        try:
            datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ApplicationContractError("INVALID_FOLLOW_UP", "completedAt is invalid") from exc
    elif completed_at is not None:
        raise ApplicationContractError("INVALID_FOLLOW_UP", "completedAt is only valid when open")
    return {k: value[k] for k in ("dueOn", "note", "status", "completedAt") if k in value and value[k] is not None}


def _is_calendar_date(value: str) -> bool:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_cv_reference(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"cvId", "documentId", "label"}:
        raise ApplicationContractError("INVALID_REFERENCE", "cvReference is invalid")
    if not isinstance(value.get("cvId"), str) or not value["cvId"].strip():
        raise ApplicationContractError("INVALID_REFERENCE", "cvReference.cvId is required")
    result = {"cvId": value["cvId"]}
    for field in ("documentId", "label"):
        if field in value and value[field] is not None:
            result[field] = _optional_text(value[field], f"cvReference.{field}", 500, allow_empty=False)
    return result


def validate_documents(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"coverLetterDraft", "coverLetterVersions", "cvReference", "documentStatus"}:
        raise ApplicationContractError("INVALID_DOCUMENTS", "documents is invalid")
    result: dict[str, Any] = {}
    if "coverLetterDraft" in value:
        result["coverLetterDraft"] = _optional_text(value["coverLetterDraft"], "coverLetterDraft", 100000, allow_empty=True)
    if "coverLetterVersions" in value:
        if not isinstance(value["coverLetterVersions"], list):
            raise ApplicationContractError("INVALID_DOCUMENTS", "coverLetterVersions is invalid")
        result["coverLetterVersions"] = [validate_cover_letter_version(item) for item in value["coverLetterVersions"]]
    if "cvReference" in value and value["cvReference"] is not None:
        result["cvReference"] = validate_cv_reference(value["cvReference"])
    if "documentStatus" in value and value["documentStatus"] not in DOCUMENT_STATUSES:
        raise ApplicationContractError("INVALID_DOCUMENTS", "documentStatus is invalid")
    if "documentStatus" in value:
        result["documentStatus"] = value["documentStatus"]
    return result


def validate_cover_letter_version(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"versionId", "jobId", "createdAt", "content", "source", "language", "model"}:
        raise ApplicationContractError("INVALID_COVER_LETTER", "cover-letter version is invalid")
    if not isinstance(value.get("jobId"), str) or not value["jobId"].strip():
        raise ApplicationContractError("INVALID_COVER_LETTER", "cover-letter jobId is required")
    if not isinstance(value.get("content"), str) or not value["content"].strip() or len(value["content"]) > 100000:
        raise ApplicationContractError("INVALID_COVER_LETTER", "cover-letter content is invalid")
    if value.get("source") not in LETTER_SOURCES:
        raise ApplicationContractError("INVALID_COVER_LETTER", "cover-letter source is invalid")
    if value.get("language") is not None and value["language"] not in {"de", "en"}:
        raise ApplicationContractError("INVALID_COVER_LETTER", "cover-letter language is invalid")
    result = dict(value)
    return result


def validate_history_event(value: Any) -> dict[str, Any]:
    """Validate Jobsearch timeline events while preserving legacy `type` events."""
    if not isinstance(value, Mapping):
        raise ApplicationContractError("INVALID_HISTORY", "history event is invalid")
    event = dict(value)
    kind = event.get("kind")
    if kind is None:
        legacy_type = event.get("type")
        if not isinstance(legacy_type, str) or not legacy_type.strip():
            raise ApplicationContractError("INVALID_HISTORY", "history kind is required")
        return event
    if kind not in {"feedback", "interview", "note"}:
        raise ApplicationContractError("INVALID_HISTORY", "history kind is invalid")
    if not isinstance(event.get("text"), str) and kind in {"feedback", "note"}:
        raise ApplicationContractError("INVALID_HISTORY", "history text is required")
    if kind == "interview":
        scheduled_at = event.get("scheduledAt")
        if not isinstance(scheduled_at, str):
            raise ApplicationContractError("INVALID_HISTORY", "scheduledAt is required")
        try:
            datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ApplicationContractError("INVALID_HISTORY", "scheduledAt is invalid") from exc
        if event.get("note") is not None:
            _optional_text(event["note"], "history.note", 2000, allow_empty=True)
    if "id" in event and (not isinstance(event["id"], str) or not event["id"].strip()):
        raise ApplicationContractError("INVALID_HISTORY", "history id is invalid")
    return event


def validate_create(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise ApplicationContractError("INVALID_JSON", "request body must be an object")
    reject_client_identity(data)
    allowed = {"job", "profileRef", "cvRef", "documents", "applicationDate", "applicationChannel", "contact", "notes", "salary", "followUp", "idempotencyKey"}
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
    if "documents" in data:
        result["documents"] = validate_documents(data["documents"])
    if "applicationDate" in data:
        result["applicationDate"] = validate_application_date(data["applicationDate"])
    if "applicationChannel" in data:
        if data["applicationChannel"] not in APPLICATION_CHANNELS:
            raise ApplicationContractError("INVALID_APPLICATION_CHANNEL", "applicationChannel is invalid")
        result["applicationChannel"] = data["applicationChannel"]
    if "contact" in data:
        result["contact"] = validate_contact(data["contact"])
    if "notes" in data:
        result["notes"] = _optional_text(data["notes"], "notes", 10000, allow_empty=True)
    if "salary" in data:
        result["salary"] = validate_salary_context(data["salary"])
    if "followUp" in data and data["followUp"] is not None:
        result["followUp"] = validate_follow_up(data["followUp"])
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
    if set(data) - {"job", "profileRef", "cvRef", "documents", "applicationDate", "applicationChannel", "contact", "notes", "salary", "followUp", "expectedVersion"}:
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
    nullable = {"documents", "applicationDate", "applicationChannel", "contact", "notes", "salary", "followUp"}
    for name in nullable:
        if name not in data:
            continue
        if data[name] is None:
            result[name] = None
        elif name == "documents":
            result[name] = validate_documents(data[name])
        elif name == "applicationDate":
            result[name] = validate_application_date(data[name])
        elif name == "applicationChannel":
            if data[name] not in APPLICATION_CHANNELS:
                raise ApplicationContractError("INVALID_APPLICATION_CHANNEL", "applicationChannel is invalid")
            result[name] = data[name]
        elif name == "contact":
            result[name] = validate_contact(data[name])
        elif name == "notes":
            result[name] = _optional_text(data[name], "notes", 10000, allow_empty=True)
        elif name == "salary":
            result[name] = validate_salary_context(data[name])
        elif name == "followUp":
            result[name] = validate_follow_up(data[name])
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
