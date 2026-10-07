"""
Tests for Event Hook (AGENT-HOOK-01)

Tests the event processing pipeline:
- Event validation
- Event normalization
- ProcessingEnvelope creation
- Trigger type handling
- Error handling for invalid events
"""

import sys
import os
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.event_hook import (
    Event, ProcessingEnvelope, EventHook, TriggerType, 
    create_processing_envelope_from_event
)


class TestEvent:
    """Test Event data structure."""
    
    def test_event_creation_required_fields(self):
        """Event can be created with required fields."""
        event = Event(
            event_id='test-123',
            event_type='ORDER_CREATED',
            occurred_at=datetime.now(timezone.utc),
            tenant_id='tenant-1',
        )
        
        assert event.event_id == 'test-123'
        assert event.event_type == 'ORDER_CREATED'
        assert event.tenant_id == 'tenant-1'
    
    def test_event_creation_with_optional_fields(self):
        """Event accepts optional fields."""
        event = Event(
            event_id='test-456',
            event_type='EVENT',
            occurred_at=datetime.now(timezone.utc),
            tenant_id='tenant-2',
            order_id='order-789',
            payload={'key': 'value'},
            metadata={'source': 'test'},
            agent_id='test_agent'
        )
        
        assert event.order_id == 'order-789'
        assert event.payload == {'key': 'value'}
        assert event.metadata == {'source': 'test'}
        assert event.agent_id == 'test_agent'
    
    def test_event_validation_missing_event_id(self):
        """Event validation fails without event_id."""
        with pytest.raises(ValueError):
            Event(
                event_id='',
                event_type='ORDER_CREATED',
                occurred_at=datetime.now(timezone.utc),
                tenant_id='tenant-1',
            )
    
    def test_event_validation_missing_event_type(self):
        """Event validation fails without event_type."""
        with pytest.raises(ValueError):
            Event(
                event_id='test-789',
                event_type='',
                occurred_at=datetime.now(timezone.utc),
                tenant_id='tenant-1',
            )
    
    def test_event_validation_missing_tenant_id(self):
        """Event validation fails without tenant_id."""
        with pytest.raises(ValueError):
            Event(
                event_id='test-789',
                event_type='ORDER_CREATED',
                occurred_at=datetime.now(timezone.utc),
                tenant_id='',
            )


class TestProcessingEnvelope:
    """Test ProcessingEnvelope structure."""
    
    def test_envelope_identity_separation(self):
        """Envelope maintains identity separation between order and processing."""
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            execution_id='exec-789',
            attempt_id='att-001',
            tenant_id='tenant-1'
        )
        
        assert envelope.order_id == 'order-123'
        assert envelope.processing_id == 'proc-456'
        assert envelope.execution_id == 'exec-789'
        assert envelope.attempt_id == 'att-001'
    
    def test_envelope_default_status(self):
        """Envelope has PENDING status by default."""
        envelope = ProcessingEnvelope(
            order_id='order-1',
            processing_id='proc-1',
            tenant_id='tenant-1'
        )
        
        assert envelope.status == 'PENDING'
    
    def test_envelope_trigger_types(self):
        """Envelope supports all trigger types."""
        for trigger in TriggerType:
            env = ProcessingEnvelope(
                order_id='order-1',
                processing_id='proc-1',
                tenant_id='tenant-1',
                trigger_type=trigger
            )
            assert env.trigger_type == trigger


class TestEventHook:
    """Test EventHook transformation logic."""
    
    def test_validate_valid_event(self):
        """Valid event passes validation."""
        hook = EventHook()
        event = Event(
            event_id='test-123',
            event_type='ORDER_CREATED',
            occurred_at=datetime.now(timezone.utc),
            tenant_id='tenant-1',
        )
        
        assert hook.validate(event) is True
    
    def test_validate_missing_event_id(self):
        """Event fails validation without event_id."""
        with pytest.raises(ValueError):
            Event(
                event_id='',
                event_type='ORDER_CREATED',
                occurred_at=datetime.now(timezone.utc),
                tenant_id='tenant-1',
            )
    
    def test_validate_unknown_event_type(self):
        """Unknown event_type fails validation."""
        hook = EventHook()
        event = Event(
            event_id='test-123',
            event_type='UNKNOWN_TYPE',
            occurred_at=datetime.now(timezone.utc),
            tenant_id='tenant-1',
        )
        
        assert hook.validate(event) is False
    
    def test_normalize_event_type(self):
        """Event types are normalized to uppercase."""
        hook = EventHook()
        event = Event(
            event_id='test-123',
            event_type='order_created',
            occurred_at=datetime.now(timezone.utc),
            tenant_id='tenant-1',
        )
        
        hook.normalize(event)
        assert event.event_type == 'ORDER_CREATED'
    
    def test_handle_event_creates_envelope(self):
        """Handle event creates valid ProcessingEnvelope."""
        hook = EventHook()
        event = Event(
            event_id='test-123',
            event_type='ORDER_CREATED',
            occurred_at=datetime.now(timezone.utc),
            tenant_id='tenant-1',
            order_id='order-456',
            payload={'test': 'data'}
        )
        
        envelope = hook.handle_event(event)
        
        assert envelope.order_id == 'order-456'
        assert envelope.tenant_id == 'tenant-1'
        assert envelope.trigger_type == TriggerType.ORDER_CREATED
        assert envelope.input == {'test': 'data'}
    
    def test_handle_event_missing_agent_id(self):
        """Envelope created even without agent_id in event."""
        hook = EventHook()
        event = Event(
            event_id='test-123',
            event_type='SCHEDULE',
            occurred_at=datetime.now(timezone.utc),
            tenant_id='tenant-1'
        )
        
        envelope = hook.handle_event(event)
        
        assert envelope.agent_id is None
        assert envelope.trigger_type == TriggerType.SCHEDULE


class TestConvenienceFunction:
    """Test convenience function for envelope creation."""
    
    def test_create_envelope_from_dict(self):
        """Can create envelope from raw dict."""
        event_dict = {
            'event_id': 'conv-123',
            'event_type': 'MANUAL',
            'tenant_id': 'tenant-1',
            'order_id': 'order-456',
            'payload': {'key': 'value'}
        }
        
        envelope = create_processing_envelope_from_event(event_dict)
        
        assert envelope.order_id == 'order-456'
        assert envelope.tenant_id == 'tenant-1'
        assert envelope.input == {'key': 'value'}
    
    def test_create_envelope_default_values(self):
        """Envelope created with defaults for missing fields."""
        event_dict = {
            'event_type': 'EVENT',
            'tenant_id': 'tenant-1'
        }
        
        envelope = create_processing_envelope_from_event(event_dict)
        
        assert envelope.order_id is None


class TestTriggerTypes:
    """Test trigger type handling."""
    
    def test_all_trigger_types_valid(self):
        """All defined trigger types are valid."""
        expected = [
            'ORDER_CREATED', 'ORDER_STATUS', 'PREVIOUS_COMPLETED',
            'EVENT', 'SCHEDULE', 'RETRY',
            'MANUAL', 'CONDITION', 'DEPENDENCY'
        ]
        
        for target in expected:
            assert TriggerType(target) is not None


class TestIdentitySeparation:
    """Test that order != processing != execution != attempt."""
    
    def test_distinct_ids_in_envelope(self):
        """Envelope maintains distinct identity for each scope."""
        envelope = ProcessingEnvelope(
            order_id='order-ABC',
            processing_id='proc-DEF',
            execution_id='exec-GHI',
            attempt_id='att-JKL',
            tenant_id='tenant-1'
        )
        
        assert envelope.order_id != envelope.processing_id
        assert envelope.order_id != envelope.execution_id
        assert envelope.processing_id != envelope.execution_id
        assert envelope.execution_id != envelope.attempt_id


if __name__ == '__main__':
    pytest.main([__file__, '-v'])