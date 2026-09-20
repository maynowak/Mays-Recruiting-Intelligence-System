"""
ATS Agent Registry Integration

This module provides the integration between the ATS Agent and the
existing Agent Ecosystem Registry.

IMPORTANT: This module does NOT modify the persistent DynamoDB catalog.
It connects to the RUNTIME Registry only.

Usage:
    from agents.ats_agent.registry import register_ats_agent
    
    registry = get_registry()
    register_ats_agent(registry)
"""

import logging
import sys

if '.' not in sys.path:
    sys.path.insert(0, '.')

from agents.ecosystem.registry import AgentRegistry, AgentDescriptor, AgentStatus, ExecutionProfile
from agents.ats_agent.agent import ATSAgent

logger = logging.getLogger(__name__)


# The capability string for ATS job analysis
ATS_ANALYZE_CAPABILITY = 'analyze.job'

# The work type for ATS processing
ATS_WORK_TYPE = 'ats_process'


def get_ats_descriptor() -> AgentDescriptor:
    """
    Get the AgentDescriptor for the ATS Agent.
    
    Returns:
        AgentDescriptor configured for ATS capabilities.
    """
    return AgentDescriptor(
        agent_id='ats-agent',
        name='ATS Agent',
        version='1.0.0',
        status=AgentStatus.ACTIVE,
        capabilities=[ATS_ANALYZE_CAPABILITY],
        supported_bodies=['1.0.0'],
        supported_runtimes=['python3.14'],
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level='low',
        description='ATS job matching agent via HTTP API integration with mays-jobsearch',
        metadata={
            'integration': 'http',
            'source': 'mays-jobsearch',
        }
    )


def register_ats_agent(registry: AgentRegistry = None) -> bool:
    """
    Register the ATS Agent in the runtime registry.
    
    This function connects the ATS Agent to the existing Agent Ecosystem
    without modifying any AWS infrastructure.
    
    Args:
        registry: AgentRegistry instance to register in.
                  If None, uses the global registry.
    
    Returns:
        True if registration successful, False otherwise.
    """
    from agents.ecosystem.registry import get_registry
    
    if registry is None:
        registry = get_registry()
    
    descriptor = get_ats_descriptor()
    
    try:
        registry.register('ats-agent', descriptor)
        logger.info("ATS Agent registered in runtime registry")
        return True
    except Exception as e:
        logger.error(f"Failed to register ATS Agent: {e}")
        return False


def is_ats_registered(registry: AgentRegistry = None) -> bool:
    """
    Check if the ATS agent is registered.
    
    Args:
        registry: AgentRegistry instance to check.
                  If None, uses the global registry.
    
    Returns:
        True if ATS agent is registered, False otherwise.
    """
    from agents.ecosystem.registry import get_registry
    
    if registry is None:
        registry = get_registry()
    
    return registry.is_registered('ats-agent')