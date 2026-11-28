"""Unit coverage for typed capability data boundaries (synthetic only)."""

from agents.ecosystem.privacy_contract import (
    declaration_from_mapping, validate_capability_input,
    validate_capability_result,
)


def _addition_policy():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = root / "agent-installations" / "addition-agent" / "privacy-contract.json"
    return declaration_from_mapping(json.loads(path.read_text(encoding="utf-8")))


def test_addition_input_allows_only_typed_numeric_operands():
    policy = _addition_policy()
    assert validate_capability_input(policy, {"left": 17, "right": 25})
    assert not validate_capability_input(policy, {"left": "Ada Lovelace", "right": 25})
    assert not validate_capability_input(
        policy, {"left": 17, "right": 25, "cvText": "synthetic forbidden marker"}
    )
    assert not validate_capability_input(policy, {"left": True, "right": 25})


def test_addition_result_is_allowlisted_and_typed():
    policy = _addition_policy()
    assert validate_capability_result(
        policy, {"success": True, "data": {"left": 17, "right": 25, "sum": 42}}
    )
    assert not validate_capability_result(
        policy, {"success": True, "data": {"left": 17, "right": 25,
                                            "sum": 42, "personalNote": "synthetic"}}
    )
    assert not validate_capability_result(
        policy, {"success": True, "data": {"left": 17, "right": 25,
                                            "sum": "synthetic personal marker"}}
    )


def test_order_result_transport_has_a_narrower_allowlist():
    from agents.runtime.pipeline import _forward_order_result

    policy = _addition_policy()
    sent = []
    item = {"workId": "work-link1", "orderId": "ord_link1",
            "correlationId": "corr-link1", "apiProfileId": "profile-a"}
    result = {"success": True, "data": {"left": 17, "right": 25, "sum": 42}}
    assert _forward_order_result(
        table=None, item=item, attempt=1, result=result, sender=sent.append,
        privacy_declaration=policy,
    ) == "SENT"
    assert len(sent) == 1

    sent.clear()
    overbroad = {"success": True, "data": {"sum": 42,
                                            "personalNote": "synthetic marker"}}
    assert _forward_order_result(
        table=None, item=item, attempt=1, result=overbroad, sender=sent.append,
        privacy_declaration=policy,
    ) == "REJECTED"
    assert sent == []
