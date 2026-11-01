"""C1B local-only integration tests using synthetic profile/S3 stores."""

from dataclasses import replace

import pytest

from agents.ecosystem.privacy_document_erasure import (
    DOCUMENT_REFERENCE_MISSING, DocumentErasureBlocked,
    DocumentErasureIntegration)
from agents.ecosystem.privacy_erasure_contract import (
    ErasureCheckpointV1, ErasureProgressV1, ErasureExecutionContextV1,
    PROGRESS_COMPLETED, PROGRESS_PARTIAL, STATUS_RUNNING)
from agents.ecosystem.privacy_s3_erasure import (
    FencedS3Adapter, FencedS3ErasureOrchestrator, PHASE_ACTION_STARTED,
    PHASE_COMPLETED, PHASE_INVENTORY, PHASE_RETRY, S3ErasurePhaseV1,
    S3VersionRef, InMemoryS3QuiescenceLeaseStore, S3QuiescenceCoordinator)
from agents.ecosystem.privacy_profile_erasure import ProfileOnlyErasureExecutor
from tests.test_r08_c1a_profile_only_erasure import (
    OperationFake, Profiles, item, make)


class PhaseFake:
    def __init__(self):
        self.phase = None

    def get(self, ctx):
        return self.phase

    def begin(self, ctx, *, expected_version, attempt_id=None):
        if self.phase is None:
            assert expected_version == 0
            self.phase = S3ErasurePhaseV1(
                operation_id=ctx.operation_id, scope=ctx.scope,
                operation_version=ctx.operation_version,
                freeze_version=ctx.freeze_version,
                attempt_id=attempt_id or "attempt-1", phase=PHASE_INVENTORY)
        else:
            assert expected_version == self.phase.version
            assert self.phase.phase in (PHASE_RETRY, PHASE_ACTION_STARTED)
            self.phase = replace(self.phase, phase=PHASE_INVENTORY,
                                 version=self.phase.version + 1,
                                 attempt_id=attempt_id or "attempt-2")
        return self.phase

    def record(self, ctx, phase, *, action, outcome, next_phase,
               error_code=None, remaining=None):
        assert phase.version == self.phase.version
        self.phase = replace(phase, phase=next_phase, version=phase.version + 1,
                             last_action=action, last_outcome=outcome,
                             error_code=error_code, remaining=remaining)
        return self.phase


class S3Fake(FencedS3Adapter):
    supports_fencing = True

    def __init__(self, objects, *, fail=False):
        self.objects = list(objects)
        self.deleted = []
        self.fail = fail
        self.calls = 0

    def inventory(self, *, attempt_id, cursor_ref=None):
        self.calls += 1
        return list(self.objects), None

    def delete_version(self, *, attempt_id, object_ref):
        if self.fail:
            raise TimeoutError("unknown fake S3 result")
        self.deleted.append(object_ref)
        self.objects = [ref for ref in self.objects
                        if not (ref.key == object_ref.key
                                and ref.version_id == object_ref.version_id)]


def make_integration(objects, *, fail=False, with_document=True):
    profile_items = {
        "cv1": item("cv1", "CVDocument", cvId="cv1", documentId="doc-1"),
    }
    if not with_document:
        profile_items["cv1"].pop("documentId")
    profiles = Profiles(profile_items)
    operation, context = make("USER")
    store = OperationFake(operation)
    profile_executor = ProfileOnlyErasureExecutor(
        profile_repository=profiles, operation_repository=store,
        delete_user_profile=lambda *args, **kwargs: None)
    phases = PhaseFake()
    adapter = S3Fake(objects, fail=fail)
    s3 = FencedS3ErasureOrchestrator(phases=phases, adapter=adapter, enabled=True)
    integration = DocumentErasureIntegration(
        profile_executor=profile_executor, profile_repository=profiles,
        operation_repository=store, s3_orchestrator=s3, phases=phases,
        adapter=adapter)
    return integration, store, profiles, adapter, context


def test_user_document_versions_and_delete_marker_are_reinventoried_before_metadata_delete():
    refs = [S3VersionRef("tenant/t1/users/u1/documents/doc-1", "v1"),
            S3VersionRef("tenant/t1/users/u1/documents/doc-1", "dm1", True)]
    integration, store, profiles, adapter, context = make_integration(refs)
    result = integration.run(store.operation, context)
    assert len(adapter.deleted) == 2
    assert adapter.calls >= 2
    assert "cv1" not in profiles.items
    assert result.progress["cvDocuments"].status == PROGRESS_COMPLETED
    assert result.status == "PARTIAL"  # other G5 categories remain open


def test_unknown_s3_result_keeps_metadata_and_retry_boundary():
    refs = [S3VersionRef("tenant/t1/users/u1/documents/doc-1", "v1")]
    integration, store, profiles, adapter, context = make_integration(refs, fail=True)
    result = integration.run(store.operation, context)
    assert result.status == "PARTIAL"
    assert result.progress["cvDocuments"].status == PROGRESS_PARTIAL
    assert "cv1" in profiles.items
    assert integration.last_s3_result is None
    assert store.operation.progress["cvDocuments"].retryable is True


def test_missing_document_reference_blocks_before_s3():
    integration, store, profiles, adapter, context = make_integration([], with_document=False)
    result = integration.run(store.operation, context)
    assert result.status == "PARTIAL"
    assert result.progress["cvDocuments"].error_code == DOCUMENT_REFERENCE_MISSING
    assert adapter.calls == 0


def test_scope_adapter_rejects_unmapped_objects_instead_of_false_empty():
    refs = [S3VersionRef("tenant/t1/users/u1/documents/other", "v1")]
    integration, store, profiles, adapter, context = make_integration(refs)
    result = integration.run(store.operation, context)
    assert result.status == "PARTIAL"
    assert "cv1" in profiles.items


def test_retry_resume_after_unknown_s3_result_then_releases_metadata():
    refs = [S3VersionRef("tenant/t1/users/u1/documents/doc-1", "v1")]
    integration, store, profiles, adapter, context = make_integration(refs, fail=True)
    first = integration.run(store.operation, context)
    assert first.progress["cvDocuments"].status == PROGRESS_PARTIAL
    adapter.fail = False
    resumed_context = replace(context, operation_version=store.operation.version)
    second = integration.run(store.operation, resumed_context)
    assert second.progress["cvDocuments"].status == PROGRESS_COMPLETED
    assert "cv1" not in profiles.items
    assert second.status == "PARTIAL"


def test_quiescence_block_is_partial_and_prevents_s3_call():
    refs = [S3VersionRef("tenant/t1/users/u1/documents/doc-1", "v1")]
    integration, store, profiles, adapter, context = make_integration(refs)
    coordinator = S3QuiescenceCoordinator(
        lease_store=InMemoryS3QuiescenceLeaseStore(), enabled=True)
    integration.quiescence = coordinator
    blocked = coordinator.assess(
        freeze_active=True, new_tickets_blocked=False, tickets=[],
        active_actions=0, inventory_complete=True, inventory_empty=True)
    result = integration.run(store.operation, context, assessment=blocked)
    assert result.status == "PARTIAL"
    assert result.progress["cvDocuments"].error_code == "S3_QUIESCENCE_BLOCKED"
    assert adapter.calls == 0
