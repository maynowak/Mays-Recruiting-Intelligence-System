"""Local transaction-fake coverage for C1A profile-only erasure."""

from dataclasses import replace

from agents.ecosystem.privacy_erasure_contract import (
    ErasureExecutionContextV1, OPERATION_SCOPE_CV, OPERATION_SCOPE_USER,
    STATUS_RUNNING, new_operation)
from agents.ecosystem.privacy_profile_erasure import (
    DOCUMENT_PENDING, ProfileOnlyErasureExecutor)


class OperationFake:
    def __init__(self, operation):
        self.operation = operation

    def save_checkpoint(self, _operation_id, category, progress, *, expected_version, context):
        assert expected_version == self.operation.version
        assert context["userId"] == self.operation.user_id
        progress_map = dict(self.operation.progress)
        progress_map[category] = progress
        self.operation = replace(self.operation, progress=progress_map,
                                 version=self.operation.version + 1)
        return self.operation

    def update(self, operation, *, expected_version, context):
        assert expected_version == self.operation.version
        self.operation = operation
        return operation

    def resume(self, _operation_id, *, context):
        self.operation = replace(self.operation, status=STATUS_RUNNING,
                                 version=self.operation.version + 1)
        return self.operation


class Profiles:
    def __init__(self, items, page_size=1):
        self.items = dict(items)
        self.page_size = page_size
        self.deleted = []

    def _select(self, resource_type, parent=None):
        values = [v for v in self.items.values()
                  if v["resourceType"] == resource_type
                  and (parent is None or v.get("parentId") == parent)]
        return sorted(values, key=lambda x: x["resourceId"])

    def list_by_user(self, user_id, tenant_id, *, resource_type, partner_app_id,
                     issuer, limit, cursor=None):
        values = [v for v in self._select(resource_type)
                  if v["userId"] == user_id and v["tenantId"] == tenant_id]
        return self._page(values, limit, cursor)

    def list_by_parent(self, parent_id, user_id, tenant_id, *, resource_type,
                       partner_app_id, issuer, limit, cursor=None):
        values = [v for v in self._select(resource_type, parent_id)
                  if v["userId"] == user_id and v["tenantId"] == tenant_id]
        return self._page(values, limit, cursor)

    @staticmethod
    def _page(values, limit, cursor):
        after = (cursor or {}).get("after")
        start = next((i + 1 for i, value in enumerate(values)
                      if value["resourceId"] == after), 0) if after else 0
        page = values[start:start + limit]
        nxt = {"after": page[-1]["resourceId"]} if start + limit < len(values) else None
        return [type("Resource", (), {
            "ats_profile_id": x.get("atsProfileId"),
            "search_profile_id": x.get("searchProfileId"),
            "manual_profile_id": x.get("manualProfileId"),
            "cv_id": x.get("cvId"), "user_id": x.get("userId"),
            "version": x.get("version", 1)})() for x in page], nxt

    def delete(self, resource_id, **kwargs):
        assert kwargs["user_id"] == "u1"
        self.deleted.append(resource_id)
        self.items.pop(resource_id, None)
        return True

    def get(self, resource_id, *args):
        return self.items.get(resource_id)


def make(scope, cv_id=None):
    op = new_operation(operation_id="op1", idempotency_key="idem",
                       user_id="u1", tenant_id="t1", partner_application_id="p1",
                       issuer="issuer", scope=scope, cv_id=cv_id)
    op = replace(op, status=STATUS_RUNNING)
    ctx = ErasureExecutionContextV1(
        operation_id="op1", user_id="u1", tenant_id="t1",
        partner_application_id="p1", issuer="issuer", scope=scope,
        operation_version=1, freeze_version=1, cv_id=cv_id)
    return op, ctx


def item(rid, rt, **extra):
    return dict(resourceId=rid, resourceType=rt, userId="u1", tenantId="t1",
                version=1, **extra)


def test_user_scope_paginates_leaf_profiles_and_keeps_documents():
    profiles = Profiles({
        "ats1": item("ats1", "ATSSearchProfile", atsProfileId="ats1"),
        "man1": item("man1", "ManualSearchProfile", manualProfileId="man1"),
        "cv1": item("cv1", "CVDocument", cvId="cv1"),
    })
    op, ctx = make(OPERATION_SCOPE_USER)
    repo = OperationFake(op)
    deleted_profile = []
    result = ProfileOnlyErasureExecutor(
        profile_repository=profiles, operation_repository=repo,
        delete_user_profile=lambda user, tenant, context: deleted_profile.append(user),
        page_size=1).run(op, ctx)
    assert profiles.deleted == ["ats1", "man1"]
    assert deleted_profile == ["u1"]
    assert "cv1" in profiles.items
    assert result.status == "PARTIAL"
    assert result.progress["cvDocuments"].error_code == DOCUMENT_PENDING
    assert result.progress["cvDocuments"].retryable is True


def test_cv_scope_deletes_ats_and_cv_search_but_not_document():
    profiles = Profiles({
        "sp1": item("sp1", "CVSearchProfile", searchProfileId="sp1", cvId="cv1", parentId="cv1"),
        "ats1": item("ats1", "ATSSearchProfile", atsProfileId="ats1", searchProfileId="sp1", parentId="sp1"),
        "other": item("other", "CVSearchProfile", searchProfileId="other", cvId="cv2", parentId="cv2"),
        "doc": item("doc", "CVDocument", cvId="cv1"),
    })
    op, ctx = make(OPERATION_SCOPE_CV, "cv1")
    result = ProfileOnlyErasureExecutor(
        profile_repository=profiles, operation_repository=OperationFake(op),
        page_size=1).run(op, ctx)
    assert profiles.deleted == ["ats1", "sp1"]
    assert "doc" in profiles.items and "other" in profiles.items
    assert result.status == "PARTIAL"
    assert result.progress["userProfile"].status == "SKIPPED"


def test_resume_replays_checkpoint_without_document_completion():
    profiles = Profiles({
        "ats1": item("ats1", "ATSSearchProfile", atsProfileId="ats1"),
        "man1": item("man1", "ManualSearchProfile", manualProfileId="man1"),
    })
    op, ctx = make(OPERATION_SCOPE_USER)
    store = OperationFake(op)
    first = ProfileOnlyErasureExecutor(
        profile_repository=profiles, operation_repository=store,
        delete_user_profile=lambda *args, **kwargs: None, page_size=1)
    result = first.run(op, ctx)
    assert result.status == "PARTIAL"
    assert result.progress["atsSearchProfiles"].status == "COMPLETED"
    # Replaying the durable result is safe: all profile lists are now empty.
    resumed_ctx = replace(ctx, operation_version=store.operation.version)
    resumed = ProfileOnlyErasureExecutor(
        profile_repository=profiles, operation_repository=store,
        delete_user_profile=lambda *args, **kwargs: None, page_size=1).run(
            store.operation, resumed_ctx)
    assert resumed.status == "PARTIAL"
    assert profiles.deleted == ["ats1", "man1"]
