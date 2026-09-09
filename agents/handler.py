"""
Agent Handler Template

This module provides the Lambda handler for agents.
Copy and customize for each specific agent.
"""

import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


class AgentHandler:
    """Base handler for agents."""
    
    def __init__(self):
        self.agent_name = os.environ.get('AGENT_NAME', 'default')
        self.agent_version = os.environ.get('AGENT_VERSION', '1.0.0')
    
    def handle(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Handle incoming SQS events.
        
        Args:
            event: SQS event with Records
            context: Lambda context
            
        Returns:
            Response dictionary
        """
        logger.info(f"Processing event for agent: {self.agent_name}")
        
        results = []
        for record in event.get('Records', []):
            result = self._process_record(record)
            results.append(result)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed': len(event.get('Records', [])),
                'agent': self.agent_name,
                'results': results
            })
        }
    
    def _process_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single SQS record."""
        try:
            body = json.loads(record['body'])
            work_item = body if isinstance(body, dict) else json.loads(body)
            
            logger.info(f"Processing work item: {work_item.get('workId')}")
            
            # Validate
            if not self.validate_work(work_item):
                return {
                    'workId': work_item.get('workId', 'unknown'),
                    'status': 'FAILED',
                    'error': 'Validation failed'
                }
            
            # Process
            result = self.process_work(work_item)
            
            logger.info(f"Completed work item: {work_item.get('workId')}")
            
            return {
                'workId': work_item.get('workId'),
                'status': 'COMPLETED',
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Error processing record: {str(e)}")
            return {
                'workId': record.get('messageId', 'unknown'),
                'status': 'FAILED',
                'error': str(e)
            }
    
    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        """Validate work item."""
        required_fields = ['workId', 'type', 'tenantId', 'idempotencyKey']
        return all(field in work_item for field in required_fields)
    
    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Process work item. Override in subclasses."""
        # Placeholder implementation
        return {
            'message': 'Work processed',
            'agentVersion': self.agent_version
        }


# Lambda entry point
handler = AgentHandler()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler."""
    return handler.handle(event, context)


# For local testing
if __name__ == '__main__':
    import sys
    
    test_event = {
        'Records': [
            {
                'body': json.dumps({
                    'workId': 'test-123',
                    'type': 'test',
                    'tenantId': 'tenant-1',
                    'idempotencyKey': 'key-1'
                })
            }
        ]
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))