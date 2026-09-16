"""
Agent Discovery

Provides discovery mechanisms for finding suitable agents
based on capabilities, requirements, and constraints.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from agents.ecosystem.registry import AgentRegistry, AgentDescriptor, AgentStatus
from agents.ecosystem.event_hook import ProcessingEnvelope

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """Result of an agent discovery query."""
    agent_id: str
    agent: AgentDescriptor
    reason: str  # Why this agent was selected


class AgentDiscovery:
    """
    Discovers eligible agents based on capability and compatibility.
    """
    
    def __init__(self, registry: AgentRegistry):
        self.registry = registry
    
    def find(self,
             capability: Optional[str] = None,
             agent_id: Optional[str] = None,
             required_runtime: Optional[str] = None,
             required_body: Optional[str] = None,
             status: Optional[AgentStatus] = None,
             max_results: int = 10) -> List[DiscoveryResult]:
        """
        Discover agents matching the given criteria.
        
        Args:
            capability: Required capability the agent must support
            agent_id: Specific agent ID to find
            required_runtime: Runtime compatibility requirement
            required_body: Agent body version requirement
            status: Filter by agent status
            max_results: Maximum number of results to return
        
        Returns:
            List of matching agent descriptors with reasons
        """
        if agent_id:
            agent = self.registry.get(agent_id)
            if agent:
                return [DiscoveryResult(agent_id=agent_id, agent=agent, 
                                       reason="Specific agent requested")]
            return []
        
        candidates = self.registry.list_all(status)
        results = []
        
        for agent in candidates:
            reasons = []
            
            # Check capability
            if capability and not agent.supports_capability(capability):
                continue
            if capability:
                reasons.append(f"supports capability: {capability}")
            
            # Check runtime compatibility
            if required_runtime and not agent.is_compatible_with_runtime(required_runtime):
                continue
            if required_runtime:
                reasons.append(f"runtime compatible: {required_runtime}")
            
            # Check body version
            if required_body and not agent.is_compatible_with_body(required_body):
                continue
            if required_body:
                reasons.append(f"body compatible: {required_body}")
            
            reason = "; ".join(reasons) if reasons else "matches all criteria"
            results.append(DiscoveryResult(
                agent_id=agent.agent_id,
                agent=agent,
                reason=reason
            ))
            
            if len(results) >= max_results:
                break
        
        return results
    
    def find_by_capability(self, capability: str) -> List[DiscoveryResult]:
        """Find all agents supporting a capability."""
        return self.find(capability=capability)
    
    def find_recipients(self, 
                        capability: str,
                        source_agent_id: Optional[str] = None) -> List[DiscoveryResult]:
        """
        Find agents that can receive an invocation.
        
        Excludes the source agent to prevent self-invocation.
        """
        results = self.find(capability=capability)
        if source_agent_id:
            results = [r for r in results if r.agent_id != source_agent_id]
        return results
    
    def find_from_envelope(self, envelope: ProcessingEnvelope) -> List[DiscoveryResult]:
        """
        Discover agents matching a processing envelope.
        
        Uses the envelope's context to find candidates:
        - explicit agent_id (if provided in envelope)
        - capability (if present in envelope input)
        - runtime compatibility
        - body version compatibility
        - status (only ACTIVE by default)
        
        Args:
            envelope: ProcessingEnvelope with context
            
        Returns:
            List of candidate agents with reasons
        """
        capability = envelope.input.get('capability')
        required_runtime = envelope.runtime or envelope.execution_profile
        required_body = envelope.body_version
        
        candidates = self.find(
            agent_id=envelope.agent_id,
            capability=capability,
            required_runtime=required_runtime,
            required_body=required_body,
            status=AgentStatus.ACTIVE,
            max_results=100
        )
        
        logger.info(
            f"Found {len(candidates)} candidates from envelope "
            f"[trigger: {envelope.trigger_type.value if envelope.trigger_type else 'N/A'}]"
        )
        
        return candidates


class CapabilityRegistry:
    """
    Registry for capabilities allowing lookup of agents by capability.
    """
    
    def __init__(self, discovery: AgentDiscovery):
        self.discovery = discovery
    
    def resolve(self, capability: str) -> Optional[AgentDescriptor]:
        """Resolve a capability to a single agent."""
        results = self.discovery.find(capability=capability, max_results=1)
        return results[0].agent if results else None
    
    def list_providers(self, capability: str) -> List[str]:
        """List all agent IDs that provide a capability."""
        results = self.discovery.find(capability=capability)
        return [r.agent_id for r in results]