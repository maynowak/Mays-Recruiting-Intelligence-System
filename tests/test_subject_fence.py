import pytest

from agents.runtime.subject_fence import (
    SubjectFenceBlocked,
    SubjectFenceUnavailable,
    assert_fence_clear,
    fence_item,
    subject_fence_key,
)


class Table:
    def __init__(self, item=None, error=None):
        self.item = item
        self.error = error

    def get_item(self, Key):
        if self.error:
            raise self.error
        return {"Item": self.item} if self.item else {}


def test_fence_key_is_stable_and_scope_bound():
    first = subject_fence_key(user_id="u", tenant_id="t")
    assert first == subject_fence_key(user_id="u", tenant_id="t")
    assert first != subject_fence_key(user_id="u", tenant_id="other")


def test_active_fence_blocks_admission():
    with pytest.raises(SubjectFenceBlocked):
        assert_fence_clear(Table(fence_item(user_id="u", tenant_id="t")),
                           user_id="u", tenant_id="t")


def test_corrupt_or_unavailable_fence_fails_closed():
    with pytest.raises(SubjectFenceUnavailable):
        assert_fence_clear(Table({"workId": "wrong"}), user_id="u", tenant_id="t")
    with pytest.raises(SubjectFenceUnavailable):
        assert_fence_clear(Table(error=RuntimeError("store down")),
                           user_id="u", tenant_id="t")
