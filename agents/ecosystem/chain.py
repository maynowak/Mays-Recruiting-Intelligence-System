"""
Processing Chain

Provides utilities for defining and managing agent processing chains.

A processing chain represents a sequence of agent invocations
where each agent's output becomes the next agent's input.

Usage:
    from agents.ecosystem.chain import ProcessingChain, ChainStep, ChainExecutor
    from agents.ecosystem.registry import AgentRegistry
    from agents.agent_body import AgentBody
    from agents.reference_agent.service import ReferenceAgent
    
    # Setup
    registry = AgentRegistry()
    body = AgentBody()
    agent = ReferenceAgent()
    body.register_agent(work_type='agent_reference_agent', handler=agent.process_work)
    
    # Create chain
    chain = ProcessingChain(
        name='test_chain',
        steps=[ChainStep(agent_id='reference_agent', capability='reference.echo')]
    )
    
    # Execute
    executor = ChainExecutor(registry)
    result = executor.execute(chain, {'test': 'data'})
"""

import logging
import uuid
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from agents.ecosystem.registry import AgentRegistry, AgentDescriptor
from agents.ecosystem.eligibility import EligibilityChecker, check_eligibility
from agents.agent_body.invocation import InvocationContract, AgentInvoker

logger = logging.getLogger(__name__)


@dataclass
class ChainStep:
    """A step in a processing chain."""
    agent_id: str
    capability: str
    description: str = ""
    required: bool = True
    optional: bool = False


@dataclass
class ProcessingResult:
    """Result of processing chain execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    chain_results: Optional[List[Dict[str, Any]]] = None
    last_step: Optional[str] = None


@dataclass
class ProcessingChain:
    """
    Represents a sequence of agent processing steps.
    """
    name: str
    steps: List[ChainStep]
    description: str = ""
    
    def validate(self, registry: AgentRegistry) -> bool:
        """Validate all steps have valid agents."""
        for step in self.steps:
            agent = registry.get(step.agent_id)
            if agent is None:
                logger.warning(f"Chain step references unknown agent: {step.agent_id}")
                return False
        return True
    
    def get_steps_for_agent(self, agent_id: str) -> List[ChainStep]:
        """Get all steps that reference a specific agent."""
        return [s for s in self.steps if s.agent_id == agent_id]
    
    def is_valid(self, registry: AgentRegistry) -> bool:
        """Check if this chain is valid for execution."""
        return self.validate(registry)


class ChainExecutor:
    """
    Executes processing chains through the agent ecosystem.
    
    Uses:
    - AgentRegistry for agent lookup
    - EligibilityCheck for access control
    - Invocation Contract for agent-to-agent communication
    - Agent Body for execution
    """
    
    def __init__(
        self,
        registry: AgentRegistry,
        invoker: Optional[AgentInvoker] = None,
        agent_body=None
    ):
        """
        Initialize ChainExecutor.
        
        Args:
            registry: Agent registry for discovery
            invoker: Optional invoker for chain execution
            agent_body: Optional Agent Body instance (must have agents registered)
        """
        self.registry = registry
        self.invoker = invoker
        self.agent_body = agent_body
    
    def execute(
        self,
        chain: ProcessingChain,
        input_data: Dict[str, Any],
        parent_work_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        capability: Optional[str] = None
    ) -> ProcessingResult:
        """
        Execute a processing chain.
        
        Args:
            chain: The processing chain to execute
            input_data: Initial input for the first agent
            parent_work_id: Parent work ID for traceability
            tenant_id: Tenant context for isolation
            actor_id: Identity of executing actor
            capability: Optional capability to route to (falls back to chain step capability)
            
        Returns:
            ProcessingResult with success status and final data
        """
        from agents.agent_body import AgentBody
        
        data = input_data.copy() if input_data else {}
        results = []
        current_work_id = parent_work_id or str(uuid.uuid4())
        
        if not chain.is_valid(self.registry):
            return ProcessingResult(
                success=False,
                error={'message': 'Invalid processing chain'}
            )
        
        # Get or create agent body
        agent_body = self.agent_body or AgentBody()
        
        for i, step in enumerate(chain.steps):
            step_capability = capability or step.capability
            
            # Create invocation contract for proper routing
            try:
                contract = InvocationContract(
                    target_agent_id=step.agent_id,
                    capability=step_capability,
                    payload=data,
                    parent_work_id=current_work_id,
                    tenant_id=tenant_id or data.get('tenantId')
                )
                
                work_item = contract.to_work_item()
                
                # Execute via Agent Body
                result = agent_body.execute(work_item)
                
                results.append({
                    'step': i,
                    'agent_id': step.agent_id,
                    'capability': step_capability,
                    'success': result.get('success', False),
                    'work_id': work_item.get('workId')
                })
                
                if not result.get('success') and not step.optional:
                    return ProcessingResult(
                        success=False,
                        error={
                            'message': f'Step failed: {step.agent_id}',
                            'step': i,
                            'details': result.get('error')
                        },
                        last_step=step.agent_id,
                        chain_results=results
                    )
                
                # Propagate output data to next step
                result_data = result.get('data', data)
                if isinstance(result_data, dict):
                    data = result_data
                current_work_id = work_item.get('workId')
                
            except Exception as e:
                logger.error(f"Chain step failed: {step.agent_id} - {e}")
                if step.required:
                    return ProcessingResult(
                        success=False,
                        error={'message': str(e), 'step': i},
                        last_step=step.agent_id,
                        chain_results=results
                    )
        
        return ProcessingResult(
            success=True,
            data=data,
            chain_results=results
        )


class ChainTemplate:
    """Template for creating processing chains."""
    
    @staticmethod
    def match_chain(name: str) -> Optional[ProcessingChain]:
        """Get a predefined chain by name."""
        templates = {
            'atp_analysis': ProcessingChain(
                name='atp_analysis',
                steps=[
                    ChainStep(agent_id='ats_agent', capability='ats.analyze'),
                    ChainStep(agent_id='cv_agent', capability='cv.process')
                ]
            ),
            'job_matching': ProcessingChain(
                name='job_matching',
                steps=[
                    ChainStep(agent_id='job_agent', capability='job.process'),
                    ChainStep(agent_id='match_agent', capability='match.evaluate')
                ]
            )
        }
        return templates.get(name)