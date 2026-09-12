"""
Agent Router

Routes work items to appropriate agents based on work type and capability.
This is a pure routing component - NO domain logic.
"""

import logging
from typing import Dict, Any, Optional, Callable, List

logger = logging.getLogger(__name__)


class AgentRouter:
    """
    Routes work items to appropriate agent handlers.
    
    Routes based on:
    - work type (e.g., 'ats_process', 'cv_analyze')
    - capability (e.g., 'match.resume', 'analyze.cv')
    - agentId (explicit routing)
    """

    def __init__(self):
        self._routes: Dict[str, Callable] = {}
        self._type_routes: Dict[str, Callable] = {}
        self._capability_routes: Dict[str, Callable] = {}

    def register(
        self, 
        work_type: Optional[str] = None,
        capability: Optional[str] = None,
        handler: Optional[Callable] = None,
        agent_id: Optional[str] = None
    ):
        """
        Register a handler for a work type or capability.
        
        Args:
            work_type: Work type to route (e.g., 'ats_process')
            capability: Capability to route (e.g., 'analyze.cv')
            handler: Handler function/class
            agent_id: Specific agent ID to route to
        """
        if handler:
            if agent_id:
                self._routes[f'agent:{agent_id}'] = handler
            if work_type:
                self._type_routes[work_type] = handler
            if capability:
                self._capability_routes[capability] = handler

    def route(self, work_item: Dict[str, Any]) -> Optional[Callable]:
        """
        Route a work item to the appropriate handler.
        
        Routing priority:
        1. Explicit agentId
        2. Capability match
        3. Work type match
        4. Default handler
        
        Args:
            work_item: Work item from SQS/API
            
        Returns:
            Handler function or None if no route found
        """
        agent_id = work_item.get('agentId')
        if agent_id and f'agent:{agent_id}' in self._routes:
            return self._routes[f'agent:{agent_id}']

        capability = work_item.get('capability')
        if capability and capability in self._capability_routes:
            return self._capability_routes[capability]

        work_type = work_item.get('type')
        if work_type and work_type in self._type_routes:
            return self._type_routes[work_type]

        return None

    def has_route(self, work_item: Dict[str, Any]) -> bool:
        """Check if a route exists for this work item."""
        return self.route(work_item) is not None

    def get_routes(self) -> Dict[str, Callable]:
        """Get all registered routes."""
        all_routes = {}
        all_routes.update(self._routes)
        all_routes.update(self._type_routes)
        all_routes.update(self._capability_routes)
        return all_routes


# Global router instance
_router = AgentRouter()


def get_router() -> AgentRouter:
    """Get the global router instance."""
    return _router


def register_route(**kwargs):
    """Decorator to register a handler."""
    def decorator(handler):
        _router.register(handler=handler, **kwargs)
        return handler
    return decorator