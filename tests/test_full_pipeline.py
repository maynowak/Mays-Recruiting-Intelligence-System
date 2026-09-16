"""
Integration test for complete Agent execution pipeline (AGENT-EXEC-01)

Full pipeline:
Event → ProcessingEnvelope → Discovery → Eligibility → Routing → Execution

No AWS, no SQS, no May's Orders.
"""

import sys
import os
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.event_hook import Event, EventHook, TriggerType, ProcessingEnvelope
from agents.ecosystem.discovery import AgentDiscovery, DiscoveryResult
from agents.ecosystem.eligibility import EligibilityPipeline
from agents.ecosystem.routing import AgentRouter, ExecutionEngine
from agents.ecosystem.registry import AgentRegistry, AgentDescriptor, AgentStatus


def test_full_pipeline_execution():
    """Complete pipeline from event to agent execution."""
    registry = AgentRegistry()
    
    registry.register('echo_agent', AgentDescriptor(
        agent_id='echo_agent',
        name='echo_agent',
        version='1.0.0',
        capabilities=['reference.echo'],
        status=AgentStatus.ACTIVE
    ))
    
    event = Event(
        event_id='event-full-pipeline',
        event_type='ORDER_CREATED',
        occurred_at=datetime.utcnow(),
        tenant_id='tenant-pipeline',
        order_id='order-789',
        payload={'message': 'hello', 'capability': 'reference.echo'}
    )
    
    hook = EventHook()
    envelope = hook.handle_event(event)
    
    discovery = AgentDiscovery(registry)
    candidates = discovery.find_from_envelope(envelope)
    
    assert len(candidates) >= 1, "Should find at least one candidate"
    
    eligibility = EligibilityPipeline(registry)
    eligibility_result = eligibility.check_candidates(candidates, envelope)
    
    assert len(eligibility_result.eligible) >= 1, "Should have eligible agents"
    
    proxy_candidates = [
        DiscoveryResult(
            agent_id=check.agent_id,
            agent=registry.get(check.agent_id),
            reason="; ".join(check.reasons) if check.reasons else "eligible"
        )
        for check in eligibility_result.eligible
    ]
    
    router = AgentRouter()
    decision = router.select(proxy_candidates)
    
    assert decision is not None
    assert decision.agent_id == 'echo_agent'
    
    engine = ExecutionEngine()
    result = engine.execute_from_decision(decision, envelope)
    
    assert result is not None
    assert 'success' in result
    assert result['agent_id'] == 'echo_agent'
    assert 'routing_reason' in result


def test_pipeline_identity_preservation():
    """Pipeline preserves all IDs correctly."""
    registry = AgentRegistry()
    registry.register('agent_1', AgentDescriptor(
        agent_id='agent_1',
        name='agent_1',
        version='1.0.0',
        capabilities=['test'],
        status=AgentStatus.ACTIVE
    ))
    
    event = Event(
        event_id='evt-identity',
        event_type='EVENT',
        occurred_at=datetime.utcnow(),
        tenant_id='tenant-identity',
        order_id='order-ABC',
        payload={'test': 'data', 'capability': 'test'}
    )
    
    hook = EventHook()
    envelope = hook.handle_event(event)
    
    discovery = AgentDiscovery(registry)
    candidates = discovery.find_from_envelope(envelope)
    
    eligibility = EligibilityPipeline(registry)
    eligibility_result = eligibility.check_candidates(candidates, envelope)
    
    assert len(eligibility_result.eligible) >= 1, "Should have eligible agents"
    
    proxy_candidates = [
        DiscoveryResult(
            agent_id=check.agent_id,
            agent=registry.get(check.agent_id),
            reason="; ".join(check.reasons) if check.reasons else "eligible"
        )
        for check in eligibility_result.eligible
    ]
    
    router = AgentRouter()
    decision = router.select(proxy_candidates)
    
    engine = ExecutionEngine()
    result = engine.execute_from_decision(decision, envelope)
    
    assert result['agent_id'] == 'agent_1'
    assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
