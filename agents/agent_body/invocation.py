"""
Agent Invocation

Provides a standardized mechanism for agents to invoke other agents.
This layer creates the abstraction for agent-to-agent communication
without exposing runtime-specific details.

Key Principle:
    Domain agents should only know ABOUT a capability, not WHERE
    or HOW it is executed.

Usage:
    from agents.agent_body.invocation import invoke_agent
    
    result = invoke_agent(
        target_agent_id="target-agent",
        capability="some.capability",
        payload={"data": "value"},
        parent_work_id="parent-work-id"
    )
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

import sys
sys.path.insert(0, '.')

logger = logging.getLogger(__name__)


class InvocationContract:
    """
    Defines the contract for agent-to-agent invocation.
    
    This contract standardizes how agents can invoke other agents,
    ensuring clean separation between domain logic and runtime.
    """
    
    SYNC = "SYNC"
    ASYNC = "ASYNC"
    
    def __init__(self,
                 target_agent_id: Optional[str] = None,
                 capability: Optional[str] = None,
                 payload: Optional[Dict[str, Any]] = None,
                 parent_work_id: Optional[str] = None,
                 tenant_id: Optional[str] = None,
                 mode: str = SYNC):
        """
        Create an invocation request.
        
        Args:
            target_agent_id: The agent to invoke
            capability: The capability/operation to execute
            payload: Input data for the target agent
            parent_work_id: WorkId of the invoking agent
            tenant_id: Tenant context for isolation
            mode: SYNC or ASYNC execution mode
        """
        self.target_agent_id = target_agent_id
        self.capability = capability
        self.payload = payload or {}
        self.parent_work_id = parent_work_id
        self.tenant_id = tenant_id
        self.mode = mode
        
        self._validate()
    
    def _validate(self):
        """Validate the invocation contract."""
        if not self.target_agent_id and not self.capability:
            raise ValueError("Must specify target_agent_id or capability")
        
        if self.mode not in (self.SYNC, self.ASYNC):
            raise ValueError(f"Invalid mode: {self.mode}")
    
    def to_work_item(self, work_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert to a work item for processing through the standard flow.
        
        This allows invocations to reuse the existing Ground Zero
        SQS → Worker → Agent Body → Agent processing path.
        """
        import uuid
        
        return {
            'workId': work_id or str(uuid.uuid4()),
            'type': f'invocation_{self.target_agent_id or "unknown"}',
            'tenantId': self.tenant_id or 'default',
            'requestedBy': 'agent-invocation',
            'agentId': self.target_agent_id,
            'capability': self.capability,
            'idempotencyKey': f'inv-{uuid.uuid4()}',
            'payloadVersion': '1.0',
            'agentVersion': '1.0.0',
            'payload': self.payload,
            'status': 'QUEUED',
            'attempt': 0,
            'parentWorkId': self.parent_work_id,
            'invocationMode': self.mode,
            'createdAt': datetime.utcnow().isoformat()
        }


class AgentInvoker:
    """
    Invokes agents through the Agent Body execution pipeline.
    
    This provides a clean interface for agents to invoke other agents
    without knowing about Lambda, SQS, or other runtime details.
    """
    
    def __init__(self, agent_body=None):
        import sys
        sys.path.insert(0, '.')
        from agents.agent_body import AgentBody
        self.agent_body = agent_body or AgentBody()
    
    def invoke(self, contract: InvocationContract) -> Dict[str, Any]:
        """
        Invoke an agent via the standard execution pipeline.
        
        Args:
            contract: The invocation contract specifying target and parameters
            
        Returns:
            Result dictionary from the invoked agent
        """
        work_item = contract.to_work_item(
            # Gate 5: Identitaet erhalten — Body sieht dieselbe workId wie das
            # registrierte WorkItem (payload traegt das Original-WorkItem).
            work_id=(contract.payload or {}).get('workId'),
        )
        
        logger.info(
            f"Invoking agent {contract.target_agent_id} "
            f"(capability: {contract.capability}) "
            f"from parent: {contract.parent_work_id}"
        )
        
        return self.agent_body.execute(work_item)
    
    def invoke_sync(self,
                    target_agent_id: str,
                    capability: str,
                    payload: Optional[Dict[str, Any]] = None,
                    parent_work_id: Optional[str] = None,
                    tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Synchronously invoke another agent.
        
        Args:
            target_agent_id: Agent to invoke
            capability: Capability to use
            payload: Input data
            parent_work_id: Parent work item for traceability
            tenant_id: Tenant context
            
        Returns:
            Direct result from the invoked agent
        """
        contract = InvocationContract(
            target_agent_id=target_agent_id,
            capability=capability,
            payload=payload,
            parent_work_id=parent_work_id,
            tenant_id=tenant_id,
            mode=InvocationContract.SYNC
        )
        
        return self.invoke(contract)


# Global invoker instance
_invoken = None


def get_invoken() -> AgentInvoker:
    """Get the global agent invoker instance."""
    global _invoken
    if _invoken is None:
        _invoken = AgentInvoker()
    return _invoken


def invoke_agent(
    target_agent_id: str,
    capability: str,
    payload: Optional[Dict[str, Any]] = None,
    parent_work_id: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to invoke an agent.
    
    Args:
        target_agent_id: Agent to invoke
        capability: Capability to execute
        payload: Input data for the agent
        parent_work_id: Parent work item for traceability
        tenant_id: Tenant context
        
    Returns:
        Result from the invoked agent
    """
    invoker = get_invoken()
    return invoker.invoke_sync(
        target_agent_id=target_agent_id,
        capability=capability,
        payload=payload,
        parent_work_id=parent_work_id,
        tenant_id=tenant_id
    )