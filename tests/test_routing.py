"""
Tests for Agent Routing (AGENT-ROUTING-01)

Tests the routing layer that selects agents from eligible candidates.

No execution, no SQS, no May's Orders integration.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.routing import (
    AgentRouter, RoutingDecision, SelectionStrategy, QueryRouter
)
from agents.ecosystem.discovery import DiscoveryResult, AgentDiscovery
from agents.ecosystem.registry import AgentRegistry, AgentDescriptor, AgentStatus


class TestRoutingDecision:
    """Test RoutingDecision dataclass."""
    
    def test_routing_decision_creation(self):
        """RoutingDecision can be created."""
        decision = RoutingDecision(
            agent_id='test_agent',
            agent=AgentDescriptor(
                agent_id='test_agent',
                name='test_agent',
                version='1.0.0'
            ),
            reason='matches criteria',
            confidence=1.0
        )
        
        assert decision.agent_id == 'test_agent'
        assert decision.reason == 'matches criteria'


class TestSelectionStrategy:
    """Test selection strategies."""
    
    def test_first_match(self):
        """First match returns first candidate."""
        registry = AgentRegistry()
        registry.register('agent_1', AgentDescriptor(
            agent_id='agent_1',
            name='agent_1',
            version='1.0.0',
            capabilities=['test']
        ))
        registry.register('agent_2', AgentDescriptor(
            agent_id='agent_2',
            name='agent_2',
            version='1.0.0',
            capabilities=['test']
        ))
        
        candidates = [
            DiscoveryResult(agent_id='agent_1', agent=registry.get('agent_1'), reason='r1'),
            DiscoveryResult(agent_id='agent_2', agent=registry.get('agent_2'), reason='r2'),
        ]
        
        selected = SelectionStrategy.first_match(candidates)
        
        assert selected.agent_id == 'agent_1'
    
    def test_first_match_empty(self):
        """First match returns None for empty list."""
        result = SelectionStrategy.first_match([])
        assert result is None
    
    def test_last_match(self):
        """Last match returns last candidate."""
        registry = AgentRegistry()
        registry.register('agent_1', AgentDescriptor(
            agent_id='agent_1',
            name='agent_1',
            version='1.0.0',
            capabilities=['test']
        ))
        registry.register('agent_2', AgentDescriptor(
            agent_id='agent_2',
            name='agent_2',
            version='1.0.0',
            capabilities=['test']
        ))
        
        candidates = [
            DiscoveryResult(agent_id='agent_1', agent=registry.get('agent_1'), reason='r1'),
            DiscoveryResult(agent_id='agent_2', agent=registry.get('agent_2'), reason='r2'),
        ]
        
        selected = SelectionStrategy.last_match(candidates)
        
        assert selected.agent_id == 'agent_2'


class TestAgentRouter:
    """Test AgentRouter."""
    
    def test_router_selects_first(self):
        """Router selects first agent from candidates."""
        registry = AgentRegistry()
        registry.register('agent_1', AgentDescriptor(
            agent_id='agent_1',
            name='agent_1',
            version='1.0.0',
            capabilities=['test']
        ))
        
        candidates = [
            DiscoveryResult(agent_id='agent_1', agent=registry.get('agent_1'), reason='matches'),
        ]
        
        router = AgentRouter()
        decision = router.select(candidates)
        
        assert decision is not None
        assert decision.agent_id == 'agent_1'
        assert decision.confidence == 1.0
    
    def test_router_no_candidates(self):
        """Router returns None for no candidates."""
        router = AgentRouter()
        decision = router.select([])
        
        assert decision is None
    
    def test_router_custom_strategy(self):
        """Router can use custom strategy."""
        registry = AgentRegistry()
        registry.register('agent_1', AgentDescriptor(
            agent_id='agent_1',
            name='agent_1',
            version='1.0.0',
            capabilities=['test']
        ))
        registry.register('agent_2', AgentDescriptor(
            agent_id='agent_2',
            name='agent_2',
            version='1.0.0',
            capabilities=['test']
        ))
        
        candidates = [
            DiscoveryResult(agent_id='agent_1', agent=registry.get('agent_1'), reason='r1'),
            DiscoveryResult(agent_id='agent_2', agent=registry.get('agent_2'), reason='r2'),
        ]
        
        router = AgentRouter(strategy=SelectionStrategy.last_match)
        decision = router.select(candidates)
        
        assert decision.agent_id == 'agent_2'


class TestQueryRouter:
    """Test QueryRouter convenience class."""
    
    def test_query_router_selects_agent(self):
        """QueryRouter can select by capability."""
        registry = AgentRegistry()
        registry.register('echo_agent', AgentDescriptor(
            agent_id='echo_agent',
            name='echo_agent',
            version='1.0.0',
            capabilities=['reference.echo']
        ))
        
        discovery = AgentDiscovery(registry)
        router = QueryRouter(registry, discovery)
        
        decision = router.route_by_capability('reference.echo')
        
        assert decision is not None
        assert decision.agent_id == 'echo_agent'
    
    def test_query_router_explicit_agent(self):
        """QueryRouter can route to explicit agent_id."""
        registry = AgentRegistry()
        registry.register('specific', AgentDescriptor(
            agent_id='specific',
            name='specific',
            version='1.0.0',
            capabilities=['test']
        ))
        
        discovery = AgentDiscovery(registry)
        router = QueryRouter(registry, discovery)
        
        decision = router.route_by_capability('test', agent_id='specific')
        
        assert decision is not None
        assert decision.agent_id == 'specific'


class TestNoExecution:
    """Verify no execution occurs during routing."""
    
    def test_routing_does_not_execute_agent(self):
        """Routing only selects, does not execute."""
        registry = AgentRegistry()
        registry.register('test_agent', AgentDescriptor(
            agent_id='test_agent',
            name='test_agent',
            version='1.0.0',
            capabilities=['test']
        ))
        
        candidates = [
            DiscoveryResult(agent_id='test_agent', agent=registry.get('test_agent'), reason='matches'),
        ]
        
        router = AgentRouter()
        decision = router.select(candidates)
        
        assert decision is not None
        assert decision.agent_id == 'test_agent'
        assert decision.reason == 'matches'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
