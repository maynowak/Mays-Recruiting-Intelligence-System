"""
Lambda Handler for Ground Zero Platform API

This module provides the Lambda entry point for all Platform API routes including:
- Platform information
- User context
- User profile
- Agent catalog and selection
- Agent execution
- Work item management
"""

import json
import os
import sys
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import boto3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

try:
    from agents.agent_body import AgentBody
    AGENT_BODY = AgentBody()
    AGENT_BODY_AVAILABLE = True
except ImportError:
    AGENT_BODY_AVAILABLE = False
    AGENT_BODY = None

# Initialize agent catalog registry from DynamoDB
try:
    from agents.ecosystem.catalog_adapter import CatalogAdapter
    from agents.ecosystem.registry import get_registry, AgentDescriptor, AgentStatus, ExecutionProfile
    
    _catalog_adapter = CatalogAdapter()
    _catalog_agents = _catalog_adapter.get_all_agents()
    _registry = get_registry()
    
    for _agent_id, _agent_data in _catalog_agents.items():
        # Map DynamoDB item to AgentDescriptor
        _status_str = _agent_data.get('status', 'ACTIVE')
        _status_map = {
            'ACTIVE': AgentStatus.ACTIVE,
            'INACTIVE': AgentStatus.INACTIVE,
            'DEPRECATED': AgentStatus.DEPRECATED,
            'RETIRED': AgentStatus.RETIRED,
            'FAILED': AgentStatus.FAILED,
            'REGISTERED': AgentStatus.REGISTERED,
            'AVAILABLE': AgentStatus.AVAILABLE,
        }
        _descriptor = AgentDescriptor(
            agent_id=_agent_id,
            name=_agent_data.get('name', _agent_id),
            version=_agent_data.get('version', '1.0.0'),
            status=_status_map.get(_status_str.upper(), AgentStatus.ACTIVE),
            capabilities=_agent_data.get('capabilities', []),
            supported_bodies=_agent_data.get('supported_bodies', ['1.0.0']),
            supported_runtimes=_agent_data.get('supported_runtimes', ['python3.14']),
            execution_profile=ExecutionProfile.LAMBDA,
            risk_level=_agent_data.get('risk_level', 'low'),
            description=_agent_data.get('description', ''),
            metadata=_agent_data.get('metadata', {}),
        )
        _registry.register(_agent_id, _descriptor)
    
    logger.info(f"Catalog initialized: {len(_catalog_agents)} agents registered")
except ImportError as e:
    logger.warning(f"Catalog adapter not available: {e}")
except Exception as e:
    logger.warning(f"Catalog initialization failed: {e}")
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

PLATFORM_NAME = os.environ.get('PLATFORM_NAME', 'Mays RIS')
PLATFORM_VERSION = os.environ.get('PLATFORM_VERSION', '1.0.0')
PLATFORM_ENVIRONMENT = os.environ.get('PLATFORM_ENVIRONMENT', 'dev')

_dynamodb = None
_sqs = None


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb')
    return _dynamodb


def _get_sqs():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client('sqs')
    return _sqs


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
    elif method == 'GET' and path == '/me/jobsearches':
        return _handle_jobsearch_list(event, context)
    elif method == 'POST' and path == '/me/jobsearches':
        return _handle_jobsearch_create(event, context)
    elif method == 'GET' and path.startswith('/me/jobsearches/'):
        job_search_id = event.get('pathParameters', {}).get('jobSearchId')
        return _handle_jobsearch_get(event, context, job_search_id)
    elif method == 'PUT' and path.startswith('/me/jobsearches/'):
        job_search_id = event.get('pathParameters', {}).get('jobSearchId')
        return _handle_jobsearch_update(event, context, job_search_id)
    elif method == 'DELETE' and path.startswith('/me/jobsearches/'):
        job_search_id = event.get('pathParameters', {}).get('jobSearchId')
        return _handle_jobsearch_delete(event, context, job_search_id)
    elif method == 'GET' and path.startswith('/api/agents'):
        return _handle_agent_api_event(event, context)
    elif method == 'POST' and path.startswith('/api/agents'):
        return _handle_agent_api_event(event, context)
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


def _handle_agent_api_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle Agent API routes."""
    path = event.get('path', '/')
    method = event.get('httpMethod', 'GET')
    
    if path == '/api/agents' and method == 'GET':
        return _list_agents(event, context)
    elif path == '/api/agents' and method == 'POST':
        return _register_agent(event, context)
    elif path.startswith('/api/agents/') and method == 'GET':
        agent_id = _extract_path_param(path, 'agentId')
        return _get_agent(event, context, agent_id)
    elif path.startswith('/api/agents/') and method == 'POST':
        agent_id = _extract_path_param(path, 'agentId')
        return _execute_agent(event, context, agent_id)
    elif path.startswith('/api/agents/') and path.endswith('/work'):
        agent_id = _extract_path_param(path, 'agentId')
        work_id = _extract_path_param(path, 'workId')
        return _get_agent_work(event, context, agent_id, work_id)
    
    return {
        'statusCode': 404,
        'body': json.dumps({'error': 'Not found'})
    }


def _extract_path_param(path: str, param: str) -> Optional[str]:
    """Extract path parameter from URL path."""
    patterns = {
        'agentId': r'/api/agents/([^/]+)',
        'workId': r'/api/agents/[^/]+/work/([^/]+)'
    }
    
    pattern = patterns.get(param)
    if pattern:
        match = re.search(pattern, path)
        if match:
            return match.group(1)
    
    return None


def _list_agents(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /api/agents - List all available agents."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    agent_catalog = _get_agent_catalog()
    return {
        'statusCode': 200,
        'body': json.dumps({
            'agents': list(agent_catalog.values())
        })
    }


def _register_agent(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle POST /api/agents - Register a new agent."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    body = json.loads(event.get('body', '{}'))
    
    return {
        'statusCode': 400,
        'body': json.dumps({
            'error': 'Agent registration not supported in this version'
        })
    }


def _get_agent(event: Dict[str, Any], context: Any, agent_id: Optional[str]) -> Dict[str, Any]:
    """Handle GET /api/agents/{agentId} - Get specific agent details."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    if not agent_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Agent ID required'})
        }
    
    entitlements = _get_entitlement_for_agent(user_context['userId'], agent_id, user_context['tenantId'])
    
    if not entitlements:
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Access denied to agent'})
        }
    
    agent_catalog = _get_agent_catalog()
    agent = agent_catalog.get(agent_id)
    
    if not agent:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Agent not found'})
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps(agent)
    }


def _execute_agent(event: Dict[str, Any], context: Any, agent_id: Optional[str]) -> Dict[str, Any]:
    """Handle POST /api/agents/{agentId}/execute - Execute an agent with capability."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    if not agent_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Agent ID required'})
        }
    
    entitlements = _get_entitlement_for_agent(user_context['userId'], agent_id, user_context['tenantId'])
    
    if not entitlements:
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Access denied to agent'})
        }
    
    body = json.loads(event.get('body', '{}'))
    capability = body.get('capability')
    payload = body.get('payload', {})
    
    agent_catalog = _get_agent_catalog()
    agent = agent_catalog.get(agent_id)
    
    if not agent:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Agent not found'})
        }
    
    if agent.get('status') != 'active':
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Agent is not active'})
        }
    
    request_id = str(uuid.uuid4())
    
    work_item = {
        'workId': str(uuid.uuid4()),
        'type': f'agent_{agent_id}',
        'tenantId': user_context['tenantId'],
        'userId': user_context['userId'],
        'requestedBy': user_context['userId'],
        'agentId': agent_id,
        'capability': capability,
        'idempotencyKey': body.get('idempotencyKey', str(uuid.uuid4())),
        'payloadVersion': '1.0',
        'agentVersion': agent.get('version', '1.0.0'),
        'requestId': request_id,
        'status': 'QUEUED',
        'attempt': 0,
        'payload': payload,
        'createdAt': datetime.utcnow().isoformat(),
        'expiresAt': (datetime.utcnow() + timedelta(days=30)).isoformat()
    }
    
    try:
        table_name = os.environ.get('WORK_ITEMS_TABLE')
        if table_name:
            dynamodb = _get_dynamodb()
            table = dynamodb.Table(table_name)
            table.put_item(Item=work_item)
        
        queue_url = os.environ.get('WORK_QUEUE_URL')
        if queue_url:
            sqs = _get_sqs()
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(work_item),
                MessageAttributes={
                    'workType': {'StringValue': work_item['type'], 'DataType': 'String'},
                    'agentId': {'StringValue': agent_id, 'DataType': 'String'}
                }
            )
        
        return {
            'statusCode': 202,
            'body': json.dumps({
                'workId': work_item['workId'],
                'status': 'QUEUED',
                'requestId': request_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error creating work item: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to create work item'})
        }


def _get_agent_work(event: Dict[str, Any], context: Any, agent_id: Optional[str], work_id: Optional[str]) -> Dict[str, Any]:
    """Handle GET /api/agents/{agentId}/work/{workId} - Get work status."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    if not agent_id or not work_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Agent ID and Work ID required'})
        }
    
    work = _get_work_item(work_id)
    
    if not work:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Work not found'})
        }
    
    if work.get('tenantId') != user_context['tenantId']:
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Access denied'})
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps(work)
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


def _get_entitlement_for_agent(user_id: str, agent_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get entitlement for specific agent for user."""
    try:
        table_name = os.environ.get('ENTITLEMENTS_TABLE')
        if not table_name:
            logger.warning("ENTITLEMENTS_TABLE not configured")
            return None
        
        dynamodb = _get_dynamodb()
        table = dynamodb.Table(table_name)
        
        response = table.query(
            KeyConditionExpression=Key('userId').eq(user_id)
        )
        
        for item in response.get('Items', []):
            if item.get('agentId') == agent_id:
                if tenant_id and item.get('tenantId') != tenant_id:
                    continue
                if _is_entitlement_valid(item):
                    return item
        
        return None
        
    except ClientError as e:
        logger.error(f"Error getting entitlements: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting entitlements: {e}")
        return None


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


def _get_work_item(work_id: str) -> Optional[Dict[str, Any]]:
    """Get work item from DynamoDB."""
    try:
        table_name = os.environ.get('WORK_ITEMS_TABLE')
        if not table_name:
            logger.warning("WORK_ITEMS_TABLE not configured")
            return None
        
        dynamodb = _get_dynamodb()
        table = dynamodb.Table(table_name)
        
        response = table.get_item(Key={'workId': work_id})
        
        if 'Item' not in response:
            return None
        
        return response['Item']
        
    except ClientError as e:
        logger.error(f"Error getting work item: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting work item: {e}")
        return None


def _process_work_item(work_item: Dict[str, Any]) -> Dict[str, Any]:
    """Process a work item through the Agent Body pipeline."""
    work_id = work_item.get('workId')
    work_type = work_item.get('type')
    
    logger.info(f"Processing work item: {work_id}, type: {work_type}")
    
    if AGENT_BODY_AVAILABLE and AGENT_BODY is not None:
        try:
            result = AGENT_BODY.execute(work_item)
            
            result.setdefault('workId', work_id)
            result.setdefault('workType', work_type)
            
            status = 'COMPLETED' if result.get('success') else 'FAILED'
            result['status'] = status
            result['agentType'] = work_item.get('agentId', 'unknown')
            
            logger.info(f"Work item {work_id} processed: {status}")
            return result
            
        except Exception as e:
            logger.error(f"Agent Body execution error for {work_id}: {e}")
            return {
                'success': False,
                'workId': work_id,
                'workType': work_type,
                'error': {
                    'message': str(e),
                    'type': type(e).__name__
                },
                'metrics': {
                    'durationMs': 0,
                    'workId': work_id,
                    'status': 'FAILED'
                }
            }
    else:
        logger.warning("Agent Body not available, using fallback processing")
        return {
            'success': True,
            'message': 'Work processed (fallback mode)',
            'workId': work_id
        }


def _create_work(body: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new work item."""
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
    work = _get_work_item(work_id) if work_id else None
    
    if not work:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Work not found'})
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'workId': work.get('workId'),
            'status': work.get('status', 'COMPLETED'),
            'result': {'message': 'Work completed'}
        })
    }



def _handle_jobsearch_list(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /me/jobsearches - List user's JobSearches."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    try:
        from jobsearch.repository import JobSearchRepository
        from jobsearch.domain_models import JobSearchStatus
        
        repo = JobSearchRepository()
        searches = repo.list_by_user(
            user_id=user_context['userId'],
            tenant_id=user_context['tenantId']
        )
        
        active_searches = [
            s for s in searches 
            if s.status == JobSearchStatus.ACTIVE or s.status == JobSearchStatus.ARCHIVED
        ]
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'jobsearches': [s.to_dict() for s in active_searches]
            })
        }
        
    except Exception as e:
        logger.error(f"Error listing JobSearches: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to list JobSearches'})
        }


def _handle_jobsearch_get(event: Dict[str, Any], context: Any, job_search_id: Optional[str]) -> Dict[str, Any]:
    """Handle GET /me/jobsearches/{jobSearchId} - Get single JobSearch."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    if not job_search_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'jobSearchId is required'})
        }
    
    try:
        from jobsearch.repository import JobSearchRepository
        
        repo = JobSearchRepository()
        search = repo.get(
            job_search_id=job_search_id,
            user_id=user_context['userId'],
            tenant_id=user_context['tenantId']
        )
        
        if not search:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'JobSearch not found'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps(search.to_dict())
        }
        
    except Exception as e:
        logger.error(f"Error getting JobSearch: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to get JobSearch'})
        }


def _handle_jobsearch_create(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle POST /me/jobsearches - Create new JobSearch."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        from jobsearch.repository import JobSearchRepository
        from jobsearch.domain_models import JobSearch, SearchConfiguration, ATSSearchProfile
        
        name = body.get('name')
        if not name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'name is required'})
            }
        
        job_search_id = str(uuid.uuid4())
        
        search_config = SearchConfiguration.from_dict(
            body.get('searchConfiguration', {})
        )
        ats_profile = ATSSearchProfile.from_dict(
            body.get('atsSearchProfile', {})
        )
        
        job_search = JobSearch(
            job_search_id=job_search_id,
            user_id=user_context['userId'],
            tenant_id=user_context['tenantId'],
            name=name,
            search_configuration=search_config,
            ats_search_profile=ats_profile,
            metadata=body.get('metadata', {})
        )
        
        repo = JobSearchRepository()
        if not repo.save(job_search):
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to save JobSearch'})
            }
        
        return {
            'statusCode': 201,
            'body': json.dumps({
                'jobSearch': job_search.to_dict()
            })
        }
        
    except Exception as e:
        logger.error(f"Error creating JobSearch: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to create JobSearch'})
        }


def _handle_jobsearch_update(event: Dict[str, Any], context: Any, job_search_id: Optional[str]) -> Dict[str, Any]:
    """Handle PUT /me/jobsearches/{jobSearchId} - Update JobSearch."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    if not job_search_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'jobSearchId is required'})
        }
    
    try:
        body = json.loads(event.get('body', '{}'))
        
        from jobsearch.repository import JobSearchRepository
        from jobsearch.domain_models import SearchConfiguration, ATSSearchProfile, JobSearchStatus
        
        repo = JobSearchRepository()
        
        existing = repo.get(
            job_search_id=job_search_id,
            user_id=user_context['userId'],
            tenant_id=user_context['tenantId']
        )
        
        if not existing:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'JobSearch not found'})
            }
        
        if 'name' in body:
            existing.name = body['name']
        if 'searchConfiguration' in body:
            existing.search_configuration = SearchConfiguration.from_dict(
                body['searchConfiguration']
            )
        if 'atsSearchProfile' in body:
            existing.ats_search_profile = ATSSearchProfile.from_dict(
                body['atsSearchProfile']
            )
        if 'status' in body:
            existing.status = JobSearchStatus(body['status'])
        if 'metadata' in body:
            existing.metadata = body['metadata']
        
        existing.updated_at = datetime.utcnow()
        
        if not repo.save(existing):
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to update JobSearch'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'jobSearch': existing.to_dict()
            })
        }
        
    except Exception as e:
        logger.error(f"Error updating JobSearch: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to update JobSearch'})
        }


def _handle_jobsearch_delete(event: Dict[str, Any], context: Any, job_search_id: Optional[str]) -> Dict[str, Any]:
    """Handle DELETE /me/jobsearches/{jobSearchId} - Delete JobSearch."""
    user_context = _extract_user_context(event)
    
    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }
    
    if not job_search_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'jobSearchId is required'})
        }
    
    try:
        from jobsearch.repository import JobSearchRepository
        
        repo = JobSearchRepository()
        
        if not repo.delete(
            job_search_id=job_search_id,
            user_id=user_context['userId'],
            tenant_id=user_context['tenantId']
        ):
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'JobSearch not found'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'JobSearch deleted',
                'jobSearchId': job_search_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error deleting JobSearch: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to delete JobSearch'})
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