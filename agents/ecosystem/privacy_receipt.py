"""R08-G0: canonical privacy receipt and capability contract.

Pure contract module. It defines the versioned receipt schema, identity
binding, event/evidence rules and a strict validator. It deliberately does
**not** persist receipts, expose an API or perform erasure. Storage, emission
and the user-facing "My privacy" view are later R08 gates.

Design rules:
- Receipts are minimal metadata, never CV text, prompts, tokens, presigned
  URLs or secrets.
- A receipt records what RIS can evidence. A client-reported or requested
  event is labelled as such; it is never promoted to a verified fact.
- Legal basis and retention references are references, not legal decisions.
  ``REVIEW_REQUIRED`` is an accepted explicit placeholder.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

RECEIPT_SCHEMA_VERSION = 1
MAX_RECEIPT_BYTES = 8192
MAX_CLOCK_SKEW_SECONDS = 300

RECEIPT_EVENT_TYPES = frozenset({
    "PRIVACY_NOTICE_PRESENTED",
    "PRIVACY_NOTICE_ACKNOWLEDGED",
    "CONSENT_GRANTED",
    "CONSENT_WITHDRAWN",
    "CV_STORAGE_CONFIRMED",
    "USER_PROFILE_UPDATED",
    "PROFILE_CREATED",
    "PROFILE_UPDATED",
    "PROFILE_DELETED",
    "AI_TRANSFER_REQUESTED",
    "AI_TRANSFER_CONFIRMED",
    "DATA_EXPORT_COMPLETED",
    "ERASURE_REQUESTED",
    "ERASURE_PARTIALLY_COMPLETED",
    "ERASURE_COMPLETED",
})

PROCESSING_DOMAINS = frozenset({
    "ris",
    "jobsearch",
    "mays_orders",
    "ai_provider",
    "browser",
    "aws_platform",
})

DATA_CATEGORIES = frozenset({
    "identity",
    "cv_metadata",
    "cv_document",
    "manual_search_profile",
    "cv_search_profile",
    "ats_search_profile",
    "partner_credential",
    "entitlement",
    "work_item",
    "audit_log",
    "cursor",
    "idempotency",
    "capacity_counter",
    "lifecycle_guard",
    "browser_session",
    "jobsearch_cache",
    "ai_provider",
})

PURPOSES = frozenset({
    "authentication",
    "cv_processing",
    "profile_management",
    "job_matching",
    "ai_processing",
    "privacy_request",
    "audit",
    "service_operation",
})

EVIDENCE_LEVELS = frozenset({
    "server_verified",
    "third_party_confirmed",
    "client_reported",
    "requested",
    "not_provable",
})

RECEIPT_STATUSES = frozenset({
    "requested",
    "completed",
    "partially_completed",
    "blocked",
    "failed",
})

PRIVACY_CAPABILITY_OPERATIONS = (
    "inspect", "export", "erase", "receipts", "request_status",
)

_NOTICE_EVENTS = frozenset({
    "PRIVACY_NOTICE_PRESENTED", "PRIVACY_NOTICE_ACKNOWLEDGED",
    "CONSENT_GRANTED", "CONSENT_WITHDRAWN",
})
_EVENT_STATUS = {
    "PRIVACY_NOTICE_PRESENTED": "completed",
    "PRIVACY_NOTICE_ACKNOWLEDGED": "completed",
    "CONSENT_GRANTED": "completed",
    "CONSENT_WITHDRAWN": "completed",
    "CV_STORAGE_CONFIRMED": "completed",
    "USER_PROFILE_UPDATED": "completed",
    "PROFILE_CREATED": "completed",
    "PROFILE_UPDATED": "completed",
    "PROFILE_DELETED": "completed",
    "AI_TRANSFER_REQUESTED": "requested",
    "AI_TRANSFER_CONFIRMED": "completed",
    "DATA_EXPORT_COMPLETED": "completed",
    "ERASURE_REQUESTED": "requested",
    "ERASURE_PARTIALLY_COMPLETED": "partially_completed",
    "ERASURE_COMPLETED": "completed",
}
_EVENT_EVIDENCE = {
    "AI_TRANSFER_REQUESTED": frozenset({
        "client_reported", "requested", "server_verified",
    }),
    "AI_TRANSFER_CONFIRMED": frozenset({
        "third_party_confirmed", "server_verified",
    }),
    "ERASURE_COMPLETED": frozenset({
        "server_verified", "third_party_confirmed",
    }),
    "ERASURE_PARTIALLY_COMPLETED": frozenset({
        "server_verified", "third_party_confirmed",
    }),
}

_FORBIDDEN_KEYS = frozenset({
    "cvtext", "cvcontent", "rawcv", "filecontent", "cvdata",
    "prompt", "prompts", "modelresponse", "modelexplanation",
    "authorization", "authorizationheader", "bearer", "accesstoken",
    "idtoken", "refreshtoken", "token", "secret", "password",
    "presignedurl", "signedurl", "xamzsignature", "rawevidence",
    "cv", "documentbody",
})
_FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"X-Amz-Signature=", re.IGNORECASE),
    re.compile(r"^Bearer\s+", re.IGNORECASE),
    re.compile(r"^eyJ[A-Za-z0-9_-]{16,}\."),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_SUBJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_ISSUER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/?#\-]{0,255}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PrivacyReceiptError(ValueError):
    """Invalid receipt. Message is safe to show to an operator."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PrivacyContextV1:
    """Verified server-side identity context for one privacy operation."""

    user_id: str
    tenant_id: str
    partner_application_id: str
    issuer: str

    def __post_init__(self):
        for name in ("user_id", "tenant_id", "partner_application_id",
                     "issuer"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise PrivacyReceiptError(
                    "MISSING_IDENTITY", f"{name} is required")
        if "@" in self.user_id:
            raise PrivacyReceiptError(
                "INVALID_IDENTITY", "user_id must be an opaque subject ref")


@dataclass(frozen=True)
class PrivacyReceiptV1:
    receipt_id: str
    subject_ref: str
    tenant_ref: str
    partner_application_ref: str
    issuer_ref: str
    event_type: str
    purpose: str
    legal_basis_ref: str
    privacy_notice_version: Optional[str]
    privacy_notice_digest: Optional[str]
    data_categories: Tuple[str, ...]
    processing_domain: str
    operation_ref: str
    recorded_at: str
    status: str
    retention_policy_ref: str
    evidence_level: str
    schema_version: int = RECEIPT_SCHEMA_VERSION

    def validate(self, *, now: Optional[datetime] = None
                 ) -> "PrivacyReceiptV1":
        if isinstance(self.schema_version, bool) or self.schema_version != 1:
            raise PrivacyReceiptError(
                "INVALID_SCHEMA_VERSION", "schemaVersion must be integer 1")
        _require_id(self.receipt_id, "receiptId")
        _require_subject(self.subject_ref, "subjectRef")
        _require_subject(self.tenant_ref, "tenantRef")
        _require_subject(self.partner_application_ref, "partnerApplicationRef")
        _require_issuer(self.issuer_ref, "issuerRef")
        if self.event_type not in RECEIPT_EVENT_TYPES:
            raise PrivacyReceiptError(
                "UNKNOWN_EVENT", "unknown eventType")
        if self.purpose not in PURPOSES:
            raise PrivacyReceiptError("UNKNOWN_PURPOSE", "unknown purpose")
        if self.processing_domain not in PROCESSING_DOMAINS:
            raise PrivacyReceiptError(
                "UNKNOWN_DOMAIN", "unknown processingDomain")
        if self.status not in RECEIPT_STATUSES:
            raise PrivacyReceiptError("UNKNOWN_STATUS", "unknown status")
        if self.evidence_level not in EVIDENCE_LEVELS:
            raise PrivacyReceiptError(
                "UNKNOWN_EVIDENCE", "unknown evidenceLevel")
        expected_status = _EVENT_STATUS[self.event_type]
        if self.status != expected_status:
            raise PrivacyReceiptError(
                "INVALID_EVENT_STATUS",
                f"{self.event_type} requires status {expected_status}")
        allowed_evidence = _EVENT_EVIDENCE.get(self.event_type)
        if allowed_evidence is not None and self.evidence_level not in allowed_evidence:
            raise PrivacyReceiptError(
                "INVALID_EVIDENCE",
                f"{self.event_type} does not allow evidenceLevel "
                f"{self.evidence_level}")
        _require_ref(self.legal_basis_ref, "legalBasisRef")
        _require_ref(self.retention_policy_ref, "retentionPolicyRef")
        _require_id(self.operation_ref, "operationRef")

        categories = self.data_categories
        if not isinstance(categories, (tuple, list)) or not categories:
            raise PrivacyReceiptError(
                "MISSING_DATA_CATEGORIES", "dataCategories is required")
        if len(categories) > 16:
            raise PrivacyReceiptError(
                "TOO_MANY_DATA_CATEGORIES", "too many dataCategories")
        if len(set(categories)) != len(categories):
            raise PrivacyReceiptError(
                "DUPLICATE_DATA_CATEGORY", "dataCategories must be unique")
        for category in categories:
            if category not in DATA_CATEGORIES:
                raise PrivacyReceiptError(
                    "UNKNOWN_DATA_CATEGORY", "unknown dataCategory")

        if self.event_type in _NOTICE_EVENTS:
            if not _valid_optional_str(self.privacy_notice_version, 1, 64):
                raise PrivacyReceiptError(
                    "MISSING_NOTICE_VERSION",
                    "privacyNoticeVersion is required for this event")
            if not isinstance(self.privacy_notice_digest, str) or \
                    not _SHA256_RE.match(self.privacy_notice_digest):
                raise PrivacyReceiptError(
                    "INVALID_NOTICE_DIGEST",
                    "privacyNoticeDigest must be a lowercase sha256")
        elif self.privacy_notice_version is not None or \
                self.privacy_notice_digest is not None:
            if not _valid_optional_str(self.privacy_notice_version, 1, 64):
                raise PrivacyReceiptError(
                    "INVALID_NOTICE_VERSION", "invalid privacyNoticeVersion")
            if not isinstance(self.privacy_notice_digest, str) or \
                    not _SHA256_RE.match(self.privacy_notice_digest):
                raise PrivacyReceiptError(
                    "INVALID_NOTICE_DIGEST",
                    "privacyNoticeDigest must be a lowercase sha256")

        recorded_at = _parse_timestamp(self.recorded_at)
        if now is not None:
            reference = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            delta = (recorded_at - reference).total_seconds()
            if delta > MAX_CLOCK_SKEW_SECONDS:
                raise PrivacyReceiptError(
                    "FUTURE_TIMESTAMP", "recordedAt is in the future")

        _assert_no_forbidden(self.to_dict())
        if len(self.canonical_json().encode("utf-8")) > MAX_RECEIPT_BYTES:
            raise PrivacyReceiptError("RECEIPT_TOO_LARGE", "receipt too large")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "receiptId": self.receipt_id,
            "subjectRef": self.subject_ref,
            "tenantRef": self.tenant_ref,
            "partnerApplicationRef": self.partner_application_ref,
            "issuerRef": self.issuer_ref,
            "eventType": self.event_type,
            "purpose": self.purpose,
            "legalBasisRef": self.legal_basis_ref,
            "privacyNoticeVersion": self.privacy_notice_version,
            "privacyNoticeDigest": self.privacy_notice_digest,
            "dataCategories": list(self.data_categories),
            "processingDomain": self.processing_domain,
            "operationRef": self.operation_ref,
            "recordedAt": self.recorded_at,
            "status": self.status,
            "retentionPolicyRef": self.retention_policy_ref,
            "evidenceLevel": self.evidence_level,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *,
                  now: Optional[datetime] = None) -> "PrivacyReceiptV1":
        if not isinstance(data, dict):
            raise PrivacyReceiptError("INVALID_RECEIPT", "receipt must be an object")
        allowed = {
            "schemaVersion", "receiptId", "subjectRef", "tenantRef",
            "partnerApplicationRef", "issuerRef", "eventType", "purpose",
            "legalBasisRef", "privacyNoticeVersion", "privacyNoticeDigest",
            "dataCategories", "processingDomain", "operationRef",
            "recordedAt", "status", "retentionPolicyRef", "evidenceLevel",
        }
        unknown = set(data) - allowed
        if unknown:
            raise PrivacyReceiptError(
                "UNKNOWN_FIELD", f"unknown receipt fields: {sorted(unknown)}")
        receipt = cls(
            schema_version=data.get("schemaVersion"),
            receipt_id=data.get("receiptId"),
            subject_ref=data.get("subjectRef"),
            tenant_ref=data.get("tenantRef"),
            partner_application_ref=data.get("partnerApplicationRef"),
            issuer_ref=data.get("issuerRef"),
            event_type=data.get("eventType"),
            purpose=data.get("purpose"),
            legal_basis_ref=data.get("legalBasisRef"),
            privacy_notice_version=data.get("privacyNoticeVersion"),
            privacy_notice_digest=data.get("privacyNoticeDigest"),
            data_categories=tuple(data.get("dataCategories") or ()),
            processing_domain=data.get("processingDomain"),
            operation_ref=data.get("operationRef"),
            recorded_at=data.get("recordedAt"),
            status=data.get("status"),
            retention_policy_ref=data.get("retentionPolicyRef"),
            evidence_level=data.get("evidenceLevel"),
        )
        return receipt.validate(now=now)


def receipt_matches_context(receipt: PrivacyReceiptV1,
                            context: PrivacyContextV1) -> bool:
    return (receipt.subject_ref == context.user_id
            and receipt.tenant_ref == context.tenant_id
            and receipt.partner_application_ref
            == context.partner_application_id
            and receipt.issuer_ref == context.issuer)


def privacy_notice_digest(text: str) -> str:
    """Digest of the exact notice text the user was shown."""
    if not isinstance(text, str) or not text:
        raise PrivacyReceiptError("INVALID_NOTICE", "notice text is required")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _valid_optional_str(value: Any, minimum: int, maximum: int) -> bool:
    return (isinstance(value, str) and minimum <= len(value) <= maximum
            and value.strip() == value)


def _require_id(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise PrivacyReceiptError(
            "INVALID_ID", f"{field} has an invalid format")


def _require_subject(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _SUBJECT_RE.match(value) or "@" in value:
        raise PrivacyReceiptError(
            "INVALID_IDENTITY", f"{field} must be an opaque reference")


def _require_issuer(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _ISSUER_RE.match(value):
        raise PrivacyReceiptError(
            "INVALID_IDENTITY", f"{field} has an invalid format")


def _require_ref(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _REF_RE.match(value):
        raise PrivacyReceiptError(
            "INVALID_REFERENCE", f"{field} has an invalid format")


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise PrivacyReceiptError("INVALID_TIMESTAMP", "recordedAt is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PrivacyReceiptError(
            "INVALID_TIMESTAMP", "recordedAt must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise PrivacyReceiptError(
            "INVALID_TIMESTAMP", "recordedAt must include a timezone")
    return parsed


def _assert_no_forbidden(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in _FORBIDDEN_KEYS:
                raise PrivacyReceiptError(
                    "FORBIDDEN_CONTENT",
                    f"receipt contains forbidden field {key!r}")
            _assert_no_forbidden(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_forbidden(item, path)
    elif isinstance(value, str):
        for pattern in _FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                raise PrivacyReceiptError(
                    "FORBIDDEN_CONTENT",
                    "receipt contains a forbidden value")
