"""
Tests for G7 Health Event Sink / Consumer.

Verifies that HealthTracker events are emitted to the operational sink,
that the sink contract is preserved, and that emission failures do not
break business processing.
"""

import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

from agents.ecosystem.health_plane import Component, HealthTracker, HealthState, REASON_AGENT_ERROR
from agents.ecosystem import health_sink
from agents.runtime.pipeline import process_record


class TestSinkContract:
    def test_emit_logs_structured_json(self):
        from agents.ecosystem.health_plane import HealthEvent, TriggerType
        ev = HealthEvent(
            event_id="e1",
            event_type=TriggerType.HEALTH_DEGRADED,
            occurred_at=datetime(2026,1,1,tzinfo=timezone.utc),
            component=Component.AGENT_EXECUTION,
            state=HealthState.DEGRADED,
            tenant_id="t1",
            work_id="w1",
            agent_id="a1",
            attempt_id="1",
            reason="AGENT_ERROR",
            consecutive_failures=3,
        )
        with patch("agents.ecosystem.health_sink.logger") as mock_logger:
            health_sink.emit([ev])
            mock_logger.info.assert_called_once()
            logged = mock_logger.info.call_args[0][0]
            data = json.loads(logged)
            assert data["eventId"] == "e1"
            assert data["eventType"] == "HEALTH_DEGRADED"
            assert data["component"] == "AGENT_EXECUTION"
            assert data["tenantId"] == "t1"
            assert data["reason"] == "AGENT_ERROR"
            for forbidden in ("payload","body","result","credential","secret"):
                assert forbidden not in data

    def test_emit_swallow_sink_failure_no_propagation(self):
        from agents.ecosystem.health_plane import HealthEvent, TriggerType
        ev = HealthEvent(
            event_id="e1",
            event_type=TriggerType.HEALTH_HEARTBEAT,
            occurred_at=datetime.now(timezone.utc),
            component=Component.WORKER,
            state=HealthState.HEALTHY,
        )
        with patch("agents.ecosystem.health_sink.logger.info", side_effect=RuntimeError("log broken")):
            health_sink.emit([ev])

    def test_emit_empty_list_no_log(self):
        with patch("agents.ecosystem.health_sink.logger.info") as mock_logger:
            health_sink.emit([])
            mock_logger.info.assert_not_called()


class TestPipelineIntegration:
    def test_tracker_events_reach_sink(self):
        tracker = HealthTracker()
        events = tracker.record_failure(Component.AGENT_EXECUTION, tenant_id="t1")
        assert len(events) == 1
        with patch("agents.ecosystem.health_sink.logger.info") as mock_info:
            health_sink.emit(events)
            assert mock_info.called
            logged = mock_info.call_args[0][0]
            data = json.loads(logged)
            assert data["eventType"] == "HEALTH_DEGRADED"
            assert data["tenantId"] == "t1"

    def test_sink_failure_does_not_break_business_processing(self):
        tracker = HealthTracker()
        with patch("agents.ecosystem.health_sink.emit", side_effect=RuntimeError("sink down")):
            record = {
                "messageId": "m2",
                "body": json.dumps({
                    "workId": "w2",
                    "type": "t",
                    "tenantId": "t2",
                    "idempotencyKey": "k2",
                    "payload": {},
                    "capability": "test",
                })
            }
            class MockTable:
                def put_item(self, **kw):
                    raise RuntimeError("no db")
            exc = None
            try:
                process_record(record, table=MockTable(), health_tracker=tracker)
            except Exception as e:
                exc = e
            assert exc is not None
            assert "sink down" not in str(exc)


class TestPrivacyAndSanitization:
    def test_sink_never_receives_payload_fields(self):
        tracker = HealthTracker()
        events = tracker.record_failure(Component.AGENT_EXECUTION, tenant_id="t1", work_id="w1", agent_id="a1", attempt_id="1", reason=REASON_AGENT_ERROR)
        for ev in events:
            d = ev.to_dict()
            for forbidden in ("payload","body","result","credential","secret","token","password","email","userid","user_id"):
                assert forbidden not in d

    def test_unknown_reason_coerced(self):
        tracker = HealthTracker()
        events = tracker.record_failure(Component.AGENT_EXECUTION, reason="DROP TABLE users")
        assert events[0].reason == "INFRASTRUCTURE"
