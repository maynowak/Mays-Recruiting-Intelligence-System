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
from agents.ecosystem.privacy_contract import (
    PRIVACY_CONTRACT_VERSION, validate_capability_input,
    validate_capability_privacy,
)

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

    # Central status decision (fail-closed, Gate 07): only ACTIVE is
    # executable. Every other known status — and any unknown/None
    # value — is INELIGIBLE. This replaces the former RETIRED/
    # DEPRECATED-only hard block (INACTIVE/FAILED/... passed before).
    from agents.ecosystem.agent_status import normalize_agent_status
    normalized = (descriptor.status
                  if isinstance(descriptor.status, AgentStatus)
                  else normalize_agent_status(descriptor.status))
    if normalized != AgentStatus.ACTIVE:
        label = (normalized.value
                 if isinstance(normalized, AgentStatus) else "UNKNOWN")
        reasons.append(f"Agent status is {label} (not executable)")
        return EligibilityCheck(
            agent_id=agent_id,
            eligible=False,
            result=EligibilityResult.INELIGIBLE,
            reasons=reasons
        )
    
    # Check capability support
    if capability and not descriptor.supports_capability(capability):
        reasons.append(f"Agent does not support capability: {capability}")

    if capability:
        if descriptor.privacy_contract_version != PRIVACY_CONTRACT_VERSION:
            reasons.append("PRIVACY_CONTRACT_VERSION_UNSUPPORTED")
        validation = validate_capability_privacy(
            agent_id=descriptor.agent_id,
            agent_version=descriptor.version,
            capability=capability,
            declaration=(descriptor.privacy_declarations.get(capability)
                         if isinstance(descriptor.privacy_declarations, dict)
                         else None),
            evidence=(descriptor.privacy_evidence.get(capability)
                      if isinstance(descriptor.privacy_evidence, dict)
                      else None),
            source_sha=descriptor.source_sha,
            artifact_sha256=descriptor.artifact_sha256,
        )
        if not validation.valid:
            reasons.append(validation.reason)
    
    # Check body compatibility
    if body_version and not descriptor.is_compatible_with_body(body_version):
        reasons.append(f"Incompatible agent body version")
    
    # Check runtime compatibility
    if runtime and not descriptor.is_compatible_with_runtime(runtime):
        reasons.append(f"Incompatible runtime: {runtime}")
    
    eligible = len(reasons) == 0
    
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


def authorize_direct_work_item(registry, work_item: Dict[str, Any]) -> bool:
    """Apply the same capability privacy gate to legacy direct execution.

    The direct AgentBody router has no candidate descriptor of its own, so it
    must resolve the registered descriptor and pass normal Eligibility. Missing
    identity/capability/registry data is a denial.
    """
    if not isinstance(work_item, dict):
        return False
    agent_id = work_item.get("agentId")
    capability = work_item.get("capability")
    if not isinstance(capability, str) or not capability.strip():
        return False
    if isinstance(agent_id, str) and agent_id.strip():
        descriptor = registry.get(agent_id)
    else:
        # Capability-only routing is supported by AgentBody. Authorization is
        # safe only when that capability resolves to exactly one registered
        # descriptor; ambiguity must not choose an arbitrary principal.
        matches = registry.list_by_capability(capability)
        if len(matches) != 1:
            return False
        descriptor = matches[0]
        agent_id = descriptor.agent_id
    check = check_eligibility(
        agent_id, descriptor, capability=capability,
        tenant_id=work_item.get("tenantId"),
        user_id=work_item.get("userId"),
    )
    if not check.eligible:
        return False
    declaration = descriptor.privacy_declarations.get(capability)
    return validate_capability_input(declaration, work_item.get("payload"))


@dataclass
class EligibilityPipelineResult:
    """
    Result of checking eligibility for a processing envelope.
    
    Contains both eligible and rejected candidates with reasons.
    """
    eligible: List[EligibilityCheck]
    rejected: List[EligibilityCheck]


class EligibilityPipeline:
    """
    Pipeline for checking eligibility of discovery candidates.
    
    Takes candidates from discovery and validates them against
    the envelope's requirements and tenant context.
    """
    
    def __init__(self, registry):
        self.registry = registry
    
    def check_candidates(
        self, 
        candidates: List['DiscoveryResult'],
        envelope: 'ProcessingEnvelope'
    ) -> EligibilityPipelineResult:
        """
        Check eligibility for a list of candidates.
        
        Args:
            candidates: List of DiscoveryResult candidates
            envelope: ProcessingEnvelope with tenant context
            
        Returns:
            EligibilityPipelineResult with eligible and rejected lists
        """
        eligible = []
        rejected = []
        
        capability = envelope.input.get('capability')
        body_version = envelope.body_version
        runtime = envelope.runtime or envelope.execution_profile
        
        for candidate in candidates:
            check = check_eligibility(
                agent_id=candidate.agent_id,
                descriptor=candidate.agent,
                capability=capability,
                body_version=body_version,
                runtime=runtime,
                tenant_id=envelope.tenant_id,
            )
            
            if check.eligible:
                eligible.append(check)
                logger.debug(
                    f"Agent {candidate.agent_id} is eligible: {check.reasons}"
                )
            else:
                rejected.append(check)
                logger.debug(
                    f"Agent {candidate.agent_id} rejected: {check.reasons}"
                )
        
        logger.info(
            f"Eligibility check: {len(eligible)} eligible, {len(rejected)} rejected"
        )
        
        return EligibilityPipelineResult(eligible=eligible, rejected=rejected)
