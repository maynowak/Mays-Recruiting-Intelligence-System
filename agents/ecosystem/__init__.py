"""
Agent Ecosystem Foundation

Provides standardized registry, discovery, and eligibility mechanisms
for agents within the Agent Body ecosystem.

This module enables agent-to-agent collaboration while maintaining
clean separation between domain logic and infrastructure.
"""

from agents.ecosystem.registry import AgentRegistry, AgentDescriptor, AgentStatus, ExecutionProfile
from agents.ecosystem.discovery import AgentDiscovery, CapabilityRegistry, DiscoveryResult
from agents.ecosystem.eligibility import EligibilityCheck, check_eligibility, EligibilityPipelineResult, EligibilityPipeline
from agents.ecosystem.chain import ProcessingChain, ChainExecutor, ChainStep
from agents.ecosystem.catalog_adapter import CatalogAdapter, populate_registry_from_catalog
from agents.ecosystem.event_hook import Event, ProcessingEnvelope, EventHook, TriggerType, create_processing_envelope_from_event

__all__ = [
    'AgentRegistry',
    'AgentDescriptor',
    'AgentStatus',
    'ExecutionProfile',
    'AgentDiscovery',
    'CapabilityRegistry',
    'DiscoveryResult',
    'EligibilityCheck',
    'check_eligibility',
    'EligibilityPipelineResult',
    'EligibilityPipeline',
    'ProcessingChain',
    'ChainExecutor',
    'ChainStep',
    'CatalogAdapter',
    'populate_registry_from_catalog',
    'Event',
    'ProcessingEnvelope',
    'EventHook',
    'TriggerType',
    'create_processing_envelope_from_event',
]


class AgentEcosystem:
    """
    Central manager for the Agent Ecosystem.
    
    Provides registry, discovery, and eligibility services
    for agent-to-agent workflows.
    """
    
    def __init__(self, registry=None, discovery=None):
        self.registry = registry or AgentRegistry()
        self.discovery = discovery or AgentDiscovery(self.registry)
    
    def register(self, agent_id: str, descriptor: AgentDescriptor):
        """Register an agent in the ecosystem."""
        return self.registry.register(agent_id, descriptor)
    
    def discover(self, capability: str = None, required_runtime: str = None):
        """Discover eligible agents by capability or runtime."""
        return self.discovery.find(capability=capability, runtime=required_runtime)


# Global ecosystem instance
_ecosystem = None


def get_ecosystem() -> AgentEcosystem:
    """Get the global agent ecosystem instance."""
    global _ecosystem
    if _ecosystem is None:
        _ecosystem = AgentEcosystem()
    return _ecosystem