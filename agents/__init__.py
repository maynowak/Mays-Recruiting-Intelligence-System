"""
Agents Package for Ground Zero Platform

This package contains modular agent implementations.
Each agent follows the AgentBase contract.
"""

from .base import AgentBase, WorkItemStatus, WorkItem, create_lambda_handler

__all__ = [
    'AgentBase',
    'WorkItemStatus', 
    'WorkItem',
    'create_lambda_handler'
]

registered_agents = [
    # Agent name: module path
    # 'cv_agent': 'agents.cv_agent.handler',
    # 'ats_agent': 'agents.ats_agent.handler',
    # 'match_agent': 'agents.match_agent.handler',
]