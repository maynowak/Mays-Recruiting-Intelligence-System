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
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

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
    if event.get('httpMethod') or ((event.get('requestContext') or {}).get('http') or {}).get('method'):
        return _handle_personal_api_boundary(event, context)
    if event.get('Records'):
        return _handle_sqs_event(event, context)
    return _handle_api_event(event, context)


def _personal_api_path(path: str) -> bool:
    """Return whether a Lambda-served path can contain subject data."""
    return (
        path in {"/me", "/agents"}
        or path.startswith("/me/")
        or path.startswith("/v1/partner/me/")
    )


def _finalize_personal_response(event: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
    path = event.get("path") or ((event.get("requestContext") or {}).get("http") or {}).get("path", "/")
    if not _personal_api_path(path) or not isinstance(response, dict):
        return response
    finalized = dict(response)
    headers = dict(finalized.get("headers") or {})
    headers["Cache-Control"] = "no-store, private"
    finalized["headers"] = headers
    return finalized


def _handle_personal_api_boundary(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Finalize all subject-bearing API responses, including early failures."""
    try:
        response = _handle_api_event(event, context)
    except Exception:
        logger.exception("personal API request failed")
        response = {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal error"}),
        }
    return _finalize_personal_response(event, response)


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
        'groups': [],
        'clientId': None,
        'audience': None,
        'tokenUse': None
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
    
    # Cognito client_credentials tokens include client_id claim
    context['clientId'] = jwt_claims.get('client_id')

    # `aud` is the audience the gateway authorizer already validated
    # against its configured audience list. For an ID token it is the
    # app client id — that is the only client identity an ID token
    # carries (no `client_id` claim). It is used as a server-side
    # tenant lookup key, never as a caller-supplied value.
    context['audience'] = jwt_claims.get('aud')
    
    context['tokenUse'] = jwt_claims.get('token_use')
    context['partnerApplicationId'] = (
        jwt_claims.get('custom:partner_application_id')
        or jwt_claims.get('partnerApplicationId'))
    context['issuer'] = jwt_claims.get('iss')
    
    # Security fix 02: normalize, never split blindly. See
    # _normalize_groups — the authorizer stringifies array claims.
    context['groups'] = _normalize_groups(jwt_claims.get('cognito:groups'))
    
    return context


# ------------------------------------------------------------------
# L03 — Tenant-Aufloesung (serverseitig, niemals vom Browser).
#
# Der Tenant ist eine SERVER-Zustandsgroesse. Er wird aus genau einer
# der folgenden Quellen bestimmt:
#
#   1. `custom:tenant_id` im JWT-Claim — autoritativ, wenn vorhanden.
#      Widerspricht der Claim der serverseitigen Aufloesung, ist das ein
#      Cross-Tenant-Versuch -> deny.
#   2. Partner-Registry: JWT `client_id` -> Partner Application ->
#      tenantId. Die Registry ist die eigene Tabelle des Servers, und
#      die `client_id` hat der Gateway-Authorizer validiert.
#      Fuellwert ist der `aud`-Claim: der Human-Authorizer laesst nur
#      ID-Tokens zu (aud = App-Client-ID), und ein ID-Token fuehrt
#      keinen `client_id`-Claim. Der Authorizer hat `aud` aber bereits
#      gegen die konfigurierte Audience geprueft — der Client ist damit
#      serverseitig festgelegt.
#
# Es gibt bewusst KEINEN Fallback auf "default": ein stiller
# "default"-Tenant wuerde die Profile verschiedener Partner in einen
# gemeinsamen Bucket legen und die Tenant-Isolation aufheben. Ohne
# aufloesbaren Tenant wird verweigert, nicht geraten.
# ------------------------------------------------------------------


def _registry_tenant(client_id: Optional[str],
                     audience: Optional[str] = None) -> Optional[str]:
    """Tenant des Cognito-Clients laut Partner-Registry (serverseitig).

    Fail closed: ein nicht registrierter, deaktivierter oder nicht
    auflösbarer Client liefert keinen Tenant.
    """
    for candidate in (client_id, audience):
        if not candidate or not isinstance(candidate, str):
            continue
        try:
            from agents.ecosystem.partner_registry import resolve_partner_application

            registry = resolve_partner_application(candidate)
        except Exception:
            logger.warning("partner registry lookup failed during tenant "
                           "resolution")
            continue
        if not registry or registry.get('status') != 'ACTIVE':
            continue
        tenant_id = registry.get('tenantId')
        if isinstance(tenant_id, str) and tenant_id.strip():
            return tenant_id.strip()
    return None


def _resolve_tenant(user_context: Dict[str, Any],
                    expected_tenant: Optional[str] = None
                    ) -> Tuple[Optional[str], bool]:
    """Effektiven Tenant bestimmen -> (tenantId, conflict).

    `expected_tenant` ist der bereits serverseitig festgelegte Tenant
    (Credential/Registry in der Partnerroute). Er ist dann allein
    massgeblich; ein abweichender Claim ist ein Cross-Tenant-Versuch.
    Ohne `expected_tenant` gilt: der Claim gewinnt, sonst die Registry.
    """
    claim = user_context.get('tenantId')
    if not isinstance(claim, str) or not claim.strip():
        claim = None
    if expected_tenant:
        expected = expected_tenant.strip()
        if claim and claim != expected:
            return None, True
        return (expected or None), False
    server = _registry_tenant(user_context.get('clientId'),
                              user_context.get('audience'))
    if claim and server and claim != server:
        return None, True
    return (claim or server), False


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
    elif method == 'PATCH' and path == '/me/profile':
        return _handle_me_profile_update(event, context)
    elif method == 'PUT' and path == '/me/profile':
        return _handle_me_profile_update(event, context)
    elif method == 'DELETE' and path == '/me/profile':
        return _handle_me_profile_delete(event, context)
    elif method == 'GET' and path == '/v1/partner/me/privacy/inspect':
        return _handle_privacy_inspect(event, context)
    elif method == 'GET' and path == '/v1/partner/me/privacy/export':
        return _handle_privacy_export(event, context)
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
        # B3 / Option D: dedicated MACHINE plane. Both authentication
        # boundaries apply (P21-01): the gateway route is JWT-protected on
        # the DEDICATED M2M authorizer (`authorization_type = "JWT"`,
        # audience = M2M app client, required scope `ris-api/m2m/execute`,
        # see terraform/modules/api/main.tf), AND the opaque `ris_...`
        # credential is verified in-Lambda. Neither replaces the other.
        # All human paths above are unchanged.
        return _machine_execute_agent(event, _machine_agent_id(path))
    elif method == 'POST' and path.startswith('/v1/partner/agents/'):
        return _partner_execute_agent(event, _machine_agent_id(path.replace('/v1/partner/agents/', '/v1/m2m/agents/')))
    elif path == '/v1/partner/me/manual-search-profiles':
        # R03: partner manual search profile CRUD (human JWT + RIS credential).
        return _partner_storage_guard(
            _handle_manual_profile_collection, event, context, method)
    elif path.startswith('/v1/partner/me/manual-search-profiles/'):
        params = event.get('pathParameters') or {}
        profile_id = params.get('profileId') or path[len('/v1/partner/me/manual-search-profiles/'):].split('?')[0]
        return _partner_storage_guard(
            _handle_manual_profile_item, event, context, method, profile_id)
    elif path == '/v1/partner/me/cvs' or path.startswith('/v1/partner/me/cvs/'):
        # R04: partner CV metadata + secure document lifecycle.
        return _partner_storage_guard(
            _handle_partner_cv_routes, event, context, method, path)
    elif path.startswith('/v1/partner/me/search-profiles/'):
        # R06: partner ATS search profiles (ATSSearchProfileV1 CRUD).
        return _partner_storage_guard(
            _handle_partner_ats_routes, event, context, method, path)
    elif path == '/v1/partner/me/applications' or path.startswith('/v1/partner/me/applications/'):
        # ApplicationV1 uses the existing authenticated partner boundary. It
        # never invokes an agent/model and never accepts client identity.
        return _application_routes(event, context, method, path)
    elif method == 'GET' and path.startswith('/work'):
        work_id = event.get('pathParameters', {}).get('workId')
        return _get_work(work_id, event)
    
    return {
        'statusCode': 404,
        'body': json.dumps({'error': 'Not found'})
    }


def _application_json_default(value):
    """Serialize DynamoDB numbers without changing stored precision.

    DynamoDB returns numbers as ``Decimal``. They stay Decimal in the
    repository/store layer; only the HTTP projection converts them to JSON
    numbers. Integral values become ints, fractional values become floats.
    Any other unserializable type still fails closed.
    """
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    raise TypeError(
        'Object of type %s is not JSON serializable' % type(value).__name__)


def _application_response(status, payload=None, code=None):
    body = payload if isinstance(payload, dict) else {'error': payload or 'Application request failed'}
    if code:
        body['code'] = code
    return {
        'statusCode': status,
        'headers': {'Cache-Control': 'no-store, private'},
        'body': json.dumps(body, ensure_ascii=False,
                           default=_application_json_default),
    }


def _application_repo():
    from jobsearch.application_repository import ApplicationRepository
    return ApplicationRepository()


def _application_ctx(event):
    from jobsearch.application_contract import ApplicationContext
    ctx, error = _partner_profile_context(event)
    if error:
        return None, error
    return ApplicationContext(
        user_id=ctx['userId'], tenant_id=ctx['tenantId'],
        partner_application_id=ctx['partnerApplicationId'], issuer=ctx['issuer']), None


def _application_body(event):
    try:
        value = json.loads(event.get('body') or '{}')
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _application_id(event, path):
    params = event.get('pathParameters') or {}
    if params.get('applicationId'):
        return params['applicationId']
    rest = path[len('/v1/partner/me/applications/'):]
    return rest.split('/', 1)[0]


def _application_cursor(event, repo, ctx, limit):
    raw = (event.get('queryStringParameters') or {}).get('cursor')
    if not raw:
        return None
    try:
        params = event.get('queryStringParameters') or {}
        return repo.resolve_cursor(raw, user_id=ctx.user_id, tenant_id=ctx.tenant_id,
                                   partner_app_id=ctx.partner_application_id,
                                   issuer=ctx.issuer, scope='applications',
                                   resource_type='ApplicationV1', limit=limit,
                                   status_filter=params.get('status'), stage_filter=params.get('stage'))
    except Exception:
        raise ValueError('invalid cursor')


def _application_routes(event, context, method, path):
    ctx, error = _application_ctx(event)
    if error:
        return error
    from jobsearch.application_contract import ApplicationContractError
    from jobsearch.application_repository import ApplicationConflict, ApplicationNotFound
    repo = _application_repo()
    try:
        base = path == '/v1/partner/me/applications'
        if base and method == 'POST':
            result = repo.create(_application_body(event), ctx)
            return _application_response(201, {'application': result})
        if base and method == 'GET':
            params = event.get('queryStringParameters') or {}
            limit = int(params.get('limit', 50))
            status_filter = params.get('status')
            stage_filter = params.get('stage')
            cursor = _application_cursor(event, repo, ctx, limit)
            items, next_key = repo.list(ctx, limit=limit, cursor=cursor,
                                        status_filter=status_filter, stage_filter=stage_filter)
            next_cursor = repo.issue_cursor(next_key, user_id=ctx.user_id, tenant_id=ctx.tenant_id,
                                            partner_app_id=ctx.partner_application_id, issuer=ctx.issuer,
                                            scope='applications', resource_type='ApplicationV1', limit=limit,
                                            status_filter=status_filter, stage_filter=stage_filter) if next_key else None
            return _application_response(200, {'items': items, 'nextCursor': next_cursor})
        if path == '/v1/partner/me/applications/metrics' and method == 'GET':
            return _application_response(200, {'metrics': repo.metrics(ctx)})
        app_id = _application_id(event, path)
        suffix = path[len('/v1/partner/me/applications/' + app_id):].strip('/')
        if not suffix and method == 'GET':
            return _application_response(200, {'application': repo.get(app_id, ctx)})
        if not suffix and method == 'PATCH':
            return _application_response(200, {'application': repo.patch(app_id, _application_body(event), ctx)})
        if not suffix and method == 'DELETE':
            body = _application_body(event) or {}
            repo.delete(app_id, int(body.get('expectedVersion', 0)), ctx)
            response = _application_response(204, {})
            response.pop('body', None)
            return response
        if suffix == 'status' and method == 'POST':
            body = _application_body(event) or {}
            if ('status' in body) == ('stage' in body):
                return _application_response(422, 'Exactly one of status or stage is required', 'STATUS_SELECTOR_REQUIRED')
            target = body.get('stage') if body.get('stage') is not None else body.get('status')
            return _application_response(200, {'application': repo.status(app_id, target, int(body.get('expectedVersion', 0)), bool(body.get('confirm')), ctx, body.get('note'))})
        if suffix == 'history' and method == 'POST':
            body = _application_body(event) or {}
            return _application_response(201, {'history': repo.add_history(app_id, body.get('event'), int(body.get('expectedVersion', 0)), ctx)})
        if suffix == 'cover-letter-versions' and method == 'POST':
            body = _application_body(event) or {}
            version = body.get('version') if body.get('version') is not None else body.get('text')
            return _application_response(201, {'version': repo.add_cover_letter(app_id, version, int(body.get('expectedVersion', 0)), ctx)})
        if suffix == 'export' and method == 'GET':
            return _application_response(200, repo.export(app_id, ctx))
        return _application_response(405, 'Method not allowed', 'METHOD_NOT_ALLOWED')
    except ApplicationNotFound:
        return _application_response(404, 'Application not found', 'NOT_FOUND')
    except ApplicationConflict as exc:
        code = str(exc) if str(exc) in {'VERSION_CONFLICT', 'HISTORY_CONFLICT', 'COVER_LETTER_CONFLICT', 'IDEMPOTENCY_PAYLOAD_CONFLICT'} else 'CONFLICT'
        return _application_response(409, 'Application conflict', code)
    except ApplicationContractError as exc:
        return _application_response(422, str(exc), exc.code)
    except (TypeError, ValueError):
        return _application_response(422, 'Invalid application request', 'VALIDATION_ERROR')
    except Exception:
        logger.exception('application request failed')
        return _application_response(503, 'Service unavailable', 'UNAVAILABLE')


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
    
    # L03: der Tenant wird serverseitig aufgeloest. Ohne aufloesbaren
    # Tenant laesst sich die Tenant-Isolation des Profils nicht pruefen
    # -> verweigern statt unklarer Datenfreigabe.
    tenant_id, tenant_conflict = _resolve_tenant(user_context)
    if tenant_conflict or not tenant_id:
        logger.warning("profile read denied: tenant not resolvable")
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Tenant not resolvable'})
        }
    
    profile = _get_user_profile(user_context['userId'], tenant_id)
    
    if not profile:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Profile not found'})
        }
    
    try:
        profile = _canonical_user_profile(profile)
    except ValueError:
        logger.error("profile read returned invalid status")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Invalid profile state'})}

    return {
        'statusCode': 200,
        'body': json.dumps(profile)
    }


def _canonical_user_profile(item: Dict[str, Any]) -> Dict[str, Any]:
    """Project a stored profile into the canonical UserProfileV1 response.

    Legacy rows may not have ``schemaVersion``/``version`` and may contain
    uppercase status values. This is a read projection only; migration is
    performed atomically by the versioned PATCH path.
    """
    if not isinstance(item, dict):
        raise ValueError('profile must be an object')
    status = str(item.get('status', 'pending') or 'pending').lower()
    if status not in {'active', 'disabled', 'pending'}:
        raise ValueError('invalid profile status')
    version = item.get('version', 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError('invalid profile version')
    result = {
        'schemaVersion': 1,
        'userId': item.get('userId'),
        'tenantId': item.get('tenantId'),
        'status': status,
        'createdAt': item.get('createdAt'),
        'updatedAt': item.get('updatedAt'),
        'version': version,
    }
    for key in ('nickname', 'firstName', 'lastName', 'email'):
        if key in item:
            result[key] = item.get(key)
    return result


class _WriteFreezeUnavailable(Exception):
    """Enabled freeze cannot safely authorize a legacy UserProfile mutation."""


class _UserProfileMutationConflict(Exception):
    """The UserProfile mutation condition failed after the guard passed."""


def _user_profile_freeze_context(event: Dict[str, Any],
                                 user_context: Dict[str, Any],
                                 tenant_id: str) -> Optional[Dict[str, Any]]:
    """Resolve the verified dual-auth scope required for atomic UserProfile writes."""
    if os.environ.get("ERASURE_WRITE_FREEZE_ENABLED", "false").strip().lower() != "true":
        return None
    verified, error = _partner_profile_context(event)
    if error or not verified:
        raise _WriteFreezeUnavailable("verified partner freeze scope unavailable")
    if (verified.get("userId") != user_context.get("userId")
            or verified.get("tenantId") != tenant_id
            or not verified.get("partnerApplicationId")
            or not verified.get("issuer")):
        raise _WriteFreezeUnavailable("verified partner freeze scope mismatch")
    return verified


def _user_profile_guard_check(freeze_context: Dict[str, Any]) -> Dict[str, Any]:
    """Build the guard ConditionCheck without reading the guard first."""
    from agents.ecosystem.privacy_erasure_contract import freeze_resource_id
    key = freeze_resource_id(
        user_id=freeze_context["userId"], tenant_id=freeze_context["tenantId"],
        partner_application_id=freeze_context["partnerApplicationId"],
        issuer=freeze_context["issuer"], scope="USER")
    return {
        "ConditionCheck": {
            "TableName": os.environ.get("PARTNER_PROFILE_TABLE"),
            "Key": {"resourceId": {"S": key}},
            "ConditionExpression": (
                "attribute_not_exists(resourceId) OR #s = :released"),
            "ExpressionAttributeNames": {"#s": "state"},
            "ExpressionAttributeValues": {":released": {"S": "RELEASED"}},
        }
    }


def _user_profile_transact(table_name: str, freeze_context: Dict[str, Any],
                           mutation: Dict[str, Any]) -> None:
    """Atomically couple the partner guard and UserProfile mutation."""
    guard_table = os.environ.get("PARTNER_PROFILE_TABLE")
    if not guard_table:
        raise _WriteFreezeUnavailable("partner profile guard store unavailable")
    check = _user_profile_guard_check(freeze_context)
    check["ConditionCheck"]["TableName"] = guard_table
    dynamodb = _get_dynamodb()
    client = getattr(getattr(dynamodb, "meta", None), "client", None)
    if client is None or not hasattr(client, "transact_write_items"):
        raise _WriteFreezeUnavailable("transactional UserProfile writer unavailable")
    mutation["Put" if "Put" in mutation else "Update" if "Update" in mutation else "Delete"]["TableName"] = table_name
    try:
        client.transact_write_items(TransactItems=[check, mutation])
    except Exception as exc:
        if hasattr(exc, "response") and exc.response.get("CancellationReasons"):
            reasons = exc.response["CancellationReasons"]
            if reasons and reasons[0].get("Code") not in (None, "None"):
                raise _WriteFreezeUnavailable("UserProfile freeze conflict") from exc
            raise _UserProfileMutationConflict("UserProfile mutation conflict") from exc
        if "ConditionalCheckFailed" in str(exc):
            raise _UserProfileMutationConflict("UserProfile mutation conflict") from exc
        raise


def _provision_user_profile(table: Any, user_context: Dict[str, Any],
                            body: Dict[str, Any],
                            tenant_id: Optional[str] = None,
                            freeze_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Profil provisionieren — NUR explizit (nie via GET).

    Gate 10: Trigger ist die Registrierung/Aktivierung (Client ruft POST
    nach Confirmation), nicht der erste Read. Conditional Write: existiert
    bereits ein Profil -> 409, kein Ueberschreiben.

    L03: `tenant_id` ist der serverseitig aufgeloeste Tenant (L03-
    Resolver). Es gibt bewusst KEINEN "default"-Fallback: ein stiller
    Default-Tenant wuerde die Profile verschiedener Partner in einen
    gemeinsamen Bucket legen. Ohne aufgeloesten Tenant wird nicht
    geschrieben.
    """
    from datetime import datetime

    now = utcnow_naive_iso()
    body = body or {}
    if not tenant_id:
        raise ValueError('tenant is required to provision a profile')
    # Gate 12 (Profile v1): NUR diese Felder; userId/tenantId/email aus JWT
    # (Body-Identitaeten werden IGNORIERT — kein Spoofing).
    item = {
        'userId': user_context['userId'],
        'tenantId': tenant_id,
        'nickname': body.get('nickname'),
        'firstName': body.get('firstName'),
        'lastName': body.get('lastName'),
        'email': user_context.get('email'),
        'schemaVersion': 1,
        'status': 'active',
        'createdAt': now,
        'updatedAt': now,
        'version': 1,
    }
    try:
        if freeze_context:
            from jobsearch.partner_profile_repository import serializer
            _user_profile_transact(table.name, freeze_context, {"Put": {
                "Item": {key: serializer(value) for key, value in item.items()},
                "ConditionExpression": "attribute_not_exists(userId)",
            }})
        else:
            table.put_item(Item=item, ConditionExpression='attribute_not_exists(userId)')
    except _UserProfileMutationConflict:
        return {'statusCode': 409, 'body': json.dumps({'error': 'Profile already exists'})}
    except Exception as e:
        if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == \
                'ConditionalCheckFailedException':
            return {'statusCode': 409, 'body': json.dumps({'error': 'Profile already exists'})}
        raise
    return {'statusCode': 201, 'body': json.dumps(_canonical_user_profile(item))}


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

    # L03: Tenant serverseitig aufloesen (Claim autoritativ, sonst
    # Registry). Ohne aufloesbaren Tenant wird kein Profil geschrieben.
    tenant_id, tenant_conflict = _resolve_tenant(user_context)
    if tenant_conflict or not tenant_id:
        logger.warning("profile create denied: tenant not resolvable")
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Tenant not resolvable'})
        }

    try:
        freeze_context = _user_profile_freeze_context(
            event, user_context, tenant_id)
        table = _get_dynamodb().Table(table_name)
        return _provision_user_profile(table, user_context, body,
                                       tenant_id=tenant_id,
                                       freeze_context=freeze_context)
    except ValueError as e:
        logger.warning(f"Profile provisioning refused: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid request'})
        }
    except _WriteFreezeUnavailable:
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Write freeze unavailable'})
        }
    except Exception as e:
        logger.error(f"Error provisioning profile: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to provision profile'})
        }


def _update_user_profile(table: Any, user_context: Dict[str, Any],
                         body: Dict[str, Any], expected_version: int,
                         tenant_id: str,
                         freeze_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Atomically PATCH UserProfileV1 with an optimistic-lock condition.

    A missing legacy ``version`` is treated as version 1 only inside the
    conditional update. The same write sets version 2, so no unprotected
    read-then-write migration exists. A successful update increments exactly
    once; a stale token cannot overwrite a newer row.
    """
    body = body or {}
    allowed = {'nickname', 'firstName', 'lastName', 'expectedVersion'}
    unknown = set(body) - allowed
    if unknown:
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid profile fields'})}

    updates = {}
    for key in ('nickname', 'firstName', 'lastName'):
        if key in body:
            value = body[key]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid profile fields'})}
            updates[key] = value.strip() if isinstance(value, str) else None
    if not updates:
        return {'statusCode': 400,
                'body': json.dumps({'error': 'No updatable v1 fields provided'})}

    updates['updatedAt'] = utcnow_naive_iso()
    updates['version'] = expected_version + 1
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
    names = {f"#{k}": k for k in updates}
    names.update({'#userId': 'userId', '#tenantId': 'tenantId'})
    values = {f":{k}": v for k, v in updates.items()}
    values.update({':tenantId': tenant_id, ':expectedVersion': expected_version})
    condition = (
        'attribute_exists(#userId) AND #tenantId = :tenantId AND '
        '(attribute_not_exists(#version) OR #version = :expectedVersion)'
    )
    names['#version'] = 'version'
    try:
        if freeze_context:
            from jobsearch.partner_profile_repository import serializer
            _user_profile_transact(table.name, freeze_context, {"Update": {
                "Key": {"userId": serializer(user_context['userId'])},
                "UpdateExpression": expr,
                "ConditionExpression": condition,
                "ExpressionAttributeNames": names,
                "ExpressionAttributeValues": {
                    key: serializer(value) for key, value in values.items()},
            }})
            result = table.get_item(
                Key={'userId': user_context['userId']}, ConsistentRead=True)
        else:
            result = table.update_item(
                Key={'userId': user_context['userId']},
                UpdateExpression=expr,
                ConditionExpression=condition,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues='ALL_NEW',
            )
    except Exception as e:
        if isinstance(e, _UserProfileMutationConflict):
            current = table.get_item(Key={'userId': user_context['userId']}).get('Item')
            if not current or current.get('tenantId') != tenant_id:
                return {'statusCode': 404, 'body': json.dumps({'error': 'Profile not found'})}
            return {'statusCode': 409, 'body': json.dumps({'error': 'Version conflict'})}
        if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == \
                'ConditionalCheckFailedException':
            # Classification read is only after the failed conditional write;
            # it is never used to authorize or perform a migration.
            current = table.get_item(Key={'userId': user_context['userId']}).get('Item')
            if not current or current.get('tenantId') != tenant_id:
                return {'statusCode': 404, 'body': json.dumps({'error': 'Profile not found'})}
            return {'statusCode': 409, 'body': json.dumps({'error': 'Version conflict'})}
        raise
    return {'statusCode': 200,
            'body': json.dumps(_canonical_user_profile(result.get('Attributes', {})))}


def _handle_me_profile_update(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle PATCH (and legacy PUT) /me/profile with optimistic locking."""
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
    if not isinstance(body, dict):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Request body must be an object'})
        }

    # Resolve authorization context before interpreting optimistic-lock
    # tokens, so an unauthorizable caller cannot learn route semantics.
    tenant_id, tenant_conflict = _resolve_tenant(user_context)
    if tenant_conflict or not tenant_id:
        logger.warning("profile update denied: tenant not resolvable")
        return {
            'statusCode': 403,
            'body': json.dumps({'error': 'Tenant not resolvable'})
        }

    headers = event.get('headers') or {}
    if_match = next((value for key, value in headers.items()
                     if str(key).lower() == 'if-match'), None)
    try:
        from jobsearch.partner_profile_contract import (
            ProfileContractError, parse_expected_version)
        expected_version = parse_expected_version(body, if_match)
    except ProfileContractError as exc:
        status = 428 if exc.code == 'MISSING_FIELD' else 400
        return {
            'statusCode': status,
            'body': json.dumps({'error': str(exc)})
        }

    table_name = os.environ.get('USER_PROFILE_TABLE')
    if not table_name:
        logger.warning("USER_PROFILE_TABLE not configured")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Profile store not configured'})
        }

    try:
        freeze_context = _user_profile_freeze_context(
            event, user_context, tenant_id)
        table = _get_dynamodb().Table(table_name)
        return _update_user_profile(table, user_context, body,
                                    expected_version=expected_version,
                                    tenant_id=tenant_id,
                                    freeze_context=freeze_context)
    except _WriteFreezeUnavailable:
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Write freeze unavailable'})
        }
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
        freeze_context = None
        if os.environ.get("ERASURE_WRITE_FREEZE_ENABLED", "false").strip().lower() == "true":
            delete_tenant, delete_conflict = _resolve_tenant(user_context)
            if delete_conflict or not delete_tenant:
                return {'statusCode': 403,
                        'body': json.dumps({'error': 'Tenant not resolvable'})}
            freeze_context = _user_profile_freeze_context(
                event, user_context, delete_tenant)
        table = _get_dynamodb().Table(table_name)
        # Delete with conditional check to ensure profile exists
        try:
            if freeze_context:
                from jobsearch.partner_profile_repository import serializer
                _user_profile_transact(table.name, freeze_context, {"Delete": {
                    "Key": {"userId": serializer(user_context['userId'])},
                    "ConditionExpression": "attribute_exists(userId)",
                }})
            else:
                table.delete_item(
                    Key={'userId': user_context['userId']},
                    ConditionExpression='attribute_exists(userId)'
                )
            return {
                'statusCode': 204,
                'body': ''
            }
        except _UserProfileMutationConflict:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Profile not found'})
            }
        except Exception as e:
            if hasattr(e, 'response') and e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': 'Profile not found'})
                }
            raise
    except _WriteFreezeUnavailable:
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Write freeze unavailable'})
        }
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
        from agents.ecosystem.privacy_erasure import (
            PrivacyErasure, ErasureExecutionUnavailable)
        from agents.ecosystem.privacy_application_erasure import ApplicationErasureExecutor
        from agents.ecosystem.partner_registry import resolve_partner_application
        from jobsearch.application_contract import ApplicationContext
        from jobsearch.application_repository import ApplicationRepository
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
        ("APPLICATIONS_TABLE", "APPLICATIONS_TABLE"),
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
    partner_application_id = user_context.get('partnerApplicationId')
    issuer = user_context.get('issuer')
    application_context = None
    if partner_application_id and issuer and user_context.get('tenantId'):
        registry = resolve_partner_application(
            user_context.get('clientId'))
        if (not registry or registry.get('status') != 'ACTIVE'
                or registry.get('applicationId') != partner_application_id
                or registry.get('tenantId') != user_context.get('tenantId')):
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Erasure authorization context invalid'})
            }
        application_context = ApplicationContext(
            user_context['userId'], user_context['tenantId'],
            partner_application_id, issuer)
    application_repository = ApplicationRepository(
        table_name=os.environ.get("APPLICATIONS_TABLE"), dynamodb=dynamodb)
    erasure = PrivacyErasure(
        credential_store=DynamoDBCredentialStore(
            table_name=os.environ.get("CREDENTIALS_TABLE")),
        profile_store=DynamoDBApiProfileStore(
            table_name=os.environ.get("API_PROFILES_TABLE")),
        work_table=dynamodb.Table(os.environ.get("WORK_ITEMS_TABLE")),
        document_deleter=_delete_documents,
        user_profile_table=dynamodb.Table(
            os.environ.get("USER_PROFILE_TABLE")),
        application_erasure=ApplicationErasureExecutor(application_repository),
        application_context=application_context,
    )

    try:
        result = erasure.erase(user_context['userId'],
                               tenant_id=user_context.get('tenantId'))
    except ErasureExecutionUnavailable:
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Erasure execution unavailable'})
        }
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
    """Authenticated, server-resolved document ownership context.

    Legacy document routes used to pass a missing tenant through to the
    storage helper, which then selected ``tenant/default``. Resolve the
    tenant from verified JWT/registry context before any S3 operation and
    fail closed when it cannot be resolved.
    """
    user_context = _extract_user_context(event)
    if not user_context.get('userId'):
        return None
    tenant_id, conflict = _resolve_tenant(user_context)
    if conflict or not tenant_id:
        user_context['_documentContextError'] = 'Tenant not resolvable'
        return user_context
    user_context['tenantId'] = tenant_id
    return user_context


def _handle_documents_create(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle POST /me/documents - kurzlebige Upload-Berechtigung (Gate 14)."""
    from documents import presign_upload

    # This legacy issuer has no CV reference or partner issuer context and is
    # therefore not representable in UploadTicketLedgerV1.  Once cutover or
    # ledger enforcement is enabled, fail closed rather than minting an
    # untracked presigned upload ticket.
    if (os.environ.get('ERASURE_UPLOAD_TICKET_LEDGER_ENABLED', 'false').strip().lower() == 'true'
            or os.environ.get('ERASURE_UPLOAD_CUTOVER_ENABLED', 'false').strip().lower() == 'true'):
        return {'statusCode': 503,
                'body': json.dumps({'error': 'Upload ticket ledger unavailable'})}

    user_context = _documents_context(event)
    if user_context is None:
        return {'statusCode': 401, 'body': json.dumps({'error': 'Unauthenticated'})}
    if user_context.get('_documentContextError'):
        return {'statusCode': 403, 'body': json.dumps({'error': 'Tenant not resolvable'})}
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
            require_tenant=True,
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
    if user_context.get('_documentContextError'):
        return {'statusCode': 403, 'body': json.dumps({'error': 'Tenant not resolvable'})}
    try:
        result = presign_download(
            tenant_id=user_context.get('tenantId'),
            user_id=user_context['userId'],
            doc_id=doc_id,
            require_tenant=True,
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
    if user_context.get('_documentContextError'):
        return {'statusCode': 403, 'body': json.dumps({'error': 'Tenant not resolvable'})}
    try:
        deleted = delete_document(
            tenant_id=user_context.get('tenantId'),
            user_id=user_context['userId'],
            doc_id=doc_id,
            require_tenant=True,
        )
    except ValueError:
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid document ID'})}
    except Exception as e:
        logger.error(f"Error deleting document: {type(e).__name__}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Failed to delete document'})}
    if not deleted:
        return {'statusCode': 404, 'body': json.dumps({'error': 'Document not found'})}
    return {'statusCode': 200, 'body': json.dumps({'deleted': True, 'documentId': doc_id})}


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


def _partner_boundary_error(status_code, error):
    """Flat dual-auth error with a stable adapter-facing category."""
    code = {401: 'unauthorized', 403: 'forbidden', 503: 'unavailable'}.get(
        status_code, 'internal_error')
    return {'statusCode': status_code,
            'body': json.dumps({'error': error, 'code': code})}


def _partner_execute_agent(event: Dict[str, Any], agent_id: Optional[str]) -> Dict[str, Any]:
    """Partner user dual-auth execution.

    Route: POST /v1/partner/agents/{agentId}/execute
    Requires human Cognito JWT + RIS API Credential.
    Multi-user partner application: credential owner is admin, JWT user is end user.
    """
    from agents.ecosystem.credentials import (
        CredentialStoreUnavailable,
        VerifyOutcome,
        resolve_credential_profile,
    )
    from agents.ecosystem.worker_authorization import check_worker_entitlement
    from agents.ecosystem.partner_registry import resolve_partner_application

    headers = {(k or "").lower(): v for k, v in (event.get("headers") or {}).items()}

    cognito_context, cognito_error = _machine_cognito_context(event)
    if cognito_error:
        return _machine_deny(cognito_error, 'Unauthorized')

    # Enforce token_use = access, reject ID tokens
    if cognito_context.get('tokenUse') != 'access':
        return _machine_deny(401, 'Unauthorized')

    bearer, header_error = _machine_bearer(headers)
    if header_error:
        return _machine_deny(header_error, 'Unauthorized')

    if not agent_id:
        return _machine_deny(401, 'Unauthorized')

    http_ctx = ((event.get('requestContext') or {}).get('http') or {})
    path = event.get('path') or http_ctx.get('path', '/')
    request_id = ((event.get('requestContext') or {}).get('requestId') or event.get('requestId'))
    route_name = 'POST /v1/partner/agents/{agentId}/execute'

    try:
        sources = _build_introspection_sources()
    except Exception:
        return {'statusCode': 503, 'body': json.dumps({'error': 'Service unavailable'})}

    # Validate credential and profile
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        meta, profile = resolve_credential_profile(
            bearer=bearer,
            credential_store=sources["credential_store"],
            profile_store=sources["profile_store"],
            now=now,
            base={"route": route_name, "request": request_id}
        )
    except Exception as exc:
        # resolve_credential_profile raises _Denied for auth failures
        # For brevity map all to 401/403 via existing patterns
        from agents.ecosystem.credentials import _Denied
        if isinstance(exc, _Denied):
            return _machine_deny(401 if exc.outcome is VerifyOutcome.UNAUTHORIZED else 403, 'Forbidden')
        raise

    # Partner Registry binding: JWT client_id -> Partner Application -> APIProfile/Tenant
    client_id = cognito_context.get('clientId')
    if not client_id:
        return _machine_deny(401, 'Unauthorized')
    try:
        registry = resolve_partner_application(client_id)
    except Exception:
        return _machine_deny(403, 'Forbidden')
    if not registry or registry.get('status') != 'ACTIVE':
        return _machine_deny(403, 'Forbidden')
    reg_api_profile_id = registry.get('apiProfileId')
    reg_tenant_id = registry.get('tenantId')
    cred_api_profile_id = meta.get('apiProfileId')
    cred_tenant_id = meta.get('tenantId')
    if not reg_api_profile_id or reg_api_profile_id != cred_api_profile_id:
        return _machine_deny(403, 'Forbidden')
    if not reg_tenant_id or reg_tenant_id != cred_tenant_id:
        return _machine_deny(403, 'Forbidden')

    # Tenant isolation (L03): the tenant is resolved SERVER-SIDE from the
    # credential and the partner registry (both are cross-checked above:
    # registry.apiProfileId == credential.apiProfileId and
    # registry.tenantId == credential.tenantId).
    #
    # The `custom:tenant_id` claim stays authoritative WHEN IT IS PRESENT:
    # a claim that contradicts the resolved tenant is a cross-tenant
    # attempt -> deny. A MISSING claim is not a failure: the tenant comes
    # from the server, never from the browser (a self-signup user has no
    # tenant claim; refusing them would make the partner route unusable
    # without weakening anything).
    resolved_tenant, tenant_conflict = _resolve_tenant(
        cognito_context, expected_tenant=cred_tenant_id)
    if tenant_conflict or not resolved_tenant:
        logger.warning("partner execution denied: tenant mismatch "
                       "client_id=%s", client_id)
        return _machine_deny(403, 'Forbidden')
    jwt_tenant = resolved_tenant

    # Entitlement check for JWT user, not credential owner
    jwt_user_id = cognito_context.get('userId')
    if not jwt_user_id:
        return _machine_deny(401, 'Unauthorized')

    try:
        auth = check_worker_entitlement(
            user_id=jwt_user_id,
            tenant_id=jwt_tenant,
            agent_id=agent_id,
            work_id=request_id,
            request_time=now,
            resolver=sources["entitlement_resolver"],
            api_profile_id=meta.get("apiProfileId"),
        )
    except Exception:
        return {'statusCode': 503, 'body': json.dumps({'error': 'Service unavailable'})}

    if not auth.authorized:
        return _machine_deny(403, 'Forbidden')

    # Agent catalog executable check
    catalog = sources["catalog"]
    if catalog is None:
        return {'statusCode': 500, 'body': json.dumps({'error': 'Catalog unavailable'})}
    from agents.ecosystem.agent_status import is_executable_status
    raw_status = catalog.get(agent_id)
    if isinstance(raw_status, dict):
        raw_status = raw_status.get("status")
    if not is_executable_status(raw_status):
        return _machine_deny(403, 'Forbidden')

    context = {
        "userId": jwt_user_id,
        "tenantId": jwt_tenant,
        "apiProfileId": meta.get("apiProfileId"),
        "credentialId": meta.get("credentialId"),
    }
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
            idempotency_key=data.get('idempotencyKey'),
            partner_application_id=context.get('partnerApplicationId'),
            issuer=context.get('issuer'))
    except Exception:
        return {'statusCode': 500, 'body': json.dumps({'error': 'Failed to create work item'})}

    return {
        'statusCode': 202,
        'body': json.dumps({
            'workId': out['workId'],
            'status': out['status'],
            'requestId': out['requestId']
        })
    }


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
    from agents.ecosystem.partner_registry import resolve_partner_application

    headers = {(k or "").lower(): v
               for k, v in (event.get("headers") or {}).items()}

    # Boundary 1 outcome: no Cognito identity means the request did not come
    # through the gateway authorizer. Deny before touching any store.
    cognito_context, cognito_error = _machine_cognito_context(event)
    if cognito_error:
        return _machine_deny(cognito_error, 'Unauthorized')

    # token_use is mandatory here too. The gateway authorizer pins audience and
    # requires the m2m/execute scope, but the in-Lambda check must stand on its
    # own: an ID token or a token with no token_use claim must never reach the
    # registry binding or the execution contract.
    if cognito_context.get('tokenUse') != 'access':
        return _machine_deny(401, 'Unauthorized')

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

    # Phase 3 binding: enforce Cognito M2M client -> Partner Application -> APIProfile
    client_id = cognito_context.get('clientId')
    if not client_id:
        logger.warning("machine execution denied: missing client_id")
        return _machine_deny(401, 'Unauthorized')
    try:
        registry = resolve_partner_application(client_id)
    except Exception:
        # Never surface a registry infrastructure failure as a 5xx on the
        # authorization path: fail closed with a neutral 403.
        logger.warning("machine execution denied: registry lookup failed")
        return _machine_deny(403, 'Forbidden')
    if not registry or registry.get('status') != 'ACTIVE':
        logger.warning("machine execution denied: inactive or unknown application client_id=%s", client_id)
        return _machine_deny(403, 'Forbidden')
    context = decision.context or {}
    # Verify tenant and APIProfile binding server-side, never trust caller
    # supplied values. There is deliberately NO environment-variable escape
    # hatch here: a bypass reachable from Lambda configuration would defeat
    # the whole point of the registry. Tests must inject a stubbed
    # `resolve_partner_application` instead.
    reg_api_profile = registry.get('apiProfileId')
    reg_tenant = registry.get('tenantId')
    if not reg_api_profile or reg_api_profile != context.get('apiProfileId'):
        logger.warning("machine execution denied: apiProfile binding mismatch client_id=%s",
                       client_id)
        return _machine_deny(403, 'Forbidden')
    if not reg_tenant or reg_tenant != context.get('tenantId'):
        logger.warning("machine execution denied: tenant binding mismatch client_id=%s",
                       client_id)
        return _machine_deny(403, 'Forbidden')

    # Authorized. The credential's own persisted tenant/owner context is the
    # execution subject — never anything from the header or the body.
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
            idempotency_key=data.get('idempotencyKey'),
            partner_application_id=context.get('partnerApplicationId'),
            issuer=context.get('issuer'))
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
                        idempotency_key: Optional[str] = None,
                        partner_application_id: Optional[str] = None,
                        issuer: Optional[str] = None
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
        'partnerApplicationId': partner_application_id or '',
        'issuer': issuer or '',
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
    if not table_name:
        raise RuntimeError("durable subject fence store is not configured")
    if not user_id or not tenant_id:
        raise RuntimeError("verified subject and tenant are required for work admission")
    table = _get_dynamodb().Table(table_name)
    from agents.runtime.pipeline import _ddb_client_item
    from agents.runtime.subject_fence import subject_fence_key
    client = getattr(getattr(table, "meta", None), "client", None)
    if client is None:
        raise RuntimeError("durable subject fence transaction unavailable")
    client.transact_write_items(TransactItems=[
            {"ConditionCheck": {
                "TableName": table_name,
                "Key": {"workId": {"S": subject_fence_key(
                    user_id=user_id or "", tenant_id=tenant_id or "",
                    partner_application_id=partner_application_id or "",
                    issuer=issuer or "")}},
                "ConditionExpression": "attribute_not_exists(workId)",
            }},
            {"Put": {
                "TableName": table_name,
                "Item": _ddb_client_item(work_item),
                "ConditionExpression": "attribute_not_exists(workId)",
            }},
    ])

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
            idempotency_key=body.get('idempotencyKey'),
            partner_application_id=user_context.get('partnerApplicationId'),
            issuer=user_context.get('issuer'))
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
    work_table = _get_dynamodb().Table(os.environ.get("WORK_ITEMS_TABLE"))
    outcome = process_record(
        {'body': work_item},
        entitlement_resolver=DynamoDBEntitlementResolver(),
        subject_fence_table=work_table,
        require_subject_fence=True)

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


# ---------------------------------------------------------------------------
# R03: Partner manual search profile CRUD
#
#   GET    /v1/partner/me/manual-search-profiles
#   POST   /v1/partner/me/manual-search-profiles
#   GET    /v1/partner/me/manual-search-profiles/{profileId}
#   PUT    /v1/partner/me/manual-search-profiles/{profileId}
#   DELETE /v1/partner/me/manual-search-profiles/{profileId}
#
# Minimal storage scope: authenticated human user + ACTIVE RIS
# credential/profile + ACTIVE partner application (registry binding).
# Agent entitlements are NOT reused as a storage permission. Storing,
# loading or deleting a profile never enqueues work and never calls a model.
# ---------------------------------------------------------------------------

_MANUAL_PROFILE_COLLECTION = '/v1/partner/me/manual-search-profiles'
_MANUAL_PROFILE_PAGE_LIMIT = 50


def _partner_profile_context(event: Dict[str, Any]):
    """Resolve the authenticated partner/user context for profile storage.

    Returns ``(context, None)`` on success or ``(None, error_response)``.
    Reuses the existing partner dual-auth boundary; nothing new is invented.
    """
    from agents.ecosystem.credentials import (
        CredentialStoreUnavailable,
        VerifyOutcome,
        _Denied,
        resolve_credential_profile,
        valid_secret_format,
    )
    from agents.ecosystem.partner_registry import resolve_partner_application

    headers = {(k or "").lower(): v for k, v in (event.get("headers") or {}).items()}

    cognito_context, cognito_error = _machine_cognito_context(event)
    if cognito_error:
        return None, _partner_boundary_error(401, 'Unauthorized')
    if cognito_context.get('tokenUse') != 'access':
        return None, _partner_boundary_error(401, 'Unauthorized')

    bearer, header_error = _machine_bearer(headers)
    if header_error:
        return None, _partner_boundary_error(401, 'Unauthorized')

    # The shared credential contract rejects malformed values before any
    # store lookup. Keep that ordering at the HTTP boundary as well: a bad
    # shape is a client denial (401), while an unavailable configured store
    # remains a truthful 503 for structurally valid credentials.
    if not valid_secret_format(bearer):
        return None, _partner_boundary_error(401, 'Unauthorized')

    try:
        sources = _build_introspection_sources()
    except Exception:
        return None, {'statusCode': 503,
                      'body': json.dumps({'error': 'Service unavailable',
                                          'code': 'unavailable'})}

    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        meta, _profile = resolve_credential_profile(
            bearer=bearer,
            credential_store=sources["credential_store"],
            profile_store=sources["profile_store"],
            now=now,
            base={"route": "partner-manual-profile"},
        )
    except CredentialStoreUnavailable:
        return None, {'statusCode': 503,
                      'body': json.dumps({'error': 'Service unavailable',
                                          'code': 'unavailable'})}
    except _Denied as exc:
        status = 401 if exc.outcome is VerifyOutcome.UNAUTHORIZED else 403
        return None, _partner_boundary_error(
            status, 'Unauthorized' if status == 401 else 'Forbidden')

    client_id = cognito_context.get('clientId')
    if not client_id:
        return None, _partner_boundary_error(401, 'Unauthorized')
    try:
        registry = resolve_partner_application(client_id)
    except Exception:
        return None, _partner_boundary_error(403, 'Forbidden')
    if not registry or registry.get('status') != 'ACTIVE':
        return None, _partner_boundary_error(403, 'Forbidden')
    if registry.get('apiProfileId') != meta.get('apiProfileId'):
        return None, _partner_boundary_error(403, 'Forbidden')
    if registry.get('tenantId') != meta.get('tenantId'):
        return None, _partner_boundary_error(403, 'Forbidden')

    resolved_tenant, tenant_conflict = _resolve_tenant(
        cognito_context, expected_tenant=meta.get('tenantId'))
    if tenant_conflict or not resolved_tenant:
        return None, _partner_boundary_error(403, 'Forbidden')

    jwt_user_id = cognito_context.get('userId')
    if not jwt_user_id:
        return None, _partner_boundary_error(401, 'Unauthorized')

    claims = (((event.get('requestContext') or {}).get('authorizer') or {})
              .get('jwt') or {}).get('claims') or {}
    issuer = claims.get('iss')
    if not issuer:
        return None, _partner_boundary_error(401, 'Unauthorized')

    return {
        'userId': jwt_user_id,
        'tenantId': resolved_tenant,
        'partnerApplicationId': registry.get('applicationId'),
        'apiProfileId': meta.get('apiProfileId'),
        'credentialId': meta.get('credentialId'),
        'issuer': issuer,
    }, None


_PRIVACY_INSPECT_ROUTE = '/v1/partner/me/privacy/inspect'
_PRIVACY_INSPECT_LIMIT = 50
_PRIVACY_INSPECT_SCOPE = 'privacy-inspect'


class _PrivacyInspectionUnavailable(Exception):
    """A storage domain could not be inspected without claiming it is empty."""


def _privacy_inspection_page(event, *, repo, ctx, resource_type, serializer,
                             query_name, limit):
    """Read one complete, identity-bound page from the profile GSI."""
    raw_cursor = (event.get('queryStringParameters') or {}).get(query_name)
    cursor = _decode_cursor(
        raw_cursor, repo=repo, ctx=ctx, scope=_PRIVACY_INSPECT_SCOPE,
        resource_type=resource_type, limit=limit)
    if cursor == 'invalid':
        raise ValueError('Invalid privacy inspection cursor')
    if not getattr(repo, 'table_name', None) or getattr(repo, 'table', None) is None:
        raise _PrivacyInspectionUnavailable('Profile storage is unavailable')
    items, next_cursor = repo.list_by_user(
        ctx['userId'], ctx['tenantId'], resource_type=resource_type,
        partner_app_id=ctx.get('partnerApplicationId'),
        issuer=ctx.get('issuer'), limit=limit, cursor=cursor)
    return {
        'items': [serializer(item) for item in items],
        'nextCursor': _encode_cursor(
            next_cursor, repo=repo, ctx=ctx, scope=_PRIVACY_INSPECT_SCOPE,
            resource_type=resource_type, limit=limit),
    }


def _privacy_category(*, name, purpose, storage_status, retention_ref,
                      page=None, status='COMPLETE', code=None):
    result = {
        'status': status,
        'dataCategory': name,
        'processingPurpose': purpose,
        'storageStatus': storage_status,
        'retentionPolicyRef': retention_ref,
        'items': (page or {}).get('items', []),
        'nextCursor': (page or {}).get('nextCursor'),
    }
    if code:
        result['code'] = code
    return result


def _privacy_read_user_profile(ctx):
    table_name = os.environ.get('USER_PROFILE_TABLE')
    if not table_name:
        raise _PrivacyInspectionUnavailable('User profile storage is unavailable')
    try:
        table = _get_dynamodb().Table(table_name)
        response = table.get_item(Key={'userId': ctx['userId']},
                                  ConsistentRead=True)
    except Exception as exc:
        raise _PrivacyInspectionUnavailable(
            'User profile storage is unavailable') from exc
    item = response.get('Item')
    if item is None:
        return None
    if item.get('tenantId') != ctx['tenantId']:
        raise _PrivacyInspectionUnavailable('User profile storage is unavailable')
    return _canonical_user_profile(item)


def _privacy_receipt_page(event, ctx, limit):
    from agents.ecosystem.privacy_receipt import PrivacyContextV1
    from agents.ecosystem.privacy_receipt_journal import (
        PrivacyReceiptJournal, PrivacyReceiptJournalDisabled,
        PrivacyReceiptInvalidCursor, PrivacyReceiptStorageError,
    )
    context = PrivacyContextV1(
        user_id=ctx['userId'], tenant_id=ctx['tenantId'],
        partner_application_id=ctx['partnerApplicationId'],
        issuer=ctx['issuer'])
    raw_cursor = (event.get('queryStringParameters') or {}).get('receiptsCursor')
    try:
        receipts, next_cursor = PrivacyReceiptJournal().list_receipts(
            context, cursor=raw_cursor, limit=limit)
    except PrivacyReceiptInvalidCursor as exc:
        raise ValueError('Invalid privacy inspection cursor') from exc
    except (PrivacyReceiptJournalDisabled, PrivacyReceiptStorageError) as exc:
        raise _PrivacyInspectionUnavailable(
            'Privacy receipt storage is unavailable') from exc
    return {
        'items': [receipt.to_dict() for receipt in receipts],
        'nextCursor': next_cursor,
    }


def _handle_privacy_inspect(event, context):
    """Read-only, self-scoped inventory of RIS user data.

    Each resource domain has its own secure cursor. A missing or failing store
    is returned as UNAVAILABLE/PARTIAL, never as an empty successful list.
    """
    ctx, error = _partner_profile_context(event)
    if error:
        return error
    params = event.get('queryStringParameters') or {}
    try:
        limit = int(params.get('limit', _PRIVACY_INSPECT_LIMIT))
    except (TypeError, ValueError):
        return _cv_error(422, 'Invalid inspection limit')
    if limit < 1 or limit > _PRIVACY_INSPECT_LIMIT:
        return _cv_error(422, 'Invalid inspection limit')

    categories = {}
    unavailable = False
    try:
        profile = _privacy_read_user_profile(ctx)
        categories['userProfile'] = _privacy_category(
            name='user_profile', purpose='account/profile management',
            storage_status='stored' if profile else 'no_data',
            retention_ref='RIS-JOBSEARCH-RETENTION-POLICY-V1#user-profile',
            page={'items': [profile] if profile else [], 'nextCursor': None})
    except _PrivacyInspectionUnavailable:
        unavailable = True
        categories['userProfile'] = _privacy_category(
            name='user_profile', purpose='account/profile management',
            storage_status='unavailable',
            retention_ref='RIS-JOBSEARCH-RETENTION-POLICY-V1#user-profile',
            status='UNAVAILABLE', code='unavailable')

    repo = _manual_profile_repo()
    profile_pages = (
        ('cvDocuments', 'CVDocument', _serialize_cv, 'cvCursor',
         'cv document metadata', 'RIS-JOBSEARCH-RETENTION-POLICY-V1#cv-metadata'),
        ('manualSearchProfiles', 'ManualSearchProfile', _serialize_manual_profile,
         'manualCursor', 'manual search configuration',
         'RIS-JOBSEARCH-RETENTION-POLICY-V1#manual-search-profile'),
        ('cvSearchProfiles', 'CVSearchProfile', _serialize_cv_search_profile,
         'cvSearchCursor', 'CV-derived search configuration',
         'RIS-JOBSEARCH-RETENTION-POLICY-V1#cv-search-profile'),
        ('atsSearchProfiles', 'ATSSearchProfile', _serialize_ats_profile,
         'atsCursor', 'ATS search configuration',
         'RIS-JOBSEARCH-RETENTION-POLICY-V1#ats-search-profile'),
    )
    for key, resource_type, serializer, query_name, purpose, retention_ref in profile_pages:
        try:
            page = _privacy_inspection_page(
                event, repo=repo, ctx=ctx, resource_type=resource_type,
                serializer=serializer, query_name=query_name, limit=limit)
            categories[key] = _privacy_category(
                name=resource_type, purpose=purpose,
                storage_status=('stored' if page['items'] or page['nextCursor']
                                else 'no_data'),
                retention_ref=retention_ref, page=page)
        except ValueError:
            return _cv_error(400, 'Invalid privacy inspection cursor')
        except _PrivacyInspectionUnavailable:
            unavailable = True
            categories[key] = _privacy_category(
                name=resource_type, purpose=purpose, storage_status='unavailable',
                retention_ref=retention_ref, status='UNAVAILABLE',
                code='unavailable')
        except Exception:
            logger.error('privacy inspection profile domain unavailable')
            unavailable = True
            categories[key] = _privacy_category(
                name=resource_type, purpose=purpose, storage_status='unavailable',
                retention_ref=retention_ref, status='UNAVAILABLE',
                code='unavailable')

    try:
        from jobsearch.application_repository import ApplicationRepository
        app_repo = ApplicationRepository()
        app_ctx = __import__('jobsearch.application_contract', fromlist=['ApplicationContext']).ApplicationContext(
            ctx['userId'], ctx['tenantId'], ctx['partnerApplicationId'], ctx['issuer'])
        app_page = []
        app_cursor = None
        while True:
            page, app_cursor = app_repo.list(app_ctx, limit=limit, cursor=app_cursor)
            app_page.extend(page)
            if not app_cursor:
                break
        categories['applications'] = _privacy_category(
            name='ApplicationV1', purpose='authenticated application tracking',
            storage_status='stored' if app_page else 'no_data',
            retention_ref='RIS-APPLICATION-V1-RETENTION-DECISION#APPROVAL_REQUIRED',
            page={'items': app_page, 'nextCursor': None})
    except Exception:
        logger.error('privacy inspection application domain unavailable')
        unavailable = True
        categories['applications'] = _privacy_category(
            name='ApplicationV1', purpose='authenticated application tracking',
            storage_status='unavailable',
            retention_ref='RIS-APPLICATION-V1-RETENTION-DECISION#APPROVAL_REQUIRED',
            status='UNAVAILABLE', code='unavailable')
    try:
        receipt_page = _privacy_receipt_page(event, ctx, limit)
        categories['privacyReceipts'] = _privacy_category(
            name='privacy_receipt', purpose='privacy evidence retrieval',
            storage_status='stored', retention_ref=(
                'RIS-PRIVACY-RECEIPT-RETENTION-DECISION#REVIEW_REQUIRED'),
            page=receipt_page)
    except ValueError:
        return _cv_error(400, 'Invalid privacy inspection cursor')
    except _PrivacyInspectionUnavailable:
        unavailable = True
        categories['privacyReceipts'] = _privacy_category(
            name='privacy_receipt', purpose='privacy evidence retrieval',
            storage_status='unavailable', retention_ref=(
                'RIS-PRIVACY-RECEIPT-RETENTION-DECISION#REVIEW_REQUIRED'),
            status='UNAVAILABLE', code='unavailable')

    payload = {
        'schemaVersion': 1,
        'status': 'PARTIAL' if unavailable else 'COMPLETE',
        'userId': ctx['userId'],
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'categories': categories,
    }
    return {'statusCode': 200, 'body': json.dumps(payload, ensure_ascii=False)}


def _privacy_export_collect(event, *, repo, ctx, resource_type, serializer,
                            query_name, limit):
    """Collect every page for one profile category using scoped cursors."""
    items = []
    cursor = None
    seen = set()
    while True:
        if cursor in seen:
            raise _PrivacyInspectionUnavailable('Cursor did not advance')
        if cursor:
            seen.add(cursor)
        page_event = {'queryStringParameters': {
            query_name: cursor} if cursor else {}}
        page = _privacy_inspection_page(
            page_event, repo=repo, ctx=ctx, resource_type=resource_type,
            serializer=serializer, query_name=query_name, limit=limit)
        items.extend(page['items'])
        cursor = page['nextCursor']
        if cursor is None:
            return items


def _privacy_export_category(*, name, purpose, storage_status,
                             retention_ref, items=None, status='COMPLETE',
                             code=None):
    result = {
        'status': status,
        'dataCategory': name,
        'processingPurpose': purpose,
        'storageStatus': storage_status,
        'retentionPolicyRef': retention_ref,
        'items': items or [],
    }
    if code:
        result['code'] = code
    return result


def _privacy_file_export(cv_items):
    """Describe secure, on-demand file retrieval without exporting URLs."""
    files = []
    for cv in cv_items:
        if cv.get('processingStatus') != 'ready' or not cv.get('documentId'):
            continue
        cv_id = cv.get('cvId')
        files.append({
            'cvId': cv_id,
            'documentId': cv['documentId'],
            'downloadEndpoint': '/v1/partner/me/cvs/%s/document' % cv_id,
            'access': 'short-lived-secure-download-ticket',
        })
    return {
        'status': 'NOT_INCLUDED',
        'complete': False,
        'items': files,
        'reason': 'File contents are not embedded; request an authorized '
                  'short-lived download ticket per document.',
    }


def _privacy_export_receipts(event, ctx, limit):
    """Collect all authorized receipt pages, if the journal is available."""
    items = []
    cursor = None
    seen = set()
    while True:
        if cursor in seen:
            raise _PrivacyInspectionUnavailable('Receipt cursor did not advance')
        if cursor:
            seen.add(cursor)
        page_event = {'queryStringParameters': {
            'receiptsCursor': cursor} if cursor else {}}
        page = _privacy_receipt_page(page_event, ctx, limit)
        items.extend(page['items'])
        cursor = page['nextCursor']
        if cursor is None:
            return items


def _handle_privacy_export(event, context):
    """Return a complete, machine-readable, self-scoped metadata export."""
    ctx, error = _partner_profile_context(event)
    if error:
        return error
    params = event.get('queryStringParameters') or {}
    try:
        limit = int(params.get('limit', _PRIVACY_INSPECT_LIMIT))
    except (TypeError, ValueError):
        return _cv_error(422, 'Invalid export limit')
    if limit < 1 or limit > _PRIVACY_INSPECT_LIMIT:
        return _cv_error(422, 'Invalid export limit')

    categories = {}
    partial = False
    cv_items = []
    try:
        profile = _privacy_read_user_profile(ctx)
        categories['userProfile'] = _privacy_export_category(
            name='user_profile', purpose='account/profile management',
            storage_status='stored' if profile else 'no_data',
            retention_ref='RIS-JOBSEARCH-RETENTION-POLICY-V1#user-profile',
            items=[profile] if profile else [])
    except _PrivacyInspectionUnavailable:
        partial = True
        categories['userProfile'] = _privacy_export_category(
            name='user_profile', purpose='account/profile management',
            storage_status='unavailable',
            retention_ref='RIS-JOBSEARCH-RETENTION-POLICY-V1#user-profile',
            status='UNAVAILABLE', code='unavailable')

    repo = _manual_profile_repo()
    profile_pages = (
        ('cvDocuments', 'CVDocument', _serialize_cv, 'cvDocuments',
         'cv document metadata', 'RIS-JOBSEARCH-RETENTION-POLICY-V1#cv-metadata'),
        ('manualSearchProfiles', 'ManualSearchProfile', _serialize_manual_profile,
         'manualSearchProfiles', 'manual search configuration',
         'RIS-JOBSEARCH-RETENTION-POLICY-V1#manual-search-profile'),
        ('cvSearchProfiles', 'CVSearchProfile', _serialize_cv_search_profile,
         'cvSearchProfiles', 'CV-derived search configuration',
         'RIS-JOBSEARCH-RETENTION-POLICY-V1#cv-search-profile'),
        ('atsSearchProfiles', 'ATSSearchProfile', _serialize_ats_profile,
         'atsSearchProfiles', 'ATS search configuration',
         'RIS-JOBSEARCH-RETENTION-POLICY-V1#ats-search-profile'),
    )
    for key, resource_type, serializer, query_name, purpose, retention_ref in profile_pages:
        try:
            collected = _privacy_export_collect(
                event, repo=repo, ctx=ctx, resource_type=resource_type,
                serializer=serializer, query_name=query_name, limit=limit)
            categories[key] = _privacy_export_category(
                name=resource_type, purpose=purpose,
                storage_status='stored' if collected else 'no_data',
                retention_ref=retention_ref, items=collected)
            if key == 'cvDocuments':
                cv_items = collected
        except _PrivacyInspectionUnavailable:
            partial = True
            categories[key] = _privacy_export_category(
                name=resource_type, purpose=purpose,
                storage_status='unavailable', retention_ref=retention_ref,
                status='UNAVAILABLE', code='unavailable')
        except Exception:
            logger.error('privacy export profile domain unavailable')
            partial = True
            categories[key] = _privacy_export_category(
                name=resource_type, purpose=purpose,
                storage_status='unavailable', retention_ref=retention_ref,
                status='UNAVAILABLE', code='unavailable')

    try:
        from jobsearch.application_repository import ApplicationRepository
        from jobsearch.application_contract import ApplicationContext
        app_repo = ApplicationRepository()
        app_ctx = ApplicationContext(ctx['userId'], ctx['tenantId'], ctx['partnerApplicationId'], ctx['issuer'])
        app_page = []
        app_cursor = None
        while True:
            page, app_cursor = app_repo.list(app_ctx, limit=limit, cursor=app_cursor)
            app_page.extend(page)
            if not app_cursor:
                break
        applications = [app_repo.export(item['applicationId'], ApplicationContext(
            ctx['userId'], ctx['tenantId'], ctx['partnerApplicationId'], ctx['issuer']))
                        for item in app_page]
        categories['applications'] = _privacy_export_category(
            name='ApplicationV1', purpose='authenticated application tracking',
            storage_status='stored' if applications else 'no_data',
            retention_ref='RIS-APPLICATION-V1-RETENTION-DECISION#APPROVAL_REQUIRED',
            items=applications)
    except Exception:
        logger.error('privacy export application domain unavailable')
        partial = True
        categories['applications'] = _privacy_export_category(
            name='ApplicationV1', purpose='authenticated application tracking',
            storage_status='unavailable',
            retention_ref='RIS-APPLICATION-V1-RETENTION-DECISION#APPROVAL_REQUIRED',
            status='UNAVAILABLE', code='unavailable')
    try:
        receipts = _privacy_export_receipts(event, ctx, limit)
        categories['privacyReceipts'] = _privacy_export_category(
            name='privacy_receipt', purpose='privacy evidence retrieval',
            storage_status='stored',
            retention_ref='RIS-PRIVACY-RECEIPT-RETENTION-DECISION#REVIEW_REQUIRED',
            items=receipts)
    except _PrivacyInspectionUnavailable:
        partial = True
        categories['privacyReceipts'] = _privacy_export_category(
            name='privacy_receipt', purpose='privacy evidence retrieval',
            storage_status='unavailable',
            retention_ref='RIS-PRIVACY-RECEIPT-RETENTION-DECISION#REVIEW_REQUIRED',
            status='UNAVAILABLE', code='unavailable')

    payload = {
        'schemaVersion': 1,
        'exportType': 'RIS_USER_PRIVACY_EXPORT',
        'status': 'PARTIAL' if partial else 'COMPLETE',
        'metadataExport': {
            'status': 'PARTIAL' if partial else 'COMPLETE',
            'categories': categories,
        },
        'fileExport': _privacy_file_export(cv_items),
        'userId': ctx['userId'],
        'generatedAt': datetime.now(timezone.utc).isoformat(),
    }
    return {'statusCode': 200, 'body': json.dumps(payload, ensure_ascii=False)}


def _idempotency_key(event: Dict[str, Any]):
    """Optional Idempotency-Key header (1..200 chars). Never logged."""
    headers = {(k or "").lower(): v for k, v in (event.get("headers") or {}).items()}
    key = headers.get("idempotency-key") or headers.get("x-idempotency-key")
    if isinstance(key, str):
        key = key.strip()
        if 1 <= len(key) <= 200:
            return key
    return None


def _manual_profile_repo():
    from jobsearch.partner_profile_repository import PartnerProfileRepository
    return PartnerProfileRepository()


def _manual_profile_error(exc):
    """Map a ProfileContractError to an HTTP response (no internal detail)."""
    from jobsearch.partner_profile_contract import ProfileContractError
    if isinstance(exc, ProfileContractError):
        code = getattr(exc, 'code', 'INVALID_INPUT')
        status = 400 if code == 'CLIENT_IDENTITY_FORBIDDEN' else 422
        return {'statusCode': status,
                'body': json.dumps({'error': 'Invalid profile', 'code': code})}
    return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid request'})}


def _manual_profile_body(event):
    try:
        data = json.loads(event.get('body') or '{}')
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _manual_profile_parse(data, *, existing=None):
    """Validate a client payload into the canonical v1 contract pieces.

    ``searchConfig`` and ``matchingPreferences`` are parsed independently. On
    update (``existing`` supplied) a missing object is preserved, so changing
    one never mutates the other. A legacy create body without ``searchConfig``
    is mapped from the old R03 fields (never silently dropped).
    """
    from jobsearch.partner_profile_contract import (
        MatchingPreferences, ProfileContractError, SearchConfiguration,
        reject_client_identity,
    )
    reject_client_identity(data)
    name = data.get('name', None)
    if name is None and existing is not None:
        name = existing.name
    if not isinstance(name, str) or not name.strip():
        raise ProfileContractError('MISSING_FIELD', 'name is required')
    description = data.get('description')
    if description is None:
        description = existing.description if existing is not None else ""

    mp_raw = data.get('matchingPreferences')
    if mp_raw is not None and not isinstance(mp_raw, dict):
        raise ProfileContractError('INVALID_FIELD',
                                   'matchingPreferences must be an object')
    if mp_raw is None and existing is not None:
        mp = existing.matching_preferences
    else:
        mp = MatchingPreferences.from_dict(mp_raw or {})

    sc_raw = data.get('searchConfig')
    sc_provided = sc_raw is not None
    if sc_provided:
        if not isinstance(sc_raw, dict):
            raise ProfileContractError('INVALID_FIELD',
                                       'searchConfig must be an object')
        sc = SearchConfiguration.from_dict(sc_raw)
    elif existing is not None:
        sc = existing.search_config
    else:
        sc = SearchConfiguration.from_legacy_matching_preferences(mp)

    # v1 write rules apply to new writes and explicitly supplied searchConfig.
    # A preserved legacy searchConfig may be incomplete; it is not silently
    # upgraded into a "complete" v1 object.
    if existing is None or sc_provided:
        if not sc.skills.strip() and not sc.target_roles:
            raise ProfileContractError(
                'INVALID_SEARCH_CONFIG',
                'searchConfig.skills or searchConfig.targetRoles is required')
        if not sc.employment_types:
            raise ProfileContractError(
                'INVALID_SEARCH_CONFIG',
                'searchConfig.employmentTypes must contain at least one value')
    return {
        'name': name.strip(),
        'description': str(description or ''),
        'search_config': sc,
        'matching_preferences': mp,
    }


def _serialize_manual_profile(profile):
    """Emit the canonical Jobsearch v1 ManualSearchProfileV1 shape."""
    body = profile.to_dict()
    return {
        'schemaVersion': body.get('schemaVersion', 1),
        'manualSearchProfileId': body.get('manualProfileId'),
        'name': body.get('name'),
        'description': body.get('description', ''),
        'origin': body.get('origin', 'manual'),
        'searchConfig': body.get('searchConfig'),
        'matchingPreferences': body.get('matchingPreferences'),
        'createdAt': body.get('createdAt'),
        'updatedAt': body.get('updatedAt'),
        'version': getattr(profile, 'version', None),
    }


def _manual_profile_response(profile, status=200):
    return {'statusCode': status,
            'body': json.dumps(_serialize_manual_profile(profile),
                               ensure_ascii=False)}


def _storage_error():
    """Generic 500 for a failed backing-store read/write (no detail leak)."""
    return {'statusCode': 500, 'body': json.dumps({'error': 'Internal error'})}


def _storage_unavailable():
    """503 for exhausted transient conflicts or an unknown commit outcome."""
    return {'statusCode': 503,
            'body': json.dumps({'error': 'Service unavailable'})}


def _integrity_conflict():
    """409 for a missing/inconsistent counter that blocks a safe delete."""
    return {'statusCode': 409,
            'body': json.dumps({'error': 'Profile integrity check failed'})}


def _post_write_response(stored, response, status=200):
    """Serialize only a freshly re-read record.

    A successful write followed by an unreadable/missing record must not fall
    back to an in-memory object: that object has no authoritative ``version``
    and would emit ``version: null`` or other incomplete fields.
    """
    if stored is None:
        logger.error('post-write read returned no item')
        return _storage_error()
    return response(stored, status)


def _partner_storage_guard(call, *args):
    """Map storage failures to 500/503 instead of 404/409."""
    from jobsearch.partner_profile_repository import (
        PartnerProfileIndeterminateError, PartnerProfileIntegrityError,
        PartnerProfileReadError, PartnerProfileTransientError,
    )
    try:
        return call(*args)
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        logger.error('partner profile transaction outcome unavailable')
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        logger.error('partner profile counter integrity check failed')
        return _integrity_conflict()
    except PartnerProfileReadError:
        logger.error('partner profile storage read failed')
        return _storage_error()


def _decode_cursor(raw, *, repo, ctx, scope, resource_type,
                   parent_id=None, limit=50):
    if not raw:
        return None
    from jobsearch.partner_profile_cursor import CursorError
    try:
        return repo.resolve_cursor(
            raw, user_id=ctx['userId'], tenant_id=ctx['tenantId'],
            partner_app_id=ctx.get('partnerApplicationId'),
            issuer=ctx.get('issuer'), scope=scope,
            resource_type=resource_type, parent_id=parent_id, limit=limit)
    except CursorError:
        return 'invalid'


def _encode_cursor(cursor, *, repo, ctx, scope, resource_type,
                   parent_id=None, limit=50):
    if not cursor:
        return None
    return repo.issue_cursor(
        cursor, user_id=ctx['userId'], tenant_id=ctx['tenantId'],
        partner_app_id=ctx.get('partnerApplicationId'),
        issuer=ctx.get('issuer'), scope=scope,
        resource_type=resource_type, parent_id=parent_id, limit=limit)


def _handle_manual_profile_collection(event, context, method):
    ctx, error = _partner_profile_context(event)
    if error:
        return error
    if method == 'GET':
        return _manual_profile_list(event, ctx)
    if method == 'POST':
        return _manual_profile_create(event, ctx)
    return {'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})}


def _manual_profile_list(event, ctx):
    params = event.get('queryStringParameters') or {}
    try:
        limit = int(params.get('limit', _MANUAL_PROFILE_PAGE_LIMIT))
    except (TypeError, ValueError):
        limit = _MANUAL_PROFILE_PAGE_LIMIT
    limit = max(1, min(limit, _MANUAL_PROFILE_PAGE_LIMIT))
    repo = _manual_profile_repo()
    try:
        cursor = _decode_cursor(
            params.get('cursor'), repo=repo, ctx=ctx,
            scope='manual-search-profiles',
            resource_type='ManualSearchProfile', limit=limit)
        if cursor == 'invalid':
            return {'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid cursor'})}
        items, next_cursor = repo.list_by_user(
            ctx['userId'], ctx['tenantId'], resource_type='ManualSearchProfile',
            partner_app_id=ctx.get('partnerApplicationId'),
            issuer=ctx.get('issuer'), limit=limit, cursor=cursor)
        next_token = _encode_cursor(
            next_cursor, repo=repo, ctx=ctx,
            scope='manual-search-profiles',
            resource_type='ManualSearchProfile', limit=limit)
    except Exception:
        logger.error('manual profile list failed')
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal error'})}

    return {'statusCode': 200, 'body': json.dumps({
        'items': [_serialize_manual_profile(p) for p in items],
        'nextCursor': next_token,
    }, ensure_ascii=False)}


def _manual_profile_create(event, ctx):
    from datetime import datetime, timezone
    import uuid
    from jobsearch.partner_profile_contract import (
        ManualSearchProfile, ProfileContractError,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    data = _manual_profile_body(event)
    if data is None:
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid JSON'})}
    try:
        parsed = _manual_profile_parse(data)
    except ProfileContractError as exc:
        return _manual_profile_error(exc)

    now = datetime.now(timezone.utc).isoformat()
    profile = ManualSearchProfile(
        manual_profile_id=uuid.uuid4().hex,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=parsed['name'],
        description=parsed['description'],
        origin='manual',
        search_config=parsed['search_config'],
        matching_preferences=parsed['matching_preferences'],
        created_at=now,
        updated_at=now,
    )
    try:
        profile.validate()
    except ProfileContractError as exc:
        return _manual_profile_error(exc)

    repo = _manual_profile_repo()
    try:
        rid = repo.create(profile, user_id=ctx['userId'], tenant_id=ctx['tenantId'],
                          partner_app_id=ctx.get('partnerApplicationId'),
                          issuer=ctx.get('issuer'),
                          idempotency_key=_idempotency_key(event))
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError as exc:
        return _partner_conflict_response(exc)
    except Exception:
        logger.error('manual profile create failed')
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal error'})}

    stored = repo.get(rid, ctx['userId'], ctx['tenantId'],
                      ctx.get('partnerApplicationId'), ctx.get('issuer'))
    return _post_write_response(stored, _manual_profile_response, 201)


def _handle_manual_profile_item(event, context, method, profile_id):
    ctx, error = _partner_profile_context(event)
    if error:
        return error
    if not profile_id:
        return {'statusCode': 400,
                'body': json.dumps({'error': 'profileId is required'})}
    if method == 'GET':
        return _manual_profile_get(ctx, profile_id)
    if method == 'PUT':
        return _manual_profile_update(event, ctx, profile_id)
    if method == 'DELETE':
        return _manual_profile_delete(event, ctx, profile_id)
    return {'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})}


def _manual_profile_get(ctx, profile_id):
    from jobsearch.partner_profile_contract import ManualSearchProfile
    repo = _manual_profile_repo()
    try:
        profile = repo.get(profile_id, ctx['userId'], ctx['tenantId'],
                           ctx.get('partnerApplicationId'), ctx.get('issuer'))
    except Exception:
        logger.error('manual profile get failed')
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal error'})}
    if profile is None or not isinstance(profile, ManualSearchProfile):
        return {'statusCode': 404, 'body': json.dumps({'error': 'Not found'})}
    return _manual_profile_response(profile)


def _manual_profile_update(event, ctx, profile_id):
    from datetime import datetime, timezone
    from jobsearch.partner_profile_contract import (
        ManualSearchProfile, ProfileContractError,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    repo = _manual_profile_repo()
    try:
        existing = repo.get(profile_id, ctx['userId'], ctx['tenantId'],
                            ctx.get('partnerApplicationId'), ctx.get('issuer'))
    except Exception:
        logger.error('manual profile update lookup failed')
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal error'})}
    if existing is None or not isinstance(existing, ManualSearchProfile):
        return {'statusCode': 404, 'body': json.dumps({'error': 'Not found'})}

    data = _manual_profile_body(event)
    if data is None:
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid JSON'})}
    try:
        parsed = _manual_profile_parse(data, existing=existing)
    except ProfileContractError as exc:
        return _manual_profile_error(exc)

    expected_version = data.get('version')
    if expected_version is not None:
        try:
            expected_version = int(expected_version)
        except (TypeError, ValueError):
            return {'statusCode': 422, 'body': json.dumps({'error': 'Invalid version'})}

    now = datetime.now(timezone.utc).isoformat()
    updated = ManualSearchProfile(
        manual_profile_id=profile_id,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=parsed['name'],
        description=parsed['description'],
        origin='manual',
        search_config=parsed['search_config'],
        matching_preferences=parsed['matching_preferences'],
        metadata=dict(existing.metadata or {}),
        created_at=existing.created_at,
        updated_at=now,
    )
    try:
        updated.validate()
        repo.update(updated, user_id=ctx['userId'], tenant_id=ctx['tenantId'],
                    partner_app_id=ctx.get('partnerApplicationId'),
                    issuer=ctx.get('issuer'),
                    expected_version=expected_version)
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return {'statusCode': 409, 'body': json.dumps({'error': 'Version conflict'})}
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    except Exception:
        logger.error('manual profile update failed')
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal error'})}

    stored = repo.get(profile_id, ctx['userId'], ctx['tenantId'],
                      ctx.get('partnerApplicationId'), ctx.get('issuer'))
    return _post_write_response(stored, _manual_profile_response)


def _manual_profile_delete(event, ctx, profile_id):
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    params = event.get('queryStringParameters') or {}
    expected = params.get('version')
    if expected is not None:
        try:
            expected = int(expected)
        except (TypeError, ValueError):
            return {'statusCode': 422, 'body': json.dumps({'error': 'Invalid version'})}

    repo = _manual_profile_repo()
    try:
        deleted = repo.delete(profile_id, ctx['userId'], ctx['tenantId'],
                              ctx.get('partnerApplicationId'), ctx.get('issuer'),
                              expected_version=expected)
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return {'statusCode': 409, 'body': json.dumps({'error': 'Version conflict'})}
    except Exception:
        logger.error('manual profile delete failed')
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal error'})}
    if not deleted:
        return {'statusCode': 404, 'body': json.dumps({'error': 'Not found'})}
    return {'statusCode': 204, 'body': ''}


# ---------------------------------------------------------------------------
# R04: Partner CV metadata + secure document lifecycle
#
#   GET    /v1/partner/me/cvs
#   POST   /v1/partner/me/cvs
#   GET    /v1/partner/me/cvs/{cvId}
#   PATCH  /v1/partner/me/cvs/{cvId}
#   DELETE /v1/partner/me/cvs/{cvId}
#   POST   /v1/partner/me/cvs/{cvId}/document/upload
#   POST   /v1/partner/me/cvs/{cvId}/document/complete
#   GET    /v1/partner/me/cvs/{cvId}/document
#
# Status machine: pending -> upload_pending -> ready. READY is only set after
# the S3 object is verified via head_object. A delete on a versioned bucket
# creates a delete marker; it is never reported as a full physical purge.
# ---------------------------------------------------------------------------

_CV_COLLECTION = '/v1/partner/me/cvs'


def _cv_repo():
    return _manual_profile_repo()


def _cv_body(event):
    try:
        data = json.loads(event.get('body') or '{}')
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _serialize_cv(cv):
    """Project a stored CVDocument into the public CVDocumentV1 shape.

    Pending/upload-pending rows deliberately omit ``sizeBytes`` because no
    verified object size exists yet. A positive size is public only for the
    verified ``ready`` state. Legacy names and lifecycle values are normalized
    without exposing repository or S3 internals.
    """
    status = str(getattr(cv, 'processing_status', 'pending') or 'pending').lower()
    status = {
        'upload_pending': 'pending',
        'error': 'failed',
        'delete_failed': 'failed',
    }.get(status, status)
    if status not in {'pending', 'ready', 'failed', 'deleted'}:
        raise ValueError('invalid CV processing status')
    content_type = getattr(cv, 'content_type', None)
    if content_type is not None and content_type != 'application/pdf':
        raise ValueError('invalid CV content type')
    version = getattr(cv, 'version', 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError('invalid CV version')
    body = {
        'schemaVersion': 1,
        'cvId': cv.cv_id,
        'filename': cv.name,
        'processingStatus': status,
        'createdAt': cv.created_at,
        'updatedAt': cv.updated_at,
        'version': version,
    }
    if content_type is not None:
        body['contentType'] = 'application/pdf'
    if getattr(cv, 'document_id', None):
        body['documentId'] = cv.document_id
    # ``size`` is trusted for the public DTO only after _cv_complete has
    # verified the object with HeadObject and moved the row to READY.
    size = getattr(cv, 'size', 0)
    if status == 'ready' and isinstance(size, int) and not isinstance(size, bool) and size >= 1:
        body['sizeBytes'] = size
    metadata = getattr(cv, 'metadata', None) or {}
    if not isinstance(metadata, dict):
        raise ValueError('invalid CV metadata')
    body['metadata'] = {
        key: metadata[key] for key in ('pageCount', 'language')
        if key in metadata
    }
    if not body['metadata']:
        body.pop('metadata')
    return body


def _validate_cv_metadata(metadata):
    """Validate the allow-listed public CV metadata fields."""
    from jobsearch.partner_profile_contract import ProfileContractError
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ProfileContractError('INVALID_FIELD', 'metadata must be an object')
    unknown = set(metadata) - {'pageCount', 'language'}
    if unknown:
        raise ProfileContractError('INVALID_FIELD', 'metadata contains unsupported fields')
    if 'pageCount' in metadata:
        page_count = metadata['pageCount']
        if (isinstance(page_count, bool) or not isinstance(page_count, int)
                or page_count < 1):
            raise ProfileContractError('INVALID_FIELD', 'metadata.pageCount must be a positive integer')
    if 'language' in metadata and (
            not isinstance(metadata['language'], str) or not metadata['language'].strip()):
        raise ProfileContractError('INVALID_FIELD', 'metadata.language must be a non-empty string')
    return dict(metadata)


def _cv_response(cv, status=200):
    return {'statusCode': status,
            'body': json.dumps(_serialize_cv(cv), ensure_ascii=False)}


def _cv_error(status, message, **extra):
    payload = {'error': message}
    code = extra.pop('code', None)
    if code is None:
        code = {
            400: 'validation', 401: 'unauthorized', 403: 'forbidden',
            404: 'not_found', 409: 'conflict', 422: 'validation',
            503: 'unavailable',
        }.get(status, 'internal_error')
    payload['code'] = code
    payload.update(extra)
    return {'statusCode': status, 'body': json.dumps(payload)}


def _partner_conflict_response(exc, message='Conflict'):
    """Keep the flat error envelope while exposing a stable error code."""
    code = 'capacity_exceeded' if 'capacity exceeded' in str(exc).lower() else 'conflict'
    return {'statusCode': 409,
            'body': json.dumps({'error': message, 'code': code})}


def _cv_parse_path(path):
    """Return (cvId, action) for a CV path.

    action in: collection, item, upload, complete, document, unknown.
    """
    rest = path[len(_CV_COLLECTION):].strip('/')
    if not rest:
        return None, 'collection'
    parts = rest.split('/')
    cv_id = parts[0]
    if len(parts) == 1:
        return cv_id, 'item'
    if len(parts) == 2 and parts[1] == 'document':
        return cv_id, 'document'
    if len(parts) == 3 and parts[1] == 'document':
        if parts[2] in ('upload', 'complete'):
            return cv_id, parts[2]
    return cv_id, 'unknown'


def _cv_identity(ctx):
    return {
        'user_id': ctx['userId'],
        'tenant_id': ctx['tenantId'],
        'partner_app_id': ctx.get('partnerApplicationId'),
        'issuer': ctx.get('issuer'),
    }


def _cv_get_owned(ctx, cv_id):
    from jobsearch.partner_profile_contract import CVDocument
    repo = _cv_repo()
    cv = repo.get(cv_id, **_cv_identity(ctx))
    return repo, (cv if isinstance(cv, CVDocument) else None)


def _handle_partner_cv_routes(event, context, method, path):
    ctx, error = _partner_profile_context(event)
    if error:
        return error
    rest = path[len(_CV_COLLECTION):].strip('/')
    parts = [p for p in rest.split('/') if p]
    if len(parts) >= 2 and parts[1] == 'search-profiles':
        cv_id = parts[0]
        if len(parts) == 2:
            return _cv_search_profile_collection(event, ctx, method, cv_id)
        if len(parts) == 3:
            return _cv_search_profile_item(event, ctx, method, cv_id, parts[2])
        return _cv_error(404, 'Not found')
    cv_id, action = _cv_parse_path(path)
    if action == 'collection':
        if method == 'GET':
            return _cv_list(event, ctx)
        if method == 'POST':
            return _cv_create(event, ctx)
        return _cv_error(405, 'Method not allowed')
    if not cv_id:
        return _cv_error(400, 'cvId is required')
    if action == 'item':
        if method == 'GET':
            return _cv_get(ctx, cv_id)
        if method == 'PATCH':
            return _cv_update(event, ctx, cv_id)
        if method == 'DELETE':
            return _cv_delete(ctx, cv_id)
        return _cv_error(405, 'Method not allowed')
    if action == 'upload' and method == 'POST':
        return _cv_upload_ticket(event, ctx, cv_id)
    if action == 'complete' and method == 'POST':
        return _cv_complete(event, ctx, cv_id)
    if action == 'document' and method == 'GET':
        return _cv_download(ctx, cv_id)
    return _cv_error(405, 'Method not allowed')


def _cv_list(event, ctx):
    # The repository performs a scoped GSI query; this is deliberately not a
    # table scan. The secure cursor is bound to this exact identity/scope.
    params = event.get('queryStringParameters') or {}
    repo = _cv_repo()
    try:
        try:
            limit = int(params.get('limit', _MANUAL_PROFILE_PAGE_LIMIT))
        except (TypeError, ValueError):
            return _cv_error(422, 'Invalid limit')
        if limit < 1 or limit > _MANUAL_PROFILE_PAGE_LIMIT:
            return _cv_error(422, 'Invalid limit')
        cursor = _decode_cursor(
            params.get('cursor'), repo=repo, ctx=ctx,
            scope='cv-documents', resource_type='CVDocument', limit=limit)
        if cursor == 'invalid':
            return _cv_error(400, 'Invalid cursor')
        items, next_cursor = repo.list_by_user(
            ctx['userId'], ctx['tenantId'], resource_type='CVDocument',
            partner_app_id=ctx.get('partnerApplicationId'),
            issuer=ctx.get('issuer'), limit=limit, cursor=cursor)
        next_token = _encode_cursor(
            next_cursor, repo=repo, ctx=ctx, scope='cv-documents',
            resource_type='CVDocument', limit=limit)
    except (TypeError, ValueError):
        return _cv_error(422, 'Invalid pagination')
    except Exception:
        logger.error('cv list failed')
        return _cv_error(503, 'Service unavailable', code='unavailable')
    return {'statusCode': 200,
            'body': json.dumps({'items': [_serialize_cv(cv) for cv in items],
                                'nextCursor': next_token}, ensure_ascii=False)}


def _cv_create(event, ctx):
    from datetime import datetime, timezone
    import uuid
    from documents import ALLOWED_CONTENT_TYPES
    from jobsearch.partner_profile_contract import (
        CVDocument, CV_STATUS_PENDING, ProfileContractError,
        reject_client_identity,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    data = _cv_body(event)
    if data is None:
        return _cv_error(400, 'Invalid JSON')
    try:
        reject_client_identity(data)
        if set(data) - {'name', 'filename', 'contentType', 'metadata'}:
            raise ProfileContractError('INVALID_FIELD', 'unsupported CV fields')
        name = data.get('filename', data.get('name'))
        if not isinstance(name, str) or not name.strip():
            raise ProfileContractError('MISSING_FIELD', 'filename is required')
        content_type = data.get('contentType') or 'application/pdf'
        if content_type not in ALLOWED_CONTENT_TYPES or content_type != 'application/pdf':
            raise ProfileContractError('INVALID_FIELD', 'contentType not allowed')
        metadata = _validate_cv_metadata(data.get('metadata'))
        now = datetime.now(timezone.utc).isoformat()
        cv = CVDocument(
            cv_id=uuid.uuid4().hex,
            user_id=ctx['userId'],
            tenant_id=ctx['tenantId'],
            name=name.strip(),
            content_type=content_type,
            processing_status=CV_STATUS_PENDING,
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )
        cv.validate()
    except ProfileContractError as exc:
        return _manual_profile_error(exc)

    repo = _cv_repo()
    try:
        rid = repo.create(cv, **_cv_identity(ctx),
                          idempotency_key=_idempotency_key(event))
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError as exc:
        return _cv_error(409, 'Conflict', code=(
            'capacity_exceeded' if 'capacity exceeded' in str(exc).lower()
            else 'conflict'))
    except Exception:
        logger.error('cv create failed')
        return _cv_error(500, 'Internal error')
    stored = repo.get(rid, **_cv_identity(ctx))
    return _post_write_response(stored, _cv_response, 201)


def _cv_get(ctx, cv_id):
    _, cv = _cv_get_owned(ctx, cv_id)
    if cv is None:
        return _cv_error(404, 'Not found')
    return _cv_response(cv)


def _cv_update(event, ctx, cv_id):
    from datetime import datetime, timezone
    from documents import ALLOWED_CONTENT_TYPES
    from jobsearch.partner_profile_contract import CVDocument, ProfileContractError
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    repo, existing = _cv_get_owned(ctx, cv_id)
    if existing is None:
        return _cv_error(404, 'Not found')
    data = _cv_body(event)
    if data is None:
        return _cv_error(400, 'Invalid JSON')
    try:
        from jobsearch.partner_profile_contract import reject_client_identity
        reject_client_identity(data)
        if set(data) - {'name', 'filename', 'contentType', 'metadata',
                        'version', 'expectedVersion'}:
            raise ProfileContractError('INVALID_FIELD', 'unsupported CV fields')
        name = data.get('filename', data.get('name', existing.name))
        if not isinstance(name, str) or not name.strip():
            raise ProfileContractError('MISSING_FIELD', 'filename is required')
        content_type = data.get('contentType', existing.content_type)
        if content_type is None:
            content_type = 'application/pdf'
        if content_type not in ALLOWED_CONTENT_TYPES or content_type != 'application/pdf':
            raise ProfileContractError('INVALID_FIELD', 'contentType not allowed')
        metadata = (_validate_cv_metadata(data.get('metadata'))
                    if 'metadata' in data else dict(existing.metadata or {}))
    except ProfileContractError as exc:
        return _manual_profile_error(exc)

    expected_version = data.get('expectedVersion')
    legacy_version = data.get('version')
    if expected_version is not None and legacy_version is not None \
            and expected_version != legacy_version:
        return _cv_error(422, 'Conflicting version tokens')
    if expected_version is None:
        expected_version = legacy_version
    headers = {(key or '').lower(): value
               for key, value in (event.get('headers') or {}).items()}
    if_match = headers.get('if-match')
    if if_match is not None:
        from jobsearch.partner_profile_contract import parse_expected_version
        try:
            header_version = parse_expected_version({}, if_match)
        except ProfileContractError:
            return _cv_error(422, 'Invalid If-Match')
        if expected_version is not None and expected_version != header_version:
            return _cv_error(422, 'Conflicting version tokens')
        expected_version = header_version
    if expected_version is not None and (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version < 1):
        return _cv_error(422, 'Invalid version')

    now = datetime.now(timezone.utc).isoformat()
    updated = CVDocument(
        cv_id=cv_id,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=name.strip(),
        size=existing.size,
        content_hash=existing.content_hash,
        content_type=content_type,
        etag=existing.etag,
        uploaded_at=existing.uploaded_at,
        document_id=existing.document_id,
        processing_status=existing.processing_status,
        created_at=existing.created_at,
        updated_at=now,
        metadata=metadata,
    )
    try:
        updated.validate()
        repo.update(updated, **_cv_identity(ctx), expected_version=expected_version)
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return _cv_error(409, 'Version conflict')
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    except Exception:
        logger.error('cv update failed')
        return _cv_error(500, 'Internal error')
    stored = repo.get(cv_id, **_cv_identity(ctx))
    return _post_write_response(stored, _cv_response)


def _cv_delete(ctx, cv_id):
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileNotFoundError,
        PartnerProfileTransientError,
    )

    repo, existing = _cv_get_owned(ctx, cv_id)
    if existing is None:
        return _cv_error(404, 'Not found')

    # Phase A: atomically reserve deletion and verify there are no child
    # CVSearchProfiles. This happens BEFORE S3 is touched, so a child conflict
    # can never delete the document.
    try:
        reservation = repo.reserve_parent_delete(
            cv_id, **_cv_identity(ctx), child_type='CVSearchProfile',
            expected_version=getattr(existing, 'version', None))
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return _cv_error(409, 'CV has child search profiles; delete refused',
                         cvId=cv_id, s3Touched=False)
    except PartnerProfileNotFoundError:
        return _cv_error(404, 'Not found')
    except Exception:
        logger.error('cv delete reservation failed')
        return _cv_error(500, 'Internal error')

    # Phase B: delete the current S3 object version only after the child guard
    # succeeded. On failure the guard is released and metadata is retained.
    document_report = None
    if existing.document_id:
        try:
            from documents import delete_document_report
            document_report = delete_document_report(
                tenant_id=ctx['tenantId'], user_id=ctx['userId'],
                doc_id=existing.document_id, require_tenant=True)
        except Exception:
            repo.release_parent_delete(reservation, **_cv_identity(ctx))
            logger.error('cv document delete failed; metadata retained')
            return _cv_error(502, 'Document deletion failed',
                             cvId=cv_id, metadataRetained=True,
                             physicalPurge=False)

    # Phase C: delete metadata + counter + guard atomically.
    try:
        deleted = repo.finalize_parent_delete(
            reservation, **_cv_identity(ctx),
            expected_version=getattr(existing, 'version', None))
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        # A concurrent complete/update may have advanced the parent version
        # after Phase A. Release the delete reservation before returning the
        # conflict so the failed delete cannot strand a deleting guard.
        repo.release_parent_delete(reservation, **_cv_identity(ctx))
        return _cv_error(409, 'Delete conflict', cvId=cv_id)
    except Exception:
        logger.error('cv metadata delete failed')
        return _cv_error(500, 'Internal error')
    if not deleted:
        return _cv_error(404, 'Not found')
    return {'statusCode': 200, 'body': json.dumps({
        'cvId': cv_id,
        'deleted': True,
        'document': document_report or {'existed': False},
        'physicalPurge': False,
    }, ensure_ascii=False)}


def _cv_upload_ticket(event, ctx, cv_id):
    from datetime import datetime, timedelta, timezone
    from documents import (ALLOWED_CONTENT_TYPES, UPLOAD_EXPIRY_SECONDS,
                           new_doc_id, presign_upload)
    from jobsearch.partner_profile_contract import (
        CVDocument, CV_STATUS_READY, CV_STATUS_UPLOAD_PENDING,
        ProfileContractError,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    repo, existing = _cv_get_owned(ctx, cv_id)
    if existing is None:
        return _cv_error(404, 'Not found')
    if existing.processing_status == CV_STATUS_READY:
        return _cv_error(409, 'Document already uploaded; re-upload not allowed')

    data = _cv_body(event) or {}
    content_type = data.get('contentType') or existing.content_type
    if content_type not in ALLOWED_CONTENT_TYPES:
        return _cv_error(422, 'contentType is required and must be allowed')

    document_id = existing.document_id or new_doc_id()
    now = datetime.now(timezone.utc).isoformat()
    updated = CVDocument(
        cv_id=cv_id,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=existing.name,
        size=existing.size,
        content_hash=existing.content_hash,
        content_type=content_type,
        etag=existing.etag,
        uploaded_at=existing.uploaded_at,
        document_id=document_id,
        processing_status=CV_STATUS_UPLOAD_PENDING,
        created_at=existing.created_at,
        updated_at=now,
        metadata=dict(existing.metadata or {}),
    )
    try:
        updated.validate()
        repo.update(updated, **_cv_identity(ctx),
                    expected_version=getattr(existing, 'version', None))
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return _cv_error(409, 'Version conflict')
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    except Exception:
        logger.error('cv upload reservation failed')
        return _cv_error(500, 'Internal error')

    ledger = None
    ledger_ticket = None
    ledger_enabled = os.environ.get(
        'ERASURE_UPLOAD_TICKET_LEDGER_ENABLED', 'false').strip().lower() == 'true'
    freeze_enabled = os.environ.get(
        'ERASURE_WRITE_FREEZE_ENABLED', 'false').strip().lower() == 'true'
    if freeze_enabled and not ledger_enabled:
        return _cv_error(503, 'Upload ticket ledger unavailable')
    if ledger_enabled:
        try:
            from agents.ecosystem.privacy_upload_ticket import (
                UploadTicketLedgerV1, UploadTicketLedgerRepository)
            expires_at = (datetime.now(timezone.utc)
                          + timedelta(seconds=UPLOAD_EXPIRY_SECONDS)).isoformat()
            ledger = UploadTicketLedgerRepository(
                client=getattr(_get_dynamodb().meta, 'client', None))
            ledger_ticket = UploadTicketLedgerV1(
                ticket_id='ticket-' + document_id,
                cv_id=cv_id, document_id=document_id,
                user_id=ctx['userId'], tenant_id=ctx['tenantId'],
                partner_application_id=ctx['partnerApplicationId'],
                issuer=ctx['issuer'], issued_at=now, expires_at=expires_at)
            ledger.register(ledger_ticket)
        except Exception:
            logger.error('cv upload ticket ledger registration failed')
            return _cv_error(503, 'Upload ticket unavailable')

    try:
        ticket = presign_upload(
            tenant_id=ctx['tenantId'], user_id=ctx['userId'],
            content_type=content_type, doc_id=document_id,
            require_tenant=True,
            expires_at=ledger_ticket.expires_at if ledger_ticket else None)
    except ValueError as exc:
        if ledger and ledger_ticket:
            try:
                ledger.transition(ledger_ticket, status='PRESIGN_FAILED',
                                  expected_version=ledger_ticket.version)
            except Exception:
                logger.error('cv upload ticket failure transition failed')
        return _cv_error(400, str(exc))
    except Exception:
        if ledger and ledger_ticket:
            try:
                ledger.transition(ledger_ticket, status='PRESIGN_FAILED',
                                  expected_version=ledger_ticket.version)
            except Exception:
                logger.error('cv upload ticket failure transition failed')
        logger.error('cv upload presign failed')
        return _cv_error(500, 'Failed to prepare upload')

    return {'statusCode': 200, 'body': json.dumps({
        'cvId': cv_id,
        'documentId': document_id,
        'uploadUrl': ticket['uploadUrl'],
        'expiresAt': ticket['expiresAt'],
        'requiredHeaders': ticket['requiredHeaders'],
    }, ensure_ascii=False)}


def _cv_complete(event, ctx, cv_id):
    from datetime import datetime, timezone
    from documents import head_document
    from jobsearch.partner_profile_contract import (
        CVDocument, CV_STATUS_READY, ProfileContractError,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    repo, existing = _cv_get_owned(ctx, cv_id)
    if existing is None:
        return _cv_error(404, 'Not found')
    if not existing.document_id:
        return _cv_error(409, 'No document assigned')

    data = _cv_body(event)
    if data is None:
        return _cv_error(400, 'Invalid JSON')
    if set(data) - {'documentId'}:
        return _cv_error(400, 'Unsupported completion fields')
    requested_document_id = data.get('documentId')
    if requested_document_id is not None and requested_document_id != existing.document_id:
        return _cv_error(409, 'Document ticket does not match CV', cvId=cv_id)

    try:
        meta = head_document(
            tenant_id=ctx['tenantId'], user_id=ctx['userId'],
            doc_id=existing.document_id, require_tenant=True)
    except ValueError as exc:
        return _cv_error(400, str(exc))
    except Exception:
        logger.error('cv upload verification failed')
        return _cv_error(500, 'Failed to verify upload')

    if meta is None:
        return _cv_error(409, 'Upload not found',
                         cvId=cv_id, processingStatus=existing.processing_status)
    if meta.get('docId') != existing.document_id:
        return _cv_error(409, 'Uploaded document does not match CV', cvId=cv_id)
    if meta.get('contentType') != 'application/pdf':
        return _cv_error(409, 'Uploaded object content type is not PDF', cvId=cv_id)
    if meta.get('size', 0) <= 0:
        return _cv_error(409, 'Uploaded object is empty', cvId=cv_id)

    if existing.processing_status == CV_STATUS_READY:
        return _cv_response(existing)

    ledger_ticket = None
    if os.environ.get('ERASURE_UPLOAD_TICKET_LEDGER_ENABLED', 'false').strip().lower() == 'true':
        try:
            from agents.ecosystem.privacy_upload_ticket import (
                STATUS_COMPLETED, UploadTicketLedgerRepository)
            ledger = UploadTicketLedgerRepository(
                client=getattr(_get_dynamodb().meta, 'client', None))
            ledger_ticket = ledger.get('ticket-' + existing.document_id)
            if ledger_ticket.status != STATUS_COMPLETED:
                ledger.transition(ledger_ticket, status=STATUS_COMPLETED,
                                  expected_version=ledger_ticket.version)
        except Exception:
            logger.error('cv upload ticket completion ledger update failed')
            return _cv_error(503, 'Upload ticket ledger unavailable')

    now = datetime.now(timezone.utc).isoformat()
    updated = CVDocument(
        cv_id=cv_id,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=existing.name,
        size=meta['size'],
        content_hash=existing.content_hash,
        content_type=meta.get('contentType') or existing.content_type,
        etag=meta.get('etag'),
        uploaded_at=meta.get('lastModified') or now,
        document_id=existing.document_id,
        processing_status=CV_STATUS_READY,
        created_at=existing.created_at,
        updated_at=now,
        metadata=dict(existing.metadata or {}),
    )
    try:
        updated.validate()
        repo.update(updated, **_cv_identity(ctx),
                    expected_version=getattr(existing, 'version', None))
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return _cv_error(409, 'Version conflict')
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    except Exception:
        logger.error('cv complete failed')
        return _cv_error(500, 'Internal error')
    stored = repo.get(cv_id, **_cv_identity(ctx))
    return _post_write_response(stored, _cv_response)


def _cv_download(ctx, cv_id):
    from documents import presign_download
    from jobsearch.partner_profile_contract import CV_STATUS_READY

    _, existing = _cv_get_owned(ctx, cv_id)
    if existing is None:
        return _cv_error(404, 'Not found')
    if existing.processing_status != CV_STATUS_READY or not existing.document_id:
        return _cv_error(409, 'Document not ready', cvId=cv_id)
    try:
        result = presign_download(
            tenant_id=ctx['tenantId'], user_id=ctx['userId'],
            doc_id=existing.document_id, require_tenant=True)
    except ValueError as exc:
        return _cv_error(400, str(exc))
    except Exception:
        logger.error('cv download presign failed')
        return _cv_error(500, 'Failed to prepare download')
    if result is None:
        return _cv_error(404, 'Document not found')
    return {'statusCode': 200, 'body': json.dumps({
        'cvId': cv_id,
        'documentId': existing.document_id,
        'downloadUrl': result['downloadUrl'],
        'expiresAt': result['expiresAt'],
    }, ensure_ascii=False)}


# ---------------------------------------------------------------------------
# R05-B: Partner CV search profiles (CVSearchProfileV1 CRUD)
#
#   GET    /v1/partner/me/cvs/{cvId}/search-profiles
#   POST   /v1/partner/me/cvs/{cvId}/search-profiles
#   GET    /v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}
#   PUT    /v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}
#   DELETE /v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}
# ---------------------------------------------------------------------------

def _serialize_cv_search_profile(profile):
    body = profile.to_dict()
    return {
        'schemaVersion': body.get('schemaVersion', 1),
        'searchProfileId': body.get('searchProfileId'),
        'cvId': body.get('cvId'),
        'name': body.get('name'),
        'description': body.get('description', ''),
        'origin': body.get('origin', 'cv'),
        'searchConfig': body.get('searchConfig'),
        'createdAt': body.get('createdAt'),
        'updatedAt': body.get('updatedAt'),
        'version': getattr(profile, 'version', None),
    }


def _cv_search_profile_response(profile, status=200):
    return {'statusCode': status,
            'body': json.dumps(_serialize_cv_search_profile(profile),
                               ensure_ascii=False)}


def _cv_search_profile_parse(data, *, existing=None):
    from jobsearch.partner_profile_contract import (
        ProfileContractError, SearchConfiguration, reject_client_identity,
    )
    reject_client_identity(data)
    name = data.get('name')
    if name is None and existing is not None:
        name = existing.name
    if not isinstance(name, str) or not name.strip():
        raise ProfileContractError('MISSING_FIELD', 'name is required')
    description = data.get('description')
    if description is None:
        description = existing.description if existing is not None else ""
    sc_raw = data.get('searchConfig')
    sc_provided = sc_raw is not None
    if sc_provided:
        if not isinstance(sc_raw, dict):
            raise ProfileContractError('INVALID_FIELD',
                                       'searchConfig must be an object')
        sc = SearchConfiguration.from_dict(sc_raw)
    elif existing is not None:
        sc = existing.search_config
    else:
        raise ProfileContractError('MISSING_FIELD', 'searchConfig is required')
    if existing is None or sc_provided:
        if not sc.skills.strip() and not sc.target_roles:
            raise ProfileContractError(
                'INVALID_SEARCH_CONFIG',
                'searchConfig.skills or searchConfig.targetRoles is required')
        if not sc.employment_types:
            raise ProfileContractError(
                'INVALID_SEARCH_CONFIG',
                'searchConfig.employmentTypes must contain at least one value')
    return {'name': name.strip(),
            'description': str(description or ''),
            'search_config': sc}


def _cv_search_profile_collection(event, ctx, method, cv_id):
    from jobsearch.partner_profile_contract import CVDocument as _CVDocument
    repo = _cv_repo()
    try:
        cv = repo.get(cv_id, **_cv_identity(ctx))
    except Exception:
        return _cv_error(500, 'Internal error')
    if cv is None or not isinstance(cv, _CVDocument):
        return _cv_error(404, 'Not found')
    if method == 'GET':
        return _cv_search_profile_list(event, ctx, cv_id)
    if method == 'POST':
        return _cv_search_profile_create(event, ctx, cv_id)
    return _cv_error(405, 'Method not allowed')


def _cv_search_profile_list(event, ctx, cv_id):
    params = event.get('queryStringParameters') or {}
    try:
        limit = int(params.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 50))
    repo = _cv_repo()
    try:
        cursor = _decode_cursor(
            params.get('cursor'), repo=repo, ctx=ctx,
            scope='cv-search-profiles', resource_type='CVSearchProfile',
            parent_id=cv_id, limit=limit)
        if cursor == 'invalid':
            return _cv_error(400, 'Invalid cursor')
        items, next_cursor = repo.list_by_parent(
            cv_id, ctx['userId'], ctx['tenantId'], 'CVSearchProfile',
            partner_app_id=ctx.get('partnerApplicationId'),
            issuer=ctx.get('issuer'), limit=limit, cursor=cursor)
        next_token = _encode_cursor(
            next_cursor, repo=repo, ctx=ctx,
            scope='cv-search-profiles', resource_type='CVSearchProfile',
            parent_id=cv_id, limit=limit)
    except Exception:
        logger.error('cv search profile list failed')
        return _cv_error(500, 'Internal error')
    return {'statusCode': 200, 'body': json.dumps({
        'items': [_serialize_cv_search_profile(p) for p in items],
        'nextCursor': next_token,
    }, ensure_ascii=False)}


def _cv_search_profile_create(event, ctx, cv_id):
    from datetime import datetime, timezone
    import uuid
    from jobsearch.partner_profile_contract import (
        CVSearchProfile, ProfileContractError,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    data = _cv_body(event)
    if data is None:
        return _cv_error(400, 'Invalid JSON')
    try:
        parsed = _cv_search_profile_parse(data)
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    now = datetime.now(timezone.utc).isoformat()
    profile = CVSearchProfile(
        search_profile_id=uuid.uuid4().hex,
        cv_id=cv_id,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=parsed['name'],
        description=parsed['description'],
        origin='cv',
        search_config=parsed['search_config'],
        created_at=now,
        updated_at=now,
    )
    try:
        profile.validate()
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    repo = _cv_repo()
    try:
        rid = repo.create(profile, **_cv_identity(ctx),
                          idempotency_key=_idempotency_key(event))
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError as exc:
        return _cv_error(409, 'Conflict', code=(
            'capacity_exceeded' if 'capacity exceeded' in str(exc).lower()
            else 'conflict'))
    except Exception:
        logger.error('cv search profile create failed')
        return _cv_error(500, 'Internal error')
    stored = repo.get(rid, **_cv_identity(ctx))
    return _post_write_response(stored, _cv_search_profile_response, 201)


def _cv_search_profile_item(event, ctx, method, cv_id, search_profile_id):
    from jobsearch.partner_profile_contract import CVSearchProfile
    repo = _cv_repo()
    try:
        existing = repo.get(search_profile_id, **_cv_identity(ctx))
    except Exception:
        return _cv_error(500, 'Internal error')
    if (existing is None or not isinstance(existing, CVSearchProfile)
            or existing.cv_id != cv_id):
        return _cv_error(404, 'Not found')
    if method == 'GET':
        return _cv_search_profile_response(existing)
    if method == 'PUT':
        return _cv_search_profile_update(event, ctx, cv_id, search_profile_id, existing)
    if method == 'DELETE':
        return _cv_search_profile_delete(event, ctx, cv_id, search_profile_id)
    return _cv_error(405, 'Method not allowed')


def _cv_search_profile_update(event, ctx, cv_id, search_profile_id, existing):
    from datetime import datetime, timezone
    from jobsearch.partner_profile_contract import (
        CVSearchProfile, ProfileContractError,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    data = _cv_body(event)
    if data is None:
        return _cv_error(400, 'Invalid JSON')
    try:
        parsed = _cv_search_profile_parse(data, existing=existing)
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    expected_version = data.get('version')
    if expected_version is not None:
        try:
            expected_version = int(expected_version)
        except (TypeError, ValueError):
            return _cv_error(422, 'Invalid version')
    now = datetime.now(timezone.utc).isoformat()
    updated = CVSearchProfile(
        search_profile_id=search_profile_id,
        cv_id=cv_id,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=parsed['name'],
        description=parsed['description'],
        origin='cv',
        search_config=parsed['search_config'],
        metadata=dict(existing.metadata or {}),
        created_at=existing.created_at,
        updated_at=now,
    )
    repo = _cv_repo()
    try:
        updated.validate()
        repo.update(updated, **_cv_identity(ctx), expected_version=expected_version)
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return _cv_error(409, 'Version conflict')
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    except Exception:
        logger.error('cv search profile update failed')
        return _cv_error(500, 'Internal error')
    stored = repo.get(search_profile_id, **_cv_identity(ctx))
    return _post_write_response(stored, _cv_search_profile_response)


def _cv_search_profile_delete(event, ctx, cv_id, search_profile_id):
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    params = event.get('queryStringParameters') or {}
    expected = params.get('version')
    if expected is not None:
        try:
            expected = int(expected)
        except (TypeError, ValueError):
            return _cv_error(422, 'Invalid version')
    repo = _cv_repo()
    try:
        deleted = repo.delete(search_profile_id, **_cv_identity(ctx),
                              expected_version=expected,
                              child_type='ATSSearchProfile')
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return _cv_error(409, 'Search profile has ATS children or version conflict',
                         cvId=cv_id)
    except Exception:
        logger.error('cv search profile delete failed')
        return _cv_error(500, 'Internal error')
    if not deleted:
        return _cv_error(404, 'Not found')
    return {'statusCode': 204, 'body': ''}


# ---------------------------------------------------------------------------
# R06: Partner ATS search profiles (ATSSearchProfileV1 CRUD)
#
# Flat parent addressing: searchProfileId identifies the CVSearchProfile; the
# CV is derived via the parent chain and never appears in the v1 DTO.
# ---------------------------------------------------------------------------

_ATS_PARENT_PREFIX = '/v1/partner/me/search-profiles/'


def _serialize_ats_profile(profile):
    body = profile.to_dict()
    out = {
        'schemaVersion': body.get('schemaVersion', 1),
        'atsSearchProfileId': body.get('atsProfileId'),
        'searchProfileId': body.get('searchProfileId'),
        'name': body.get('name'),
        'targetRoles': body.get('targetRoles', []),
        'skills': body.get('skills', []),
        'createdAt': body.get('createdAt'),
        'updatedAt': body.get('updatedAt'),
        'version': getattr(profile, 'version', None),
    }
    if body.get('criteria') is not None:
        out['criteria'] = body['criteria']
    return out


def _ats_response(profile, status=200):
    return {'statusCode': status,
            'body': json.dumps(_serialize_ats_profile(profile),
                               ensure_ascii=False)}


def _ats_parent(ctx, search_profile_id):
    from jobsearch.partner_profile_contract import CVSearchProfile, CVDocument
    repo = _cv_repo()
    # Read failures must propagate (-> 500); only genuinely missing/wrong
    # parents become 404. No broad catch here.
    parent = repo.get(search_profile_id, **_cv_identity(ctx))
    if not isinstance(parent, CVSearchProfile):
        return None, None, None
    cv = repo.get(parent.cv_id, **_cv_identity(ctx))
    if not isinstance(cv, CVDocument):
        return None, None, None
    return repo, parent, cv


def _ats_parse(data, *, existing=None):
    from jobsearch.partner_profile_contract import (
        ATSCriteria, ProfileContractError, reject_client_identity,
    )

    def _str_list(value, field):
        if not isinstance(value, list):
            raise ProfileContractError('INVALID_FIELD',
                                       f'{field} must be a list of strings')
        out = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ProfileContractError(
                    'INVALID_FIELD', f'{field} entries must be non-empty strings')
            out.append(item.strip())
        return out

    reject_client_identity(data)
    name = data.get('name')
    if name is None and existing is not None:
        name = existing.name
    if not isinstance(name, str) or not name.strip():
        raise ProfileContractError('MISSING_FIELD', 'name is required')

    if 'targetRoles' in data:
        target_roles = _str_list(data.get('targetRoles'), 'targetRoles')
    elif existing is not None:
        target_roles = list(existing.target_roles)
    else:
        raise ProfileContractError('MISSING_FIELD', 'targetRoles is required')

    if 'skills' in data:
        skills = _str_list(data.get('skills'), 'skills')
    elif existing is not None:
        skills = list(existing.skills)
    else:
        raise ProfileContractError('MISSING_FIELD', 'skills is required')

    if 'criteria' in data:
        raw = data.get('criteria')
        if raw is None:
            # Explicit removal of the optional criteria object.
            criteria = None
        elif isinstance(raw, dict):
            parsed_raw = ATSCriteria.from_dict(raw)
            if existing is not None and existing.criteria is not None:
                # Merge: an omitted list is preserved; an explicit [] clears it.
                criteria = ATSCriteria(
                    required_skills=(parsed_raw.required_skills
                                     if 'requiredSkills' in raw
                                     else list(existing.criteria.required_skills)),
                    preferred_skills=(parsed_raw.preferred_skills
                                      if 'preferredSkills' in raw
                                      else list(existing.criteria.preferred_skills)),
                    excluded_terms=(parsed_raw.excluded_terms
                                    if 'excludedTerms' in raw
                                    else list(existing.criteria.excluded_terms)),
                )
                criteria.validate()
            else:
                criteria = parsed_raw
        else:
            raise ProfileContractError('INVALID_FIELD',
                                       'criteria must be an object or null')
    else:
        criteria = existing.criteria if existing is not None else None

    return {'name': name.strip(), 'target_roles': target_roles,
            'skills': skills, 'criteria': criteria}


def _handle_partner_ats_routes(event, context, method, path):
    ctx, error = _partner_profile_context(event)
    if error:
        return error
    rest = path[len(_ATS_PARENT_PREFIX):].strip('/')
    parts = [p for p in rest.split('/') if p]
    if len(parts) < 2 or parts[1] != 'ats-profiles':
        return _cv_error(404, 'Not found')
    search_profile_id = parts[0]
    if len(parts) == 2:
        return _ats_collection(event, ctx, method, search_profile_id)
    if len(parts) == 3:
        return _ats_item(event, ctx, method, search_profile_id, parts[2])
    return _cv_error(404, 'Not found')


def _ats_collection(event, ctx, method, search_profile_id):
    repo, parent, cv = _ats_parent(ctx, search_profile_id)
    if parent is None:
        return _cv_error(404, 'Not found')
    if method == 'GET':
        return _ats_list(event, ctx, repo, search_profile_id)
    if method == 'POST':
        return _ats_create(event, ctx, repo, parent)
    return _cv_error(405, 'Method not allowed')


def _ats_list(event, ctx, repo, search_profile_id):
    params = event.get('queryStringParameters') or {}
    try:
        limit = int(params.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 50))
    try:
        cursor = _decode_cursor(
            params.get('cursor'), repo=repo, ctx=ctx,
            scope='ats-search-profiles', resource_type='ATSSearchProfile',
            parent_id=search_profile_id, limit=limit)
        if cursor == 'invalid':
            return _cv_error(400, 'Invalid cursor')
        items, next_cursor = repo.list_by_parent(
            search_profile_id, ctx['userId'], ctx['tenantId'],
            'ATSSearchProfile',
            partner_app_id=ctx.get('partnerApplicationId'),
            issuer=ctx.get('issuer'), limit=limit, cursor=cursor)
        next_token = _encode_cursor(
            next_cursor, repo=repo, ctx=ctx,
            scope='ats-search-profiles', resource_type='ATSSearchProfile',
            parent_id=search_profile_id, limit=limit)
    except Exception:
        logger.error('ats list failed')
        return _cv_error(500, 'Internal error')
    return {'statusCode': 200, 'body': json.dumps({
        'items': [_serialize_ats_profile(p) for p in items],
        'nextCursor': next_token,
    }, ensure_ascii=False)}


def _ats_create(event, ctx, repo, parent):
    from datetime import datetime, timezone
    import uuid
    from jobsearch.partner_profile_contract import (
        ATSSearchProfile, ProfileContractError,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    data = _cv_body(event)
    if data is None:
        return _cv_error(400, 'Invalid JSON')
    try:
        parsed = _ats_parse(data)
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    now = datetime.now(timezone.utc).isoformat()
    profile = ATSSearchProfile(
        ats_profile_id=uuid.uuid4().hex,
        search_profile_id=parent.search_profile_id,
        cv_id=parent.cv_id,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=parsed['name'],
        target_roles=parsed['target_roles'],
        skills=parsed['skills'],
        criteria=parsed['criteria'],
        created_at=now,
        updated_at=now,
    )
    try:
        profile.validate()
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    try:
        rid = repo.create(profile, **_cv_identity(ctx),
                          idempotency_key=_idempotency_key(event))
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError as exc:
        return _cv_error(409, 'Conflict', code=(
            'capacity_exceeded' if 'capacity exceeded' in str(exc).lower()
            else 'conflict'))
    except Exception:
        logger.error('ats create failed')
        return _cv_error(500, 'Internal error')
    stored = repo.get(rid, **_cv_identity(ctx))
    return _post_write_response(stored, _ats_response, 201)


def _ats_item(event, ctx, method, search_profile_id, ats_id):
    from jobsearch.partner_profile_contract import ATSSearchProfile
    repo, parent, cv = _ats_parent(ctx, search_profile_id)
    if parent is None:
        return _cv_error(404, 'Not found')
    try:
        existing = repo.get(ats_id, **_cv_identity(ctx))
    except Exception:
        return _cv_error(500, 'Internal error')
    if (existing is None or not isinstance(existing, ATSSearchProfile)
            or existing.search_profile_id != search_profile_id):
        return _cv_error(404, 'Not found')
    if method == 'GET':
        return _ats_response(existing)
    if method == 'PUT':
        return _ats_update(event, ctx, repo, search_profile_id, ats_id, existing)
    if method == 'DELETE':
        return _ats_delete(event, ctx, repo, search_profile_id, ats_id)
    return _cv_error(405, 'Method not allowed')


def _ats_update(event, ctx, repo, search_profile_id, ats_id, existing):
    from datetime import datetime, timezone
    from jobsearch.partner_profile_contract import (
        ATSSearchProfile, ProfileContractError,
    )
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )

    data = _cv_body(event)
    if data is None:
        return _cv_error(400, 'Invalid JSON')
    try:
        parsed = _ats_parse(data, existing=existing)
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    expected_version = data.get('version')
    if expected_version is not None:
        try:
            expected_version = int(expected_version)
        except (TypeError, ValueError):
            return _cv_error(422, 'Invalid version')
    now = datetime.now(timezone.utc).isoformat()
    updated = ATSSearchProfile(
        ats_profile_id=ats_id,
        search_profile_id=search_profile_id,
        cv_id=existing.cv_id,
        user_id=ctx['userId'],
        tenant_id=ctx['tenantId'],
        name=parsed['name'],
        target_roles=parsed['target_roles'],
        skills=parsed['skills'],
        criteria=parsed['criteria'],
        ats_keywords=existing.ats_keywords,
        requirements=existing.requirements,
        preferred_criteria=existing.preferred_criteria,
        exclusions=existing.exclusions,
        location=existing.location,
        radius=existing.radius,
        work_mode=existing.work_mode,
        metadata=dict(existing.metadata or {}),
        created_at=existing.created_at,
        updated_at=now,
    )
    try:
        updated.validate()
        repo.update(updated, **_cv_identity(ctx),
                    expected_version=expected_version)
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return _cv_error(409, 'Version conflict')
    except ProfileContractError as exc:
        return _manual_profile_error(exc)
    except Exception:
        logger.error('ats update failed')
        return _cv_error(500, 'Internal error')
    stored = repo.get(ats_id, **_cv_identity(ctx))
    return _post_write_response(stored, _ats_response)


def _ats_delete(event, ctx, repo, search_profile_id, ats_id):
    from jobsearch.partner_profile_repository import (
        PartnerProfileConflictError, PartnerProfileIndeterminateError,
        PartnerProfileIntegrityError, PartnerProfileTransientError,
    )
    params = event.get('queryStringParameters') or {}
    expected = params.get('version')
    if expected is not None:
        try:
            expected = int(expected)
        except (TypeError, ValueError):
            return _cv_error(422, 'Invalid version')
    try:
        deleted = repo.delete(ats_id, **_cv_identity(ctx),
                              expected_version=expected)
    except (PartnerProfileTransientError, PartnerProfileIndeterminateError):
        return _storage_unavailable()
    except PartnerProfileIntegrityError:
        return _integrity_conflict()
    except PartnerProfileConflictError:
        return _cv_error(409, 'Version conflict')
    except Exception:
        logger.error('ats delete failed')
        return _cv_error(500, 'Internal error')
    if not deleted:
        return _cv_error(404, 'Not found')
    return {'statusCode': 204, 'body': ''}


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
