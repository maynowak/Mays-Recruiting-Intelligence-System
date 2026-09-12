"""
Agent Context

Extracts and validates context from work items.
Provides user, tenant, and execution context for agents.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class AgentContext:
    """
    Provides context for agent execution.
    
    Extracts context from work items and ensures
    tenant isolation and proper tracing.
    """

    def __init__(self, work_item: Dict[str, Any]):
        self._work_item = work_item
        self._validated = False
        self._extracted = False

    def validate(self) -> bool:
        """
        Validate the work item has required context.
        
        Returns:
            True if valid, False otherwise
        """
        required = ['workId', 'type', 'tenantId', 'idempotencyKey']
        for field in required:
            if field not in self._work_item:
                logger.error(f"Missing required field: {field}")
                return False
        
        self._validated = True
        return True

    @property
    def work_id(self) -> Optional[str]:
        """Unique work identifier."""
        return self._work_item.get('workId')

    @property
    def tenant_id(self) -> Optional[str]:
        """Tenant context for isolation."""
        return self._work_item.get('tenantId')

    @property
    def user_id(self) -> Optional[str]:
        """User who requested the work."""
        return self._work_item.get('requestedBy')

    @property
    def agent_id(self) -> Optional[str]:
        """Target agent."""
        return self._work_item.get('agentId')

    @property
    def capability(self) -> Optional[str]:
        """Specific capability to execute."""
        return self._work_item.get('capability')

    @property
    def work_type(self) -> Optional[str]:
        """Type of work."""
        return self._work_item.get('type')

    @property
    def idempotency_key(self) -> Optional[str]:
        """Key for deduplication."""
        return self._work_item.get('idempotencyKey')

    @property
    def request_id(self) -> Optional[str]:
        """Request correlation ID."""
        return self._work_item.get('requestId')

    @property
    def payload(self) -> Dict[str, Any]:
        """Agent-specific payload."""
        return self._work_item.get('payload', {})

    @property
    def attempt(self) -> int:
        """Retry attempt number."""
        return self._work_item.get('attempt', 0)

    @property
    def status(self) -> Optional[str]:
        """Current status."""
        return self._work_item.get('status')

    @property
    def created_at(self) -> Optional[str]:
        """Creation timestamp."""
        return self._work_item.get('createdAt')

    def get_context_dict(self) -> Dict[str, Any]:
        """Get all context as dictionary."""
        return {
            'workId': self.work_id,
            'tenantId': self.tenant_id,
            'userId': self.user_id,
            'agentId': self.agent_id,
            'capability': self.capability,
            'type': self.work_type,
            'idempotencyKey': self.idempotency_key,
            'requestId': self.request_id,
            'payload': self.payload,
            'attempt': self.attempt,
        }

    def assign_ids(self):
        """Generate any missing IDs."""
        if not self.work_id:
            self._work_item['workId'] = str(uuid.uuid4())
        if not self.idempotency_key:
            self._work_item['idempotencyKey'] = str(uuid.uuid4())

    @classmethod
    def from_work_item(cls, work_item: Dict[str, Any]) -> 'AgentContext':
        """Create context from work item."""
        return cls(work_item)


def create_context(work_item: Dict[str, Any]) -> Optional[AgentContext]:
    """
    Create and validate agent context.
    
    Args:
        work_item: Work item dictionary
        
    Returns:
        AgentContext if valid, None otherwise
    """
    context = AgentContext.from_work_item(work_item)
    if context.validate():
        return context
    return None