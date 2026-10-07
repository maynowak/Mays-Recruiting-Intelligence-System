"""
Regression tests for entitlement window validation (fail-open fix).

`_is_entitlement_valid` previously compared a naive `datetime.utcnow()`
against offset-bearing bounds. That raised TypeError, which the same
`except` clause caught as a parse failure and swallowed, so ANY
offset-bearing window (`Z`, `+00:00`, any offset) evaluated as VALID —
including long-expired and not-yet-valid entitlements.

These tests pin both directions and assert parity with the worker-side
re-check, which was already correct.

Gate: RIS-TRUTH-RECOVERY-01 follow-up (authorization fail-open).
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lambda'))

from handler import _is_entitlement_valid
from agents.ecosystem.worker_authorization import (
    is_entitlement_valid as worker_is_entitlement_valid,
)

NOW = datetime.now(timezone.utc)


def _naive_iso(moment):
    """Deliberately NAIVE UTC string.

    This test asserts that naive entitlement windows are still honoured,
    so it must keep producing the legacy naive form. Built from an aware
    instant with the offset stripped, which is byte-identical to the
    old datetime.utcnow().isoformat() without using it.
    """
    return moment.astimezone(timezone.utc).replace(tzinfo=None).isoformat()


def _offset(delta_days):
    return (NOW + timedelta(days=delta_days)).isoformat()


def _naive(delta_days):
    return _naive_iso(datetime.now(timezone.utc) + timedelta(days=delta_days))


class TestOffsetAwareWindowsAreEnforced:
    """The defect: offset-bearing bounds must NOT be silently ignored."""

    def test_expired_offset_window_is_rejected(self):
        assert _is_entitlement_valid(
            {'validUntil': '2020-01-01T00:00:00+00:00'}) is False

    def test_expired_zulu_window_is_rejected(self):
        assert _is_entitlement_valid(
            {'validUntil': '2020-01-01T00:00:00Z'}) is False

    def test_future_validfrom_offset_is_rejected(self):
        assert _is_entitlement_valid({'validFrom': _offset(30)}) is False

    def test_future_validfrom_zulu_is_rejected(self):
        assert _is_entitlement_valid(
            {'validFrom': (NOW + timedelta(days=30)).strftime(
                '%Y-%m-%dT%H:%M:%SZ')}) is False

    def test_nonzero_offset_is_normalized(self):
        """+02:00 must be interpreted as UTC, not compared naively."""
        # 23:00 at +02:00 == 21:00Z; relative to NOW this is the past,
        # so an already-started window must be accepted.
        past_local = datetime.now(timezone(timedelta(hours=2))) - timedelta(days=1)
        assert _is_entitlement_valid(
            {'validFrom': past_local.isoformat()}) is True

    def test_past_offset_validfrom_is_accepted(self):
        assert _is_entitlement_valid({'validFrom': _offset(-30)}) is True

    def test_future_offset_validuntil_is_accepted(self):
        assert _is_entitlement_valid({'validUntil': _offset(30)}) is True


class TestNaiveWindowsStillWork:
    """Regression guard: existing naive behaviour is unchanged."""

    def test_future_naive_validfrom_rejected(self):
        assert _is_entitlement_valid({'validFrom': _naive(30)}) is False

    def test_past_naive_validfrom_accepted(self):
        assert _is_entitlement_valid({'validFrom': _naive(-30)}) is True

    def test_past_naive_validuntil_rejected(self):
        assert _is_entitlement_valid({'validUntil': _naive(-30)}) is False

    def test_future_naive_validuntil_accepted(self):
        assert _is_entitlement_valid({'validUntil': _naive(30)}) is True


class TestAbsentAndUnparsableBounds:
    def test_no_bounds_is_valid(self):
        assert _is_entitlement_valid({'agentId': 'a'}) is True

    def test_unparsable_bound_is_ignored(self):
        """Documented contract: unparsable == no bound (not fail-closed)."""
        assert _is_entitlement_valid({'validFrom': 'not-a-date'}) is True


class TestIngressWorkerParity:
    """Ingress must never be MORE permissive than the worker re-check.

    Worker authorization is the last gate before execution; if ingress
    grants something the worker denies, the caller gets a confusing 403
    at execution time and the two gates disagree about authorization.
    """

    @pytest.mark.parametrize('entitlement', [
        {'validUntil': '2020-01-01T00:00:00+00:00'},
        {'validUntil': '2020-01-01T00:00:00Z'},
        {'validFrom': (NOW + timedelta(days=365)).isoformat()},
        {'validUntil': (NOW - timedelta(days=365)).isoformat()},
    ], ids=['expired-offset', 'expired-zulu', 'future-from', 'expired-until'])
    def test_parity(self, entitlement):
        assert _is_entitlement_valid(entitlement) == worker_is_entitlement_valid(
            entitlement, NOW)

    @pytest.mark.parametrize('entitlement', [
        {'validFrom': (NOW - timedelta(days=1)).isoformat()},
        {'validUntil': (NOW + timedelta(days=1)).isoformat()},
        {'validFrom': (NOW - timedelta(days=1)).isoformat(),
         'validUntil': (NOW + timedelta(days=1)).isoformat()},
        {},
    ], ids=['started', 'not-expired', 'window', 'no-bounds'])
    def test_parity_positive(self, entitlement):
        assert _is_entitlement_valid(entitlement) == worker_is_entitlement_valid(
            entitlement, NOW)