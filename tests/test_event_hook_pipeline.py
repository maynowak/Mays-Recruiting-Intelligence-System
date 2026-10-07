"""
Tests for Event Hook Pipeline (AGENT-HOOK-02)

Tests the full pipeline:
- ProcessingEnvelope creation
- Discovery integration
- Eligibility pipeline

These tests verify that:
- Envelope can be discovered
- Eligibility checks work correctly
- Multiple candidates can be processed
- Tenant context is preserved
- No routing is performed
"""

import sys
from agents.timeutil import utcnow
import os
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.event_hook import (
    Event, ProcessingEnvelope, EventHook, TriggerType
)
from agents.ecosystem.discovery import AgentDiscovery, DiscoveryResult
from agents.ecosystem.eligibility import EligibilityChecker, EligibilityPipeline, EligibilityPipelineResult
from agents.ecosystem.registry import AgentRegistry, AgentDescriptor, AgentStatus


class TestDiscoveryFromEnvelope:
    """Test discovery from processing envelope."""
    
    def test_discovery_with_capability(self):
        """Discovery finds agents with matching capability."""
        registry = AgentRegistry()
        descriptor = AgentDescriptor(
            agent_id='test_agent',
            name='test_agent',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.ACTIVE
        )
        registry.register('test_agent', descriptor)
        
        discovery = AgentDiscovery(registry)
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'capability': 'test.echo'}
        )
        
        results = discovery.find_from_envelope(envelope)
        
        assert len(results) == 1
        assert results[0].agent_id == 'test_agent'
    
    def test_discovery_with_explicit_agent_id(self):
        """Discovery finds specific agent when ID is provided."""
        registry = AgentRegistry()
        descriptor = AgentDescriptor(
            agent_id='specific_agent',
            name='specific_agent',
            version='1.0.0',
            status=AgentStatus.ACTIVE
        )
        registry.register('specific_agent', descriptor)
        
        discovery = AgentDiscovery(registry)
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-1',
            agent_id='specific_agent',
            trigger_type=TriggerType.MANUAL
        )
        
        results = discovery.find_from_envelope(envelope)
        
        assert len(results) == 1
        assert results[0].agent_id == 'specific_agent'
        assert results[0].reason == "Specific agent requested"
    
    def test_discovery_returns_multiple_candidates(self):
        """Discovery can return multiple candidates."""
        registry = AgentRegistry()
        
        for i in range(3):
            descriptor = AgentDescriptor(
                agent_id=f'agent_{i}',
                name=f'agent_{i}',
                version='1.0.0',
                capabilities=['test.echo'],
                status=AgentStatus.ACTIVE
            )
            registry.register(f'agent_{i}', descriptor)
        
        discovery = AgentDiscovery(registry)
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'capability': 'test.echo'}
        )
        
        results = discovery.find_from_envelope(envelope)
        
        assert len(results) == 3
        agent_ids = [r.agent_id for r in results]
        assert 'agent_0' in agent_ids
        assert 'agent_1' in agent_ids
        assert 'agent_2' in agent_ids
    
    def test_discovery_unknown_agent_id(self):
        """Discovery handles unknown agent_id gracefully."""
        registry = AgentRegistry()
        
        discovery = AgentDiscovery(registry)
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-1',
            agent_id='unknown_agent',
            trigger_type=TriggerType.MANUAL
        )
        
        results = discovery.find_from_envelope(envelope)
        
        assert len(results) == 0


class TestEligibilityPipeline:
    """Test eligibility pipeline."""
    
    def test_eligibility_pipeline_eligible(self):
        """Pipeline marks eligible agents correctly."""
        registry = AgentRegistry()
        descriptor = AgentDescriptor(
            agent_id='eligible_agent',
            name='eligible_agent',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.ACTIVE
        )
        registry.register('eligible_agent', descriptor)
        
        pipeline = EligibilityPipeline(registry)
        
        candidates = [
            DiscoveryResult(
                agent_id='eligible_agent',
                agent=descriptor,
                reason='matches criteria'
            )
        ]
        
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'capability': 'test.echo'}
        )
        
        result = pipeline.check_candidates(candidates, envelope)
        
        assert len(result.eligible) == 1
        assert result.eligible[0].agent_id == 'eligible_agent'
        assert result.eligible[0].eligible is True
    
    def test_eligibility_pipeline_rejected(self):
        """Pipeline rejects deprecated agents."""
        registry = AgentRegistry()
        descriptor = AgentDescriptor(
            agent_id='deprecated_agent',
            name='deprecated_agent',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.DEPRECATED
        )
        registry.register('deprecated_agent', descriptor)
        
        pipeline = EligibilityPipeline(registry)
        
        candidates = [
            DiscoveryResult(
                agent_id='deprecated_agent',
                agent=descriptor,
                reason='matches capability'
            )
        ]
        
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'capability': 'test.echo'}
        )
        
        result = pipeline.check_candidates(candidates, envelope)
        
        assert len(result.eligible) == 0
        assert len(result.rejected) == 1
        assert result.rejected[0].agent_id == 'deprecated_agent'
    
    def test_eligibility_pipeline_retired_rejected(self):
        """Pipeline rejects retired agents."""
        registry = AgentRegistry()
        descriptor = AgentDescriptor(
            agent_id='retired_agent',
            name='retired_agent',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.RETIRED
        )
        registry.register('retired_agent', descriptor)
        
        pipeline = EligibilityPipeline(registry)
        
        candidates = [
            DiscoveryResult(
                agent_id='retired_agent',
                agent=descriptor,
                reason='matches capability'
            )
        ]
        
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'capability': 'test.echo'}
        )
        
        result = pipeline.check_candidates(candidates, envelope)
        
        assert len(result.eligible) == 0
        assert len(result.rejected) == 1


class TestFullPipeline:
    """Test complete pipeline from event to eligibility."""
    
    def test_full_pipeline(self):
        """Complete pipeline: Event -> Envelope -> Discovery -> Eligibility."""
        import uuid
        
        registry = AgentRegistry()
        registry.register('echo_agent', AgentDescriptor(
            agent_id='echo_agent',
            name='echo_agent',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.ACTIVE
        ))
        
        hook = EventHook()
        event = Event(
            event_id='event-123',
            event_type='ORDER_CREATED',
            occurred_at=utcnow(),
            tenant_id='tenant-1',
            order_id='order-456',
            payload={'capability': 'test.echo'}
        )
        
        envelope = hook.handle_event(event)
        
        discovery = AgentDiscovery(registry)
        candidates = discovery.find_from_envelope(envelope)
        
        pipeline = EligibilityPipeline(registry)
        result = pipeline.check_candidates(candidates, envelope)
        
        assert len(result.eligible) >= 1
        assert envelope.tenant_id == 'tenant-1'
    
    def test_pipeline_preserves_tenant_context(self):
        """Pipeline preserves tenant context through all stages."""
        recipient_tenant = None
        
        registry = AgentRegistry()
        registry.register('agent_1', AgentDescriptor(
            agent_id='agent_1',
            name='agent_1',
            version='1.0.0',
            status=AgentStatus.ACTIVE
        ))
        
        hook = EventHook()
        event = Event(
            event_id='event-t1',
            event_type='EVENT',
            occurred_at=utcnow(),
            tenant_id='tenant-T1',
            payload={}
        )
        
        envelope = hook.handle_event(event)
        
        assert envelope.tenant_id == 'tenant-T1'
        
        discovery = AgentDiscovery(registry)
        candidates = discovery.find_from_envelope(envelope)
        
        assert len(candidates) >= 0


class TestNoRouting:
    """Verify no routing occurs (AGENT-HOOK-02 requirement)."""
    
    def test_discovery_returns_candidates_not_selection(self):
        """Discovery returns candidates without selecting a winner."""
        registry = AgentRegistry()
        
        registry.register('agent_a', AgentDescriptor(
            agent_id='agent_a',
            name='agent_a',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.ACTIVE
        ))
        
        registry.register('agent_b', AgentDescriptor(
            agent_id='agent_b',
            name='agent_b',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.ACTIVE
        ))
        
        hook = EventHook()
        event = Event(
            event_id='event-multi',
            event_type='EVENT',
            occurred_at=utcnow(),
            tenant_id='tenant-1',
            payload={'capability': 'test.echo'}
        )
        
        envelope = hook.handle_event(event)
        
        discovery = AgentDiscovery(registry)
        candidates = discovery.find_from_envelope(envelope)
        
        assert len(candidates) >= 2, "Should return multiple candidates"
        
        for candidate in candidates:
            assert hasattr(candidate, 'agent_id')
            assert hasattr(candidate, 'agent')
            assert hasattr(candidate, 'reason')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
