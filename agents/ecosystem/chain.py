"""
Processing Chain

Provides utilities for defining and managing agent processing chains.

A processing chain represents a sequence of agent invocations
where each agent's output becomes the next agent's input.
"""

import logging
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from agents.ecosystem.registry import AgentRegistry, AgentDescriptor

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
    """
    
    def __init__(self, registry: AgentRegistry, invoker=None):
        self.registry = registry
        self.invoker = invoker
    
    def execute(self, 
                chain: ProcessingChain, 
                input_data: Dict[str, Any],
                parent_work_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a processing chain.
        
        Args:
            chain: The processing chain to execute
            input_data: Initial input for the first agent
            parent_work_id: Parent work ID for traceability
            
        Returns:
            Final result after all chain steps
        """
        if not chain.is_valid(self.registry):
            return {
                'success': False,
                'error': {'message': 'Invalid processing chain'}
            }
        
        data = input_data.copy()
        results = []
        
        for step in chain.steps:
            agent = self.registry.get(step.agent_id)
            if agent is None:
                if step.required:
                    return {
                        'success': False,
                        'error': {'message': f'Agent not found: {step.agent_id}'}
                    }
                continue
            
            # Invoke the agent (simplified - in real use would use invoker)
            work_item = {
                'workId': f'chain-{datetime.utcnow().timestamp()}',
                'type': f'invocation_{step.agent_id}',
                'tenantId': data.get('tenantId'),
                'agentId': step.agent_id,
                'capability': step.capability,
                'payloadVersion': '1.0',
                'payload': data,
                'parentWorkId': parent_work_id
            }
            
            if self.invoker:
                result = self.invoker.invoke(work_item)
            else:
                result = {'success': True, 'data': data}
            
            results.append({
                'step': step.agent_id,
                'result': result
            })
            
            if not result.get('success') and not step.optional:
                return {
                    'success': False,
                    'error': {'message': f'Step failed: {step.agent_id}'}
                }
            
            data = result.get('data', data)
        
        return {
            'success': True,
            'data': data,
            'chainResults': results
        }


class ChainTemplate:
    """Template for creating processing chains."""
    
    @staticmethod
    def match_chain(name: str) -> ProcessingChain:
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