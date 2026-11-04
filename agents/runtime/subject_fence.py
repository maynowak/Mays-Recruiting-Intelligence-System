"""Durable RIS subject-fence primitives for worker admission.

The module contains no AWS client construction.  Callers inject a DynamoDB
resource/table.  Fence rows are write-once and intentionally have no TTL or
release path; erasure/recovery approval is required before any future policy
can change that state.
"""

from __future__ import annotations

import hashlib


FENCE_ACTIVE = "ACTIVE"
FENCE_COMPLETED = "COMPLETED"


class SubjectFenceBlocked(RuntimeError):
    pass


class SubjectFenceUnavailable(RuntimeError):
    pass


def subject_fence_key(*, user_id: str, tenant_id: str,
                      partner_application_id: str = "", issuer: str = "") -> str:
    material = "|".join((tenant_id or "", user_id or "",
                         partner_application_id or "", issuer or ""))
    return "erasure-fence#" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def fence_item(*, user_id: str, tenant_id: str,
               partner_application_id: str = "", issuer: str = "",
               operation_id: str = "") -> dict[str, str]:
    key = subject_fence_key(
            user_id=user_id, tenant_id=tenant_id,
            partner_application_id=partner_application_id, issuer=issuer)
    return {
        "workId": key,
        "fenceKey": key,
        "resourceType": "ErasureSubjectFence",
        "schemaVersion": "1",
        "state": FENCE_ACTIVE,
        "userId": user_id,
        "tenantId": tenant_id,
        "partnerApplicationId": partner_application_id,
        "issuer": issuer,
        "operationId": operation_id,
    }


def assert_fence_clear(table, *, user_id: str, tenant_id: str,
                       partner_application_id: str = "", issuer: str = None) -> None:
    try:
        item = table.get_item(Key={"workId": subject_fence_key(
            user_id=user_id, tenant_id=tenant_id,
            partner_application_id=partner_application_id, issuer=issuer or "")}).get("Item")
    except Exception as exc:
        raise SubjectFenceUnavailable("subject fence lookup failed") from exc
    if item is not None:
        if item.get("resourceType") != "ErasureSubjectFence" or item.get("schemaVersion") != "1":
            raise SubjectFenceUnavailable("subject fence is corrupt")
        raise SubjectFenceBlocked("subject is fenced by erasure")


__all__ = ["FENCE_ACTIVE", "FENCE_COMPLETED", "SubjectFenceBlocked",
           "SubjectFenceUnavailable", "subject_fence_key", "fence_item",
           "assert_fence_clear"]
