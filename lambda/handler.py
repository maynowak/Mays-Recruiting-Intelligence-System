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
import re
import sys
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.timeutil import utcnow, utcnow_naive_iso

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
        from agents.ecosystem.registry import get_registry, AgentDescriptor, ExecutionProfile

        _catalog_adapter = CatalogAdapter()
        _catalog_agents = _catalog_adapter.get_all_agents()
        _registry = get_registry()

        for _agent_id, _agent_data in _catalog_agents.items():
            # Central status decision (fail-closed, Gate 07): unknown /
            # None / empty values are NOT registered (blocked), never
            # defaulted to ACTIVE. Persisted DDB values stay untouched.
            from agents.ecosystem.agent_status import normalize_agent_status
            _status = normalize_agent_status(_agent_data.get('status'))
            if _status is None:
                logger.warning(
                    "Skipping catalog agent %s: unsupported status %r",
                    _agent_id, _agent_data.get('status'))
                continue
            _descriptor = AgentDescriptor(
                agent_id=_agent_id,
                name=_agent_data.get('name', _agent_id),
                version=_agent_data.get('version', '1.0.0'),
                status=_status,
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


#: Group-claim token whitelist. Only literal group-name characters are
#: accepted; anything else is dropped. This can never ADD a group that
#: was not present in the claim (no permissive fallback).
_GROUP_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:@-]+$")


def _normalize_groups(raw: Any) -> List[str]:
    """Deterministic normalization of the Cognito group claim.

    Gate SECURITY-FIX-02. The API Gateway JWT authorizer delivers the
    `cognito:groups` claim stringified (e.g. "[admins]"), while a direct
    invocation or another gateway shape delivers a native list. The
    previous `split(",")` turned "[admins]" into ["[admins]"], so every
    role check ("admins" in groups) failed and an admin was silently
    treated as a plain owner. Proof: P19 controlled A/B, Gate 01.

    Supported real-world forms -> semantic group names:
      None                       -> []
      []                         -> []
      ["admins"]                 -> ["admins"]
      ["Staff"]                  -> ["Staff"]
      "[admins]"                 -> ["admins"]
      "[Staff]"                  -> ["Staff"]
      '["admins", "Staff"]'      -> ["admins", "Staff"]
      "admins,Staff"             -> ["admins", "Staff"]
      "" / "   "                 -> []

    NO PERMISSIVE FALLBACK (security invariant):
      - unknown / malformed value -> no groups at all
      - unexpected type           -> no groups
      - non-string list entry     -> dropped
      - never ever admins, Staff or an elevated role by accident

    An unrecognized claim therefore yields LESS privilege, never more.
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        items = list(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        if text.startswith("["):
            # Stringified array. The authorizer delivers Python's
            # str(list) form ("[admins]"), which is NOT valid JSON, so
            # JSON is tried first and the bracket form is the fallback.
            items = None
            try:
                parsed = json.loads(text)
            except (ValueError, TypeError):
                parsed = None
            if isinstance(parsed, list):
                items = parsed
            elif text.endswith("]"):
                inner = text[1:-1].strip()
                if not inner:
                    return []
                items = inner.split(",")
            else:
                # Starts with "[" but is not a list representation.
                return []
        else:
            # Plain comma-separated form.
            items = text.split(",")
    else:
        # Unexpected type (number, dict, bool, ...) -> no groups.
        return []

    groups: List[str] = []
    for item in items:
        if not isinstance(item, str):
            # A non-string entry means the shape is not what we expect.
            # Reject the whole claim rather than guessing.
            return []
        name = item.strip().strip('"').strip("'").strip()
        if not name:
            # Empty token (e.g. trailing comma) — ignore.
            continue
        if not _GROUP_TOKEN_RE.match(name):
            # Malformed token -> reject the ENTIRE claim. Partial
            # parsing would be a permissive fallback: we never keep the
            # tokens that happen to look privileged.
            return []
        if name not in groups:
            groups.append(name)
    return groups


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
    
    # Security fix 02: normalize, never split blindly. See
    # _normalize_groups — the authorizer stringifies array claims.
    context['groups'] = _normalize_groups(jwt_claims.get('cognito:groups'))
    
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
    
    if method == 'GET' and path == '/health':
        # P20-01 Scope 1: the route and integration already existed in
        # terraform/modules/api, but this branch did not, so the probe fell
        # through to the generic 404 below. Reuses the existing path.
        return _handle_health(event, context)
    elif method == 'GET' and path == '/platform':
        return _handle_platform(event, context)
    elif method == 'GET' and path == '/me':
        return _handle_me(event, context)
    elif method == 'GET' and path == '/me/profile':
        return _handle_me_profile(event, context)
    elif method == 'POST' and path == '/me/profile':
        return _handle_me_profile_create(event, context)
    elif method == 'PUT' and path == '/me/profile':
        return _handle_me_profile_update(event, context)
    elif method == 'DELETE' and path == '/me/profile':
        return _handle_me_profile_delete(event, context)
    elif method == 'POST' and path == '/me/erasure':
        return _handle_me_erasure(event, context)
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
    elif path == '/v1/offers' or path.startswith('/v1/offers/'):
        # P23-01: Offer product administration. Pure HTTP wiring over the
        # existing agents.ecosystem.offers domain (role check, agent
        # validation, grant, audit) -- no second product logic here.
        return _handle_offer_routes(event, context, method, path)
    elif method == 'GET' and path == '/v1/introspection':
        # P13: read-only capability introspection (JWT + X-Api-Profile
        # header; GW route provisioned in terraform/modules/api).
        return _handle_introspection(event, context)
    elif path == '/v1/apiprofiles' or path.startswith('/v1/apiprofiles/'):
        # P19: APIProfile-Management (Human JWT) und P15/P16 Credential
        # Management teilen sich das /v1/apiprofiles-Praefix. Credential
        # Routen bleiben unveraendert an _handle_credential_routes.
        if '/credentials' not in path:
            return _handle_apiprofile_routes(event, context, method, path)
        return _handle_credential_routes(event, context, method, path)
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
    elif method == 'POST' and path.startswith('/v1/m2m/'):
        # B3 / Option D: dedicated MACHINE plane. It is reached with an
        # opaque `ris_...` credential, NOT a Cognito JWT, so its gateway
        # route carries AuthorizationType NONE (P03 route boundary: human
        # JWT and machine credential never compete for one route). All
        # human paths above are unchanged.
        return _machine_execute_agent(event, _machine_agent_id(path))
    elif method == 'GET' and path.startswith('/work'):
        work_id = event.get('pathParameters', {}).get('workId')
        return _get_work(work_id, event)
    
    return {
        'statusCode': 404,
        'body': json.dumps({'error': 'Not found'})
    }


def _handle_health(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle GET /health - infrastructure liveness probe.

    Deliberately dependency-free (no DynamoDB, Cognito, or SQS call). A
    probe that fails on a dependency would mark the target unhealthy during
    a dependency outage even though the Lambda itself is startable and able
    to serve. Dependency reachability is reported by GET /platform
    (JWT-protected), not by the liveness probe.
    """
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'ok',
            'service': PLATFORM_NAME,
            'version': PLATFORM_VERSION,
            'environment': PLATFORM_ENVIRONMENT
        })
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

    now = utcnow_naive_iso()
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
    updates['updatedAt'] = utcnow_naive_iso()
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


def _handle_me_profile_delete(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle DELETE /me/profile - Privacy deletion of user profile."""
    user_context = _extract_user_context(event)

    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
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
        # Delete with conditional check to ensure profile exists
        try:
            table.delete_item(
                Key={'userId': user_context['userId']},
                ConditionExpression='attribute_exists(userId)'
            )
            return {
                'statusCode': 204,
                'body': ''
            }
        except Exception as e:
            if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': 'Profile not found'})
                }
            raise
    except Exception as e:
        logger.error(f"Error deleting profile: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to delete profile'})
        }


def _handle_me_erasure(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle POST /me/erasure - privacy erasure lifecycle (G5).

    SEPARATE from DELETE /me/profile on purpose. That endpoint deletes one
    application-profile row and is documented as such. Erasure additionally
    revokes machine credentials, revokes owned API profiles, cancels
    non-terminal work and deletes owned documents -- and it is the only
    operation that can end the caller's machine access.

    Ordering guarantee (agents.ecosystem.privacy_erasure): credentials are
    revoked FIRST, so a successful run cannot leave a usable ris_...
    credential behind.

    Idempotent: re-running revokes only what is not already REVOKED and
    cancels only work that is still non-terminal.

    Response is the honest lifecycle report. `complete: false` means at
    least one step failed and the caller must NOT assume their data is
    gone -- in particular, if revocation failed, a live credential may
    still exist.
    """
    user_context = _extract_user_context(event)

    if not user_context['userId']:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthenticated'})
        }

    try:
        from agents.ecosystem.privacy_erasure import PrivacyErasure
        from agents.ecosystem.credentials import DynamoDBCredentialStore
        from agents.ecosystem.api_profiles import DynamoDBApiProfileStore
    except Exception as e:
        logger.error(f"Erasure subsystem unavailable: {e}")
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Erasure temporarily unavailable'})
        }

    missing = [name for name, env in (
        ("CREDENTIALS_TABLE", "CREDENTIALS_TABLE"),
        ("API_PROFILES_TABLE", "API_PROFILES_TABLE"),
        ("WORK_ITEMS_TABLE", "WORK_ITEMS_TABLE"),
        ("USER_PROFILE_TABLE", "USER_PROFILE_TABLE"),
    ) if not os.environ.get(env)]
    if missing:
        logger.warning("erasure stores unconfigured: %s", ",".join(missing))
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Erasure temporarily unavailable'})
        }

    def _delete_documents(user_id: str) -> int:
        """Delete every document object the platform holds for this user."""
        try:
            import documents
            return documents.delete_all_for_user(user_id)
        except Exception as exc:
            logger.warning("document purge unavailable for %s: %s",
                           user_id, exc)
            return 0

    dynamodb = _get_dynamodb()
    erasure = PrivacyErasure(
        credential_store=DynamoDBCredentialStore(
            table_name=os.environ.get("CREDENTIALS_TABLE")),
        profile_store=DynamoDBApiProfileStore(
            table_name=os.environ.get("API_PROFILES_TABLE")),
        work_table=dynamodb.Table(os.environ.get("WORK_ITEMS_TABLE")),
        document_deleter=_delete_documents,
        user_profile_table=dynamodb.Table(
            os.environ.get("USER_PROFILE_TABLE")),
    )

    try:
        result = erasure.erase(user_context['userId'],
                               tenant_id=user_context.get('tenantId'))
    except Exception as e:
        logger.error(f"Erasure failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Erasure failed'})
        }

    status = 200 if result.complete else 207
    return {
        'statusCode': status,
        'body': json.dumps(result.to_dict())
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

    # Positive capability contract (P22-01): the answer is the set of agents
    # this authenticated caller may use, one entry per agent. Several
    # entitlements can authorize the same agent (e.g. one user-wide plus one
    # profile-bound), and the loop below appends per entitlement -- without a
    # guard the same agent would be returned repeatedly and the website would
    # render it multiple times. Keyed by agentId, so a later valid entitlement
    # never hides an already accepted one.
    allowed_agents = {}
    for entitlement in entitlements:
        agent_id = entitlement.get('agentId')
        if not agent_id or agent_id in allowed_agents:
            continue

        agent = agent_catalog.get(agent_id)
        if not agent:
            continue

        # Central status decision (fail-closed, Gate 07): only ACTIVE
        # is executable — any case, unknown, None, or empty blocked.
        from agents.ecosystem.agent_status import is_executable_status
        if not is_executable_status(agent.get('status')):
            continue

        if not _is_entitlement_valid(entitlement):
            continue

        allowed_agents.setdefault(agent_id, agent)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'agents': list(allowed_agents.values())
        })
    }


#: Header carrying the opaque machine credential on the machine route.
#:
#: P21-01: the route is Cognito-JWT protected, and the gateway authorizer
#: reads `Authorization`. The Cognito JWT therefore occupies that header, and
#: the opaque credential travels here instead. Same secret, same digest store,
#: same verifier — only the channel changed, so that Cognito becomes the first
#: boundary without discarding the product credential.
MACHINE_CREDENTIAL_HEADER = 'x-api-credential'


def _machine_bearer(headers):
    """Extract the opaque machine credential from the request headers.

    Returns (bearer, None) on success or (None, status_code) when the header
    cannot carry a valid opaque bearer.

    P21-01: reads `X-Api-Credential`, NOT `Authorization`. The gateway JWT
    authorizer validates `Authorization` and rejects the request before the
    Lambda is invoked, so a Cognito JWT can never reach this function as a
    credential. Reading the opaque secret from a separate channel also makes the
    two boundaries unambiguous: Cognito answers "authenticated?", this answers
    "which product context?".

    Deliberately strict, and deliberately NOT logging anything: neither the
    header nor the value is ever written to a log or an audit field. The
    whitespace check keeps a JWT (three dot-separated segments, spaces free)
    from being mistaken for a machine credential even if a caller puts one
    here. Full credential validity is still decided by verify_api_credential —
    this only guarantees the "shape" of the header, never "valid credential".
    """
    raw = headers.get(MACHINE_CREDENTIAL_HEADER)
    if not raw or not isinstance(raw, str):
        return None, 401
    parts = raw.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        value = parts[1].strip()
    else:
        # Bare value without a scheme is accepted: this header is
        # credential-specific and unambiguous, unlike Authorization, where a
        # scheme is mandatory because the value could be a JWT.
        value = raw.strip()
    if not value or ' ' in value or value.count('.') >= 2:
        return None, 401
    return value, None


def _machine_cognito_context(event):
    """Authenticated Cognito identity for the machine route (P21-01).

    API Gateway already validated the JWT signature, issuer and audience before
    invoking this function, so these claims cannot be forged by the caller.

    Returns (user_context, None) when Cognito identified the caller, otherwise
    (None, 401). Refusing to continue without it is what makes "no anonymous
    machine user" enforceable: a direct Lambda invocation, or any path that
    skips the gateway authorizer, has no Cognito claims and is denied here.

    The identity is used for audit/correlation only. It never replaces the
    APIProfile owner: verify_api_credential still derives the execution identity
    from the credential's profile, so a caller cannot execute as another user.
    """
    user_context = _extract_user_context(event)
    if not user_context.get('userId'):
        return None, 401
    return user_context, None


def _machine_agent_id(path):
    """Extract the explicit operation target from the machine route path.

    The target comes from the request, never from a default and never by
    guessing a capability -> agent mapping (P04/P09: the verifier never
    guesses the target).
    """
    import re as _re
    match = _re.match(r"^/v1/m2m/agents/([^/]+)/execute$", path)
    if not match:
        return None
    return _re.sub(r"[^A-Za-z0-9_.\-]", "", match.group(1)) or None


def _machine_deny(status_code, error):
    """Neutral external denial (no oracle, no reason category leaked)."""
    return {'statusCode': status_code,
            'body': json.dumps({'error': error})}


def _machine_execute_agent(event: Dict[str, Any], agent_id: Optional[str]) -> Dict[str, Any]:
    """Machine credential entry point (Gate B3-...-08, Option D).

Route: POST /v1/m2m/agents/{agentId}/execute

    Two authentication boundaries, both mandatory (P21-01):

      1. Cognito JWT, validated by API Gateway BEFORE this function runs. The
         route is authorization_type JWT and reuses the same authorizer as the
         human routes. Nothing here can bypass it.
      2. Opaque `ris_...` credential in X-Api-Credential, validated by the
         EXISTING central verification
         (agents.ecosystem.credentials.verify_api_credential) and nothing else.

    Neither replaces the other. This handler deliberately contains NO
    simplified check such as "if credential_exists: execute()". Its only jobs
    are transport-level: extract the credential, confirm a Cognito identity is
    present, name the operation target, call the central verifier, map its
    outcome to the contract's HTTP semantics, and forward an authorized request
    into the shared execution contract.

    Identity binding: the Cognito identity is recorded for audit, never used to
    select the executing user. The execution identity stays the credential's
    APIProfile owner (verify_api_credential), so no request body or header can
    choose whose context runs.

    HTTP semantics come from the credential contract (P09):
    401 unknown / invalid / malformed credential, or missing Cognito identity
    403 known but unusable (disabled, revoked, expired, profile not
    ACTIVE, tenant/owner mismatch, no entitlement, agent not
    executable)
    503 store/infrastructure failure — never 401/403, because an
    unreachable store must not be reported as a bad credential.
    """
    from agents.ecosystem.credentials import (
        CredentialStoreUnavailable,
        VerifyOutcome,
    )
    from agents.ecosystem.credentials import verify_api_credential

    headers = {(k or "").lower(): v
               for k, v in (event.get("headers") or {}).items()}

    # Boundary 1 outcome: no Cognito identity means the request did not come
    # through the gateway authorizer. Deny before touching any store.
    cognito_context, cognito_error = _machine_cognito_context(event)
    if cognito_error:
        return _machine_deny(cognito_error, 'Unauthorized')

    # Boundary 2: the opaque product credential.
    bearer, header_error = _machine_bearer(headers)
    if header_error:
        return _machine_deny(header_error, 'Unauthorized')

    # No target -> 401 (the verifier enforces the same rule itself).
    if not agent_id:
        return _machine_deny(401, 'Unauthorized')

    http_ctx = ((event.get('requestContext') or {}).get('http') or {})
    path = event.get('path') or http_ctx.get('path', '/')
    request_id = ((event.get('requestContext') or {}).get('requestId')
                  or event.get('requestId'))
    route_name = 'POST /v1/m2m/agents/{agentId}/execute'

    # Reuse the existing source builder (profile/credential/entitlement
    # stores + catalog in the production shape) instead of adding a second
    # one. Unconfigured stores raise here and map to 503 below.
    try:
        sources = _build_introspection_sources()
    except Exception:
        return {'statusCode': 503,
                'body': json.dumps({'error': 'Service unavailable'})}

    try:
        decision = verify_api_credential(
            bearer=bearer,
            agent_id=agent_id,
            credential_store=sources["credential_store"],
            profile_store=sources["profile_store"],
            entitlement_resolver=sources["entitlement_resolver"],
            catalog=sources["catalog"],
            operation="agent.execute",
            route="POST /v1/m2m/agents/{agentId}/execute",
            method="POST",
            request_id=request_id,
            selection_hint=headers.get("x-api-profile"),
        )
    except CredentialStoreUnavailable:
        return {'statusCode': 503,
                'body': json.dumps({'error': 'Service unavailable'})}

    if decision.outcome is not VerifyOutcome.AUTHORIZED:
        if decision.outcome is VerifyOutcome.UNAUTHORIZED:
            logger.info(
                "machine verification denied: route=%s outcome=unauthorized "
                "cognitoUser=%s request=%s",
                route_name, cognito_context.get('userId'), request_id)
            return _machine_deny(401, 'Unauthorized')
        logger.info(
            "machine verification denied: route=%s outcome=forbidden "
            "cognitoUser=%s request=%s",
            route_name, cognito_context.get('userId'), request_id)
        return _machine_deny(403, 'Forbidden')

    # Authorized. The credential's own persisted tenant/owner context is the
    # execution subject — never anything from the header or the body.
    context = decision.context or {}
    body = event.get('body') or '{}'
    try:
        data = json.loads(body) if body else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    catalog_item = sources["catalog"].get(agent_id)
    agent_version = '1.0.0'
    if isinstance(catalog_item, dict):
        agent_version = catalog_item.get('agentVersion') or '1.0.0'

    try:
        out = _enqueue_agent_work(
            agent_id=agent_id,
            capability=data.get('capability'),
            payload=data.get('payload', {}),
            tenant_id=context.get('tenantId'),
            user_id=context.get('userId'),
            agent_version=agent_version,
            idempotency_key=data.get('idempotencyKey'))
    except Exception:
        return {'statusCode': 500,
                'body': json.dumps({'error': 'Failed to create work item'})}

    return {
        'statusCode': 202,
        'body': json.dumps({
            'workId': out['workId'],
            'status': out['status'],
            'requestId': out['requestId']
        })
    }


def _build_introspection_sources():
    """Production introspection sources (lazy, read-only).

    PREPARED for the gateway gate (P12): the api-profiles / offers /
    credentials tables are NOT provisioned yet, so this raises until
    the deployment gate exists (maps to neutral 503 — no false live
    claims). Catalog + entitlements reuse provisioned infrastructure.
    """
    import os

    from agents.ecosystem.api_profiles import DynamoDBApiProfileStore
    from agents.ecosystem.catalog_adapter import CatalogAdapter
    from agents.ecosystem.credentials import DynamoDBCredentialStore
    from agents.ecosystem.offers import DynamoDBOfferStore
    from agents.ecosystem.worker_authorization import (
        DynamoDBEntitlementResolver,
    )

    missing = [name for name in ("API_PROFILES_TABLE", "OFFERS_TABLE",
                                 "CREDENTIALS_TABLE", "ENTITLEMENTS_TABLE")
               if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"introspection stores unconfigured: {missing}")
    catalog_items = CatalogAdapter().get_all_agents()
    catalog = {agent_id: (item.get("status") if isinstance(item, dict)
                          else item)
               for agent_id, item in catalog_items.items()}
    return {
        "profile_store": DynamoDBApiProfileStore(
            table_name=os.environ.get("API_PROFILES_TABLE")),
        "entitlement_resolver": DynamoDBEntitlementResolver(),
        "offer_store": DynamoDBOfferStore(
            table_name=os.environ.get("OFFERS_TABLE")),
        "credential_store": DynamoDBCredentialStore(
            table_name=os.environ.get("CREDENTIALS_TABLE")),
        "catalog": catalog,
    }


def _handle_introspection(event, context, bearer_credential=None):
    """Read-only capability introspection (handler P12, live geroutet P13).

    Routed as GET /v1/introspection (JWT, terraform/modules/api). The P12
    docstring said "NOT routed from API Gateway yet"; that was true when
    written and wrong afterwards -- corrected in P20-01 Scope 2 rather than
    left to mislead. Never mutates anything.
    """
    from agents.ecosystem import introspection as introspect_mod

    user_context = _extract_user_context(event)
    headers = {(k or "").lower(): v
               for k, v in (event.get("headers") or {}).items()}
    selection_hint = headers.get("x-api-profile")
    request_id = ((event.get("requestContext") or {}).get("requestId")
                  or event.get("requestId"))

    try:
        sources = _build_introspection_sources()
    except Exception as exc:
        logger.warning(f"Introspection unavailable: {type(exc).__name__}")
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Temporarily unavailable'})
        }

    try:
        if bearer_credential:
            status, body = introspect_mod.introspect_credential(
                bearer_credential, sources,
                selection_hint=selection_hint, request_id=request_id)
        elif not user_context.get("userId"):
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthenticated'})
            }
        elif selection_hint:
            status, body = introspect_mod.introspect_profile(
                user_context["userId"], user_context.get("tenantId"),
                sources, selection_hint=selection_hint,
                request_id=request_id)
        else:
            status, body = introspect_mod.introspect_human(
                user_context["userId"], user_context.get("tenantId"),
                sources, request_id=request_id)
    except introspect_mod.IntrospectionUnavailable:
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Temporarily unavailable'})
        }
    except Exception:
        logger.exception("Introspection failed")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal error'})
        }
    return {
        'statusCode': status,
        'body': json.dumps(body)
    }


# ------------------------------------------------------------------
# P15: Credential Management HTTP (Human JWT only, P14 service)
# ------------------------------------------------------------------
# Routes (contract, NO Gateway change in this gate):
#   POST   /v1/apiprofiles/{pid}/credentials
#   GET    /v1/apiprofiles/{pid}/credentials
#   GET    /v1/apiprofiles/{pid}/credentials/{cid}
#   POST   .../{cid}/rotate|disable|enable|revoke
# The handler NEVER decides roles/entitlements itself (P14 service is
# authoritative); it only parses, validates syntax, maps errors and
# keeps secrets out of logs. No M2M credential auth on these routes.

_CRED_ACTIONS = ("rotate", "disable", "enable", "revoke")


class _CredBad(Exception):
    """Syntactic request error -> 400 (never leaks internals)."""


def _cred_sources():
    """Lazy production stores (prepared; unconfigured -> 503).

    Tables are NOT provisioned in this gate (see P15 report); missing
    configuration maps to neutral 503, never to false live claims.
    """
    import os

    from agents.ecosystem.api_profiles import DynamoDBApiProfileStore
    from agents.ecosystem.credentials import DynamoDBCredentialStore

    if not os.environ.get("CREDENTIALS_TABLE") or \
            not os.environ.get("API_PROFILES_TABLE"):
        raise RuntimeError("credential management stores unconfigured")
    return {
        "credentials": DynamoDBCredentialStore(
            table_name=os.environ.get("CREDENTIALS_TABLE")),
        "profiles": DynamoDBApiProfileStore(
            table_name=os.environ.get("API_PROFILES_TABLE")),
    }


def _cred_actor(user_context):
    """JWT claims -> service actor (role derived, IDs verified downstream)."""
    groups = user_context.get("groups") or []
    if "admins" in groups:
        role = "admin"
    elif "Staff" in groups:
        role = "staff"
    else:
        role = "owner"
    return {"role": role, "id": user_context.get("userId"),
            "tenant": user_context.get("tenantId")}


def _cred_ids(path):
    """Parse credential paths -> (pid, cid|None, action|None) or None."""
    parts = (path or "").strip("/").split("/")
    if len(parts) < 4 or parts[0] != "v1" or parts[1] != "apiprofiles" \
            or parts[3] != "credentials":
        return None
    pid = parts[2]
    if not pid:
        return None
    if len(parts) == 4:
        return (pid, None, None)
    cid = parts[4]
    if not cid:
        return None
    if len(parts) == 5:
        return (pid, cid, None)
    if len(parts) == 6 and parts[5] in _CRED_ACTIONS:
        return (pid, cid, parts[5])
    return None


def _cred_headers(event):
    return {(k or "").lower(): v
            for k, v in (event.get("headers") or {}).items()}


def _cred_correlation(event, headers):
    return headers.get("x-correlation-id") \
        or ((event.get("requestContext") or {}).get("requestId")) \
        or event.get("requestId")


def _cred_idem(headers):
    raw = headers.get("idempotency-key")
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 128:
        raise _CredBad("Invalid Idempotency-Key")
    return raw.strip()


def _cred_body(event, allowed, required=()):
    try:
        data = json.loads(event.get("body") or "{}")
    except (ValueError, TypeError):
        raise _CredBad("Request body must be valid JSON")
    if not isinstance(data, dict):
        raise _CredBad("Request body must be valid JSON")
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise _CredBad("Unknown fields: " + ", ".join(unknown))
    for field in required:
        if field not in data:
            raise _CredBad("Missing field: " + field)
    return data


def _cred_str(data, field, required=True):
    value = data.get(field)
    if value is None:
        if required:
            raise _CredBad("Missing field: " + field)
        return None
    if not isinstance(value, str) or not value.strip():
        raise _CredBad("Invalid field: " + field)
    return value.strip()


def _cred_fail(exc, actor_role=None):
    """Service/domain errors -> neutral HTTP (owner-foreign -> 404)."""
    from agents.ecosystem.credentials import (
        CredentialConflict,
        CredentialNotFound,
        CredentialStateConflict,
        CredentialStoreUnavailable,
        UnauthorizedManagementAttempt,
    )

    if isinstance(exc, UnauthorizedManagementAttempt):
        if actor_role == "owner":
            return 404, "Not found"
        return 403, "Forbidden"
    if isinstance(exc, CredentialNotFound):
        return 404, "Not found"
    if isinstance(exc, (CredentialConflict, CredentialStateConflict)):
        return 409, "Conflict"
    if isinstance(exc, _CredBad):
        return 400, str(exc) or "Invalid request"
    if isinstance(exc, ValueError):
        return 400, "Invalid request"
    if isinstance(exc, CredentialStoreUnavailable):
        return 503, "Temporarily unavailable"
    logger.exception("Credential management failed")
    return 500, "Internal error"


def _cred_reason(data, event):
    """Reason from body (POST) or query (GET); present must be non-empty."""
    query = event.get("queryStringParameters") or {}
    raw = data.get("reason", query.get("reason"))
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise _CredBad("Invalid field: reason")
    return raw.strip()


def _handle_credential_collection(event, context, method, pid,
                                  user_context, actor, headers, sources,
                                  corr):
    from agents.ecosystem import credentials as creds

    if method == "POST":
        data = _cred_body(event, {"label", "expiresAt", "clientRef",
                                  "reason"}, {"expiresAt"})
        _cred_str(data, "expiresAt")
        if "label" in data:
            _cred_str(data, "label", required=False)
        try:
            from dateutil.parser import parse as _parse
            _parse(data["expiresAt"])
        except Exception:
            raise _CredBad("Invalid field: expiresAt")
        reason = _cred_reason(data, event)
        out = creds.issue_credential(
            sources["credentials"], sources["profiles"], pid,
            data["expiresAt"], actor["role"], actor["id"],
            label=data.get("label"),
            reason=reason, actor_tenant=actor["tenant"],
            idempotency_key=_cred_idem(headers),
            correlation_id=corr)
        return {
            "statusCode": 200 if out.get("duplicate") else 201,
            "body": json.dumps({**out["metadata"],
                                "secret": out.get("secret"),
                                "duplicate": bool(out.get("duplicate"))}),
        }
    if method == "GET":
        reason = _cred_reason({}, event)
        rows = creds.list_credentials(
            sources["credentials"], actor["role"], actor["id"],
            api_profile_id=pid, actor_tenant=actor["tenant"],
            reason=reason, correlation_id=corr)
        return {
            "statusCode": 200,
            "body": json.dumps({"items": rows}),
        }
    return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}


def _handle_credential_item(event, context, method, pid, cid,
                            user_context, actor, headers, sources, corr):
    from agents.ecosystem import credentials as creds

    if method != "GET":
        return {"statusCode": 404,
                "body": json.dumps({"error": "Not found"})}
    reason = _cred_reason({}, event)
    meta = creds.get_credential_metadata(
        sources["credentials"], actor["role"], actor["id"], cid,
        actor_tenant=actor["tenant"], reason=reason,
        correlation_id=corr)
    if meta is None or meta.get("apiProfileId") != pid:
        return {"statusCode": 404,
                "body": json.dumps({"error": "Not found"})}
    return {"statusCode": 200, "body": json.dumps(meta)}


def _cred_bound_credential(sources, actor, cid, pid, reason, corr):
    """Neutral pre-read: credential must exist, be visible AND bound to
    the path profile — checked BEFORE any mutation (no cross-profile
    side effects)."""
    from agents.ecosystem import credentials as creds

    meta = creds.get_credential_metadata(
        sources["credentials"], actor["role"], actor["id"], cid,
        actor_tenant=actor["tenant"], reason=reason,
        correlation_id=corr)
    if meta is None or meta.get("apiProfileId") != pid:
        return None
    return meta


def _handle_credential_action(event, context, pid, cid, action,
                              user_context, actor, headers, sources, corr):
    from agents.ecosystem import credentials as creds

    data = _cred_body(event, {"expiresAt", "label", "reason"})
    reason = _cred_reason(data, event)
    key = _cred_idem(headers)
    bound = _cred_bound_credential(sources, actor, cid, pid, reason, corr)
    if bound is None:
        return {"statusCode": 404,
                "body": json.dumps({"error": "Not found"})}
    if action == "rotate":
        _cred_str(data, "expiresAt")
        try:
            from dateutil.parser import parse as _parse
            _parse(data["expiresAt"])
        except Exception:
            raise _CredBad("Invalid field: expiresAt")
        if "label" in data:
            _cred_str(data, "label", required=False)
        out = creds.rotate_credential(
            sources["credentials"], sources["profiles"], cid,
            data["expiresAt"], actor["role"], actor["id"],
            label=data.get("label"), reason=reason,
            actor_tenant=actor["tenant"], idempotency_key=key,
            correlation_id=corr)
        return {
            "statusCode": 200 if out.get("duplicate") else 201,
            "body": json.dumps({**out["metadata"],
                                "secret": out.get("secret"),
                                "duplicate": bool(out.get("duplicate"))}),
        }
    if action in ("disable", "revoke"):
        fn = creds.disable_credential if action == "disable" \
            else creds.revoke_credential
        meta = fn(sources["credentials"], cid, actor["role"], actor["id"],
                  reason=reason, actor_tenant=actor["tenant"],
                  correlation_id=corr)
    else:  # enable
        meta = creds.enable_credential(
            sources["credentials"], cid, actor["role"], actor["id"],
            actor_tenant=actor["tenant"], reason=reason,
            correlation_id=corr)
    return {"statusCode": 200, "body": json.dumps(meta)}


def _handle_credential_routes(event, context, method, path):
    """Dispatch credential management (Human JWT only, no M2M auth here)."""
    user_context = _extract_user_context(event)
    if not user_context.get("userId"):
        return {"statusCode": 401,
                "body": json.dumps({"error": "Unauthenticated"})}
    ids = _cred_ids(path)
    if ids is None:
        return {"statusCode": 404,
                "body": json.dumps({"error": "Not found"})}
    pid, cid, action = ids
    headers = _cred_headers(event)
    hint = headers.get("x-api-profile")
    if hint is not None and hint != pid:
        logger.warning("credential route profile mismatch (pid=%s)", pid)
        return {"statusCode": 400,
                "body": json.dumps({"error": "Profile mismatch"})}
    actor = _cred_actor(user_context)
    corr = _cred_correlation(event, headers)
    try:
        sources = _cred_sources()
    except Exception:
        logger.warning("Credential stores unconfigured")
        return {"statusCode": 503,
                "body": json.dumps({"error": "Temporarily unavailable"})}
    try:
        if cid is None:
            return _handle_credential_collection(
                event, context, method, pid, user_context, actor,
                headers, sources, corr)
        if action is None:
            return _handle_credential_item(
                event, context, method, pid, cid, user_context, actor,
                headers, sources, corr)
        if method != "POST":
            return {"statusCode": 404,
                    "body": json.dumps({"error": "Not found"})}
        return _handle_credential_action(
            event, context, pid, cid, action, user_context, actor,
            headers, sources, corr)
    except Exception as exc:
        status, message = _cred_fail(exc, actor["role"])
        return {"statusCode": status,
                "body": json.dumps({"error": message})}


# ------------------------------------------------------------------
# P23-01: Offer -> Entitlement Product Admin provisioning.
#
# This is HTTP WIRING ONLY. The entire product semantics already exist in
# agents.ecosystem.offers (create_offer, update_offer, set_offer_status,
# list_offers, grant_offer, withdraw_entitlement) and are reused unchanged:
# role check, agent validation against the catalog, name uniqueness, reason
# obligations, idempotency, overlap detection, all-or-nothing writes and
# audit all stay in the domain. There is deliberately no second product
# logic here and no direct DynamoDB write.
#
# Offer is the decided RIS product object (P23-01, not re-opened). The
# grant creates one entitlement row per offer agent inside the already
# authenticated Cognito context: Cognito stays the authentication boundary,
# this layer only adds product administration.
# ------------------------------------------------------------------

_OFFER_ACTIONS = ("status", "grant", "withdraw")


class _OfferBad(Exception):
    """Neutral 400 (no stack leak, no field values)."""


def _offer_sources():
    """Lazy production stores (missing config -> neutral 503)."""
    import os

    from agents.ecosystem.offers import (
        DynamoDBEntitlementStore,
        DynamoDBOfferStore,
    )

    if not os.environ.get("OFFERS_TABLE") \
            or not os.environ.get("ENTITLEMENTS_TABLE"):
        raise RuntimeError("offer stores unconfigured")
    return {
        "offers": DynamoDBOfferStore(
            table_name=os.environ.get("OFFERS_TABLE")),
        "entitlements": DynamoDBEntitlementStore(
            table_name=os.environ.get("ENTITLEMENTS_TABLE")),
    }


def _offer_actor(user_context):
    """JWT claims -> domain actor.

    The domain checks the role itself (offers._is_admin reads
    actor["groups"]); this dict only carries what the domain needs. No header
    or body field can influence the role: the groups come exclusively from the
    gateway-validated JWT.
    """
    groups = list(user_context.get("groups") or [])
    return {"userId": user_context.get("userId"),
            "tenantId": user_context.get("tenantId"),
            "groups": groups,
            "role": _cred_actor(user_context)["role"]}


def _offer_ids(path):
    """Parse offer paths -> (offerId|None, action|None) or None.

    /v1/offers                     -> (None, None)
    /v1/offers/{offerId}           -> (offerId, None)
    /v1/offers/{offerId}/status    -> (offerId, "status")
    /v1/offers/{offerId}/grant     -> (offerId, "grant")
    /v1/offers/{offerId}/withdraw  -> (offerId, "withdraw")
    """
    parts = (path or "").strip("/").split("/")
    if len(parts) < 2 or parts[0] != "v1" or parts[1] != "offers":
        return None
    if len(parts) == 2:
        return (None, None)
    offer_id = parts[2]
    if not offer_id:
        return None
    if len(parts) == 3:
        if offer_id in _OFFER_ACTIONS:
            return (None, offer_id)
        return (offer_id, None)
    if len(parts) == 4 and parts[3] in _OFFER_ACTIONS:
        return (offer_id, parts[3])
    return None


def _offer_fail(exc, actor_role=None):
    """Domain errors -> neutral HTTP (non-admin -> 403, never an oracle)."""
    from agents.ecosystem.offers import (
        EntitlementNotFound,
        GrantConflict,
        GrantDenied,
        OfferConflict,
        OfferNotFound,
        UnauthorizedOfferAction,
    )

    if isinstance(exc, UnauthorizedOfferAction):
        return 403, "Forbidden"
    if isinstance(exc, (OfferNotFound, EntitlementNotFound)):
        return 404, "Not found"
    if isinstance(exc, (OfferConflict, GrantConflict)):
        return 409, "Conflict"
    if isinstance(exc, GrantDenied):
        # Admin-target problem (unknown agent, offer inactive, unusable
        # profile). Neutral message, but the honest status.
        return 400, str(exc) or "Invalid request"
    if isinstance(exc, _OfferBad):
        return 400, str(exc) or "Invalid request"
    if isinstance(exc, ValueError):
        return 400, str(exc) or "Invalid request"
    logger.exception("Offer management failed")
    return 500, "Internal error"


def _offer_body(event, allowed, required=()):
    try:
        data = json.loads(event.get("body") or "{}")
    except (ValueError, TypeError):
        raise _OfferBad("Request body must be valid JSON")
    if not isinstance(data, dict):
        raise _OfferBad("Request body must be valid JSON")
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise _OfferBad("Unknown fields: " + ", ".join(unknown))
    for field in required:
        if field not in data:
            raise _OfferBad("Missing field: " + field)
    return data


def _offer_str(data, field, required=False):
    if field not in data:
        if required:
            raise _OfferBad("Missing field: " + field)
        return None
    value = data[field]
    if not isinstance(value, str):
        raise _OfferBad("Invalid field: " + field)
    clean = value.strip()
    if required and not clean:
        raise _OfferBad("Missing field: " + field)
    return clean or None


def _handle_offer_routes(event, context, method, path):
    """Offer management + grant (Human JWT, product admin only)."""
    user_context = _extract_user_context(event)
    if not user_context.get("userId"):
        return {"statusCode": 401,
                "body": json.dumps({"error": "Unauthenticated"})}
    ids = _offer_ids(path)
    if ids is None:
        return {"statusCode": 404,
                "body": json.dumps({"error": "Not found"})}
    offer_id, action = ids
    actor = _offer_actor(user_context)
    try:
        sources = _offer_sources()
    except Exception:
        logger.warning("Offer stores unconfigured")
        return {"statusCode": 503,
                "body": json.dumps({"error": "Temporarily unavailable"})}
    try:
        if offer_id is None and action is None:
            status, body = _handle_offer_collection(event, method, sources,
                                                    actor)
        elif action is None:
            # GET/PATCH /v1/offers/{offerId} — the item view.
            status, body = _handle_offer_status(event, method, offer_id,
                                                sources, actor)
        elif action == "status":
            status, body = _handle_offer_status(event, method, offer_id,
                                                sources, actor)
        elif action == "grant":
            status, body = _handle_offer_grant(event, method, offer_id,
                                               sources, actor)
        else:
            status, body = _handle_offer_withdraw(event, method, offer_id,
                                                  sources, actor)
    except Exception as exc:
        code, message = _offer_fail(exc, actor.get("role"))
        return {"statusCode": code,
                "body": json.dumps({"error": message})}
    return {"statusCode": status, "body": json.dumps(body)}


def _handle_offer_collection(event, method, sources, actor):
    from agents.ecosystem.offers import create_offer, list_offers

    if method == "GET":
        data = _offer_body(event, {"includeInactive"})
        include = data.get("includeInactive") is True
        return 200, {"offers": list_offers(sources["offers"], actor,
                                            include_inactive=include)}
    if method == "POST":
        data = _offer_body(event, {"name", "description", "agentIds",
                                   "status"}, {"name", "agentIds"})
        agent_ids = data.get("agentIds")
        if not isinstance(agent_ids, list):
            raise _OfferBad("Invalid field: agentIds")
        status = _offer_str(data, "status") or "ACTIVE"
        return 201, create_offer(
            sources["offers"], actor,
            _offer_str(data, "name", required=True), agent_ids,
            _get_agent_catalog(),
            description=_offer_str(data, "description"),
            status=status)
    return 404, {"error": "Not found"}


def _handle_offer_status(event, method, offer_id, sources, actor):
    from agents.ecosystem.offers import get_offer, set_offer_status

    if method == "GET":
        item = get_offer(sources["offers"], offer_id)
        if item is None:
            return 404, {"error": "Not found"}
        return 200, item
    if method == "PATCH":
        data = _offer_body(event, {"agentIds", "description"}, set())
        agent_ids = data.get("agentIds")
        if agent_ids is not None and not isinstance(agent_ids, list):
            raise _OfferBad("Invalid field: agentIds")
        from agents.ecosystem.offers import update_offer
        return 200, update_offer(
            sources["offers"], actor, offer_id, _get_agent_catalog(),
            description=_offer_str(data, "description"),
            agent_ids=agent_ids)
    if method == "POST":
        data = _offer_body(event, {"status", "reason"}, {"status", "reason"})
        return 200, set_offer_status(sources["offers"], actor, offer_id,
                                     _offer_str(data, "status", required=True),
                                     reason=_offer_str(data, "reason",
                                                       required=True))
    return 404, {"error": "Not found"}


def _handle_offer_grant(event, method, offer_id, sources, actor):
    """Offer -> entitlements, reusing grant_offer unchanged.

    User-wide (scope USER) is the mode proven end to end in this gate: it
    writes rows WITHOUT apiProfileId, which is exactly the shape
    check_worker_entitlement treats as user-wide. Profile-bound grants stay
    available in the domain but are not exercised here.
    """
    from agents.ecosystem.offers import SCOPE_USER, grant_offer

    if method != "POST":
        return 404, {"error": "Not found"}
    # validFrom/validUntil are required: _windows_ok in the domain refuses a
    # grant without a window ("validFrom/validUntil required and parseable"),
    # so making them optional here would only defer the same 400 into the
    # domain layer. The domain check stays authoritative either way.
    data = _offer_body(event, {"userId", "tenantId", "reason",
                               "validFrom", "validUntil"},
                       {"userId", "tenantId", "reason", "validFrom",
                        "validUntil"})
    from agents.ecosystem.api_profiles import DynamoDBApiProfileStore
    import os
    return 200, grant_offer(
        sources["offers"], sources["entitlements"],
        DynamoDBApiProfileStore(
            table_name=os.environ.get("API_PROFILES_TABLE")),
        _get_agent_catalog(), actor, offer_id,
        _offer_str(data, "userId", required=True),
        _offer_str(data, "tenantId", required=True),
        SCOPE_USER,
        valid_from=_offer_str(data, "validFrom"),
        valid_until=_offer_str(data, "validUntil"),
        reason=_offer_str(data, "reason", required=True))


def _handle_offer_withdraw(event, method, offer_id, sources, actor):
    """Withdraw one entitlement produced by this offer's grant (admin).

    The domain function withdraw_entitlement works on an entitlement id alone.
    Binding it to the offer in the path and checking the provenance keeps an
    admin from withdrawing an entitlement of a DIFFERENT offer by passing the
    wrong offer id -- the path must actually describe the row.
    """
    from agents.ecosystem.offers import withdraw_entitlement

    if method != "POST":
        return 404, {"error": "Not found"}
    data = _offer_body(event, {"entitlementId", "reason"},
                       {"entitlementId", "reason"})
    entitlement_id = _offer_str(data, "entitlementId", required=True)
    row = sources["entitlements"].get_entitlement(entitlement_id)
    if row is None or row.get("offerId") != offer_id:
        return 404, {"error": "Not found"}
    withdraw_entitlement(sources["entitlements"], actor, entitlement_id,
                         reason=_offer_str(data, "reason", required=True))
    return 200, {"withdrawn": True, "entitlementId": entitlement_id}


# ------------------------------------------------------------------
# P19: APIProfile management HTTP (Human JWT only).
#
# Diese Schicht ist REINE VERDRAHTUNG. Rollenmatrix, Tenant-Isolation,
# Uniqueness, Lifecycle und Audit kommen unveraendert aus
# agents/ecosystem/api_profiles.py (create_profile, get_profile,
# list_profiles, update_profile, transition_status). Es gibt hier
# bewusst KEINE zweite Validierung und KEINE eigene Statusmaschine.
#
# Nicht veroeffentlicht (bleiben interne Domain-Unterstuetzung, siehe
# P19-Report): set_client_ref, set_expires_at, renew_profile. Sie sind
# admin-only Vertragsfelder, aber kein eigenstaendiger HTTP-Vertrag.
# ------------------------------------------------------------------

_APROF_STATUS_TARGETS = ("ACTIVE", "DISABLED", "REVOKED")


class _AProfBad(Exception):
    """Neutral 400 (kein Stack-Leak, keine Feldwerte)."""


def _aprof_store():
    """Lazy production store (fehlende Config -> neutral 503)."""
    import os

    from agents.ecosystem.api_profiles import DynamoDBApiProfileStore

    if not os.environ.get("API_PROFILES_TABLE"):
        raise RuntimeError("api-profile store unconfigured")
    return DynamoDBApiProfileStore(
        table_name=os.environ.get("API_PROFILES_TABLE"))


def _aprof_actor(user_context):
    """JWT claims -> domain actor.

    WICHTIG: die Domain prueft Rollen ueber actor["groups"]
    (api_profiles._is_admin/_is_staff). Der Rollenstring wird nur fuer
    die HTTP-Fehlerausgabe (403 vs. neutral 404) gebraucht.
    """
    groups = list(user_context.get("groups") or [])
    return {
        "userId": user_context.get("userId"),
        "tenantId": user_context.get("tenantId"),
        "groups": groups,
        "role": _cred_actor(user_context)["role"],
    }


def _aprof_ids(path):
    """Parse profile paths -> (pid|None, action|None) oder None.

    /v1/apiprofiles                 -> (None, None)
    /v1/apiprofiles/{pid}           -> (pid, None)
    /v1/apiprofiles/{pid}/status    -> (pid, "status")
    """
    parts = (path or "").strip("/").split("/")
    if len(parts) < 2 or parts[0] != "v1" or parts[1] != "apiprofiles":
        return None
    if len(parts) == 2:
        return (None, None)
    pid = parts[2]
    if not pid:
        return None
    if len(parts) == 3:
        return (pid, None)
    if len(parts) == 4 and parts[3] == "status":
        return (pid, "status")
    return None


def _aprof_body(event, allowed, required=()):
    try:
        data = json.loads(event.get("body") or "{}")
    except (ValueError, TypeError):
        raise _AProfBad("Request body must be valid JSON")
    if not isinstance(data, dict):
        raise _AProfBad("Request body must be valid JSON")
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        # Deckt immutable/system/admin-only Felder ab: update_profile
        # lehnt sie ebenfalls ab, hier wird schon vor dem Store
        # neutral abgewiesen.
        raise _AProfBad("Unknown fields: " + ", ".join(unknown))
    for field in required:
        if field not in data:
            raise _AProfBad("Missing field: " + field)
    return data


def _aprof_str(data, field, required=True):
    value = data.get(field)
    if value is None:
        if required:
            raise _AProfBad("Missing field: " + field)
        return None
    if not isinstance(value, str) or not value.strip():
        raise _AProfBad("Invalid field: " + field)
    return value.strip()


def _aprof_reason(data, event):
    """Reason aus Body (Schreib-Requests) oder Query (Reads)."""
    query = event.get("queryStringParameters") or {}
    raw = data.get("reason", query.get("reason"))
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise _AProfBad("Invalid field: reason")
    return raw.strip()


def _aprof_fail(exc, actor_role=None):
    """Domain-Fehler -> neutrales HTTP.

    Owner + fremdes Profil -> 404 (kein Oracle: fremd und fehlend sind
    ununterscheidbar). Admin/Staff -> 403.
    """
    from agents.ecosystem.api_profiles import (
        InvalidProfileTransition,
        ProfileConflict,
        ProfileNotFound,
        UnauthorizedProfileAction,
    )

    if isinstance(exc, UnauthorizedProfileAction):
        if actor_role == "owner":
            return 404, "Not found"
        return 403, "Forbidden"
    if isinstance(exc, ProfileNotFound):
        return 404, "Not found"
    if isinstance(exc, (ProfileConflict, InvalidProfileTransition)):
        return 409, "Conflict"
    if isinstance(exc, _AProfBad):
        return 400, str(exc) or "Invalid request"
    if isinstance(exc, ValueError):
        return 400, "Invalid request"
    logger.exception("APIProfile management failed")
    return 500, "Internal error"


def _handle_apiprofile_collection(event, method, store, actor):
    """POST /v1/apiprofiles (create) und GET /v1/apiprofiles (list)."""
    from agents.ecosystem import api_profiles

    if method == "POST":
        data = _aprof_body(event, {"name", "description", "targetOwner",
                                   "reason"}, {"name"})
        name = _aprof_str(data, "name")
        description = _aprof_str(data, "description", required=False)
        # targetOwner ist der einzige zulaessige Admin-Pfad laut
        # Contract (create_profile -> target_owner). Die Domain
        # verweigert ihn fuer Nicht-Admin (UnauthorizedProfileAction).
        target_owner = _aprof_str(data, "targetOwner", required=False)
        reason = _aprof_reason(data, event)
        if target_owner and target_owner != actor["userId"] \
                and reason is None and "admins" not in actor["groups"]:
            # Kein Vorab-Vorteil: die Domain entscheidet. Wir geben
            # nur eine klare Fehlermeldung statt stiller Annahme.
            raise _AProfBad("Invalid field: targetOwner")
        item = api_profiles.create_profile(
            store, actor, name, description=description,
            target_owner=target_owner,
            idempotency_key=_cred_idem(_cred_headers(event)))
        return 201, item
    if method == "GET":
        reason = _aprof_reason({}, event)
        items = api_profiles.list_profiles(store, actor, reason=reason)
        return 200, {"items": items}
    return 404, {"error": "Not found"}


def _handle_apiprofile_item(event, method, pid, store, actor):
    """GET/PATCH /v1/apiprofiles/{apiProfileId}."""
    from agents.ecosystem import api_profiles

    if method == "GET":
        reason = _aprof_reason({}, event)
        item = api_profiles.get_profile(store, actor, pid, reason=reason)
        if item is None:
            return 404, {"error": "Not found"}
        return 200, item
    if method == "PATCH":
        data = _aprof_body(event, {"name", "description", "reason"})
        name = _aprof_str(data, "name", required=False)
        description = None
        if "description" in data:
            raw = data["description"]
            if raw is not None and not isinstance(raw, str):
                raise _AProfBad("Invalid field: description")
            description = raw
        reason = _aprof_reason(data, event)
        item = api_profiles.update_profile(
            store, actor, pid, name=name, description=description,
            reason=reason)
        if item is None:
            return 404, {"error": "Not found"}
        return 200, item
    return 404, {"error": "Not found"}


def _handle_apiprofile_status(event, method, pid, store, actor):
    """POST /v1/apiprofiles/{apiProfileId}/status (Lifecycle).

    Nutzt ausschliesslich transition_status. EXPIRED ist im Contract
    abgeleitet und wird hier bewusst nicht als Ziel akzeptiert.
    """
    from agents.ecosystem import api_profiles

    if method != "POST":
        return 404, {"error": "Not found"}
    data = _aprof_body(event, {"status", "reason"}, {"status"})
    target = _aprof_str(data, "status")
    if target not in _APROF_STATUS_TARGETS:
        raise _AProfBad("Invalid field: status")
    reason = _aprof_reason(data, event)
    item = api_profiles.transition_status(
        store, actor, pid, target, reason=reason)
    return 200, item


def _handle_apiprofile_routes(event, context, method, path):
    """Dispatch APIProfile management (Human JWT only, kein M2M hier)."""
    user_context = _extract_user_context(event)
    if not user_context.get("userId"):
        return {"statusCode": 401,
                "body": json.dumps({"error": "Unauthenticated"})}
    ids = _aprof_ids(path)
    if ids is None:
        return {"statusCode": 404,
                "body": json.dumps({"error": "Not found"})}
    pid, action = ids
    if not user_context.get("tenantId"):
        # Contract: tenantId ist Pflicht fuer owner/tenant-Pfade.
        return {"statusCode": 403,
                "body": json.dumps({"error": "Forbidden"})}
    actor = _aprof_actor(user_context)
    try:
        store = _aprof_store()
    except Exception:
        logger.warning("APIProfile store unconfigured")
        return {"statusCode": 503,
                "body": json.dumps({"error": "Temporarily unavailable"})}
    try:
        if pid is None:
            status, body = _handle_apiprofile_collection(
                event, method, store, actor)
        elif action == "status":
            status, body = _handle_apiprofile_status(
                event, method, pid, store, actor)
        else:
            status, body = _handle_apiprofile_item(
                event, method, pid, store, actor)
    except Exception as exc:
        status, message = _aprof_fail(exc, actor["role"])
        return {"statusCode": status,
                "body": json.dumps({"error": message})}
    return {"statusCode": status, "body": json.dumps(body)}


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


def _enqueue_agent_work(agent_id: str, capability: str,
                        payload: Dict[str, Any],
                        tenant_id: Optional[str],
                        user_id: Optional[str],
                        agent_version: str = '1.0.0',
                        idempotency_key: Optional[str] = None
                        ) -> Dict[str, Any]:
    """Single execution contract: build the work item, persist, enqueue.

    Shared by the human path (`_execute_agent`) and the machine path
    (`_machine_execute_agent`, Gate B3-...-08) so both authenticators reach
    the EXACT same execution contract. There is deliberately no second
    execution shape: one work_item schema, one SQS hand-off, one 202
    response.
    """
    request_id = str(uuid.uuid4())
    now = utcnow()

    work_item = {
        'workId': str(uuid.uuid4()),
        'type': f'agent_{agent_id}',
        'tenantId': tenant_id,
        'userId': user_id,
        'requestedBy': user_id,
        'agentId': agent_id,
        'capability': capability,
        'idempotencyKey': idempotency_key or str(uuid.uuid4()),
        'payloadVersion': '1.0',
        'agentVersion': agent_version or '1.0.0',
        'requestId': request_id,
        'status': 'QUEUED',
        'attempt': 0,
        'payload': payload,
        'createdAt': now.isoformat(),
        'expiresAt': (now + timedelta(days=30)).isoformat()
    }

    table_name = os.environ.get('WORK_ITEMS_TABLE')
    if table_name:
        table = _get_dynamodb().Table(table_name)
        table.put_item(Item=work_item)

    queue_url = os.environ.get('WORK_QUEUE_URL')
    if queue_url:
        _get_sqs().send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(work_item),
            MessageAttributes={
                'workType': {'StringValue': work_item['type'],
                             'DataType': 'String'},
                'agentId': {'StringValue': agent_id, 'DataType': 'String'}
            }
        )

    return {'workId': work_item['workId'], 'status': 'QUEUED',
            'requestId': request_id, 'workItem': work_item}


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

    # Central status decision (fail-closed, Gate 07).
    from agents.ecosystem.agent_status import is_executable_status
    if not is_executable_status(agent.get('status')):
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Agent is not active'})
        }
    
    # Single execution contract (shared with the machine path).
    try:
        out = _enqueue_agent_work(
            agent_id=agent_id,
            capability=capability,
            payload=payload,
            tenant_id=user_context['tenantId'],
            user_id=user_context['userId'],
            agent_version=agent.get('version', '1.0.0'),
            idempotency_key=body.get('idempotencyKey'))
    except Exception as e:
        logger.error(f"Error creating work item: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to create work item'})
        }

    return {
        'statusCode': 202,
        'body': json.dumps({
            'workId': out['workId'],
            'status': out['status'],
            'requestId': out['requestId']
        })
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

        # B3: userId is NOT the table key (PK entitlementId) — the
        # query must name the gsi-user index explicitly, otherwise
        # DynamoDB answers ValidationException (silent None below).
        response = table.query(
            IndexName='gsi-user',
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

        # B3: see _get_entitlement_for_agent (gsi-user required).
        response = table.query(
            IndexName='gsi-user',
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
    """Check if an entitlement is currently valid based on temporal constraints.

    Thin delegation to the canonical domain function
    `agents.ecosystem.worker_authorization.is_entitlement_valid`.

    This used to be a second, independent implementation. It compared a
    naive `datetime.utcnow()` against `dateutil` bounds and caught the
    resulting TypeError in the same `except` used for parse failures, so
    any offset-bearing window (`Z`, `+00:00`, any offset) evaluated as
    VALID — including long-expired and not-yet-valid entitlements. That
    is fail-open on an authorization gate, and it made ingress MORE
    permissive than the worker re-check that guards actual execution.

    One implementation, one contract: ingress and worker can no longer
    disagree about whether an entitlement is valid.
    """
    from agents.ecosystem.worker_authorization import is_entitlement_valid
    return is_entitlement_valid(entitlement)


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
    from agents.ecosystem.worker_authorization import (
        DynamoDBEntitlementResolver,
    )

    # Execution-Time-Entitlement-Re-check (Gate 08): Produktion injiziert
    # immer den DDB-Resolver (lazy, keine Import-Kosten ohne Nutzung).
    outcome = process_record(
        {'body': work_item},
        entitlement_resolver=DynamoDBEntitlementResolver())

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
    if outcome.get('denied'):
        result['denied'] = True
        result['reason'] = outcome.get('reason')
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
        'createdAt': utcnow_naive_iso(),
        'expiresAt': (utcnow() + timedelta(days=30)).replace(tzinfo=None).isoformat()
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
        
        existing.updated_at = utcnow()
        
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