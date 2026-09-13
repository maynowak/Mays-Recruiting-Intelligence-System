"""
Agent Registry

Provides centralized agent registration and lookup functionality.

The registry maintains descriptions of available agents and their
capabilities, allowing discovery services to find appropriate
agents for tasks.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent lifecycle status."""
    REGISTERED = "REGISTERED"
    AVAILABLE = "AVAILABLE"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"
    FAILED = "FAILED"


class ExecutionProfile(Enum):
    """Supported execution environments."""
    LAMBDA = "LAMBDA"
    # Future: MICROVM, CONTAINER, WORKER, etc.


@dataclass
class AgentDescriptor:
    """
    Describes an agent's capabilities and requirements.
    """
    agent_id: str
    name: str
    version: str
    status: AgentStatus = AgentStatus.ACTIVE
    capabilities: List[str] = field(default_factory=list)
    supported_bodies: List[str] = field(default_factory=lambda: ["1.0.0"])
    supported_runtimes: List[str] = field(default_factory=lambda: ["python3.14"])
    execution_profile: ExecutionProfile = ExecutionProfile.LAMBDA
    risk_level: str = "low"
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_compatible_with_body(self, body_version: str) -> bool:
        """Check if this agent supports the given agent body version."""
        return body_version in self.supported_bodies
    
    def is_compatible_with_runtime(self, runtime: str) -> bool:
        """Check if this agent supports the given runtime."""
        return runtime in self.supported_runtimes
    
    def supports_capability(self, capability: str) -> bool:
        """Check if this agent supports the given capability."""
        return capability in self.capabilities
    
    def can_execute(self, capability: str = None, 
                    body_version: str = None,
                    runtime: str = None) -> bool:
        """Full compatibility check."""
        if capability and not self.supports_capability(capability):
            return False
        if body_version and not self.is_compatible_with_body(body_version):
            return False
        if runtime and not self.is_compatible_with_runtime(runtime):
            return False
        return True


class AgentRegistry:
    """
    Central registry for agent descriptors.
    
    Provides registration, lookup, and listing capabilities for agents.
    """
    
    def __init__(self):
        self._agents: Dict[str, AgentDescriptor] = {}
    
    def register(self, agent_id: str, descriptor: AgentDescriptor) -> bool:
        """Register an agent descriptor."""
        self._agents[agent_id] = descriptor
        logger.info(f"Registered agent: {agent_id}")
        return True
    
    def unregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
            return True
        return False
    
    def get(self, agent_id: str) -> Optional[AgentDescriptor]:
        """Get agent descriptor by ID."""
        return self._agents.get(agent_id)
    
    def list_all(self, status: Optional[AgentStatus] = None) -> List[AgentDescriptor]:
        """List all registered agents, optionally filtered by status."""
        agents = list(self._agents.values())
        if status:
            agents = [a for a in agents if a.status == status]
        return agents
    
    def list_by_capability(self, capability: str) -> List[AgentDescriptor]:
        """Find agents that support a given capability."""
        return [
            a for a in self._agents.values() 
            if a.supports_capability(capability)
        ]
    
    def list_by_status(self, status: AgentStatus) -> List[AgentDescriptor]:
        """Find agents with a specific status."""
        return [a for a in self._agents.values() if a.status == status]
    
    def is_registered(self, agent_id: str) -> bool:
        """Check if an agent is registered."""
        return agent_id in self._agents


# Global registry instance
_registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    """Get the global registry instance."""
    return _registry