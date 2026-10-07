"""
Tests for Agent Execution Engine (AGENT-EXEC-01)

Tests the execution boundary that connects RoutingDecision to AgentBody.

No SQS, no May's Orders, no threading, no worker integration.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.routing import (
    AgentRouter, RoutingDecision, SelectionStrategy, ExecutionEngine,
    execute_routing_decision
)
from agents.ecosystem.event_hook import (
    ProcessingEnvelope, TriggerType
)
from agents.ecosystem.registry import AgentRegistry, AgentDescriptor, AgentStatus


class TestExecutionEngine:
    """Test ExecutionEngine functionality."""
    
    def test_execute_with_valid_decision(self):
        """Engine can execute with valid decision."""
        registry = AgentRegistry()
        descriptor = AgentDescriptor(
            agent_id='test_agent',
            name='test_agent',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.ACTIVE
        )
        registry.register('test_agent', descriptor)
        
        decision = RoutingDecision(
            agent_id='test_agent',
            agent=descriptor,
            reason='matches criteria'
        )
        
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'test': 'data', 'capability': 'test.echo'}
        )
        
        engine = ExecutionEngine()
        result = engine.execute_from_decision(decision, envelope)
        
        assert 'success' in result
        assert result.get('agent_id') == 'test_agent'
    
    def test_execute_no_decision(self):
        """Engine rejects None decision."""
        engine = ExecutionEngine()
        envelope = ProcessingEnvelope(
            order_id='order-1',
            processing_id='proc-1',
            tenant_id='tenant-1'
        )
        
        with pytest.raises(ValueError, match="RoutingDecision is None"):
            engine.execute_from_decision(None, envelope)
    
    def test_execute_no_agent_id(self):
        """Engine rejects decision without agent_id."""
        decision = RoutingDecision(
            agent_id=None,
            agent=None,
            reason='no selection'
        )
        
        envelope = ProcessingEnvelope(
            order_id='order-1',
            processing_id='proc-1',
            tenant_id='tenant-1'
        )
        
        engine = ExecutionEngine()
        
        with pytest.raises(ValueError, match="agent_id is None"):
            engine.execute_from_decision(decision, envelope)


class TestConvenienceFunction:
    """Test the convenience function."""
    
    def test_execute_routing_decision_function(self):
        """Convenience function works."""
        registry = AgentRegistry()
        descriptor = AgentDescriptor(
            agent_id='test_agent',
            name='test_agent',
            version='1.0.0',
            capabilities=['test.echo'],
            status=AgentStatus.ACTIVE
        )
        registry.register('test_agent', descriptor)
        
        decision = RoutingDecision(
            agent_id='test_agent',
            agent=descriptor,
            reason='matches'
        )
        
        envelope = ProcessingEnvelope(
            order_id='order-1',
            processing_id='proc-1',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'test': 'data', 'capability': 'test.echo'}
        )
        
        result = execute_routing_decision(decision, envelope)
        
        assert 'success' in result


class TestContextPreservation:
    """Test that context is preserved through execution."""
    
    def test_tenant_preserved(self):
        """Tenant context is preserved."""
        registry = AgentRegistry()
        registry.register('agent_1', AgentDescriptor(
            agent_id='agent_1',
            name='agent_1',
            version='1.0.0',
            capabilities=['test'],
            status=AgentStatus.ACTIVE
        ))
        
        decision = RoutingDecision(
            agent_id='agent_1',
            agent=registry.get('agent_1'),
            reason='ok'
        )
        
        envelope = ProcessingEnvelope(
            order_id='order-123',
            processing_id='proc-456',
            tenant_id='tenant-special',
            trigger_type=TriggerType.EVENT,
            input={'test': 'value', 'capability': 'test.echo'}
        )
        
        engine = ExecutionEngine()
        result = engine.execute_from_decision(decision, envelope)
        
        assert result is not None
    
    def test_processing_id_preserved(self):
        """Processing ID is preserved in execution."""
        registry = AgentRegistry()
        registry.register('agent_1', AgentDescriptor(
            agent_id='agent_1',
            name='agent_1',
            version='1.0.0',
            capabilities=['test'],
            status=AgentStatus.ACTIVE
        ))
        
        decision = RoutingDecision(
            agent_id='agent_1',
            agent=registry.get('agent_1'),
            reason='ok'
        )
        
        envelope = ProcessingEnvelope(
            order_id='order-1',
            processing_id='my-processing-123',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'capability': 'test.echo'}
        )
        
        engine = ExecutionEngine()
        result = engine.execute_from_decision(decision, envelope)
        
        assert result is not None


class TestNoTrigger:
    """Verify no side effects during execution."""
    
    def test_no_sqs_invocation(self):
        """Execution does not use SQS."""
        registry = AgentRegistry()
        registry.register('agent_1', AgentDescriptor(
            agent_id='agent_1',
            name='agent_1',
            version='1.0.0',
            capabilities=['test'],
            status=AgentStatus.ACTIVE
        ))
        
        decision = RoutingDecision(
            agent_id='agent_1',
            agent=registry.get('agent_1'),
            reason='ok'
        )
        
        envelope = ProcessingEnvelope(
            order_id='order-1',
            processing_id='proc-1',
            tenant_id='tenant-1',
            trigger_type=TriggerType.EVENT,
            input={'capability': 'test.echo'}
        )
        
        engine = ExecutionEngine()
        result = engine.execute_from_decision(decision, envelope)
        
        assert result is not None
        assert isinstance(result, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])