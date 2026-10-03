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

# Initialize agent catalog registry from DynamoDB — LAZY (Gate 10).
# Der fruehere Import-seitige Aufruf zog boto3 beim blossen Modul-Import
# (inkl. Test-Prozesse) und machte Netzwerk beim Cold Start. Verhalten
# identisch, nur Zeitpunkt: beim ersten Katalog-Zugriff.
_catalog_initialized = False


def _init_catalog():
    """Katalog einmalig in die globale Registry laden (lazy)."""
    global _catalog_initialized
    if _catalog_initialized:
        return
    _catalog_initialized = True
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


def _dynamo_key(name: str):
    """Key-Condition lazy (kein boto3-Import auf Modulebene)."""
    from boto3.dynamodb.conditions import Key
    return Key(name)

PLATFORM_NAME = os.environ.get('PLATFORM_NAME', 'Mays RIS')
PLATFORM_VERSION = os.environ.get('PLATFORM_VERSION', '1.0.0')
PLATFORM_ENVIRONMENT = os.environ.get('PLATFORM_ENVIRONMENT', 'dev')

_dynamodb = None
_sqs = None


class _NoAwsError(Exception):
    """Platzhalter wenn botocore fehlt (praktisch nie; Lambda stellt boto3 bereit)."""


def _aws_error_types():
    """AWS-Fehlerklassen lazy (kein boto-Import auf Modulebene)."""
    try:
        from botocore.exceptions import ClientError
        return (ClientError,)
    except ImportError:
        return (_NoAwsError,)


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        import boto3
        _dynamodb = boto3.resource('dynamodb')
    return _dynamodb


def _get_sqs():
    global _sqs
    if _sqs is None:
        import boto3
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

    # Gate 10: Dispatch ohne KeyError (die alte Einzeiler-Bedingung warf bei
    # jedem API-Event ohne 'Records'-Key). v1-Payload: httpMethod/path;
    # SQS: Records-Liste.
    if event.get('httpMethod'):
        return _handle_api_event(event, context)
    if event.get('Records'):
        return _handle_sqs_event(event, context)
    return _handle_api_event(event, context)


# Live-Einstieg der deployten Funktion (handler.lambda_handler).
lambda_handler = handler


def _handle_sqs_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle SQS-triggered events.

    Gate 5: Schlaegt ein Record fehl (Exception), wird der Fehler
    protokolliert UND nach Verarbeitung aller Records erneut geworfen,
    damit SQS die Nachricht erneut zustellt (Retry -> neuer Attempt).
    Bereits erfolgreiche Records sind durch Idempotency abgesichert.
    """
    results = []
    failures = 0

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
            failures += 1
            logger.error(f"Error processing record: {str(e)}")
            results.append({
                'error': str(e),
                'messageId': record.get('messageId')
            })

    if failures:
        raise RuntimeError(f"{failures}/{len(event.get('Records', []))} SQS records failed")

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
    context['username'] = (
        jwt_claims.get('preferred_username')
        or jwt_claims.get('cognito:username')
    )
    
    tenant_id_claim = jwt_claims.get('custom:tenant_id')
    if tenant_id_claim:
        context['tenantId'] = tenant_id_claim
    
    groups = jwt_claims.get('cognito:groups', [])
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.split(',')]
    context['groups'] = groups
    
    return context


def _handle_api_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle API Gateway events (Payload 1.0 und 2.0)."""
    route_key = event.get('routeKey') or ''
    http_ctx = ((event.get('requestContext') or {}).get('http') or {})
    # Methode: Payload 1.0/2.0/routeKey. Pfad: IMMER echt (nie Template —
    # routeKey enthaelt {docId}-Platzhalter, http.path den echten Wert).
    if ' ' in route_key:
        rk_method, _, _rk_path = route_key.partition(' ')
    else:
        rk_method = ''
    method = event.get('httpMethod') or http_ctx.get('method') or rk_method or 'GET'
    path = event.get('path') or http_ctx.get('path', '/')

    logger.info(f"API request: {method} {path}")
    
    if method == 'GET' and path == '/platform':
        return _handle_platform(event, context)
    elif method == 'GET' and path == '/me':
        return _handle_me(event, context)
    elif method == 'GET' and path == '/me/profile':
        return _handle_me_profile(event, context)
    elif method == 'POST' and path == '/me/profile':
        return _handle_me_profile_create(event, context)
    elif method == 'PUT' and path == '/me/profile':
        return _handle_me_profile_update(event, context)
    elif method == 'POST' and path == '/me/documents':
        return _handle_documents_create(event, context)
    elif method == 'GET' and path.startswith('/me/documents/'):
        params = event.get('pathParameters') or {}
        doc_id = params.get('docId') or path[len('/me/documents/'):].split('?')[0]
        return _handle_documents_get(event, context, doc_id)
    elif method == 'DELETE' and path.startswith('/me/documents/'):
        params = event.get('pathParameters') or {}
        doc_id = params.get('docId') or path[len('/me/documents/'):].split('?')[0]
        return _handle_documents_delete(event, context, doc_id)
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


def _provision_user_profile(table: Any, user_context: Dict[str, Any],
                            body: Dict[str, Any]) -> Dict[str, Any]:
    """Profil provisionieren — NUR explizit (nie via GET).

    Gate 10: Trigger ist die Registrierung/Aktivierung (Client ruft POST
    nach Confirmation), nicht der erste Read. Conditional Write: existiert
    bereits ein Profil -> 409, kein Ueberschreiben.
    """
    from datetime import datetime

    now = datetime.utcnow().isoformat()
    body = body or {}
    # Gate 12 (Profile v1): NUR diese Felder; userId/tenantId/email aus JWT
    # (Body-Identitaeten werden IGNORIERT — kein Spoofing).
    item = {
        'userId': user_context['userId'],
        'tenantId': user_context.get('tenantId') or 'default',
        'nickname': body.get('nickname'),
        'firstName': body.get('firstName'),
        'lastName': body.get('lastName'),
        'email': user_context.get('email'),
        'status': 'ACTIVE',
        'createdAt': now,
        'updatedAt': now,
    }
    try:
        table.put_item(Item=item, ConditionExpression='attribute_not_exists(userId)')
    except Exception as e:
        if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == \
                'ConditionalCheckFailedException':
            return {'statusCode': 409, 'body': json.dumps({'error': 'Profile already exists'})}
        raise
    return {'statusCode': 201, 'body': json.dumps(item)}


def _handle_me_profile_create(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle POST /me/profile - Profil explizit provisionieren."""
    user_context = _extract_user_context(event)

    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }

    try:
        body = json.loads(event.get('body') or '{}')
    except (ValueError, TypeError):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Request body must be valid JSON'})
        }

    table_name = os.environ.get('USER_PROFILE_TABLE')
    if not table_name:
        logger.warning("USER_PROFILE_TABLE not configured")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Profile store not configured'})
        }

    try:
        table = _get_dynamodb().Table(table_name)
        return _provision_user_profile(table, user_context, body)
    except Exception as e:
        logger.error(f"Error provisioning profile: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to provision profile'})
        }


def _update_user_profile(table: Any, user_context: Dict[str, Any],
                         body: Dict[str, Any]) -> Dict[str, Any]:
    """Profil aktualisieren — nur v1-Felder; userId/tenantId/createdAt unveränderlich.

    Gate 12: Body-userId/tenantId/createdAt werden IGNORIERT (Identitaet aus
    JWT); updatedAt serverseitig. Fehlt das Profil -> 404 (kein Upsert).
    """
    from datetime import datetime

    body = body or {}
    updates = {k: body.get(k) for k in ('nickname', 'firstName', 'lastName')
               if body.get(k) is not None}
    if not updates:
        return {'statusCode': 400,
                'body': json.dumps({'error': 'No updatable v1 fields provided'})}
    updates['updatedAt'] = datetime.utcnow().isoformat()
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
    names = {f"#{k}": k for k in updates}
    values = {f":{k}": v for k, v in updates.items()}
    try:
        result = table.update_item(
            Key={'userId': user_context['userId']},
            UpdateExpression=expr,
            ConditionExpression='attribute_exists(userId)',
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues='ALL_NEW',
        )
    except Exception as e:
        if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == \
                'ConditionalCheckFailedException':
            return {'statusCode': 404, 'body': json.dumps({'error': 'Profile not found'})}
        raise
    return {'statusCode': 200, 'body': json.dumps(result.get('Attributes', {}))}


def _handle_me_profile_update(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle PUT /me/profile - eigenes Profil aktualisieren."""
    user_context = _extract_user_context(event)

    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }

    try:
        body = json.loads(event.get('body') or '{}')
    except (ValueError, TypeError):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Request body must be valid JSON'})
        }

    table_name = os.environ.get('USER_PROFILE_TABLE')
    if not table_name:
        logger.warning("USER_PROFILE_TABLE not configured")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Profile store not configured'})
        }

    try:
        table = _get_dynamodb().Table(table_name)
        return _update_user_profile(table, user_context, body)
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to update profile'})
        }


def _documents_context(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Authentifizierter Dokumenten-Kontext (None wenn unauthentifiziert)."""
    user_context = _extract_user_context(event)
    if not user_context.get('userId'):
        return None
    return user_context


def _handle_documents_create(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle POST /me/documents - kurzlebige Upload-Berechtigung (Gate 14)."""
    from documents import presign_upload

    user_context = _documents_context(event)
    if user_context is None:
        return {'statusCode': 401, 'body': json.dumps({'error': 'Unauthenticated'})}
    try:
        body = json.loads(event.get('body') or '{}')
    except (ValueError, TypeError):
        return {'statusCode': 400,
                'body': json.dumps({'error': 'Request body must be valid JSON'})}
    try:
        result = presign_upload(
            tenant_id=user_context.get('tenantId'),
            user_id=user_context['userId'],
            content_type=(body or {}).get('contentType'),
        )
    except ValueError as e:
        return {'statusCode': 400, 'body': json.dumps({'error': str(e)})}
    except Exception as e:
        logger.error(f"Error presigning upload: {type(e).__name__}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Failed to prepare upload'})}
    return {'statusCode': 200, 'body': json.dumps(result)}


def _handle_documents_get(event: Dict[str, Any], context: Any,
                          doc_id: str) -> Dict[str, Any]:
    """Handle GET /me/documents/{docId} - kurzlebige Lese-Berechtigung (Gate 14)."""
    from documents import presign_download

    user_context = _documents_context(event)
    if user_context is None:
        return {'statusCode': 401, 'body': json.dumps({'error': 'Unauthenticated'})}
    try:
        result = presign_download(
            tenant_id=user_context.get('tenantId'),
            user_id=user_context['userId'],
            doc_id=doc_id,
        )
    except ValueError:
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid document ID'})}
    except Exception as e:
        logger.error(f"Error presigning download: {type(e).__name__}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Failed to prepare download'})}
    if result is None:
        return {'statusCode': 404, 'body': json.dumps({'error': 'Document not found'})}
    return {'statusCode': 200, 'body': json.dumps(result)}


def _handle_documents_delete(event: Dict[str, Any], context: Any,
                             doc_id: str) -> Dict[str, Any]:
    """Handle DELETE /me/documents/{docId} - eigenes Dokument loeschen (Gate 14)."""
    from documents import delete_document

    user_context = _documents_context(event)
    if user_context is None:
        return {'statusCode': 401, 'body': json.dumps({'error': 'Unauthenticated'})}
    try:
        deleted = delete_document(
            tenant_id=user_context.get('tenantId'),
            user_id=user_context['userId'],
            doc_id=doc_id,
        )
    except ValueError:
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid document ID'})}
    except Exception as e:
        logger.error(f"Error deleting document: {type(e).__name__}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Failed to delete document'})}
    if not deleted:
        return {'statusCode': 404, 'body': json.dumps({'error': 'Document not found'})}
    return {'statusCode': 200, 'body': json.dumps({'deleted': True, 'docId': doc_id})}


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
        
    except _aws_error_types() as e:
        logger.error(f"Error getting user profile: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting user profile: {e}")
        return None


def _get_agent_catalog() -> Dict[str, Dict[str, Any]]:
    """Get agent catalog from DynamoDB."""
    _init_catalog()
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
        
    except _aws_error_types() as e:
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
            KeyConditionExpression=_dynamo_key('userId').eq(user_id)
        )
        
        for item in response.get('Items', []):
            if item.get('agentId') == agent_id:
                if tenant_id and item.get('tenantId') != tenant_id:
                    continue
                if _is_entitlement_valid(item):
                    return item
        
        return None
        
    except _aws_error_types() as e:
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
            KeyConditionExpression=_dynamo_key('userId').eq(user_id)
        )
        
        entitlements = []
        for item in response.get('Items', []):
            if tenant_id and item.get('tenantId') != tenant_id:
                continue
            
            if _is_entitlement_valid(item):
                entitlements.append(item)
        
        return entitlements
        
    except _aws_error_types() as e:
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
        
    except _aws_error_types() as e:
        logger.error(f"Error getting work item: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting work item: {e}")
        return None


def _process_work_item(work_item: Dict[str, Any]) -> Dict[str, Any]:
    """Process a work item through the Agent Body runtime pipeline.

    Gate 5: SQS -> WorkItem -> Agent Body -> Ecosystem/Registry ->
    Reference Agent -> Result, mit Idempotency (kein neuer fachlicher
    Run bei Duplikat) und Attempt-Zaelung bei Retry.
    """
    work_id = work_item.get('workId')
    work_type = work_item.get('type')

    logger.info(f"Processing work item: {work_id}, type: {work_type}")

    # Exceptions propagieren bewusst (kein Swallow): SQS stellt die
    # Nachricht erneut zu (Retry -> neuer Attempt); Duplikate sind durch
    # Idempotency gesichert. Ungueltige WorkItems landen nach
    # maxReceiveCount in der bestehenden DLQ.
    from agents.runtime.pipeline import process_record

    outcome = process_record({'body': work_item})

    success = outcome.get('status') == 'COMPLETED'
    result = {
        'success': success,
        'workId': work_id,
        'workType': work_type,
        'status': outcome.get('status'),
        'agentType': outcome.get('agent_id', work_item.get('agentId', 'unknown')),
        'duplicate': outcome.get('duplicate', False),
        'attempt_no': outcome.get('attempt_no', 1),
    }
    if outcome.get('result') is not None:
        result['result'] = outcome['result']
    if outcome.get('result_reference') is not None:
        result['result_reference'] = outcome['result_reference']

    logger.info(f"Work item {work_id} processed: {result['status']}")
    return result


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