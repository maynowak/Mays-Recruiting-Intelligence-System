"""
ATS Agent Module

Integration adapter for the existing ATS Core HTTP API from mays-jobsearch repository.

This module provides:
- ATSAgent: AgentBase implementation that delegates to the ATS API
- ATSHttpClient: Thin HTTP client for the ATS service
- create_ats_handler: Factory for Lambda handler
"""

from agents.ats_agent.agent import ATSAgent, ATSHttpClient, create_ats_handler, ATSAPIError

__all__ = ['ATSAgent', 'ATSHttpClient', 'create_ats_handler', 'ATSAPIError']