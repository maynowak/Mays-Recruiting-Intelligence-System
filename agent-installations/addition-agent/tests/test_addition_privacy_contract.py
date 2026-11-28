"""Addition capability privacy assertions using synthetic numeric inputs."""

import json
from pathlib import Path

from agents.addition_agent.agent import add_operands


ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "agent-installations" / "addition-agent" / "privacy-contract.json"


def test_declaration_limits_payload_to_numeric_operands_and_no_recipients():
    declaration = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert declaration["capability"] == "math.add"
    assert declaration["allowed_input_fields"] == ["left", "right"]
    assert declaration["external_recipients"] == []
    assert {"personal-data", "cv-content", "free-text"}.issubset(
        declaration["prohibited_inline_categories"]
    )


def test_result_body_is_limited_to_declared_numeric_fields():
    result = add_operands(17, 25)
    declaration = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert set(result) == {"left", "right", "sum"}
    assert declaration["allowed_result_fields"] == ["left", "right", "sum"]
    assert declaration["allowed_order_result_fields"] == ["left", "right", "sum"]
    assert result["sum"] == 42
