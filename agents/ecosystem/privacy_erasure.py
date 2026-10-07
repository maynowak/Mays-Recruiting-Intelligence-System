"""
Privacy erasure lifecycle (G5).

Erasure is an ordered lifecycle, not a recursive delete. The ordering is
the security property: **active authorization capability must not survive
a successful erasure**, so revocation of credentials happens FIRST, before
any record is removed or cancelled.

Order of operations
-------------------
1. **REVOKE credentials** (the capability itself). Once this step
   completes, the user can no longer authenticate as a machine principal,
   regardless of what happens afterwards. Every later step is data
   lifecycle, not access control.
2. **REVOKE API profiles** the user owns. A revoked credential is inert,
   but the profile is a still-visible capability surface; revoking it
   closes the surface and makes any future re-issue deliberate.
3. **CANCEL non-terminal work**. Queued/running work is transitioned to a
   terminal state rather than deleted, so SQS redelivery of an in-flight
   message cannot start a fresh attempt against an erased subject.
4. **DELETE documents** (S3 objects the platform owns for this user).
5. **DELETE the user profile row** -- last, because it is the record the
   other steps are keyed by.

Deliberately NOT done
--------------------
* Terminal work (COMPLETED / FAILED / DEAD_LETTER) is **retained**. Deleting
  it would re-admit duplicate execution: `TERMINAL_DUPLICATE_STATES` in the
  runtime suppresses a second business run for a COMPLETED `workId`, and
  removing the row removes that suppression. Retention duration is not
  invented here; the table's existing TTL governs.
* Entitlements are **retained**. They carry no capability of their own once
  credentials are revoked, and they already self-expire via TTL.
* Orders are **untouched** -- Mays-Orders owns them; Mays-RIS holds only a
  reference.

Partial failure
---------------
The result reports per-step outcomes. `complete` is True only when every
step succeeded. A failure is never reported as success: if revocation
itself fails, the run is `complete: False` and the caller must not be told
their data is gone while a live credential still exists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Work states that erasure transitions to CANCELLED. Everything else is
#: terminal history and is retained.
NON_TERMINAL_WORK_STATUSES = frozenset({
    "CREATED", "QUEUED", "RUNNING", "RETRY",
})

#: Status written when erasure cancels in-flight work. WorkItemStatus
#: already defines CANCELLED; until now nothing wrote it.
CANCELLED_STATUS = "CANCELLED"

REVOKED_CREDENTIAL_STATUS = "REVOKED"
REVOKED_PROFILE_STATUS = "REVOKED"

ERASURE_REASON = "privacy-erasure"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StepResult:
    """Outcome of one lifecycle step."""

    step: str
    ok: bool
    affected: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"step": self.step, "ok": self.ok,
                "affected": self.affected, "error": self.error}


@dataclass
class ErasureResult:
    """Ordered lifecycle outcome.

    `complete` is the honest field: it is False if ANY step failed, so a
    caller can never mistake a partial run for a finished erasure.
    """

    user_id: str
    tenant_id: Optional[str]
    complete: bool
    steps: List[StepResult] = field(default_factory=list)
    credentials_revoked: int = 0
    profiles_revoked: int = 0
    work_cancelled: int = 0
    documents_deleted: int = 0
    profile_deleted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "complete": self.complete,
            "credentialsRevoked": self.credentials_revoked,
            "profilesRevoked": self.profiles_revoked,
            "workCancelled": self.work_cancelled,
            "documentsDeleted": self.documents_deleted,
            "profileDeleted": self.profile_deleted,
            "steps": [s.to_dict() for s in self.steps],
        }

    @property
    def capability_revoked(self) -> bool:
        """True only when the revocation step itself succeeded.

        Authorization capability can be considered gone only when every
        owned credential reached REVOKED.
        """
        step = next((s for s in self.steps if s.step == "revoke-credentials"),
                    None)
        return bool(step and step.ok)


class PrivacyErasure:
    """Ordered erasure for one user, scoped to one tenant.

    Collaborators are injected so the workflow stays testable and so no
    AWS access is created implicitly.
    """

    def __init__(self, *,
                 credential_store: Any = None,
                 profile_store: Any = None,
                 work_table: Any = None,
                 document_deleter: Optional[Callable[[str], int]] = None,
                 user_profile_table: Any = None,
                 user_profile_key: str = "userId",
                 clock: Callable[[], datetime] = _utcnow,
                 ) -> None:
        self.credentials = credential_store
        self.profiles = profile_store
        self.work_table = work_table
        self.documents = document_deleter
        self.user_profiles = user_profile_table
        self.user_profile_key = user_profile_key
        self._clock = clock

    # ------------------------------------------------------------------
    def erase(self, user_id: str,
              tenant_id: Optional[str] = None) -> ErasureResult:
        """Run the full lifecycle. Never raises for a step failure.

        A step failure is recorded and the run continues only where doing
        so is still safe. Revocation failures are recorded but the run
        continues to attempt data cleanup -- leaving data behind while
        revoking access is strictly better than the reverse, and the
        result still reports `complete: False`.
        """
        if not user_id:
            raise ValueError("user_id is required")
        result = ErasureResult(user_id=user_id, tenant_id=tenant_id,
                               complete=False)
        stamp = self._clock().isoformat()

        # 1. Credentials FIRST -- this is the capability, not the data.
        result.steps.append(self._revoke_credentials(result))
        # 2. API profiles the user owns.
        result.steps.append(self._revoke_profiles(result))
        # 3. Non-terminal work is cancelled, never deleted.
        result.steps.append(self._cancel_work(result))
        # 4. Documents owned by the platform for this user.
        result.steps.append(self._delete_documents(result))
        # 5. Profile row last.
        result.steps.append(self._delete_profile(result, stamp))

        result.complete = all(step.ok for step in result.steps)
        return result

    # ------------------------------------------------------------------
    def _revoke_credentials(self, result: ErasureResult) -> StepResult:
        if self.credentials is None:
            return StepResult("revoke-credentials", True, 0)
        try:
            rows = self.credentials.list_by_owner(result.user_id)
        except Exception as exc:
            logger.error("credential lookup failed for %s: %s",
                         result.user_id, exc)
            return StepResult("revoke-credentials", False, 0, str(exc))

        stamp = self._clock().isoformat()
        revoked = 0
        failures: List[str] = []
        for row in rows:
            if row.get("status") == REVOKED_CREDENTIAL_STATUS:
                continue  # already terminal; idempotent
            try:
                meta = dict(row)
                meta.update({
                    "status": REVOKED_CREDENTIAL_STATUS,
                    "revokedAt": stamp,
                    "revokedBy": result.user_id,
                    "revokeReason": ERASURE_REASON,
                    "updatedAt": stamp,
                })
                self.credentials.update_credential(
                    meta["credentialId"], meta)
                revoked += 1
            except Exception as exc:
                failures.append("%s: %s" % (row.get("credentialId"), exc))

        result.credentials_revoked = revoked
        if failures:
            return StepResult("revoke-credentials", False, revoked,
                              "; ".join(failures))
        return StepResult("revoke-credentials", True, revoked)

    def _revoke_profiles(self, result: ErasureResult) -> StepResult:
        if self.profiles is None:
            return StepResult("revoke-api-profiles", True, 0)
        try:
            rows = self.profiles.list_by_owner(result.user_id)
        except Exception as exc:
            logger.error("api profile lookup failed for %s: %s",
                         result.user_id, exc)
            return StepResult("revoke-api-profiles", False, 0, str(exc))

        revoked = 0
        failures: List[str] = []
        for row in rows:
            if row.get("status") == REVOKED_PROFILE_STATUS:
                continue
            try:
                item = dict(row)
                item["status"] = REVOKED_PROFILE_STATUS
                item["updatedAt"] = self._clock().isoformat()
                item["revokeReason"] = ERASURE_REASON
                # Direct store write, not the service layer: erasure is a
                # self-service operation on the caller's OWN profiles, so
                # the actor/role indirection of update_profile() (which
                # exists to police admin-vs-owner edits) would only add a
                # second authorization path for the same outcome.
                self.profiles.update_profile(item["apiProfileId"], item)
                revoked += 1
            except Exception as exc:
                failures.append("%s: %s" % (row.get("apiProfileId"), exc))

        result.profiles_revoked = revoked
        if failures:
            return StepResult("revoke-api-profiles", False, revoked,
                              "; ".join(failures))
        return StepResult("revoke-api-profiles", True, revoked)

    def _cancel_work(self, result: ErasureResult) -> StepResult:
        if self.work_table is None:
            return StepResult("cancel-non-terminal-work", True, 0)
        try:
            response = self.work_table.query(
                IndexName="gsi-user",
                KeyConditionExpression=(
                    Key("userId").eq(result.user_id)),
            )
            items = response.get("Items", [])
        except Exception as exc:
            logger.error("work lookup failed for %s: %s",
                         result.user_id, exc)
            return StepResult("cancel-non-terminal-work", False, 0, str(exc))

        cancelled = 0
        failures: List[str] = []
        for item in items:
            status = item.get("status")
            if status not in NON_TERMINAL_WORK_STATUSES:
                continue  # terminal history is retained, never deleted
            try:
                self.work_table.update_item(
                    Key={"workId": item["workId"]},
                    UpdateExpression="SET #s = :c, updatedAt = :u",
                    ConditionExpression="attribute_exists(workId)",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":c": CANCELLED_STATUS,
                        ":u": self._clock().isoformat()},
                )
                cancelled += 1
            except Exception as exc:
                failures.append("%s: %s" % (item.get("workId"), exc))

        result.work_cancelled = cancelled
        if failures:
            return StepResult("cancel-non-terminal-work", False, cancelled,
                              "; ".join(failures))
        return StepResult("cancel-non-terminal-work", True, cancelled)

    def _delete_documents(self, result: ErasureResult) -> StepResult:
        if self.documents is None:
            return StepResult("delete-documents", True, 0)
        try:
            deleted = self.documents(result.user_id)
        except Exception as exc:
            logger.error("document deletion failed for %s: %s",
                         result.user_id, exc)
            return StepResult("delete-documents", False, 0, str(exc))
        result.documents_deleted = deleted
        return StepResult("delete-documents", True, deleted)

    def _delete_profile(self, result: ErasureResult,
                        stamp: str) -> StepResult:
        if self.user_profiles is None:
            return StepResult("delete-user-profile", True, 0)
        try:
            self.user_profiles.delete_item(
                Key={self.user_profile_key: result.user_id})
            result.profile_deleted = True
            return StepResult("delete-user-profile", True, 1)
        except Exception as exc:
            logger.error("profile deletion failed for %s: %s",
                         result.user_id, exc)
            return StepResult("delete-user-profile", False, 0, str(exc))


# Imported late so the module stays importable without boto3 at module
# scope, matching the lazy-import discipline used elsewhere in this
# package.
def Key(name: str):  # noqa: N802 - mirrors boto3.dynamodb.conditions.Key
    from boto3.dynamodb.conditions import Key as _Key
    return _Key(name)