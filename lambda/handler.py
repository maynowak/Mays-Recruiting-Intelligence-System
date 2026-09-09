"""
Lambda Handler for Ground Zero Agents

This module provides the Lambda entry point for all agents.
"""

import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Standard Lambda handler for Ground Zero.
    
    Args:
        event: API Gateway or SQS event
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    logger.info(f"Processing request for agent: {os.environ.get('AGENT_NAME', 'unknown')}")
    
    # Handle different event types
    if 'Records' in event and 'body' in event['Records'][0] if event['Records'] else False:
        return _handle_sqs_event(event, context)
    else:
        return _handle_api_event(event, context)


def _handle_sqs_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle SQS-triggered events."""
    results = []
    
    for record in event.get('Records', []):
        try:
            body = json.loads(record['body'])
            work_item = body
            
            result = _process_work_item(work_item)
            results.append({
                'workId': work_item.get('workId'),
                'result': result
            })
            
        except Exception as e:
            logger.error(f"Error processing record: {str(e)}")
            results.append({
                'error': str(e),
                'messageId': record.get('messageId')
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps({'processed': len(event.get('Records', [])), 'results': results})
    }


def _handle_api_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle API Gateway events."""
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    
    logger.info(f"API request: {method} {path}")
    
    if method == 'POST' and path == '/work':
        body = json.loads(event.get('body', '{}'))
        return _create_work(body, event)
    
    elif method == 'GET' and path.startswith('/work'):
        work_id = event.get('pathParameters', {}).get('workId')
        return _get_work(work_id, event)
    
    return {
        'statusCode': 404,
        'body': json.dumps({'error': 'Not found'})
    }


def _process_work_item(work_item: Dict[str, Any]) -> Dict[str, Any]:
    """Process a work item."""
    work_id = work_item.get('workId')
    work_type = work_item.get('type')
    
    logger.info(f"Processing work item: {work_id}, type: {work_type}")
    
    # Check if already completed (idempotency)
    # This would check DynamoDB or similar
    
    return {
        'success': True,
        'message': 'Work processed successfully'
    }


def _create_work(body: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new work item."""
    import uuid
    from datetime import datetime, timedelta
    
    work_item = {
        'workId': str(uuid.uuid4()),
        'type': body.get('type', 'default'),
        'tenantId': context.get('tenantId', 'default'),
        'requestedBy': body.get('requestedBy', 'unknown'),
        'idempotencyKey': body.get('idempotencyKey'),
        'payloadVersion': '1.0',
        'agentVersion': os.environ.get('AGENT_VERSION', '1.0.0'),
        'status': 'QUEUED',
        'attempt': 0,
        'payload': body.get('payload', {}),
        'createdAt': datetime.utcnow().isoformat(),
        'expiresAt': (datetime.utcnow() + timedelta(days=30)).isoformat()
    }
    
    return {
        'statusCode': 201,
        'body': json.dumps({
            'workId': work_item['workId'],
            'status': 'QUEUED'
        })
    }


def _get_work(work_id: Optional[str], context: Dict[str, Any]) -> Dict[str, Any]:
    """Get work item status."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'workId': work_id,
            'status': 'COMPLETED',
            'result': {'message': 'Work completed'}
        })
    }


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
    
    print(json.dumps(handler(test_event, None), indent=2))