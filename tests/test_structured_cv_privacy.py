"""Privacy lifecycle integration tests for structured CV profiles."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.ecosystem.privacy_erasure import PrivacyErasure


def test_structured_cv_erasure_runs_as_a_separate_idempotent_step():
    calls = []

    def erase(user_id, tenant_id):
        calls.append((user_id, tenant_id))
        return 2

    result = PrivacyErasure(structured_cv_eraser=erase).erase("user-1", tenant_id="tenant-1")
    assert result.complete is True
    assert calls == [("user-1", "tenant-1")]
    step = next(item for item in result.steps
                if item.step == "erase-structured-cv-profiles")
    assert step.ok is True
    assert step.affected == 2


def test_structured_cv_step_is_absent_until_wired():
    result = PrivacyErasure().erase("user-1", tenant_id="tenant-1")
    assert result.complete is True
    assert not any(item.step == "erase-structured-cv-profiles"
                   for item in result.steps)


def test_structured_cv_failure_is_not_reported_as_complete():
    def fail(_user_id, _tenant_id):
        raise RuntimeError("storage unavailable")

    result = PrivacyErasure(structured_cv_eraser=fail).erase(
        "user-1", tenant_id="tenant-1")
    assert result.complete is False
    step = next(item for item in result.steps
                if item.step == "erase-structured-cv-profiles")
    assert step.ok is False
    assert step.error == "STRUCTURED_CV_ERASURE_FAILED"
