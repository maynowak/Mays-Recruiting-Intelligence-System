"""Test-only ApplicationV1 harness.

This module deliberately stops at the existing trusted repository seam. It
does not create JWTs, call API Gateway/Lambda, or alter production code. DEV2
is an explicit non-executable mode until a separate live-mutation approval
exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from jobsearch.application_contract import ApplicationContext
from jobsearch.application_repository import ApplicationRepository


class HarnessMode(str, Enum):
    LOCAL = "LOCAL"
    DEV2 = "DEV2"


class Dev2MutationBlocked(RuntimeError):
    """DEV2 writes require a separate explicit approval outside this harness."""


@dataclass(frozen=True)
class SyntheticIdentity:
    user_id: str
    tenant_id: str
    partner_application_id: str
    issuer: str

    def context(self) -> ApplicationContext:
        return ApplicationContext(
            self.user_id,
            self.tenant_id,
            self.partner_application_id,
            self.issuer,
        )


PRIMARY = SyntheticIdentity(
    "synthetic-user-application-v1-a",
    "synthetic-tenant-application-v1",
    "synthetic-partner-application-v1",
    "https://synthetic.invalid/issuer/application-v1",
)
SECONDARY_USER = SyntheticIdentity(
    "synthetic-user-application-v1-b",
    PRIMARY.tenant_id,
    PRIMARY.partner_application_id,
    PRIMARY.issuer,
)
SECONDARY_TENANT = SyntheticIdentity(
    PRIMARY.user_id,
    "synthetic-tenant-application-v1-b",
    PRIMARY.partner_application_id,
    PRIMARY.issuer,
)
SECONDARY_PARTNER = SyntheticIdentity(
    PRIMARY.user_id,
    PRIMARY.tenant_id,
    "synthetic-partner-application-v1-b",
    PRIMARY.issuer,
)
SECONDARY_ISSUER = SyntheticIdentity(
    PRIMARY.user_id,
    PRIMARY.tenant_id,
    PRIMARY.partner_application_id,
    "https://synthetic.invalid/issuer/application-v1-b",
)


def synthetic_create(sequence: int, *, idempotency_key: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "job": {
            "jobId": f"synthetic-job-application-v1-{sequence}",
            "source": "synthetic-fixture",
            "title": f"Synthetic Role {sequence}",
            "company": "Synthetic Company",
            "location": "Synthetic Location",
            "url": f"https://synthetic.invalid/jobs/{sequence}",
        },
        "profileRef": {"id": f"synthetic-profile-{sequence}", "version": 1},
    }
    if idempotency_key is not None:
        data["idempotencyKey"] = idempotency_key
    return data


class ApplicationE2EHarness:
    """Small local-only adapter around the existing ApplicationRepository."""

    def __init__(self, dynamodb: Any, table_name: str, *, mode: HarnessMode = HarnessMode.LOCAL):
        if mode is not HarnessMode.LOCAL:
            raise Dev2MutationBlocked(
                "DEV2 mutation requires separate explicit approval; LOCAL only"
            )
        self.mode = mode
        self.repository = ApplicationRepository(table_name, dynamodb)

    def context(self, identity: SyntheticIdentity = PRIMARY) -> ApplicationContext:
        return identity.context()

    def create(self, sequence: int, identity: SyntheticIdentity = PRIMARY,
               *, idempotency_key: str | None = None) -> dict[str, Any]:
        return self.repository.create(
            synthetic_create(sequence, idempotency_key=idempotency_key),
            self.context(identity),
        )

    def cleanup_identity(self, identity: SyntheticIdentity = PRIMARY) -> int:
        """Delete only records visible through this synthetic identity."""
        ctx = self.context(identity)
        deleted = 0
        cursor = None
        while True:
            items, cursor = self.repository.list(ctx, limit=100, cursor=cursor)
            for item in items:
                self.repository.delete(item["applicationId"], item["version"], ctx)
                deleted += 1
            if not cursor:
                return deleted
