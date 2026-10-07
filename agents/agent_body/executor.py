"""
Agent Executor

Manages the execution lifecycle for agents.
"""

import json
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

import sys
sys.path.insert(0, '.')

from agents.agent_body.context import AgentContext
from agents.agent_body.router import AgentRouter

logger = logging.getLogger(__name__)

from agents.timeutil import utcnow



class AgentExecutor:
    """
    Executes agents with standard lifecycle management.
    """

    def __init__(self, router: Optional[AgentRouter] = None, context_class=AgentContext):
        self.router = router or AgentRouter()
        self.context_class = context_class

    def execute(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a work item through the agent pipeline.
        
        Args:
            work_item: Work item to process
            
        Returns:
            Result dictionary
        """
        start_time = utcnow()
        
        logger.info(f"Starting execution for work: {work_item.get('workId')}")

        context = self.context_class.from_work_item(work_item)
        if not context.validate():
            return self._error_result(
                work_item, 
                "Validation failed", 
                "VALIDATION_ERROR"
            )

        handler = self.router.route(work_item)
        if not handler:
            return self._error_result(
                work_item,
                "No agent found for this work",
                "NOT_FOUND"
            )

        try:
            result = handler(work_item)
            
            duration_ms = (utcnow() - start_time).total_seconds() * 1000
            
            result.setdefault('metrics', {})
            result['metrics'].update({
                'durationMs': duration_ms,
                'workId': work_item.get('workId'),
                'agentVersion': self._get_agent_version(work_item)
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing work {work_item.get('workId')}: {e}")
            return self._error_result(work_item, str(e), type(e).__name__)

    def _error_result(self, work_item: Dict[str, Any], message: str, error_type: str) -> Dict[str, Any]:
        """Create standardized error result."""
        return {
            'success': False,
            'error': {
                'message': message,
                'type': error_type,
                'workId': work_item.get('workId')
            },
            'metrics': {
                'workId': work_item.get('workId'),
                'status': 'FAILED'
            }
        }

    def _get_agent_version(self, work_item: Dict[str, Any]) -> str:
        """Get agent version from work item."""
        return work_item.get('agentVersion', '1.0.0')


# Lambda-compatible handler
def create_agent_handler(router: Optional[AgentRouter] = None) -> Callable:
    """
    Create a Lambda-compatible handler.
    
    Args:
        router: Optional router instance
        
    Returns:
        Lambda handler function
    """
    executor = AgentExecutor(router=router)
    
    def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        if 'Records' in event:
            results = []
            for record in event.get('Records', []):
                try:
                    body = json.loads(record['body'])
                    result = executor.execute(body)
                    results.append({
                        'workId': body.get('workId'),
                        'result': result
                    })
                except Exception as e:
                    logger.error(f"Error processing record: {e}")
                    results.append({
                        'workId': record.get('messageId'),
                        'error': str(e)
                    })
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'processed': len(event.get('Records', [])),
                    'results': results
                })
            }
        else:
            return executor.execute(event)
    
    return handler