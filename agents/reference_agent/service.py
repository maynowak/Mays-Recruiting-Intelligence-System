"""
Reference Agent Service

Provides a minimal technical implementation that demonstrates:
- AgentBase contract compliance
- Capability-based processing
- Tenant isolation through May's Orders

Capability: reference.echo
- Simple pass-through echo for testing
- No domain logic
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

import sys
sys.path.insert(0, '.')

from agents.base import AgentBase

logger = logging.getLogger(__name__)


class ReferenceAgent(AgentBase):
    """
    Reference agent for technical demonstration.
    
    This agent implements the AgentBase contract and provides
    a single capability: reference.echo
    """
    
    CAPABILITY_ECHO = 'reference.echo'
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = 'reference_agent'
        self.version = '1.0.0'
    
    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process work item based on capability.
        
        Args:
            work_item: Work item containing capability and payload
            
        Returns:
            Result dictionary with success, data, error
        """
        capability = work_item.get('capability', self.CAPABILITY_ECHO)
        payload = work_item.get('payload', {})
        
        logger.info(f"Processing work: {work_item.get('workId')} "
                   f"with capability: {capability}")
        
        if capability == self.CAPABILITY_ECHO:
            return self._handle_echo(work_item, payload)
        else:
            return {
                'success': False,
                'error': {
                    'message': f'Unknown capability: {capability}',
                    'type': 'ValidationError'
                }
            }
    
    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        """
        Validate work item before processing.
        
        Args:
            work_item: Work item to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(work_item, dict):
            return False
        
        required_fields = ['workId', 'type', 'tenantId', 'idempotencyKey']
        
        for field in required_fields:
            if field not in work_item:
                logger.warning(f"Missing required field: {field}")
                return False
        
        if work_item.get('type') != 'agent_work':
            logger.warning(f"Invalid work type: {work_item.get('type')}")
            return False
        
        if not work_item.get('agentId') and work_item.get('capability') != self.CAPABILITY_ECHO:
            logger.warning("Missing agentId for non-echo capability")
            return False
        
        return True
    
    def get_status(self, work_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Get the status of a work item.
        
        Args:
            work_id: Work item ID
            tenant_id: Tenant ID
            
        Returns:
            Status dictionary
        """
        logger.info(f"Getting status for work: {work_id}")
        
        return {
            'workId': work_id,
            'status': 'COMPLETED',
            'result': {
                'message': 'Work completed successfully',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    def _handle_echo(self, work_item: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the echo capability.
        
        Simply returns the payload with success flag.
        
        Args:
            work_item: Original work item
            payload: Input payload to echo
            
        Returns:
            Success result with echoed payload
        """
        logger.info(f"Echo capability processing for work: {work_item.get('workId')}")
        
        result = {
            'success': True,
            'data': {
                'echoed': payload,
                'workId': work_item.get('workId'),
                'agentId': work_item.get('agentId'),
                'capability': self.CAPABILITY_ECHO,
                'processedAt': datetime.utcnow().isoformat()
            },
            'metrics': {
                'durationMs': 0,
                'workId': work_item.get('workId'),
                'agentVersion': self.version
            }
        }
        
        return result


def create_reference_handler(config: Optional[Dict[str, Any]] = None):
    """
    Factory function to create Lambda handler for reference agent.
    
    Args:
        config: Optional agent configuration
        
    Returns:
        Lambda handler function
    """
    agent = ReferenceAgent(config)
    
    def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        results = []
        
        for record in event.get('Records', []):
            try:
                body = json.loads(record['body'])
                work_item = body if isinstance(body, dict) else json.loads(body)
                
                if agent.validate_work(work_item):
                    result = agent.process_work(work_item)
                    results.append({
                        'workId': work_item.get('workId'),
                        'result': result
                    })
                else:
                    results.append({
                        'workId': work_item.get('workId', record.get('messageId')),
                        'error': 'Validation failed'
                    })
                    
            except Exception as e:
                logger.error(f"Error processing record: {str(e)}")
                results.append({
                    'error': str(e),
                    'messageId': record.get('messageId')
                })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed': len(event.get('Records', [])),
                'results': results
            })
        }
    
    return handler


lambda_handler = create_reference_handler()