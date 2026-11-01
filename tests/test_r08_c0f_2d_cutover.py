"""R08-C0F-2D legacy upload-ticket cutover tests."""

from datetime import datetime, timezone
import os
import sys
from pathlib import Path

import pytest

from agents.ecosystem.privacy_s3_erasure import (
    InMemoryS3QuiescenceLeaseStore, S3QuiescenceCoordinator)
from agents.ecosystem.privacy_upload_cutover import (
    CUTOVER_BLOCKED, CUTOVER_PROVEN, UploadCutoverConflict,
    UploadCutoverEvidenceV1, UploadCutoverRepository, UploadCutoverStateV1)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def evidence(**changes):
    values = dict(
        expected_issuers=("issuer-a",), covered_issuers=("issuer-a",),
        expected_paths=("cv-upload",), covered_paths=("cv-upload",),
        ledger_registration_verified=True, unknown_legacy_tickets=False,
        historical_max_expiry="2025-12-31T23:00:00+00:00",
        active_actions_known_zero=True, inventory_complete=True,
        inventory_empty=True, evidence_ref="cutover-evidence-1")
    values.update(changes)
    return UploadCutoverEvidenceV1(**values)


def state(ev):
    return UploadCutoverStateV1(
        cutover_id="cutover-1", introduced_at="2025-01-01T00:00:00+00:00",
        effective_at=None, status=CUTOVER_BLOCKED, version=1, evidence=ev)


def test_cutover_proves_only_complete_known_expired_population():
    proven = state(evidence()).evaluate(now=NOW)
    assert proven.status == CUTOVER_PROVEN
    assert state(evidence(historical_max_expiry=None)).evaluate(
        now=NOW).status == CUTOVER_BLOCKED
    assert state(evidence(unknown_legacy_tickets=True)).evaluate(
        now=NOW).status == CUTOVER_BLOCKED
    assert state(evidence(covered_issuers=())).evaluate(
        now=NOW).status == CUTOVER_BLOCKED


def test_cutover_does_not_treat_expiry_as_inventory_or_action_proof():
    blocked = state(evidence(active_actions_known_zero=False,
                             inventory_complete=False,
                             inventory_empty=False)).evaluate(now=NOW)
    assert blocked.status == CUTOVER_BLOCKED
    reasons = blocked.evidence.reasons(now=NOW)
    assert "ACTIVE_UPLOAD_ACTIONS_UNKNOWN_OR_PRESENT" in reasons
    assert "FINAL_INVENTORY_INCOMPLETE" in reasons
    coordinator = S3QuiescenceCoordinator(
        lease_store=InMemoryS3QuiescenceLeaseStore(), enabled=True)
    assessment = coordinator.assess(
        freeze_active=True, new_tickets_blocked=True, tickets=[],
        active_actions=0, inventory_complete=True, inventory_empty=True,
        cutover_proven=False)
    assert not assessment.ready
    assert "UPLOAD_TICKET_CUTOVER_UNPROVEN" in assessment.reasons


class Table:
    def __init__(self):
        self.items = {}

    def put_item(self, **kwargs):
        key = kwargs["Item"]["resourceId"]
        if key in self.items:
            raise Exception("ConditionalCheckFailedException")
        self.items[key] = kwargs["Item"]


def test_cutover_repository_is_versioned_and_replay_conflicts():
    table = Table()
    repo = UploadCutoverRepository(table=table, table_name="cutovers", enabled=True)
    first = state(evidence())
    repo.save(first, expected_version=0)
    with pytest.raises(UploadCutoverConflict):
        repo.save(first, expected_version=0)


def test_legacy_generic_issuer_is_blocked_at_cutover(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "lambda"))
    import handler
    monkeypatch.setenv("ERASURE_UPLOAD_CUTOVER_ENABLED", "true")
    response = handler._handle_documents_create({}, None)
    assert response["statusCode"] == 503
