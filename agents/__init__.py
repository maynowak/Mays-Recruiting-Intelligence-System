"""
Agents Package for Ground Zero Platform

This package contains modular agent implementations.
Each agent follows the AgentBase contract.
"""

from .base import AgentBase, WorkItemStatus, WorkItem, create_lambda_handler
from .reference_agent.service import ReferenceAgent

__all__ = [
    'AgentBase',
    'WorkItemStatus', 
    'WorkItem',
    'create_lambda_handler',
    'ReferenceAgent'
]

registered_agents = [
    'reference_agent',
]