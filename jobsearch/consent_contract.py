"""Partner consent contract (V1).

Identity is always server-derived. A caller can only choose a purpose and a
notice version; subject, tenant, partner and issuer come from the verified
partner context.

Only ``application-storage`` is defined in V1. Additional purposes are added
here deliberately, not accepted from clients.

Notice versions have an explicit lifecycle. A version identifier is *not* a
legal approval: a draft may be usable for technical/synthetic end-to-end runs
while still being rejected for real processing.

    DRAFT        text exists, not approved by the responsible body
    APPROVED     approved, not yet offered to new users
    ACTIVE       approved and offered to new users / accepted for new grants
    SUPERSEDED   replaced by a newer version; existing grants stay valid

Existing grants are never silently rewritten when a newer version appears.
Re-consent under a new version is a separate product/legal decision.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

SCHEMA_VERSION = 1

#: Purpose -> notice version identifiers the server understands for grants.
#: A client-invented version is rejected with ``INVALID_NOTICE_VERSION``.
#: Whether an understood version may actually be granted also depends on its
#: lifecycle state (see :data:`NOTICE_REGISTRY` and
#: :func:`notice_state_enforced`).
CONSENT_PURPOSES = {
    "application-storage": frozenset({"1.0"}),
}

# --- notice version lifecycle -------------------------------------------
NOTICE_DRAFT = "DRAFT"
NOTICE_APPROVED = "APPROVED"
NOTICE_ACTIVE = "ACTIVE"
NOTICE_SUPERSEDED = "SUPERSEDED"
NOTICE_STATES = frozenset(
    {NOTICE_DRAFT, NOTICE_APPROVED, NOTICE_ACTIVE, NOTICE_SUPERSEDED})

#: Only approved versions may be granted when state enforcement is on.
GRANTABLE_NOTICE_STATES = frozenset({NOTICE_APPROVED, NOTICE_ACTIVE})

#: States that imply the text has been approved at some point. ``SUPERSEDED``
#: is an approved older version, not a draft.
APPROVED_NOTICE_STATES = frozenset(
    {NOTICE_APPROVED, NOTICE_ACTIVE, NOTICE_SUPERSEDED})


@dataclass(frozen=True)
class NoticeVersion:
    """One declared notice version and its lifecycle state."""

    purpose: str
    version: str
    state: str = NOTICE_DRAFT
    label: str = ""
    #: Reference to the legal-approval record. ``None`` means "not approved".
    legal_approval_ref: str | None = None
    supersedes: str | None = None
    #: External identifiers that describe the same *purpose* but are not
    #: automatically equivalent. Mapping requires a separate decision.
    external_refs: dict[str, str] = field(default_factory=dict)

    @property
    def approved(self) -> bool:
        return self.state in APPROVED_NOTICE_STATES

    @property
    def grantable(self) -> bool:
        return self.state in GRANTABLE_NOTICE_STATES

    def payload(self) -> dict:
        return {
            "purpose": self.purpose,
            "noticeVersion": self.version,
            "noticeState": self.state,
            "noticeApproved": self.approved,
            "grantableWhenEnforced": self.grantable,
            "legalApprovalRef": self.legal_approval_ref,
            "supersedes": self.supersedes,
            "externalRefs": dict(self.external_refs),
        }


#: Server-owned catalog. The identifiers below are technical; legal approval
#: is tracked separately and is ``None`` until a real approval record exists.
NOTICE_REGISTRY: dict[str, dict[str, NoticeVersion]] = {
    "application-storage": {
        "1.0": NoticeVersion(
            purpose="application-storage",
            version="1.0",
            state=NOTICE_DRAFT,
            label="RIS application-storage notice v1 (technical draft)",
            legal_approval_ref=None,
        ),
    },
}

#: Partner-side identifiers that are *known* but deliberately not equivalent
#: to a RIS notice version yet. ``2026-11-04-draft-1`` and the
#: ``application-storage-consent-*`` text candidates are Jobsearch drafts;
#: renaming or hashing them must never turn them into an approved RIS version.
EXTERNAL_NOTICE_REFS: dict[str, dict[str, dict[str, object]]] = {
    "application-storage": {
        "2026-11-04-draft-1": {
            "source": "mays-jobsearch",
            "noticeState": NOTICE_DRAFT,
            "noticeVersion": None,  # no equivalence until separately approved
        },
        # Historical ApplicationV1 text candidate (Jobsearch v1). It was never
        # approved and was replaced by v2; it deliberately stays DRAFT (not
        # SUPERSEDED, which would imply a prior approval) and is recorded as
        # superseded for traceability only.
        "application-storage-consent-2026-11-07-v1": {
            "source": "mays-jobsearch",
            "noticeState": NOTICE_DRAFT,
            "noticeVersion": None,  # no equivalence until separately approved
            "textSha256": (
                "2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953"
            ),
            "supersededBy": "application-storage-consent-2026-11-07-v2",
        },
        # Current ApplicationV1 consent text candidate (Jobsearch v2, commit
        # 47f73c4). The hash pins the exact text; the mapping to RIS 1.0 is
        # NOT approved and stays DRAFT.
        "application-storage-consent-2026-11-07-v2": {
            "source": "mays-jobsearch",
            "noticeState": NOTICE_DRAFT,
            "noticeVersion": None,  # no equivalence until separately approved
            "textSha256": (
                "232cc8206261b5d14f7a269f63a58320f76eea435a65f7e039b25c62d26da0ca"
            ),
        },
    },
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


def notice_state_enforced() -> bool:
    """Whether only approved/active notice versions may be granted.

    Default is ``false`` so the technical consent flow (and synthetic
    end-to-end runs) keeps working while the notice text is still a draft.
    Real processing must run with ``CONSENT_NOTICE_STATE_ENFORCED=true`` so a
    draft can never be recorded as an approved consent.
    """
    return os.environ.get(
        "CONSENT_NOTICE_STATE_ENFORCED", "false").strip().lower() == "true"


def notice_version(purpose: str, version: object) -> NoticeVersion | None:
    return NOTICE_REGISTRY.get(purpose, {}).get(version) \
        if isinstance(version, str) else None


def validate_notice_version(purpose: str, version: object, *,
                            require_active: bool | None = None) -> str:
    purpose = validate_purpose(purpose)
    accepted = CONSENT_PURPOSES[purpose]
    if not isinstance(version, str) or version not in accepted:
        raise ConsentContractError(
            "INVALID_NOTICE_VERSION",
            "noticeVersion is not an accepted version for this purpose")
    enforce = notice_state_enforced() if require_active is None else require_active
    if enforce:
        entry = notice_version(purpose, version)
        if entry is None or entry.state not in GRANTABLE_NOTICE_STATES:
            raise ConsentContractError(
                "NOTICE_NOT_ACTIVE",
                "noticeVersion is not approved for new consents")
    return version


def _entry_payload(purpose: str, version: str | None) -> dict:
    entry = notice_version(purpose, version)
    if entry is None:
        return {
            "noticeState": None,
            "noticeApproved": False,
            "acceptedForNewGrant": False,
        }
    return {
        "noticeState": entry.state,
        "noticeApproved": entry.approved,
        # A draft is technically accepted while state enforcement is off
        # (synthetic/technical runs); with enforcement on only approved
        # versions are accepted.
        "acceptedForNewGrant": entry.grantable or not notice_state_enforced(),
    }


def catalog_payload(purpose: str) -> list[dict]:
    """Declared notice versions for a purpose, with lifecycle state."""
    purpose = validate_purpose(purpose)
    out: list[dict] = []
    for entry in NOTICE_REGISTRY.get(purpose, {}).values():
        item = entry.payload()
        item["acceptedForNewGrant"] = (
            entry.grantable or not notice_state_enforced())
        out.append(item)
    return out


def external_refs_payload(purpose: str) -> list[dict]:
    purpose = validate_purpose(purpose)
    return [
        {"externalRef": ref, **meta}
        for ref, meta in EXTERNAL_NOTICE_REFS.get(purpose, {}).items()
    ]


def status_payload(purpose: str, *, status: str, notice_version: str | None,
                   granted_at: str | None, withdrawn_at: str | None,
                   version: int = 0) -> dict:
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "purpose": purpose,
        "status": status,
        "noticeVersion": notice_version,
        "grantedAt": granted_at,
        "withdrawnAt": withdrawn_at,
        "version": version,
    }
    payload.update(_entry_payload(purpose, notice_version))
    return payload
