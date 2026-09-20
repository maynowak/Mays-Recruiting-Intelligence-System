"""
ATS Agent Module

Integration adapter for the existing ATS Core HTTP API from mays-jobsearch repository.

This module:
- Provides an HTTP client for the ATS API
- Implements the AgentBase contract for integration
- Provides registry integration for the Agent Ecosystem

IMPORTANT: This agent does NOT implement any ATS business logic.
All ATS functionality is delegated to the external ATS API.
"""

from agents.ats_agent.agent import ATSAgent, ATSHttpClient, create_ats_handler, ATSAPIError
from agents.ats_agent.registry import register_ats_agent, get_ats_descriptor, is_ats_registered, ATS_ANALYZE_CAPABILITY, ATS_WORK_TYPE

__all__ = [
    # Main classes
    'ATSAgent',
    'ATSHttpClient',
    'ATSAPIError',
    
    # Factory
    'create_ats_handler',
    
    # Registry integration
    'register_ats_agent',
    'get_ats_descriptor',
    'is_ats_registered',
    
    # Constants
    'ATS_ANALYZE_CAPABILITY',
    'ATS_WORK_TYPE',
]