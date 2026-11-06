"""Partner consent contract (V1).

Identity is always server-derived. A caller can only choose a purpose and a
notice version; subject, tenant, partner and issuer come from the verified
partner context.

Only ``application-storage`` is defined in V1. Additional purposes are added
here deliberately, not accepted from clients.
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = 1

#: Purpose -> accepted notice versions. A client-invented version is rejected.
CONSENT_PURPOSES = {
    "application-storage": frozenset({"1.0"}),
}

STATUS_NOT_GRANTED = "NOT_GRANTED"
STATUS_GRANTED = "GRANTED"
STATUS_WITHDRAWN = "WITHDRAWN"
STORED_STATUSES = frozenset({STATUS_GRANTED, STATUS_WITHDRAWN})

EVENT_GRANTED = "GRANTED"
EVENT_WITHDRAWN = "WITHDRAWN"
EVENT_REGRANTED = "REGRANTED"


class ConsentContractError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ConsentContext:
    """Verified partner/user scope. Never built from request bodies."""

    user_id: str
    tenant_id: str
    partner_application_id: str
    issuer: str

    def validate(self) -> "ConsentContext":
        if not all(isinstance(v, str) and v for v in (
                self.user_id, self.tenant_id,
                self.partner_application_id, self.issuer)):
            raise ConsentContractError(
                "INVALID_CONTEXT", "verified consent context is incomplete")
        return self

    @property
    def scope_key(self) -> str:
        return "|".join((self.tenant_id, self.partner_application_id,
                         self.issuer, self.user_id))


def validate_purpose(purpose: object) -> str:
    if not isinstance(purpose, str) or purpose not in CONSENT_PURPOSES:
        raise ConsentContractError("UNKNOWN_PURPOSE", "purpose is not supported")
    return purpose


def validate_notice_version(purpose: str, version: object) -> str:
    accepted = CONSENT_PURPOSES[validate_purpose(purpose)]
    if not isinstance(version, str) or version not in accepted:
        raise ConsentContractError(
            "INVALID_NOTICE_VERSION",
            "noticeVersion is not an accepted version for this purpose")
    return version


def status_payload(purpose: str, *, status: str, notice_version: str | None,
                   granted_at: str | None, withdrawn_at: str | None,
                   version: int = 0) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "purpose": purpose,
        "status": status,
        "noticeVersion": notice_version,
        "grantedAt": granted_at,
        "withdrawnAt": withdrawn_at,
        "version": version,
    }
