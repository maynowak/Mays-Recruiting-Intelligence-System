"""A01–A03 — Agent Order Body V1 contract, versioning and ecosystem mapping.

Local only: no AWS, no Orders call, no network.
"""

import copy
import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_body import AgentBody  # noqa: E402
from agents.addition_agent import register_addition_agent  # noqa: E402
from agents.ecosystem.registry import AgentRegistry  # noqa: E402
from agents.orders.agent_order import (  # noqa: E402
    AGENT_ORDER_SCHEMA_VERSION,
    AgentOrderError,
    dispatch_payload,
    fingerprint,
    to_work_item,
    validate_agent_order,
    validate_order_document,
    validate_result,
    version_matrix,
)
from agents.transport import VerifiedContext  # noqa: E402

NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)

CONTEXT = VerifiedContext(
    context_ref="ctx_partner_a",
    tenant_id="tenant-a",
    owner_id="user-a",
    api_profile_id="profile-a",
    partner_application_id="partner-a",
    issuer="https://cognito.example/ris",
    actor_id="machine-client-a",
)


def agent_order(**overrides):
    body = {
        "schemaVersion": "1.0",
        "target": {
            "agentId": "addition_agent",
            "capability": "math.add",
            "agentVersion": "1.0.0",
        },
        "input": {"schemaVersion": "1.0", "data": {"left": 17, "right": 25}},
        "metadata": {
            "source": "ris-agent-ecosystem",
            "partnerApplicationRef": "partner-a",
            "apiProfileRef": "profile-a",
            "requestId": "req-001",
            "idempotencyKey": "addition-001",
        },
        "processing": {
            "trigger": "ORDER_CREATED",
            "parentOrderId": None,
            "parentWorkId": None,
            "executionProfile": "default",
        },
        "resultContract": {
            "schemaVersion": "1.0",
            "format": "json",
            "expectedCapability": "math.add",
            "delivery": "order-result",
        },
    }
    body.update(overrides)
    return body


def order_document(**overrides):
    doc = {"orderType": "agent.execution", "agentOrder": agent_order()}
    doc.update(overrides)
    return doc


class TestValidDocuments:
    def test_full_document_validates(self):
        out = validate_agent_order(agent_order())
        assert out["target"]["capability"] == "math.add"
        assert out["input"]["data"] == {"left": 17, "right": 25}

    def test_minimal_document_receives_documented_defaults(self):
        minimal = {
            "schemaVersion": "1.0",
            "target": {"agentId": "addition_agent", "capability": "math.add"},
            "input": {"data": {"left": 17, "right": 25}},
        }
        out = validate_agent_order(minimal)
        assert out["processing"]["trigger"] == "ORDER_CREATED"
        assert out["processing"]["executionProfile"] == "default"
        assert out["metadata"]["source"] == "ris-agent-ecosystem"
        assert out["resultContract"]["format"] == "json"
        assert out["resultContract"]["delivery"] == "order-result"
        assert out["resultContract"]["expectedCapability"] == "math.add"

    @pytest.mark.parametrize("version", ["1.0", "1"])
    def test_accepted_versions(self, version):
        assert validate_agent_order(agent_order(schemaVersion=version))

    def test_order_document_with_agent_type(self):
        assert validate_order_document(order_document())["target"]["agentId"] == \
            "addition_agent"

    def test_validation_is_deterministic(self):
        first = validate_agent_order(agent_order())
        second = validate_agent_order(agent_order())
        assert first == second


class TestInvalidDocuments:
    @pytest.mark.parametrize("version", ["2.0", "0.9", "", None, 1])
    def test_unknown_version_is_rejected(self, version):
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(agent_order(schemaVersion=version))
        assert ctx.value.code == "unsupported_agent_order_version"

    def test_unknown_top_level_field_is_rejected(self):
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(agent_order(extra="x"))
        assert ctx.value.code == "unknown_field"

    def test_unknown_nested_field_is_rejected(self):
        body = agent_order()
        body["target"]["priority"] = 1
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(body)
        assert ctx.value.code == "unknown_field"

    def test_missing_target_is_rejected(self):
        body = agent_order()
        body.pop("target")
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(body)
        assert ctx.value.code == "invalid_target"

    def test_missing_capability_is_rejected(self):
        body = agent_order()
        body["target"].pop("capability")
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(body)
        assert ctx.value.code == "invalid_field"

    def test_invalid_capability_format_is_rejected(self):
        body = agent_order()
        body["target"]["capability"] = "math"
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(body)
        assert ctx.value.code == "invalid_capability"

    def test_missing_input_data_is_rejected(self):
        body = agent_order()
        body["input"] = {"schemaVersion": "1.0"}
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(body)
        assert ctx.value.code == "invalid_input"

    def test_expected_capability_mismatch_is_rejected(self):
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(agent_order(), expected_capability="cv.process")
        assert ctx.value.code == "capability_mismatch"

    def test_expected_agent_mismatch_is_rejected(self):
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(agent_order(), expected_agent="other_agent")
        assert ctx.value.code == "target_mismatch"

    def test_unsupported_result_format_is_rejected(self):
        body = agent_order()
        body["resultContract"]["format"] = "protobuf"
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(body)
        assert ctx.value.code == "unsupported_result_format"

    def test_result_contract_capability_mismatch_is_rejected(self):
        body = agent_order()
        body["resultContract"]["expectedCapability"] = "cv.process"
        with pytest.raises(AgentOrderError) as ctx:
            validate_agent_order(body)
        assert ctx.value.code == "result_contract_mismatch"

    @pytest.mark.parametrize("data", [
        {"api_key": "x"},
        {"nested": {"authorization": "Bearer abc"}},
        {"token": "abc"},
        {"note": "ris_" + "A" * 47},
    ])
    def test_secret_shaped_input_is_rejected(self, data):
        body = agent_order()
        body["input"]["data"] = data
        with pytest.raises(AgentOrderError):
            validate_agent_order(body)

    def test_order_document_requires_agent_order(self):
        with pytest.raises(AgentOrderError) as ctx:
            validate_order_document({"orderType": "agent.execution"})
        assert ctx.value.code == "missing_agent_order"

    def test_retail_order_type_is_not_an_agent_order(self):
        with pytest.raises(AgentOrderError) as ctx:
            validate_order_document({"orderType": "retail", "agentOrder": {}})
        assert ctx.value.code == "unsupported_order_type"


class TestVersioning:
    def test_three_versions_are_independent(self):
        matrix = version_matrix()
        assert matrix["transportEnvelope"]["version"] == "1"
        assert matrix["agentOrder"]["version"] == AGENT_ORDER_SCHEMA_VERSION
        assert matrix["ordersModule"]["version"] is None

    def test_agent_order_version_does_not_imply_transport_version(self):
        matrix = version_matrix()
        assert matrix["agentOrder"]["version"] != \
            matrix["transportEnvelope"]["version"]

    def test_fingerprint_is_stable(self):
        a = validate_agent_order(agent_order())
        b = validate_agent_order(agent_order())
        assert fingerprint(a) == fingerprint(b)

    def test_fingerprint_changes_when_input_changes(self):
        a = validate_agent_order(agent_order())
        changed = agent_order()
        changed["input"]["data"] = {"left": 17, "right": 26}
        b = validate_agent_order(changed)
        assert fingerprint(a) != fingerprint(b)

    def test_fingerprint_ignores_correlation_only_fields(self):
        a = validate_agent_order(agent_order())
        changed = agent_order()
        changed["metadata"]["requestId"] = "req-999"
        changed["metadata"]["idempotencyKey"] = "addition-999"
        b = validate_agent_order(changed)
        assert fingerprint(a) == fingerprint(b)

    def test_fingerprint_changes_when_target_changes(self):
        a = validate_agent_order(agent_order())
        changed = agent_order()
        changed["target"]["agentVersion"] = "1.0.1"
        b = validate_agent_order(changed)
        assert fingerprint(a) != fingerprint(b)


class TestEcosystemMapping:
    def test_maps_target_input_and_processing(self):
        body = validate_agent_order(agent_order())
        item = to_work_item(body, verified_context=CONTEXT,
                            order_id="ord_abc123", correlation_id="corr-1",
                            work_id="work-1", now=NOW)
        assert item["agentId"] == "addition_agent"
        assert item["capability"] == "math.add"
        assert item["payload"] == {"left": 17, "right": 25}
        assert item["type"] == "agent_addition_agent"
        assert item["orderId"] == "ord_abc123"
        assert item["correlationId"] == "corr-1"

    def test_metadata_references_are_not_authorization(self):
        body = validate_agent_order(agent_order())
        item = to_work_item(body, verified_context=CONTEXT,
                            order_id="ord_abc123", correlation_id="corr-1",
                            work_id="work-1", now=NOW)
        # Identity comes from the verified context, not from metadata.
        assert item["apiProfileId"] == "profile-a"
        assert item["partnerApplicationId"] == "partner-a"
        assert item["userId"] == "user-a"
        assert item["requestedBy"] == "machine-client-a"

    def test_mismatched_metadata_reference_is_rejected(self):
        body = agent_order()
        body["metadata"]["apiProfileRef"] = "profile-foreign"
        with pytest.raises(AgentOrderError) as ctx:
            to_work_item(validate_agent_order(body), verified_context=CONTEXT,
                         order_id="ord_abc123", correlation_id="corr-1")
        assert ctx.value.code == "identity_mismatch"

    def test_fingerprint_is_recorded_on_the_work_item(self):
        body = validate_agent_order(agent_order())
        item = to_work_item(body, verified_context=CONTEXT,
                            order_id="ord_abc123", correlation_id="corr-1")
        assert item["agentOrderFingerprint"] == fingerprint(body)
        assert item["agentOrderVersion"] == "1.0"

    def test_invalid_order_id_is_rejected(self):
        body = validate_agent_order(agent_order())
        with pytest.raises(AgentOrderError) as ctx:
            to_work_item(body, verified_context=CONTEXT,
                         order_id="order-123", correlation_id="corr-1")
        assert ctx.value.code == "invalid_order_id"

    def test_dispatch_payload_is_only_the_fachliche_input(self):
        body = validate_agent_order(agent_order())
        assert dispatch_payload(body) == {"left": 17, "right": 25}


class TestEndToEnd:
    def test_agent_order_executes_and_returns_42(self):
        body = validate_agent_order(agent_order())
        item = to_work_item(body, verified_context=CONTEXT,
                            order_id="ord_abc123", correlation_id="corr-1",
                            work_id="work-1", now=NOW)

        registry = AgentRegistry()
        agent_body = AgentBody()
        register_addition_agent(registry, agent_body)

        result = agent_body.execute(item)
        assert result["success"] is True
        assert result["data"] == {"left": 17, "right": 25, "sum": 42}
        assert validate_result(body, result["data"])["sum"] == 42

    def test_decimal_addition_is_exact(self):
        body = agent_order()
        body["input"]["data"] = {"left": 0.1, "right": 0.2}
        validated = validate_agent_order(body)
        item = to_work_item(validated, verified_context=CONTEXT,
                            order_id="ord_abc123", correlation_id="corr-1")

        registry = AgentRegistry()
        agent_body = AgentBody()
        register_addition_agent(registry, agent_body)
        assert agent_body.execute(item)["data"]["sum"] == 0.3

    def test_result_with_secret_is_rejected_by_the_contract(self):
        body = validate_agent_order(agent_order())
        with pytest.raises(AgentOrderError):
            validate_result(body, {"sum": 42, "api_key": "ris_" + "A" * 47})

    def test_result_shape_is_checked(self):
        body = validate_agent_order(agent_order())
        with pytest.raises(AgentOrderError) as ctx:
            validate_result(body, {"other": 1})
        assert ctx.value.code == "result_shape"
