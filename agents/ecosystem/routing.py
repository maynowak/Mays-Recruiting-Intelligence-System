"""
Agent Routing & Selection

Provides routing mechanisms for selecting a single agent from
eligible candidates.

This module implements:
- AgentRouter: Selects the best agent for a given context
- SelectionStrategy: Strategy pattern for selection logic
- Simple deterministic selection for now (no AI ranking)

Usage:
    from agents.ecosystem.routing import AgentRouter, SelectionStrategy
    
    router = AgentRouter()
    winner = router.select(criteria='capability:echo')
"""

import logging
from typing import Optional, List, Callable, Any
from dataclasses import dataclass

from agents.ecosystem.registry import AgentDescriptor
from agents.ecosystem.discovery import DiscoveryResult
from agents.ecosystem.eligibility import EligibilityCheck

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """
    Result of agent routing selection.
    
    Contains the selected agent and metadata about the decision.
    """
    agent_id: str
    agent: AgentDescriptor
    reason: str
    confidence: float = 1.0
    selected_at: Optional[str] = None


class SelectionStrategy:
    """
    Strategy for selecting an agent from candidates.
    
    Default strategy is deterministic selection (first match).
    """
    
    @staticmethod
    def first_match(candidates: List[DiscoveryResult]) -> Optional[DiscoveryResult]:
        """Select the first candidate."""
        if not candidates:
            return None
        return candidates[0]
    
    @staticmethod
    def last_match(candidates: List[DiscoveryResult]) -> Optional[DiscoveryResult]:
        """Select the last candidate."""
        if not candidates:
            return None
        return candidates[-1]
    
    @staticmethod
    def capacity_aware(candidates: List[DiscoveryResult]) -> Optional[DiscoveryResult]:
        """
        Select based on capacity (future extension point).
        
        For now, falls back to first match.
        """
        return SelectionStrategy.first_match(candidates)


class AgentRouter:
    """
    Routes to a single agent from eligible candidates.
    
    This router selects ONE agent from the candidates provided.
    It does NOT perform ranking or AI-based selection.
    
    The router maintains the boundary that:
    - Discovery finds candidates
    - Eligibility validates candidates
    - Router selects ONE winner
    """
    
    def __init__(self, strategy: Callable = None):
        """
        Initialize the router.
        
        Args:
            strategy: Selection strategy function. Defaults to first_match.
        """
        self.strategy = strategy or SelectionStrategy.first_match
    
    def select(
        self,
        candidates: List[DiscoveryResult],
        context: Optional[dict] = None
    ) -> Optional[RoutingDecision]:
        """
        Select a single agent from candidates.
        
        Args:
            candidates: List of eligible candidates from discovery
            context: Optional context for context-aware selection
            
        Returns:
            RoutingDecision with selected agent, or None if no candidates
        """
        if not candidates:
            logger.warning("No candidates to select from")
            return None
        
        selected = self.strategy(candidates)
        
        if selected is None:
            logger.warning("Selection strategy returned None")
            return None
        
        decision = RoutingDecision(
            agent_id=selected.agent_id,
            agent=selected.agent,
            reason=selected.reason,
            confidence=1.0
        )
        
        logger.info(
            f"Selected agent {decision.agent_id} "
            f"[candidates: {len(candidates)}, reason: {decision.reason}]"
        )
        
        return decision
    
    def select_from_eligibility(
        self,
        eligibility_result: Any,
        context: Optional[dict] = None
    ) -> Optional[RoutingDecision]:
        """
        Select from eligibility pipeline result.
        
        Args:
            eligibility_result: EligibilityPipelineResult with eligible list
            context: Optional context for selection
            
        Returns:
            RoutingDecision or None
        """
        candidates = [
            DiscoveryResult(
                agent_id=check.agent_id,
                agent=None,
                reason="; ".join(check.reasons) if check.reasons else "eligible"
            )
            for check in eligibility_result.eligible
        ]
        
        if candidates:
            for check in eligibility_result.eligible:
                desc = check.__dict__.get('agent') if hasattr(check, 'agent') else None
                if desc is None:
                    from agents.ecosystem.registry import AgentRegistry
                    registry = AgentRegistry()
                    desc = registry.get(check.agent_id)
                
                candidates = [
                    DiscoveryResult(
                        agent_id=r.agent_id,
                        agent=r.agent or desc,
                        reason=r.reason
                    )
                    for r in candidates
                ]
                break
        
        return self.select(candidates, context)


class QueryRouter:
    """
    Route based on capability queries.
    
    Combines discovery and routing for convenience.
    """
    
    def __init__(self, registry, discovery, strategy=None):
        """
        Initialize with registry and discovery.
        
        Args:
            registry: AgentRegistry instance
            discovery: AgentDiscovery instance
            strategy: Optional selection strategy
        """
        self.registry = registry
        self.discovery = discovery
        self.router = AgentRouter(strategy)
    
    def route_by_capability(
        self,
        capability: str,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Optional[RoutingDecision]:
        """
        Route to an agent by capability.
        
        Args:
            capability: Required capability
            tenant_id: Optional tenant context
            agent_id: Optional specific agent to route to
            
        Returns:
            RoutingDecision or None
        """
        candidates = self.discovery.find(
            capability=capability,
            agent_id=agent_id,
            status=None,
            max_results=10
        )
        
        return self.router.select(candidates)