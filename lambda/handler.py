"""
Lambda Handler for Ground Zero Platform

This module provides the Lambda entry point for all Platform API routes.
"""

import json
import os
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

PLATFORM_NAME = os.environ.get('PLATFORM_NAME', 'Mays RIS')
PLATFORM_VERSION = os.environ.get('PLATFORM_VERSION', '1.0.0')
PLATFORM_ENVIRONMENT = os.environ.get('PLATFORM_ENVIRONMENT', 'dev')

_dynamodb = None


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb')
    return _dynamodb


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Standard Lambda handler for Ground Zero Platform API.
    
    Args:
        event: API Gateway or SQS event
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    logger.info(f"Processing request")
    
    if event.get('httpMethod'):
        return _handle_api_event(event, context)
    elif 'Records' in event and 'body' in event['Records'][0] if event['Records'] else False:
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


def _extract_user_context(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract user context from JWT claims in API Gateway event."""
    context = {
        'userId': None,
        'tenantId': None,
        'email': None,
        'groups': []
    }
    
    request_context = event.get('requestContext', {})
    authorizer = request_context.get('authorizer', {})
    
    jwt_claims = authorizer.get('jwt', {}).get('claims', {})
    
    context['userId'] = jwt_claims.get('sub')
    context['email'] = jwt_claims.get('email')
    
    tenant_id_claim = jwt_claims.get('custom:tenant_id')
    if tenant_id_claim:
        context['tenantId'] = tenant_id_claim
    
    groups = jwt_claims.get('cognito:groups', [])
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.split(',')]
    context['groups'] = groups
    
    return context


def _handle_api_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle API Gateway events."""
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    
    logger.info(f"API request: {method} {path}")
    
    if method == 'GET' and path == '/platform':
        return _handle_platform(event, context)
    elif method == 'GET' and path == '/me':
        return _handle_me(event, context)
    elif method == 'GET' and path == '/me/profile':
        return _handle_me_profile(event, context)
    elif method == 'GET' and path == '/agents':
        return _handle_agents(event, context)
    elif method == 'POST' and path == '/work':
        body = json.loads(event.get('body', '{}'))
        return _create_work(body, event)
    elif method == 'GET' and path.startswith('/work'):
        work_id = event.get('pathParameters', {}).get('workId')
        return _get_work(work_id, event)
    
    return {
        'statusCode': 404,
        'body': json.dumps({'error': 'Not found'})
    }


def _handle_platform(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /platform - Platform information endpoint."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'platform': {
                'name': PLATFORM_NAME,
                'version': PLATFORM_VERSION,
                'environment': PLATFORM_ENVIRONMENT
            }
        })
    }


def _handle_me(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /me - Current authenticated user context."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'userId': user_context['userId'],
            'email': user_context['email'],
            'tenantId': user_context['tenantId'],
            'groups': user_context['groups']
        })
    }


def _handle_me_profile(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /me/profile - Current user's profile."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    profile = _get_user_profile(user_context['userId'], user_context['tenantId'])
    
    if not profile:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Profile not found'})
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps(profile)
    }


def _handle_agents(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /agents - Personal agent catalog based on entitlements."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    entitlements = _get_entitlements(user_context['userId'], user_context['tenantId'])
    agent_catalog = _get_agent_catalog()
    
    allowed_agents = []
    for entitlement in entitlements:
        agent_id = entitlement.get('agentId')
        if not agent_id:
            continue
            
        agent = agent_catalog.get(agent_id)
        if not agent:
            continue
        
        if agent.get('status') != 'active':
            continue
        
        if not _is_entitlement_valid(entitlement):
            continue
        
        allowed_agents.append(agent)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'agents': allowed_agents
        })
    }


def _get_user_profile(user_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get user profile from DynamoDB."""
    try:
        table_name = os.environ.get('USER_PROFILE_TABLE')
        if not table_name:
            logger.warning("USER_PROFILE_TABLE not configured")
            return None
        
        dynamodb = _get_dynamodb()
        table = dynamodb.Table(table_name)
        
        response = table.get_item(Key={'userId': user_id})
        
        if 'Item' not in response:
            return None
        
        item = response['Item']
        
        if tenant_id and item.get('tenantId') != tenant_id:
            logger.warning(f"Tenant isolation violation for user {user_id}")
            return None
        
        return item
        
    except ClientError as e:
        logger.error(f"Error getting user profile: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting user profile: {e}")
        return None


def _get_agent_catalog() -> Dict[str, Dict[str, Any]]:
    """Get agent catalog from DynamoDB."""
    try:
        table_name = os.environ.get('AGENT_CATALOG_TABLE')
        if not table_name:
            logger.warning("AGENT_CATALOG_TABLE not configured")
            return {}
        
        dynamodb = _get_dynamodb()
        table = dynamodb.Table(table_name)
        
        response = table.scan()
        
        agents = {}
        for item in response.get('Items', []):
            agent_id = item.get('agentId')
            if agent_id:
                agents[agent_id] = item
        
        return agents
        
    except ClientError as e:
        logger.error(f"Error getting agent catalog: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error getting agent catalog: {e}")
        return {}


def _get_entitlements(user_id: str, tenant_id: Optional[str] = None) -> list:
    """Get entitlements for user from DynamoDB."""
    try:
        table_name = os.environ.get('ENTITLEMENTS_TABLE')
        if not table_name:
            logger.warning("ENTITLEMENTS_TABLE not configured")
            return []
        
        dynamodb = _get_dynamodb()
        table = dynamodb.Table(table_name)
        
        response = table.query(
            KeyConditionExpression=Key('userId').eq(user_id)
        )
        
        entitlements = []
        for item in response.get('Items', []):
            if tenant_id and item.get('tenantId') != tenant_id:
                continue
            
            if _is_entitlement_valid(item):
                entitlements.append(item)
        
        return entitlements
        
    except ClientError as e:
        logger.error(f"Error getting entitlements: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting entitlements: {e}")
        return []


def _is_entitlement_valid(entitlement: Dict[str, Any]) -> bool:
    """Check if an entitlement is currently valid based on temporal constraints."""
    now = datetime.utcnow()
    
    valid_from = entitlement.get('validFrom')
    if valid_from:
        try:
            from dateutil.parser import parse
            start_time = parse(valid_from)
            if now < start_time:
                return False
        except Exception as e:
            logger.warning(f"Invalid validFrom format: {e}")
    
    valid_until = entitlement.get('validUntil')
    if valid_until:
        try:
            from dateutil.parser import parse
            end_time = parse(valid_until)
            if now > end_time:
                return False
        except Exception as e:
            logger.warning(f"Invalid validUntil format: {e}")
    
    return True


def _process_work_item(work_item: Dict[str, Any]) -> Dict[str, Any]:
    """Process a work item."""
    work_id = work_item.get('workId')
    work_type = work_item.get('type')
    
    logger.info(f"Processing work item: {work_id}, type: {work_type}")
    
    return {
        'success': True,
        'message': 'Work processed successfully'
    }


def _create_work(body: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new work item."""
    import uuid
    
    user_context = _extract_user_context(context) if isinstance(context, dict) else {}
    
    work_item = {
        'workId': str(uuid.uuid4()),
        'type': body.get('type', 'default'),
        'tenantId': user_context.get('tenantId', 'default'),
        'requestedBy': user_context.get('userId', 'unknown'),
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