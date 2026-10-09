import pytest
from datetime import datetime, timedelta, timezone
from agents.health.contract import HealthState, HealthStatus, evaluate_overall, validate_state


def make_state(status, seconds_valid=3600):
    now = datetime.now(timezone.utc)
    return HealthState(
        component_id="comp-1",
        component_type="lambda",
        status=status,
        observed_at=now,
        valid_until=now + timedelta(seconds=seconds_valid),
        source="test"
    )


def test_valid_alive():
    s = make_state(HealthStatus.ALIVE, 3600)
    assert s.is_valid()


def test_expired_alive():
    s = make_state(HealthStatus.ALIVE, -10)
    assert not s.is_valid()
    assert s.is_expired()


def test_non_alive_invalid():
    s = make_state(HealthStatus.DEGRADED, 3600)
    assert not s.is_valid()


def test_evaluate_overall_ok():
    states = [make_state(HealthStatus.ALIVE, 3600) for _ in range(3)]
    assert evaluate_overall(states) is True


def test_evaluate_overall_missing():
    assert evaluate_overall([]) is False


def test_evaluate_overall_stale():
    states = [make_state(HealthStatus.ALIVE, 3600), make_state(HealthStatus.ALIVE, -1)]
    assert evaluate_overall(states) is False


def test_validate_state_ok():
    s = make_state(HealthStatus.ALIVE)
    validate_state(s)


def test_validate_state_bad_timestamps():
    now = datetime.now(timezone.utc)
    s = HealthState("c", "t", HealthStatus.ALIVE, now + timedelta(hours=1), now, "src")
    with pytest.raises(ValueError):
        validate_state(s)
