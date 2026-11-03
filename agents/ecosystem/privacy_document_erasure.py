"""C1B local integration of C1A profile and C0F document phases.

Only injected, fencing-capable S3-shaped adapters are accepted.  The module
does not create an AWS client and does not treat a fake-S3 result as production
evidence.  CVDocument metadata is deleted only after the C0F orchestrator has
completed its final empty re-inventory.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from agents.ecosystem.privacy_erasure_contract import (
    CHECKPOINT_COMPLETED,
    CHECKPOINT_IN_PROGRESS,
    ErasureCheckpointV1,
    ErasureExecutionContextV1,
    ErasureOperationV1,
    ErasureProgressV1,
    PROGRESS_COMPLETED,
    PROGRESS_PARTIAL,
    PROGRESS_SKIPPED,
    STATUS_COMPLETED,
    STATUS_PARTIAL,
    STATUS_RUNNING,
)
from agents.ecosystem.privacy_profile_erasure import (
    ProfileErasureConflict,
    ProfileErasureError,
    ProfileOnlyErasureExecutor,
)
from agents.ecosystem.privacy_s3_erasure import (
    FencedS3Adapter,
    FencedS3ErasureOrchestrator,
    S3ErasureError,
    S3ErasurePhaseV1,
    S3QuiescenceBlocked,
    S3QuiescenceAssessment,
    S3QuiescenceCoordinator,
    S3VersionRef,
)


DOCUMENT_PHASE = "DOCUMENT_S3"
DOCUMENT_RETRY = "DOCUMENT_S3_RETRY"
DOCUMENT_REFERENCE_MISSING = "DOCUMENT_REFERENCE_MISSING"
OTHER_PHASES_PENDING = "OTHER_REQUIRED_PHASES_PENDING"


class DocumentErasureIntegrationError(RuntimeError):
    pass


class DocumentErasureBlocked(DocumentErasureIntegrationError):
    pass


@dataclass(frozen=True)
class DocumentReferenceV1:
    """Internal reference; object keys never enter public operation output."""

    resource_id: str
    document_id: str
    key: str
    version: int


def _opaque(value: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(value), sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


class _ScopedDocumentAdapter(FencedS3Adapter):
    """Restrict the existing C0F adapter to C1A-discovered document refs."""

    def __init__(self, delegate: FencedS3Adapter, allowed_keys: Iterable[str]):
        self.delegate = delegate
        self.allowed_keys = frozenset(allowed_keys)
        self.supports_fencing = bool(getattr(delegate, "supports_fencing", False))

    def inventory(self, *, attempt_id: str, cursor_ref: Optional[str] = None):
        page = self.delegate.inventory(attempt_id=attempt_id, cursor_ref=cursor_ref)
        objects, next_cursor = page if isinstance(page, tuple) else (page, None)
        refs = list(objects or [])
        # An object in the authorized prefix without a corresponding retained
        # CVDocument reference is not silently ignored.  Ignoring it could
        # turn a scope error into a false empty verification.
        if any(ref.key not in self.allowed_keys for ref in refs):
            raise DocumentErasureBlocked(DOCUMENT_REFERENCE_MISSING)
        return refs, next_cursor

    def delete_version(self, *, attempt_id: str, object_ref: S3VersionRef):
        if object_ref.key not in self.allowed_keys:
            raise DocumentErasureBlocked(DOCUMENT_REFERENCE_MISSING)
        return self.delegate.delete_version(attempt_id=attempt_id,
                                            object_ref=object_ref)


class DocumentErasureIntegration:
    """Connect C1A profile progress to the existing C0F S3 phase ledger."""

    def __init__(self, *, profile_executor: ProfileOnlyErasureExecutor,
                 profile_repository: Any, operation_repository: Any,
                 s3_orchestrator: FencedS3ErasureOrchestrator,
                 phases: Any, adapter: FencedS3Adapter,
                 document_key: Optional[Callable[[Any, ErasureOperationV1], str]] = None,
                 quiescence: Optional[S3QuiescenceCoordinator] = None):
        self.profile_executor = profile_executor
        self.profiles = profile_repository
        self.operations = operation_repository
        self.s3 = s3_orchestrator
        self.phases = phases
        self.adapter = adapter
        self.document_key = document_key or self._default_key
        self.quiescence = quiescence
        self.last_s3_result: Optional[Dict[str, Any]] = None

    @staticmethod
    def _default_key(document: Any, operation: ErasureOperationV1) -> str:
        document_id = getattr(document, "document_id", None)
        if not document_id:
            raise DocumentErasureBlocked(DOCUMENT_REFERENCE_MISSING)
        return (f"tenant/{operation.tenant_id}/users/{operation.user_id}/"
                f"documents/{document_id}")

    @staticmethod
    def _scope_context(operation: ErasureOperationV1) -> Dict[str, str]:
        return {"userId": operation.user_id, "tenantId": operation.tenant_id,
                "partnerApplicationId": operation.partner_application_id,
                "issuer": operation.issuer}

    @staticmethod
    def _context_for(ctx: ErasureExecutionContextV1,
                     operation: ErasureOperationV1) -> ErasureExecutionContextV1:
        return replace(ctx, operation_version=operation.version)

    def _profiles_done(self, operation: ErasureOperationV1) -> bool:
        required = ("atsSearchProfiles", "cvSearchProfiles",
                    "manualSearchProfiles", "userProfile")
        if self.profile_executor.applications is not None:
            required += ("applications",)
        return all(operation.progress.get(name, ErasureProgressV1()).status
                   in (PROGRESS_COMPLETED, PROGRESS_SKIPPED) for name in required)

    @staticmethod
    def _local_operation_complete(operation: ErasureOperationV1) -> bool:
        """Only complete an explicitly local operation with no open category."""
        return bool(operation.progress) and all(
            progress.status in (PROGRESS_COMPLETED, PROGRESS_SKIPPED)
            for progress in operation.progress.values())

    def _save(self, operation: ErasureOperationV1,
              progress: ErasureProgressV1) -> ErasureOperationV1:
        return self.operations.save_checkpoint(
            operation.operation_id, "cvDocuments", progress,
            expected_version=operation.version,
            context=self._scope_context(operation))

    def _mark_partial(self, operation: ErasureOperationV1,
                      *, error_code: str,
                      update_document: bool = True) -> ErasureOperationV1:
        if operation.status != STATUS_RUNNING:
            if operation.status == STATUS_PARTIAL and update_document:
                old = operation.progress.get("cvDocuments", ErasureProgressV1())
                checkpoint = old.checkpoint or ErasureCheckpointV1(
                    phase=DOCUMENT_PHASE, state=CHECKPOINT_IN_PROGRESS)
                return self._save(operation, ErasureProgressV1(
                    status=PROGRESS_PARTIAL, affected=old.affected,
                    checkpoint=checkpoint, error_code=error_code,
                    retryable=True))
            return operation
        if update_document:
            old = operation.progress.get("cvDocuments", ErasureProgressV1())
            checkpoint = old.checkpoint or ErasureCheckpointV1(
                phase=DOCUMENT_PHASE, state=CHECKPOINT_IN_PROGRESS)
            operation = self._save(operation, ErasureProgressV1(
                status=PROGRESS_PARTIAL, affected=old.affected,
                checkpoint=checkpoint, error_code=error_code, retryable=True))
        partial = operation.transition(STATUS_PARTIAL,
                                       now=operation.updated_at or operation.created_at,
                                       error_code=error_code)
        return self.operations.update(partial, expected_version=operation.version,
                                      context=self._scope_context(operation))

    def _resume_running(self, operation: ErasureOperationV1,
                        context: ErasureExecutionContextV1
                        ) -> Tuple[ErasureOperationV1, ErasureExecutionContextV1]:
        if operation.status == STATUS_RUNNING:
            return operation, context
        if operation.status == STATUS_COMPLETED:
            raise DocumentErasureBlocked("completed operation cannot resume")
        operation = self.operations.resume(operation.operation_id,
                                           context=self._scope_context(operation))
        return operation, self._context_for(context, operation)

    def _documents(self, operation: ErasureOperationV1) -> List[Tuple[Any, DocumentReferenceV1]]:
        cursor = None
        found: List[Tuple[Any, DocumentReferenceV1]] = []
        while True:
            items, cursor = self.profiles.list_by_user(
                operation.user_id, operation.tenant_id,
                resource_type="CVDocument",
                partner_app_id=operation.partner_application_id,
                issuer=operation.issuer, limit=50, cursor=cursor)
            for document in items:
                if operation.scope == "CV" and getattr(document, "cv_id", None) != operation.cv_id:
                    continue
                document_id = getattr(document, "document_id", None)
                if not document_id:
                    raise DocumentErasureBlocked(DOCUMENT_REFERENCE_MISSING)
                found.append((document, DocumentReferenceV1(
                    resource_id=getattr(document, "cv_id", None) or document_id,
                    document_id=document_id, key=self.document_key(document, operation),
                    version=int(getattr(document, "version", 1) or 1))))
            if not cursor:
                return found

    def _phase(self, context: ErasureExecutionContextV1) -> Optional[S3ErasurePhaseV1]:
        getter = getattr(self.phases, "get", None)
        return getter(context) if callable(getter) else None

    def _delete_metadata(self, operation: ErasureOperationV1,
                         context: ErasureExecutionContextV1,
                         docs: List[Tuple[Any, DocumentReferenceV1]]) -> ErasureOperationV1:
        old = operation.progress.get("cvDocuments", ErasureProgressV1())
        affected = old.affected
        for document, ref in docs:
            try:
                result = self.profiles.delete(
                    ref.resource_id, user_id=operation.user_id,
                    tenant_id=operation.tenant_id,
                    partner_app_id=operation.partner_application_id,
                    issuer=operation.issuer, expected_version=ref.version)
                if result is False:
                    # Replay after a committed metadata delete is safe.
                    current = self.profiles.get(ref.resource_id,
                                                operation.user_id,
                                                operation.tenant_id,
                                                operation.partner_application_id,
                                                operation.issuer)
                    if current is not None:
                        raise DocumentErasureIntegrationError("document metadata mutation conflict")
            except Exception as exc:
                raise DocumentErasureIntegrationError("document metadata deletion failed") from exc
            affected += 1
            cp = ErasureCheckpointV1(
                phase=DOCUMENT_PHASE, state=CHECKPOINT_IN_PROGRESS,
                cursor_ref=_opaque({"documentId": ref.document_id}),
                last_resource_ref=ref.resource_id, updated_at=operation.updated_at)
            operation = self._save(operation, ErasureProgressV1(
                status=PROGRESS_PARTIAL, affected=affected, checkpoint=cp,
                error_code=DOCUMENT_RETRY, retryable=True))
            context = self._context_for(context, operation)
        cp = ErasureCheckpointV1(
            phase=DOCUMENT_PHASE, state=CHECKPOINT_COMPLETED,
            last_resource_ref=docs[-1][1].resource_id if docs else None,
            updated_at=operation.updated_at)
        return self._save(operation, ErasureProgressV1(
            status=PROGRESS_COMPLETED, affected=affected, checkpoint=cp))

    def run(self, operation: ErasureOperationV1,
            context: ErasureExecutionContextV1,
            *, assessment: Optional[S3QuiescenceAssessment] = None,
            lease: Any = None,
            final_assessment: Optional[S3QuiescenceAssessment] = None
            ) -> ErasureOperationV1:
        """Run/resume C1A then C0F; leave unresolved work as PARTIAL/RETRY."""
        operation, context = self._resume_running(operation, context)
        if not self._profiles_done(operation):
            operation = self.profile_executor.run(operation, context)
            # C1A intentionally ends at a document-pending boundary.  Resume
            # the same existing operation for the C0F phase; no second engine
            # or new operation identity is created.
            operation, context = self._resume_running(operation, context)
            if not self._profiles_done(operation):
                return self._mark_partial(operation, error_code="PROFILE_PHASE_PENDING")

        try:
            docs = self._documents(operation)
        except DocumentErasureBlocked:
            return self._mark_partial(operation, error_code=DOCUMENT_REFERENCE_MISSING)
        if not getattr(self.adapter, "supports_fencing", False):
            return self._mark_partial(operation, error_code="S3_FENCING_UNAVAILABLE")
        if self.quiescence:
            if assessment is None or not assessment.ready:
                return self._mark_partial(operation, error_code="S3_QUIESCENCE_BLOCKED")
            if lease is None:
                return self._mark_partial(operation, error_code="S3_QUIESCENCE_BLOCKED")
            self.quiescence.assert_current(lease)

        scoped = _ScopedDocumentAdapter(self.adapter, (ref.key for _, ref in docs))
        previous_adapter = self.s3.adapter
        self.s3.adapter = scoped
        try:
            phase = self._phase(context)
            expected = phase.version if phase is not None else 0
            if phase is not None and phase.phase == "COMPLETED":
                s3_result = {"complete": True, "phase": "COMPLETED", "remaining": 0}
            else:
                s3_result = self.s3.run(context, expected_version=expected,
                                        attempt_id=phase.attempt_id if phase else None)
            self.last_s3_result = s3_result
            if not s3_result.get("complete"):
                return self._mark_partial(operation, error_code=DOCUMENT_RETRY)
            if self.quiescence:
                if final_assessment is None or not final_assessment.ready:
                    return self._mark_partial(operation, error_code=DOCUMENT_RETRY)
                self.quiescence.complete(lease=lease,
                                         final_assessment=final_assessment)
            operation = self._delete_metadata(operation, context, docs)
        except (S3ErasureError, DocumentErasureIntegrationError, S3QuiescenceBlocked):
            return self._mark_partial(operation, error_code=DOCUMENT_RETRY)
        finally:
            self.s3.adapter = previous_adapter

        if operation.status == STATUS_RUNNING:
            if self._local_operation_complete(operation):
                completed = operation.transition(
                    STATUS_COMPLETED,
                    now=operation.updated_at or operation.created_at)
                operation = self.operations.update(
                    completed, expected_version=operation.version,
                    context=self._scope_context(operation))
            else:
                # Other G5 phases are intentionally outside C1B.  Do not claim
                # complete merely because profile+document work passed.
                operation = self._mark_partial(
                    operation, error_code=OTHER_PHASES_PENDING,
                    update_document=False)
        return operation


__all__ = ["DocumentReferenceV1", "DocumentErasureIntegration",
           "DocumentErasureIntegrationError", "DocumentErasureBlocked",
           "DOCUMENT_PHASE", "DOCUMENT_RETRY", "DOCUMENT_REFERENCE_MISSING"]
