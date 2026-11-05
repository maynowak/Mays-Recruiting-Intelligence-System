"""C1A resumable DynamoDB-only profile hierarchy erasure.

This module is deliberately an orchestration layer over the existing
``PartnerProfileRepository`` and C0A operation/checkpoint repository.  It does
not create AWS clients, delete documents, or call S3.  Document metadata is
therefore retained and the operation can never become COMPLETED here.
"""

from __future__ import annotations

import base64
import json
from dataclasses import replace
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from agents.ecosystem.privacy_erasure_contract import (
    CHECKPOINT_COMPLETED,
    CHECKPOINT_IN_PROGRESS,
    ErasureCheckpointV1,
    ErasureExecutionContextV1,
    ErasureOperationV1,
    ErasureProgressV1,
    OPERATION_SCOPE_CV,
    OPERATION_SCOPE_USER,
    PROGRESS_COMPLETED,
    PROGRESS_PARTIAL,
    PROGRESS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PARTIAL,
    STATUS_RUNNING,
)


PROFILE_CATEGORIES = (
    "atsSearchProfiles", "cvSearchProfiles", "manualSearchProfiles",
    "userProfile", "cvDocuments",
)
DOCUMENT_PENDING = "DOCUMENT_S3_PHASE_PENDING"
FREEZE_LOST = "ERASURE_WRITE_FREEZE_LOST"
CONCURRENT_MUTATION = "PROFILE_CONCURRENT_MUTATION"
CHECKPOINT_CONFLICT = "ERASURE_CHECKPOINT_CONFLICT"


class ProfileErasureError(RuntimeError):
    """Base class for fail-closed profile erasure errors."""


class ProfileErasureConflict(ProfileErasureError):
    pass


class ProfileErasureBlocked(ProfileErasureError):
    pass


def _cursor_encode(value: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not value:
        return None
    raw = json.dumps(dict(value), sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _cursor_decode(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    padded = value + ("=" * (-len(value) % 4))
    try:
        result = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, TypeError, UnicodeDecodeError):
        raise ProfileErasureBlocked("invalid erasure checkpoint cursor")
    if not isinstance(result, dict):
        raise ProfileErasureBlocked("invalid erasure checkpoint cursor")
    return result


def _resource_id(resource: Any) -> str:
    for name in ("ats_profile_id", "search_profile_id", "manual_profile_id", "cv_id"):
        value = getattr(resource, name, None)
        if value:
            return str(value)
    # UserProfile is represented by its stable user identity.  CVDocuments are
    # never passed here because they remain for the document phase.
    user_id = getattr(resource, "user_id", None)
    if user_id:
        return str(user_id)
    raise ProfileErasureBlocked("profile has no stable resource identity")


def _cv_id(resource: Any) -> Optional[str]:
    return getattr(resource, "cv_id", None)


def _is_conflict(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in (
        "freeze", "conflict", "conditionalcheckfailed", "version"))


class ProfileOnlyErasureExecutor:
    """Run one authorized USER or CV profile-only operation.

    ``operation_repository`` is the existing C0A repository.  It is injected so
    tests can use a transaction fake; production persistence remains governed
    by its existing disabled-by-default switch.  ``delete_user_profile`` is
    the existing UserProfile transactional delete binding, not a replacement
    profile engine.
    """

    def __init__(self, *, profile_repository: Any, operation_repository: Any,
                 delete_user_profile: Optional[Callable[..., Any]] = None,
                 application_repository: Any = None,
                 page_size: int = 50):
        if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 1:
            raise ValueError("page_size must be positive")
        self.profiles = profile_repository
        self.operations = operation_repository
        self.delete_user_profile = delete_user_profile
        self.applications = application_repository
        self.page_size = page_size
        self._last_operation: Optional[ErasureOperationV1] = None

    @staticmethod
    def _require_context(operation: ErasureOperationV1,
                         context: ErasureExecutionContextV1) -> None:
        if operation.status != STATUS_RUNNING:
            raise ProfileErasureBlocked("operation is not RUNNING")
        if (context.operation_id != operation.operation_id
                or context.operation_version != operation.version
                or context.scope != operation.scope
                or context.user_id != operation.user_id
                or context.tenant_id != operation.tenant_id
                or context.partner_application_id != operation.partner_application_id
                or context.issuer != operation.issuer
                or context.cv_id != operation.cv_id):
            raise ProfileErasureConflict("execution context is stale or foreign")

    def _save(self, operation: ErasureOperationV1, category: str,
              progress: ErasureProgressV1) -> ErasureOperationV1:
        try:
            updated = self.operations.save_checkpoint(
                operation.operation_id, category, progress,
                expected_version=operation.version,
                context={"userId": operation.user_id, "tenantId": operation.tenant_id,
                         "partnerApplicationId": operation.partner_application_id,
                         "issuer": operation.issuer})
            self._last_operation = updated
            return updated
        except Exception as exc:
            raise ProfileErasureConflict(CHECKPOINT_CONFLICT) from exc

    def _progress(self, operation: ErasureOperationV1, category: str,
                  *, status: str, affected: int,
                  checkpoint: ErasureCheckpointV1,
                  error_code: Optional[str] = None,
                  retryable: bool = False) -> ErasureOperationV1:
        return self._save(operation, category, ErasureProgressV1(
            status=status, affected=affected, checkpoint=checkpoint,
            error_code=error_code, retryable=retryable))

    def _context_for(self, context: ErasureExecutionContextV1,
                     operation: ErasureOperationV1) -> ErasureExecutionContextV1:
        return replace(context, operation_version=operation.version)

    def _delete(self, resource: Any, operation: ErasureOperationV1) -> None:
        rid = _resource_id(resource)
        kwargs = dict(
            user_id=operation.user_id, tenant_id=operation.tenant_id,
            partner_app_id=operation.partner_application_id,
            issuer=operation.issuer, expected_version=getattr(resource, "version", None))
        try:
            result = self.profiles.delete(rid, **kwargs)
        except Exception as exc:
            if _is_conflict(exc):
                raise ProfileErasureConflict(CONCURRENT_MUTATION) from exc
            raise
        if result is False:
            # A replay after a committed delete is successful.  A direct
            # false result for a foreign item is not converted into progress.
            current = self.profiles.get(rid, operation.user_id, operation.tenant_id,
                                        operation.partner_application_id,
                                        operation.issuer)
            if current is not None:
                raise ProfileErasureConflict(CONCURRENT_MUTATION)

    def _page_by_user(self, resource_type: str, operation: ErasureOperationV1,
                      cursor: Optional[Mapping[str, Any]]):
        return self.profiles.list_by_user(
            operation.user_id, operation.tenant_id, resource_type=resource_type,
            partner_app_id=operation.partner_application_id,
            issuer=operation.issuer, limit=self.page_size, cursor=dict(cursor) if cursor else None)

    def _page_by_parent(self, parent_id: str, resource_type: str,
                        operation: ErasureOperationV1,
                        cursor: Optional[Mapping[str, Any]]):
        return self.profiles.list_by_parent(
            parent_id, operation.user_id, operation.tenant_id,
            resource_type=resource_type, partner_app_id=operation.partner_application_id,
            issuer=operation.issuer, limit=self.page_size,
            cursor=dict(cursor) if cursor else None)

    def _delete_user_category(self, operation: ErasureOperationV1, category: str,
                              resource_type: str, context: ErasureExecutionContextV1
                              ) -> ErasureOperationV1:
        old = operation.progress.get(category, ErasureProgressV1())
        checkpoint = old.checkpoint or ErasureCheckpointV1(
            phase=category, state=CHECKPOINT_IN_PROGRESS, attempt=0)
        cursor = _cursor_decode(checkpoint.cursor_ref)
        affected = old.affected
        while True:
            items, next_cursor = self._page_by_user(resource_type, operation, cursor)
            for item in items:
                self._require_context(operation, context)
                self._delete(item, operation)
                affected += 1
                checkpoint = ErasureCheckpointV1(
                    phase=category, state=CHECKPOINT_IN_PROGRESS,
                    cursor_ref=_cursor_encode(cursor),
                    last_resource_ref=_resource_id(item),
                    attempt=checkpoint.attempt, updated_at=operation.updated_at)
                operation = self._progress(operation, category,
                    status=PROGRESS_RUNNING, affected=affected, checkpoint=checkpoint)
                context = self._context_for(context, operation)
            if not next_cursor:
                checkpoint = ErasureCheckpointV1(
                    phase=category, state=CHECKPOINT_COMPLETED,
                    last_resource_ref=checkpoint.last_resource_ref,
                    attempt=checkpoint.attempt, updated_at=operation.updated_at)
                return self._progress(operation, category,
                    status=PROGRESS_COMPLETED, affected=affected, checkpoint=checkpoint)
            cursor = next_cursor
            checkpoint = ErasureCheckpointV1(
                phase=category, state=CHECKPOINT_IN_PROGRESS,
                cursor_ref=_cursor_encode(cursor),
                last_resource_ref=checkpoint.last_resource_ref,
                attempt=checkpoint.attempt, updated_at=operation.updated_at)
            operation = self._progress(operation, category,
                status=PROGRESS_RUNNING, affected=affected, checkpoint=checkpoint)
            context = self._context_for(context, operation)

    def _delete_cv_hierarchy(self, operation: ErasureOperationV1,
                             context: ErasureExecutionContextV1) -> ErasureOperationV1:
        # The cursor contains the current parent and its opaque child cursor.
        # ``searchIds`` keeps the rest of a page: deleting from a GSI while
        # walking it must not make the next parent disappear from the resume
        # state.
        category = "atsSearchProfiles"
        progress = operation.progress.get(category, ErasureProgressV1())
        state = _cursor_decode(progress.checkpoint.cursor_ref) if progress.checkpoint else None
        search_cursor = _cursor_decode(state.get("searchCursor")) if state else None
        ats_cursor = _cursor_decode(state.get("atsCursor")) if state and state.get("atsCursor") else None
        current_search = state.get("searchId") if state else None
        search_ids = list(state.get("searchIds", [])) if state else []
        search_exhausted = bool(state.get("searchExhausted")) if state else False
        affected = progress.affected
        while True:
            if current_search:
                items, next_ats = self._page_by_parent(current_search, "ATSSearchProfile", operation, ats_cursor)
                for item in items:
                    self._require_context(operation, context)
                    self._delete(item, operation)
                    affected += 1
                    state = {"searchId": current_search,
                             "searchIds": search_ids,
                             "searchExhausted": search_exhausted,
                             "searchCursor": _cursor_encode(search_cursor),
                             "atsCursor": _cursor_encode(next_ats)}
                    cp = ErasureCheckpointV1(phase=category, state=CHECKPOINT_IN_PROGRESS,
                        cursor_ref=_cursor_encode(state), last_resource_ref=_resource_id(item),
                        updated_at=operation.updated_at)
                    operation = self._progress(operation, category, status=PROGRESS_RUNNING,
                        affected=affected, checkpoint=cp)
                    context = self._context_for(context, operation)
                if next_ats:
                    ats_cursor = next_ats
                    continue
                current_search = None
                ats_cursor = None
            if search_ids:
                current_search = search_ids.pop(0)
                ats_cursor = None
                continue
            if search_exhausted:
                break
            searches, next_search = self._page_by_parent(operation.cv_id, "CVSearchProfile", operation, search_cursor)
            if not searches:
                break
            search_ids = [_resource_id(search) for search in searches]
            search_cursor = next_search
            search_exhausted = not bool(next_search)
        cp = ErasureCheckpointV1(phase=category, state=CHECKPOINT_COMPLETED,
            last_resource_ref=progress.checkpoint.last_resource_ref if progress.checkpoint else None,
            updated_at=operation.updated_at)
        operation = self._progress(operation, category, status=PROGRESS_COMPLETED,
                                   affected=affected, checkpoint=cp)
        # CVSearchProfile parents can now be removed, but the CVDocument itself
        # remains as the document/S3 reference anchor.
        context = self._context_for(context, operation)
        operation = self._delete_cv_search(operation, context)
        return operation

    def _delete_cv_search(self, operation: ErasureOperationV1,
                          context: ErasureExecutionContextV1) -> ErasureOperationV1:
        category = "cvSearchProfiles"
        progress = operation.progress.get(category, ErasureProgressV1())
        cursor = _cursor_decode(progress.checkpoint.cursor_ref) if progress.checkpoint else None
        affected = progress.affected
        while True:
            items, next_cursor = self._page_by_parent(operation.cv_id, "CVSearchProfile", operation, cursor)
            for item in items:
                self._require_context(operation, context)
                self._delete(item, operation)
                affected += 1
                cp = ErasureCheckpointV1(phase=category, state=CHECKPOINT_IN_PROGRESS,
                    cursor_ref=_cursor_encode(cursor), last_resource_ref=_resource_id(item),
                    updated_at=operation.updated_at)
                operation = self._progress(operation, category, status=PROGRESS_RUNNING,
                    affected=affected, checkpoint=cp)
                context = self._context_for(context, operation)
            if not next_cursor:
                cp = ErasureCheckpointV1(phase=category, state=CHECKPOINT_COMPLETED,
                    last_resource_ref=progress.checkpoint.last_resource_ref if progress.checkpoint else None,
                    updated_at=operation.updated_at)
                return self._progress(operation, category, status=PROGRESS_COMPLETED,
                    affected=affected, checkpoint=cp)
            cursor = next_cursor

    def _pending_documents(self, operation: ErasureOperationV1) -> ErasureOperationV1:
        old = operation.progress.get("cvDocuments", ErasureProgressV1())
        cp = old.checkpoint or ErasureCheckpointV1(phase="cvDocuments", state=CHECKPOINT_IN_PROGRESS)
        return self._progress(operation, "cvDocuments", status=PROGRESS_PARTIAL,
            affected=old.affected, checkpoint=cp, error_code=DOCUMENT_PENDING, retryable=True)

    def _delete_user_profile(self, operation: ErasureOperationV1,
                             context: ErasureExecutionContextV1) -> ErasureOperationV1:
        if not self.delete_user_profile:
            cp = ErasureCheckpointV1(phase="userProfile", state=CHECKPOINT_IN_PROGRESS)
            return self._progress(operation, "userProfile", status=PROGRESS_PARTIAL,
                affected=0, checkpoint=cp, error_code="USER_PROFILE_DELETE_UNAVAILABLE", retryable=True)
        self._require_context(operation, context)
        try:
            self.delete_user_profile(operation.user_id, operation.tenant_id, context=context)
        except Exception as exc:
            if _is_conflict(exc):
                raise ProfileErasureConflict(FREEZE_LOST) from exc
            raise
        cp = ErasureCheckpointV1(phase="userProfile", state=CHECKPOINT_COMPLETED,
                                 last_resource_ref=operation.user_id,
                                 updated_at=operation.updated_at)
        return self._progress(operation, "userProfile", status=PROGRESS_COMPLETED,
                              affected=1, checkpoint=cp)

    def _delete_applications(self, operation: ErasureOperationV1,
                             context: ErasureExecutionContextV1) -> ErasureOperationV1:
        """Delete ApplicationV1 records through the same fenced operation.

        The repository receives the verified operation scope, never a client
        payload. The persisted cursor is opaque to the public erasure
        contract, and a replay treats an already-deleted application as
        success so a failed checkpoint can safely resume.
        """
        category = "applications"
        if self.applications is None:
            cp = ErasureCheckpointV1(phase=category, state=CHECKPOINT_IN_PROGRESS)
            return self._progress(operation, category, status=PROGRESS_PARTIAL,
                                  affected=0, checkpoint=cp,
                                  error_code="APPLICATION_STORAGE_UNAVAILABLE",
                                  retryable=True)
        from jobsearch.application_contract import ApplicationContext
        from jobsearch.application_repository import ApplicationNotFound
        old = operation.progress.get(category, ErasureProgressV1())
        cursor = _cursor_decode(old.checkpoint.cursor_ref) if old.checkpoint else None
        affected = old.affected
        app_context = ApplicationContext(operation.user_id, operation.tenant_id,
                                         operation.partner_application_id,
                                         operation.issuer)
        while True:
            items, next_cursor = self.applications.list(
                app_context, limit=self.page_size, cursor=cursor,
                include_deleting=True)
            for item in items:
                self._require_context(operation, context)
                try:
                    self.applications.delete(item["applicationId"],
                                             item["version"], app_context)
                    affected += 1
                except ApplicationNotFound:
                    # A prior attempt committed before its checkpoint write.
                    pass
                cp = ErasureCheckpointV1(
                    phase=category, state=CHECKPOINT_IN_PROGRESS,
                    cursor_ref=_cursor_encode(cursor),
                    last_resource_ref=item.get("applicationId"),
                    updated_at=operation.updated_at)
                operation = self._progress(operation, category,
                    status=PROGRESS_RUNNING, affected=affected, checkpoint=cp)
                context = self._context_for(context, operation)
            if not next_cursor:
                cp = ErasureCheckpointV1(
                    phase=category, state=CHECKPOINT_COMPLETED,
                    last_resource_ref=(old.checkpoint.last_resource_ref
                                       if old.checkpoint else None),
                    updated_at=operation.updated_at)
                return self._progress(operation, category,
                                      status=PROGRESS_COMPLETED,
                                      affected=affected, checkpoint=cp)
            cursor = next_cursor
            cp = ErasureCheckpointV1(
                phase=category, state=CHECKPOINT_IN_PROGRESS,
                cursor_ref=_cursor_encode(cursor),
                last_resource_ref=(old.checkpoint.last_resource_ref
                                   if old.checkpoint else None),
                updated_at=operation.updated_at)
            operation = self._progress(operation, category,
                                       status=PROGRESS_RUNNING,
                                       affected=affected, checkpoint=cp)
            context = self._context_for(context, operation)

    def run(self, operation: ErasureOperationV1,
            context: ErasureExecutionContextV1) -> ErasureOperationV1:
        """Execute/resume profile work; failures are durable PARTIAL progress."""
        if operation.status != STATUS_RUNNING:
            if operation.status == STATUS_COMPLETED:
                raise ProfileErasureBlocked("completed operation cannot resume")
            scope_context = {"userId": operation.user_id, "tenantId": operation.tenant_id,
                             "partnerApplicationId": operation.partner_application_id,
                             "issuer": operation.issuer}
            if hasattr(self.operations, "resume"):
                operation = self.operations.resume(operation.operation_id,
                                                   context=scope_context)
            else:
                resumed = operation.transition(STATUS_RUNNING,
                                               now=operation.updated_at or operation.created_at)
                operation = self.operations.update(resumed,
                                                   expected_version=operation.version,
                                                   context=scope_context)
            context = self._context_for(context, operation)
        self._require_context(operation, context)
        self._last_operation = operation
        try:
            if operation.scope == OPERATION_SCOPE_CV:
                operation = self._delete_cv_hierarchy(operation, context)
                context = self._context_for(context, operation)
                operation = self._progress(
                    operation, "applications", status="SKIPPED", affected=0,
                    checkpoint=ErasureCheckpointV1(
                        phase="applications", state=CHECKPOINT_COMPLETED))
                context = self._context_for(context, operation)
                operation = self._progress(
                    operation, "manualSearchProfiles", status="SKIPPED", affected=0,
                    checkpoint=ErasureCheckpointV1(
                        phase="manualSearchProfiles", state=CHECKPOINT_COMPLETED))
                context = self._context_for(context, operation)
            else:
                if self.applications is not None:
                    operation = self._delete_applications(operation, context)
                else:
                    operation = self._progress(
                        operation, "applications", status="SKIPPED", affected=0,
                        checkpoint=ErasureCheckpointV1(
                            phase="applications", state=CHECKPOINT_COMPLETED))
                context = self._context_for(context, operation)
                operation = self._delete_user_category(operation, "atsSearchProfiles", "ATSSearchProfile", context)
                context = self._context_for(context, operation)
                operation = self._delete_user_category(operation, "cvSearchProfiles", "CVSearchProfile", context)
                context = self._context_for(context, operation)
                operation = self._delete_user_category(operation, "manualSearchProfiles", "ManualSearchProfile", context)
                context = self._context_for(context, operation)
            if operation.scope == OPERATION_SCOPE_USER:
                operation = self._delete_user_profile(operation, context)
            else:
                operation = self._progress(operation, "userProfile", status="SKIPPED", affected=0,
                    checkpoint=ErasureCheckpointV1(phase="userProfile", state=CHECKPOINT_COMPLETED))
            operation = self._pending_documents(operation)
            # Never transition to COMPLETED: cvDocuments remains an explicit
            # required phase until a separate document/S3 executor resolves it.
            if operation.status != STATUS_PARTIAL:
                operation = operation.transition(STATUS_PARTIAL, now=operation.updated_at or operation.created_at,
                                                 error_code=DOCUMENT_PENDING)
                operation = self.operations.update(operation, expected_version=operation.version - 1,
                                                   context={"userId": operation.user_id, "tenantId": operation.tenant_id,
                                                            "partnerApplicationId": operation.partner_application_id,
                                                            "issuer": operation.issuer})
            return operation
        except ProfileErasureConflict:
            # The last successful checkpoint is the only safe resume point.
            # Do not overwrite it when the checkpoint store itself reported a
            # CAS conflict; another worker owns the operation in that case.
            current = self._last_operation
            if current is not None and current.status == STATUS_RUNNING:
                try:
                    partial = current.transition(STATUS_PARTIAL,
                                                 now=current.updated_at or current.created_at,
                                                 error_code=CONCURRENT_MUTATION)
                    self.operations.update(
                        partial, expected_version=current.version,
                        context={"userId": current.user_id, "tenantId": current.tenant_id,
                                 "partnerApplicationId": current.partner_application_id,
                                 "issuer": current.issuer})
                except Exception:
                    pass
            raise
        except Exception as exc:
            raise ProfileErasureError(str(exc)) from exc


__all__ = ["ProfileOnlyErasureExecutor", "ProfileErasureError",
           "ProfileErasureConflict", "ProfileErasureBlocked", "DOCUMENT_PENDING"]
