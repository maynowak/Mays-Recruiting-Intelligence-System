"""
Agent Eligibility

Provides eligibility checking for agent invocations.

Eligibility determines whether an agent can be invoked given the
current request context and requirements.
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from agents.ecosystem.registry import AgentDescriptor, AgentStatus

logger = logging.getLogger(__name__)


class EligibilityResult(Enum):
    """Result of an eligibility check."""
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class EligibilityCheck:
    """
    Result of checking if an agent is eligible for invocation.
    """
    agent_id: str
    eligible: bool
    result: EligibilityResult
    reasons: List[str] = None
    
    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []


def check_eligibility(agent_id: str,
                      descriptor: AgentDescriptor,
                      capability: Optional[str] = None,
                      body_version: Optional[str] = None,
                      runtime: Optional[str] = None,
                      tenant_id: Optional[str] = None,
                      user_id: Optional[str] = None) -> EligibilityCheck:
    """
    Check if an agent is eligible for invocation.
    
    Args:
        agent_id: Agent being checked
        descriptor: Agent descriptor
        capability: Required capability
        body_version: Required agent body version
        runtime: Required runtime
        tenant_id: Tenant context (for future checks)
        user_id: User context (for future checks)
    
    Returns:
        EligibilityCheck with result and reasons
    """
    reasons = []
    
    # Check if agent is registered
    if descriptor is None:
        return EligibilityCheck(
            agent_id=agent_id,
            eligible=False,
            result=EligibilityResult.UNKNOWN,
            reasons=["Agent not registered"]
        )
    
    # Check status
    if descriptor.status != AgentStatus.ACTIVE:
        reasons.append(f"Agent status is {descriptor.status.value}")
        if descriptor.status in (AgentStatus.RETIRED, AgentStatus.DEPRECATED):
            return EligibilityCheck(
                agent_id=agent_id,
                eligible=False,
                result=EligibilityResult.INELIGIBLE,
                reasons=reasons
            )
    
    # Check capability support
    if capability and not descriptor.supports_capability(capability):
        reasons.append(f"Agent does not support capability: {capability}")
    
    # Check body compatibility
    if body_version and not descriptor.is_compatible_with_body(body_version):
        reasons.append(f"Incompatible agent body version")
    
    # Check runtime compatibility
    if runtime and not descriptor.is_compatible_with_runtime(runtime):
        reasons.append(f"Incompatible runtime: {runtime}")
    
    eligible = len(reasons) == 0 or all(
        "does not support" not in r for r in reasons
    )
    
    if eligible:
        reasons.insert(0, "Agent is eligible")
        result = EligibilityResult.ELIGIBLE
    else:
        result = EligibilityResult.INELIGIBLE
    
    return EligibilityCheck(
        agent_id=agent_id,
        eligible=eligible,
        result=result,
        reasons=reasons
    )


class EligibilityChecker:
    """
    Checks eligibility for agent invocations.
    """
    
    def __init__(self, registry):
        self.registry = registry
    
    def check(self, agent_id: str, **kwargs) -> EligibilityCheck:
        """Check eligibility for an agent."""
        descriptor = self.registry.get(agent_id)
        return check_eligibility(agent_id, descriptor, **kwargs)