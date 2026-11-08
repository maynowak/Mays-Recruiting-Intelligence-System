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
import re
from dataclasses import dataclass, field

SCHEMA_VERSION = 1

#: Purpose -> notice version identifiers the server understands for grants.
#: A client-invented version is rejected with ``INVALID_NOTICE_VERSION``.
#: Whether an understood version may actually be granted also depends on its
#: lifecycle state (see :data:`NOTICE_REGISTRY` and
#: :func:`notice_state_enforced`).
CONSENT_PURPOSES = {
    "application-storage": frozenset({"1.0"}),
    # Separate purpose: durable CV-PDF storage is not covered by the
    # ApplicationV1 consent. The notice is a technical candidate until the
    # operator/legal approval is recorded.
    "cv-storage": frozenset({"1.0"}),
    # Separate durable search-profile purpose: manual, CV-search and ATS
    # profiles. Technical candidate only until the operator approves the text.
    "search-profile-storage": frozenset({"1.0"}),
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


#: Server-owned catalog. The identifiers below are technical; the legal
#: approval is recorded per version in ``legal_approval_ref``.
NOTICE_REGISTRY: dict[str, dict[str, NoticeVersion]] = {
    "application-storage": {
        "1.0": NoticeVersion(
            purpose="application-storage",
            version="1.0",
            state=NOTICE_APPROVED,
            label="RIS application-storage notice v1 (operator-approved limited beta pilot)",
            legal_approval_ref="JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08",
        ),
    },
    "cv-storage": {
        "1.0": NoticeVersion(
            purpose="cv-storage",
            version="1.0",
            state=NOTICE_APPROVED,
            label="RIS cv-storage notice v1 (operator-approved limited beta pilot)",
            legal_approval_ref="JM-CV-STORAGE-V1-BETA-2026-11-08",
        ),
    },
    "search-profile-storage": {
        "1.0": NoticeVersion(
            purpose="search-profile-storage",
            version="1.0",
            state=NOTICE_DRAFT,
            label="RIS search-profile-storage notice v1 (technical candidate, no legal approval)",
            legal_approval_ref=None,
        ),
    },
}

#: Partner-side identifiers that are *known* to RIS. Historical refs stay
#: DRAFT/superseded and are never equivalent to a RIS notice version. The
#: approved v4 text is the only mapped and only Art. 9-capable text.
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
        # Current ApplicationV1 consent text (Jobsearch v4, commit 5ac025f,
        # explicit Art. 9 special-category consent incl. sex life and no
        # inference). Operator-approved for the limited beta pilot on
        # 2026-11-08; mapped to RIS notice 1.0. This is not a general rollout.
        "application-storage-consent-2026-11-07-v4": {
            "source": "mays-jobsearch",
            "noticeState": NOTICE_APPROVED,
            "noticeVersion": "1.0",
            "textSha256": (
                "8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7"
            ),
        },
        # Historical v3 (Jobsearch 9eecf83), replaced by v4. Only v4 is
        # Art. 9-capable.
        "application-storage-consent-2026-11-07-v3": {
            "source": "mays-jobsearch",
            "noticeState": NOTICE_DRAFT,
            "noticeVersion": None,  # no equivalence until separately approved
            "textSha256": (
                "696f9e66d8098b2dce56a93418ba598145b669934662e2b52d9a332731517668"
            ),
            "supersededBy": "application-storage-consent-2026-11-07-v4",
        },
        # Historical v2 (Jobsearch 47f73c4), replaced by v3.
        "application-storage-consent-2026-11-07-v2": {
            "source": "mays-jobsearch",
            "noticeState": NOTICE_DRAFT,
            "noticeVersion": None,  # no equivalence until separately approved
            "textSha256": (
                "232cc8206261b5d14f7a269f63a58320f76eea435a65f7e039b25c62d26da0ca"
            ),
            "supersededBy": "application-storage-consent-2026-11-07-v3",
        },
    },
    "cv-storage": {
        "cv-storage-consent-2026-11-08-v1": {
            "source": "mays-jobsearch",
            "noticeState": NOTICE_APPROVED,
            "noticeVersion": "1.0",
            "textSha256": (
                "2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036"
            ),
        },
    },
    "search-profile-storage": {
        "search-profile-storage-consent-2026-11-08-v2": {
            "source": "mays-jobsearch",
            "noticeState": NOTICE_DRAFT,
            "noticeVersion": None,
            "textSha256": (
                "75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6"
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

#: Stable Art. 9 special-category codes. The tuple order is the canonical order
#: used in the stored proof; the frozenset is the validation allowlist.
SPECIAL_CATEGORY_ORDER = (
    "health",
    "religious_or_philosophical_beliefs",
    "trade_union_membership",
    "political_opinions",
    "sexual_orientation",
    "sex_life",
    "biometric_data",
    "genetic_data",
    "racial_or_ethnic_origin",
)
SPECIAL_CATEGORY_CODES = frozenset(SPECIAL_CATEGORY_ORDER)

#: External text that is allowed to carry an explicit Art. 9 consent. A
#: historical text may be recorded for a non-Art. 9 grant but must never be
#: accepted as proof for special categories.
ART9_EXTERNAL_TEXT_VERSION = "application-storage-consent-2026-11-07-v4"
ART9_EXTERNAL_TEXT_SHA256 = (
    "8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7"
)
#: Purpose-specific Art. 9-capable external texts. Keeping the current
#: ApplicationV1 constants above preserves the existing contract while the
#: separate CV-storage purpose gets its own approved text identity.
ART9_EXTERNAL_TEXTS: dict[tuple[str, str], str] = {
    ("application-storage", ART9_EXTERNAL_TEXT_VERSION): ART9_EXTERNAL_TEXT_SHA256,
    ("cv-storage", "cv-storage-consent-2026-11-08-v1"): (
        "2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036"
    ),
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def validate_special_category_consent(
        consent: object, categories: object) -> tuple[bool, list[str]]:
    """Validate the explicit Art. 9 consent and its category subset.

    ``True`` requires a non-empty, duplicate-free subset of
    :data:`SPECIAL_CATEGORY_CODES`; ``False`` requires that no categories are
    claimed. Anything else fails closed. The returned list is in canonical
    order so the stored proof is deterministic.
    """
    if not isinstance(consent, bool):
        raise ConsentContractError(
            "INVALID_SPECIAL_CATEGORY_CONSENT",
            "specialCategoriesConsent must be a boolean")
    if consent is False:
        if categories not in (None, []):
            raise ConsentContractError(
                "SPECIAL_CATEGORIES_WITHOUT_CONSENT",
                "specialCategories requires explicit consent")
        return False, []
    if not isinstance(categories, (list, tuple)) or not categories:
        raise ConsentContractError(
            "SPECIAL_CATEGORIES_REQUIRED",
            "explicit consent requires a non-empty category list")
    seen: set[str] = set()
    for value in categories:
        if not isinstance(value, str) or value not in SPECIAL_CATEGORY_CODES:
            raise ConsentContractError(
                "UNKNOWN_SPECIAL_CATEGORY",
                "specialCategories contains an unknown code")
        if value in seen:
            raise ConsentContractError(
                "DUPLICATE_SPECIAL_CATEGORY",
                "specialCategories contains a duplicate code")
        seen.add(value)
    return True, [code for code in SPECIAL_CATEGORY_ORDER if code in seen]


def validate_external_text(purpose: str, version: object, sha256: object,
                           ) -> tuple[str | None, str | None]:
    """Validate an optional external text proof against the known refs.

    Both fields must be present together. The version must be a known external
    reference for the purpose and the hash must exactly match its pinned
    ``textSha256``. The external text is proof only; it never becomes a RIS
    ``noticeVersion``.
    """
    purpose = validate_purpose(purpose)
    if version is None and sha256 is None:
        return None, None
    if not isinstance(version, str) or not version.strip() \
            or not isinstance(sha256, str):
        raise ConsentContractError(
            "INVALID_EXTERNAL_TEXT",
            "externalTextVersion and externalTextSha256 must be provided together")
    version = version.strip()
    digest = sha256.strip().lower()
    if not _SHA256_RE.match(digest):
        raise ConsentContractError(
            "INVALID_EXTERNAL_TEXT",
            "externalTextSha256 is not a SHA-256 hex digest")
    entry = EXTERNAL_NOTICE_REFS.get(purpose, {}).get(version)
    if entry is None:
        raise ConsentContractError(
            "UNKNOWN_EXTERNAL_TEXT_VERSION",
            "externalTextVersion is not a known partner text")
    pinned = str(entry.get("textSha256") or "").strip().lower()
    if not pinned or pinned != digest:
        raise ConsentContractError(
            "EXTERNAL_TEXT_HASH_MISMATCH",
            "externalTextSha256 does not match the pinned text")
    return version, digest


def validate_consent_proof(
        purpose: str, *, special_categories_consent: object,
        special_categories: object, external_text_version: object,
        external_text_sha256: object,
) -> tuple[bool, list[str], str | None, str | None]:
    """Validate the full grant proof, including the Art. 9 text binding.

    An explicit Art. 9 consent requires the **current** Art. 9-capable text
    (version and hash). A historical text may be recorded for a non-Art. 9
    grant, but it can never back special-category consent.
    """
    consent, categories = validate_special_category_consent(
        special_categories_consent, special_categories)
    if consent:
        if external_text_version is None or external_text_sha256 is None \
                or not str(external_text_version).strip() \
                or not str(external_text_sha256).strip():
            raise ConsentContractError(
                "EXTERNAL_TEXT_REQUIRED_FOR_SPECIAL_CATEGORIES",
                "explicit Art. 9 consent requires the external text version "
                "and SHA-256")
        version, digest = validate_external_text(
            purpose, external_text_version, external_text_sha256)
        expected_hash = ART9_EXTERNAL_TEXTS.get((purpose, version))
        if (expected_hash is None and purpose == "application-storage"
                and version == ART9_EXTERNAL_TEXT_VERSION):
            # Preserve the existing, patchable ApplicationV1 constants for
            # compatibility with the historical contract tests.
            expected_hash = ART9_EXTERNAL_TEXT_SHA256
        if expected_hash is None:
            raise ConsentContractError(
                "EXTERNAL_TEXT_NOT_ART9",
                "only a purpose-specific Art. 9-capable text may carry "
                "special-category consent")
        if digest != expected_hash:
            raise ConsentContractError(
                "EXTERNAL_TEXT_NOT_ART9",
                "the external text hash is not the purpose Art. 9 text")
        return consent, categories, version, digest
    version, digest = validate_external_text(
        purpose, external_text_version, external_text_sha256)
    return consent, categories, version, digest


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
                   version: int = 0,
                   special_categories_consent: bool = False,
                   special_categories: object = None,
                   external_text_version: str | None = None,
                   external_text_sha256: str | None = None) -> dict:
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "purpose": purpose,
        "status": status,
        "noticeVersion": notice_version,
        "grantedAt": granted_at,
        "withdrawnAt": withdrawn_at,
        "version": version,
        # Stored consent proof. Legacy rows without proof report the
        # fail-closed defaults; they are never inferred from the notice.
        "specialCategoriesConsent": special_categories_consent is True,
        "specialCategories": [
            value for value in (special_categories or [])
            if isinstance(value, str)
        ],
        "externalTextVersion": external_text_version,
        "externalTextSha256": external_text_sha256,
    }
    payload.update(_entry_payload(purpose, notice_version))
    return payload
