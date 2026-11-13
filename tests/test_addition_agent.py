"""G03 tests — Addition Agent (RIS-MO-ADDITION-AGENT-E2E-01).

Local only: no AWS, no network, no credentials.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.addition_agent import (
    ADDITION_AGENT_ID,
    ADDITION_CAPABILITY,
    ADDITION_WORK_TYPE,
    AdditionAgent,
    AdditionInputError,
    add_operands,
    create_addition_handler,
    get_addition_descriptor,
    is_addition_registered,
    register_addition_agent,
)
from agents.agent_body import AgentBody
from agents.ecosystem.registry import AgentRegistry, AgentStatus


def work_item(left, right, **overrides):
    item = {
        "workId": "work-add-1",
        "type": ADDITION_WORK_TYPE,
        "tenantId": "tenant-a",
        "idempotencyKey": "idem-1",
        "agentId": ADDITION_AGENT_ID,
        "capability": ADDITION_CAPABILITY,
        "payload": {"left": left, "right": right},
    }
    item.update(overrides)
    return item


class TestAdditionMath:
    def test_reference_case_17_plus_25_is_42(self):
        assert add_operands(17, 25) == {"left": 17, "right": 25, "sum": 42}

    def test_deterministic_across_repeats(self):
        results = [add_operands(17, 25) for _ in range(50)]
        assert all(r == {"left": 17, "right": 25, "sum": 42} for r in results)

    def test_negative_and_zero_operands(self):
        assert add_operands(-5, 5)["sum"] == 0
        assert add_operands(0, 0)["sum"] == 0
        assert add_operands(-10, -15)["sum"] == -25

    def test_float_operands_are_exact_not_binary_artifacts(self):
        # 0.1 + 0.2 must not surface 0.30000000000000004
        assert add_operands(0.1, 0.2)["sum"] == 0.3

    def test_int_plus_float_renders_json_number(self):
        result = add_operands(2, 0.5)
        assert result == {"left": 2, "right": 0.5, "sum": 2.5}

    def test_result_is_json_serializable(self):
        payload = json.dumps(add_operands(17, 25))
        assert json.loads(payload) == {"left": 17, "right": 25, "sum": 42}

    @pytest.mark.parametrize("left,right", [
        (None, 25),
        (17, None),
        ("17", 25),
        (17, "25"),
        (True, 25),
        (17, False),
        ([], 1),
        (17, {}),
    ])
    def test_invalid_operands_are_rejected(self, left, right):
        with pytest.raises(AdditionInputError):
            add_operands(left, right)

    @pytest.mark.parametrize("left,right", [
        (float("inf"), 1),
        (1, float("-inf")),
        (float("nan"), 1),
    ])
    def test_non_finite_operands_are_rejected(self, left, right):
        with pytest.raises(AdditionInputError):
            add_operands(left, right)


class TestAdditionAgentContract:
    def test_process_work_returns_reference_result(self):
        agent = AdditionAgent()
        result = agent.process_work(work_item(17, 25))
        assert result["success"] is True
        assert result["data"] == {"left": 17, "right": 25, "sum": 42}
        assert result["metrics"]["agentVersion"] == "1.0.0"
        assert result["metrics"]["capability"] == ADDITION_CAPABILITY

    def test_process_work_repeat_is_identical(self):
        agent = AdditionAgent()
        first = agent.process_work(work_item(17, 25))
        second = agent.process_work(work_item(17, 25))
        assert first == second

    def test_unknown_capability_fails_closed(self):
        agent = AdditionAgent()
        result = agent.process_work(work_item(17, 25, capability="math.divide"))
        assert result["success"] is False
        assert result["error"]["type"] == "ValidationError"

    def test_missing_payload_returns_validation_error(self):
        agent = AdditionAgent()
        item = work_item(17, 25)
        item.pop("payload")
        result = agent.process_work(item)
        assert result["success"] is False
        assert result["error"]["type"] == "ValidationError"

    def test_invalid_operand_returns_validation_error_not_exception(self):
        agent = AdditionAgent()
        result = agent.process_work(work_item("seventeen", 25))
        assert result["success"] is False
        assert "finite number" in result["error"]["message"]

    def test_validate_work_accepts_valid_item(self):
        assert AdditionAgent().validate_work(work_item(17, 25)) is True

    def test_validate_work_rejects_missing_identity_fields(self):
        item = work_item(17, 25)
        item.pop("tenantId")
        assert AdditionAgent().validate_work(item) is False


class TestAdditionRegistration:
    def test_descriptor_is_active_with_math_add(self):
        descriptor = get_addition_descriptor()
        assert descriptor.agent_id == ADDITION_AGENT_ID
        assert descriptor.status is AgentStatus.ACTIVE
        assert descriptor.capabilities == [ADDITION_CAPABILITY]

    def test_registration_is_idempotent(self):
        registry = AgentRegistry()
        body = AgentBody()
        register_addition_agent(registry, body)
        register_addition_agent(registry, body)
        assert is_addition_registered(registry) is True
        assert len(registry.list_by_capability(ADDITION_CAPABILITY)) == 1

    def test_executes_through_existing_agent_body(self):
        """Acceptance: runnable via the existing Agent Run Body and returns 42."""
        registry = AgentRegistry()
        body = AgentBody()
        register_addition_agent(registry, body)

        result = body.execute(work_item(17, 25))

        assert result["success"] is True
        assert result["data"] == {"left": 17, "right": 25, "sum": 42}

    def test_body_routes_by_capability_without_agent_id(self):
        registry = AgentRegistry()
        body = AgentBody()
        register_addition_agent(registry, body)

        item = work_item(17, 25)
        item.pop("agentId")
        item["type"] = "agent_unknown"

        result = body.execute(item)
        assert result["data"]["sum"] == 42


class TestAdditionLambdaParity:
    def test_handler_processes_sqs_records(self):
        handler = create_addition_handler()
        event = {"Records": [{"messageId": "m1", "body": json.dumps(work_item(17, 25))}]}
        response = handler(event, None)
        body = json.loads(response["body"])
        assert body["processed"] == 1
        assert body["results"][0]["result"]["data"]["sum"] == 42
