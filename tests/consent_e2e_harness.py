"""Joint partner-consent / ApplicationV1 end-to-end harness.

Local-only, synthetic data. It exercises the real repositories and the real
handler consent gate; it never creates JWTs, calls API Gateway, or touches an
AWS account. The Jobsearch BFF is simulated by calling the same repository
seam the handler uses, so the contract under test is the RIS one.

Scenario order (JM-RIS-CONSENT-RECONCILIATION-01 §8):

    1 no consent      -> write denied
    2 grant           -> stored
    3 create          -> allowed
    4 withdraw        -> stored
    5 patch           -> denied
    6 read/export/del -> still allowed
    7 regrant         -> stored
    8 history         -> complete events
"""

from __future__ import annotations

from dataclasses import dataclass

from jobsearch.application_contract import ApplicationContext
from jobsearch.application_repository import ApplicationRepository
from jobsearch.consent_contract import ConsentContext
from jobsearch.consent_repository import ConsentRepository

PURPOSE = "application-storage"
NOTICE_VERSION = "1.0"
FOREIGN_NOTICE_VERSION = "2026-11-04-draft-1"


@dataclass(frozen=True)
class SyntheticConsentIdentity:
    user_id: str
    tenant_id: str
    partner_application_id: str
    issuer: str

    def consent_context(self) -> ConsentContext:
        return ConsentContext(
            self.user_id, self.tenant_id,
            self.partner_application_id, self.issuer)

    def application_context(self) -> ApplicationContext:
        return ApplicationContext(
            self.user_id, self.tenant_id,
            self.partner_application_id, self.issuer)


PRIMARY = SyntheticConsentIdentity(
    "synthetic-consent-user-a",
    "synthetic-consent-tenant",
    "synthetic-consent-partner",
    "https://synthetic.invalid/issuer/consent",
)

SECONDARY_USER = SyntheticConsentIdentity(
    "synthetic-consent-user-b",
    PRIMARY.tenant_id,
    PRIMARY.partner_application_id,
    PRIMARY.issuer,
)

FOREIGN_TENANT = SyntheticConsentIdentity(
    PRIMARY.user_id,
    "synthetic-consent-tenant-b",
    PRIMARY.partner_application_id,
    PRIMARY.issuer,
)


class ConsentGateDenied(RuntimeError):
    """Raised by the harness when a write is attempted without a grant."""


class JointConsentE2EHarness:
    """LOCAL-only seam shared by the consent and application repositories."""

    def __init__(self, dynamodb, applications_table: str,
                 consents_table: str, *, enforced: bool = True):
        self.enforced = enforced
        self.applications = ApplicationRepository(applications_table, dynamodb)
        self.consent = ConsentRepository(consents_table, dynamodb)

    # -- consent -------------------------------------------------------
    def status(self, identity=PRIMARY) -> dict:
        return self.consent.get(identity.consent_context(), PURPOSE)

    def grant(self, identity=PRIMARY, notice_version=NOTICE_VERSION) -> dict:
        return self.consent.grant(
            identity.consent_context(), PURPOSE, notice_version)

    def withdraw(self, identity=PRIMARY) -> dict:
        return self.consent.withdraw(identity.consent_context(), PURPOSE)

    def history(self, identity=PRIMARY) -> list[dict]:
        items, _ = self.consent.history(identity.consent_context(), PURPOSE)
        return items

    def write_allowed(self, identity=PRIMARY) -> bool:
        if not self.enforced:
            return True
        return self.consent.has_consent(identity.consent_context(), PURPOSE)

    def require_write(self, identity=PRIMARY) -> None:
        if not self.write_allowed(identity):
            raise ConsentGateDenied("storage consent is required")

    # -- ApplicationV1 writes (gauntlet for the gate) -------------------
    def create(self, payload: dict, identity=PRIMARY) -> dict:
        self.require_write(identity)
        return self.applications.create(
            payload, identity.application_context())

    def patch(self, app_id: str, payload: dict, identity=PRIMARY) -> dict:
        self.require_write(identity)
        return self.applications.patch(
            app_id, payload, identity.application_context())

    # -- ApplicationV1 reads (must never be gated) ---------------------
    def get(self, app_id: str, identity=PRIMARY) -> dict:
        return self.applications.get(app_id, identity.application_context())

    def export(self, app_id: str, identity=PRIMARY) -> dict:
        return self.applications.export(app_id, identity.application_context())

    def delete(self, app_id: str, expected_version: int, identity=PRIMARY) -> None:
        self.applications.delete(
            app_id, expected_version, identity.application_context())
