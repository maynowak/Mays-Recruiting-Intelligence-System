"""T02/T04/T05 — Generic Order Transport Envelope V1 tests.

Local only: no AWS, no SQS, no network. The dispatch is executed through the
existing Agent Body, and the result is correlated back to the original order.
"""

import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_body import AgentBody  # noqa: E402
from agents.addition_agent import register_addition_agent  # noqa: E402
from agents.ecosystem.registry import AgentRegistry  # noqa: E402
from agents.runtime.work_item import build_work_item  # noqa: E402
from agents.transport import (  # noqa: E402
    ORDER_CANCELLED,
    ORDER_DISPATCH,
    ORDER_FAILED,
    ORDER_RESULT,
    ORDER_STATUS_CHANGED,
    RESERVED_MESSAGE_TYPES,
    SCHEMA_VERSION,
    SUPPORTED_MESSAGE_TYPES,
    TransportError,
    VerifiedContext,
    accepted_message_types,
    dispatch_to_work_item,
    is_stale_attempt,
    result_from_work_item,
    validate_envelope,
)

NOW = datetime(2026, 11, 13, 9, 0, 0, tzinfo=timezone.utc)

CONTEXT = VerifiedContext(
    context_ref="ctx_partner_a",
    tenant_id="tenant-a",
    owner_id="user-a",
    api_profile_id="profile-a",
    partner_application_id="app-a",
    issuer="https://cognito.example/ris",
    actor_id="machine-client-a",
)


def dispatch(**overrides):
    envelope = {
        "schemaVersion": SCHEMA_VERSION,
        "messageId": "msg_dispatch_1",
        "messageType": ORDER_DISPATCH,
        "orderId": "ord_abc123",
        "correlationId": "corr-1",
        "idempotencyKey": "ord_abc123:dispatch",
        "sender": {"system": "mays-orders", "reference": "app-a"},
        "recipient": {"system": "ris", "agentId": "addition_agent",
                      "capability": "math.add"},
        "identity": {
            "contextRef": "ctx_partner_a",
            "tenantId": "tenant-a",
            "apiProfileId": "profile-a",
            "partnerApplicationId": "app-a",
            "issuer": "https://cognito.example/ris",
        },
        "payload": {"left": 17, "right": 25},
        "createdAt": "2026-11-13T09:00:00+00:00",
    }
    envelope.update(overrides)
    return envelope


def result_envelope(**overrides):
    envelope = {
        "schemaVersion": SCHEMA_VERSION,
        "messageId": "msg_result_1",
        "messageType": ORDER_RESULT,
        "orderId": "ord_abc123",
        "correlationId": "corr-1",
        "idempotencyKey": "ord_abc123:work-1:ORDER_RESULT",
        "sender": {"system": "ris", "reference": "ris-runtime"},
        "recipient": {"system": "mays-orders"},
        "identity": {"contextRef": "ctx_partner_a", "tenantId": "tenant-a"},
        "payload": {"left": 17, "right": 25, "sum": 42},
        "createdAt": "2026-11-13T09:00:05+00:00",
        "execution": {"workId": "work-1", "attempt": 1},
    }
    envelope.update(overrides)
    return envelope


class TestSchemaPositive:
    def test_valid_dispatch_is_accepted(self):
        assert validate_envelope(dispatch())["messageType"] == ORDER_DISPATCH

    def test_valid_result_is_accepted(self):
        assert validate_envelope(result_envelope())["messageType"] == ORDER_RESULT

    def test_all_supported_types_are_implemented(self):
        assert set(accepted_message_types()) == set(SUPPORTED_MESSAGE_TYPES)
        assert SUPPORTED_MESSAGE_TYPES == {
            ORDER_DISPATCH, ORDER_RESULT, ORDER_FAILED,
            ORDER_CANCELLED, ORDER_STATUS_CHANGED,
        }

    def test_reserved_types_are_not_advertised_as_accepted(self):
        assert RESERVED_MESSAGE_TYPES.isdisjoint(
            set(accepted_message_types()))

    @pytest.mark.parametrize("version", ["1", "1.0"])
    def test_accepted_versions(self, version):
        assert validate_envelope(dispatch(schemaVersion=version))["schemaVersion"] == version

    def test_payload_reference_instead_of_inline_payload(self):
        envelope = dispatch()
        envelope.pop("payload")
        envelope["payloadRef"] = "s3://bucket/key"
        assert validate_envelope(envelope)["payloadRef"] == "s3://bucket/key"

    def test_parent_references_are_optional(self):
        envelope = dispatch(parentOrderId="ord_parent1", parentWorkId="work-parent")
        assert validate_envelope(envelope)["parentOrderId"] == "ord_parent1"


class TestSchemaNegative:
    @pytest.mark.parametrize("version", ["2", "0.9", "", None, 1])
    def test_unsupported_schema_version_is_rejected(self, version):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(dispatch(schemaVersion=version))
        assert ctx.value.code in ("unsupported_schema_version", "missing_field")

    def test_unknown_message_type_is_rejected(self):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(dispatch(messageType="ORDER_TELEPORT"))
        assert ctx.value.code == "unknown_message_type"

    def test_reserved_message_type_is_rejected_distinctly(self):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(dispatch(messageType="ORDER_ACK"))
        assert ctx.value.code == "reserved_message_type"

    def test_missing_order_id_is_rejected(self):
        envelope = dispatch()
        envelope.pop("orderId")
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "missing_field"

    def test_invalid_order_id_format_is_rejected(self):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(dispatch(orderId="order-123"))
        assert ctx.value.code == "invalid_order_id"

    def test_missing_correlation_id_is_rejected(self):
        envelope = dispatch()
        envelope.pop("correlationId")
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "missing_field"

    def test_missing_verified_context_ref_is_rejected(self):
        envelope = dispatch(identity={"tenantId": "tenant-a"})
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "missing_verified_context"

    def test_unknown_top_level_field_is_rejected(self):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(dispatch(extraField="x"))
        assert ctx.value.code == "unknown_field"

    def test_unknown_recipient_field_is_rejected(self):
        envelope = dispatch(recipient={"system": "ris",
                                       "agentId": "addition_agent",
                                       "priority": 1})
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "unknown_field"

    def test_manipulated_recipient_system_is_rejected(self):
        envelope = dispatch(recipient={"system": "mays-orders",
                                       "agentId": "addition_agent"})
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "wrong_recipient_system"

    def test_result_with_orders_sender_is_rejected(self):
        envelope = result_envelope(sender={"system": "mays-orders"})
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "wrong_sender_system"

    def test_payload_and_reference_together_are_rejected(self):
        envelope = dispatch(payloadRef="s3://bucket/key")
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "invalid_payload_reference"

    def test_neither_payload_nor_reference_is_rejected(self):
        envelope = dispatch()
        envelope.pop("payload")
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "invalid_payload_reference"

    def test_result_without_execution_correlation_is_rejected(self):
        envelope = result_envelope()
        envelope.pop("execution")
        with pytest.raises(TransportError) as ctx:
            validate_envelope(envelope)
        assert ctx.value.code == "missing_execution"

    def test_invalid_attempt_is_rejected(self):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(result_envelope(execution={"workId": "w", "attempt": 0}))
        assert ctx.value.code == "invalid_attempt"

    def test_invalid_timestamp_is_rejected(self):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(dispatch(createdAt="yesterday"))
        assert ctx.value.code == "invalid_timestamp"

    @pytest.mark.parametrize("payload", [
        {"api_key": "x"},
        {"nested": {"Authorization": "Bearer abc"}},
        {"list": [{"client_secret": "s"}]},
        {"note": "ris_" + "A" * 47},
    ])
    def test_secret_shaped_payload_is_rejected(self, payload):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(dispatch(payload=payload))
        assert ctx.value.code == "secret_in_transport"

    def test_oversized_payload_is_rejected(self):
        with pytest.raises(TransportError) as ctx:
            validate_envelope(dispatch(payload={"blob": "x" * (17 * 1024)}))
        assert ctx.value.code == "payload_too_large"


class TestDispatchMapping:
    def test_dispatch_maps_to_the_canonical_work_item(self):
        item = dispatch_to_work_item(validate_envelope(dispatch()), CONTEXT,
                                     now=NOW, work_id="work-1")
        reference = build_work_item(
            agent_id="addition_agent", capability="math.add",
            payload={"left": 17, "right": 25}, tenant_id="tenant-a",
            user_id="user-a", requested_by="machine-client-a",
            idempotency_key="ord_abc123:dispatch", request_id="corr-1",
            work_id="work-1", now=NOW,
            api_profile_id="profile-a",
            partner_application_id="app-a",
            issuer="https://cognito.example/ris",
            extra={"orderId": "ord_abc123"},
        )
        # Every reference key must exist with the same value; the transport adds
        # correlation/identity extras on top instead of redefining the shape.
        for key, value in reference.items():
            assert item[key] == value, key

    def test_order_and_correlation_are_preserved(self):
        item = dispatch_to_work_item(validate_envelope(dispatch()), CONTEXT,
                                     now=NOW, work_id="work-1")
        assert item["orderId"] == "ord_abc123"
        assert item["correlationId"] == "corr-1"
        assert item["transportMessageId"] == "msg_dispatch_1"

    def test_verified_identity_is_stamped_not_the_claim(self):
        item = dispatch_to_work_item(validate_envelope(dispatch()), CONTEXT,
                                     now=NOW, work_id="work-1")
        assert item["tenantId"] == "tenant-a"
        assert item["userId"] == "user-a"
        assert item["requestedBy"] == "machine-client-a"
        assert item["apiProfileId"] == "profile-a"
        assert item["partnerApplicationId"] == "app-a"
        assert item["issuer"] == "https://cognito.example/ris"

    def test_owner_and_actor_are_distinguishable(self):
        item = dispatch_to_work_item(validate_envelope(dispatch()), CONTEXT,
                                     now=NOW, work_id="work-1")
        assert item["userId"] != item["requestedBy"]

    def test_context_ref_mismatch_is_rejected(self):
        envelope = validate_envelope(dispatch())
        other = VerifiedContext("ctx_other", "tenant-a", "user-a", "profile-a",
                                "app-a", "iss")
        with pytest.raises(TransportError) as ctx:
            dispatch_to_work_item(envelope, other, now=NOW)
        assert ctx.value.code == "missing_verified_context"

    @pytest.mark.parametrize("claim,value", [
        ("tenantId", "tenant-b"),
        ("apiProfileId", "profile-b"),
        ("partnerApplicationId", "app-b"),
        ("issuer", "https://evil.example"),
    ])
    def test_identity_claim_that_contradicts_the_context_is_rejected(self, claim, value):
        envelope = dispatch()
        envelope["identity"][claim] = value
        with pytest.raises(TransportError) as ctx:
            dispatch_to_work_item(validate_envelope(envelope), CONTEXT, now=NOW)
        assert ctx.value.code == "identity_mismatch"

    def test_result_envelope_is_not_a_dispatch(self):
        with pytest.raises(TransportError) as ctx:
            dispatch_to_work_item(validate_envelope(result_envelope()), CONTEXT)
        assert ctx.value.code == "unexpected_message_type"


class TestEndToEndThroughAgentBody:
    def _execute(self):
        registry = AgentRegistry()
        body = AgentBody()
        register_addition_agent(registry, body)

        envelope = validate_envelope(dispatch())
        item = dispatch_to_work_item(envelope, CONTEXT, now=NOW, work_id="work-1")

        from agents.addition_agent import AdditionAgent
        agent = AdditionAgent()
        result = agent.process_work(item)
        work_row = {
            "workId": item["workId"],
            "status": "COMPLETED" if result["success"] else "FAILED",
            "attempt_no": 1,
            "result": result.get("data") if result["success"] else None,
            "error": result.get("error"),
        }
        return envelope, item, result, work_row, body

    def test_dispatch_reaches_the_addition_agent_and_returns_42(self):
        _envelope, item, result, _row, body = self._execute()
        assert result["success"] is True
        assert result["data"] == {"left": 17, "right": 25, "sum": 42}

        # and the same item also executes through the shared body
        executed = body.execute(item)
        assert executed["data"]["sum"] == 42

    def test_result_is_correlated_to_the_original_order(self):
        envelope, item, _result, row, _body = self._execute()
        out = result_from_work_item(envelope, row, now=NOW)
        assert out["messageType"] == ORDER_RESULT
        assert out["orderId"] == "ord_abc123"
        assert out["execution"]["workId"] == item["workId"]
        assert out["payload"]["sum"] == 42
        assert validate_envelope(out)["orderId"] == "ord_abc123"

    def test_result_idempotency_key_is_stable(self):
        envelope, item, _result, row, _body = self._execute()
        first = result_from_work_item(envelope, row, now=NOW)
        second = result_from_work_item(envelope, row, now=NOW)
        assert first["idempotencyKey"] == second["idempotencyKey"]
        assert first["idempotencyKey"] == f"ord_abc123:{item['workId']}:ORDER_RESULT"

    def test_result_for_incomplete_work_is_rejected(self):
        envelope, item, _result, row, _body = self._execute()
        with pytest.raises(TransportError) as ctx:
            result_from_work_item(envelope, dict(row, status="RUNNING"), now=NOW)
        assert ctx.value.code == "result_not_completed"

    def test_failed_work_maps_to_order_failed_not_order_result(self):
        envelope, item, _result, _row, _body = self._execute()
        failed = {"workId": item["workId"], "status": "FAILED", "attempt_no": 2,
                  "error": {"message": "agent failed", "type": "RuntimeError"}}
        out = result_from_work_item(envelope, failed,
                                    message_type=ORDER_FAILED, now=NOW)
        assert out["messageType"] == ORDER_FAILED
        assert out["execution"]["attempt"] == 2
        assert out["payload"]["error"]["message"] == "agent failed"

    def test_completed_work_cannot_be_reported_as_failed(self):
        envelope, item, _result, row, _body = self._execute()
        with pytest.raises(TransportError) as ctx:
            result_from_work_item(envelope, row, message_type=ORDER_FAILED, now=NOW)
        assert ctx.value.code == "result_not_failed"

    def test_result_payload_with_secret_is_rejected(self):
        envelope, item, _result, _row, _body = self._execute()
        leaky = {"workId": item["workId"], "status": "COMPLETED", "attempt_no": 1,
                 "result": {"api_key": "ris_" + "A" * 47}}
        with pytest.raises(TransportError) as ctx:
            result_from_work_item(envelope, leaky, now=NOW)
        assert ctx.value.code == "secret_in_transport"

    def test_no_secret_appears_in_dispatch_work_item_or_result(self):
        envelope, item, _result, row, _body = self._execute()
        out = result_from_work_item(envelope, row, now=NOW)
        serialized = json.dumps({"dispatch": envelope, "work": item, "result": out})
        assert "ris_" not in serialized.replace("ris-runtime", "")

    def test_stale_attempt_detection(self):
        row = {"workId": "w", "status": "COMPLETED", "attempt_no": 3}
        assert is_stale_attempt(row, 2) is True
        assert is_stale_attempt(row, 3) is False
        assert is_stale_attempt(row, 4) is False
        assert is_stale_attempt(row, None) is True


class TestWorkItemSingleSource:
    def test_handler_and_transport_share_the_builder(self):
        """The handler must not keep a second work-item literal."""
        handler_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "lambda", "handler.py")
        with open(handler_path, encoding="utf-8") as handle:
            source = handle.read()
        start = source.index("def _enqueue_agent_work")
        block = source[start:start + 2600]
        assert "build_work_item(" in block
        # no inline schema literal in the enqueue path
        assert "'requestedBy': user_id" not in block
        assert "'payloadVersion': '1.0'" not in block
