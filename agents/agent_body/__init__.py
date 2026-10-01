"""
Agent Body

A unified, reusable technical foundation for Ground Zero agents.

This module provides:
- AgentRouter: Routes work items to appropriate agents
- AgentContext: Extracts execution context from work items
- AgentExecutor: Manages execution lifecycle
- AgentResultHandler: Standardizes result formatting
- AgentMonitor: Provides observability

Usage:
    from agents.agent_body import AgentBody
    
    agent_body = AgentBody()
    result = agent_body.execute(work_item)
"""

from agents.agent_body.router import AgentRouter, get_router, register_route
from agents.agent_body.context import AgentContext, create_context
from agents.agent_body.executor import AgentExecutor, create_agent_handler
from agents.agent_body.result import AgentResultHandler
from agents.agent_body.monitor import AgentMonitor, get_monitor

__all__ = [
    'AgentRouter',
    'AgentContext',
    'AgentExecutor',
    'AgentResultHandler',
    'AgentMonitor',
    'create_context',
    'create_agent_handler',
    'get_router',
    'get_monitor',
    'register_route',
]


class AgentBody:
    """
    Unified Agent Body for Ground Zero.
    
    Coordinates routing, context, execution, result handling, and monitoring.
    """

    def __init__(self, router: AgentRouter = None):
        self.router = router or AgentRouter()
        self.executor = AgentExecutor(router=self.router)
        self.monitor = AgentMonitor()

    def execute(self, work_item: dict) -> dict:
        """Execute a work item through the agent body."""
        return self.executor.execute(work_item)

    def register_agent(self, work_type: str = None, capability: str = None, handler: callable = None, agent_id: str = None):
        """Register an agent handler."""
        self.router.register(work_type=work_type, capability=capability, handler=handler, agent_id=agent_id)