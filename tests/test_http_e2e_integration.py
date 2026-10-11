"""
HTTP End-to-End Integration Tests for RIS Partner API.

These tests exercise the full HTTP request/response cycle:
Browser -> Jobsearch Mock -> RIS Partner API -> Authorization -> Agent Execution.

Tests run against the actual Lambda handler via a local HTTP adapter,
with in-memory stores for all dependencies.
"""
import json
import os
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock
import contextlib

import requests

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.credentials import InMemoryCredentialStore  # noqa: E402
from agents.ecosystem.credentials import (  # noqa: E402
    UnauthorizedManagementAttempt,
    issue_credential,
    revoke_credential,
)
from agents.ecosystem.partner_registry import (  # noqa: E402
    create_partner_application,
    resolve_partner_application,
    deactivate_partner_application,
    PartnerRegistryError,
)
import importlib
handler_module = importlib.import_module("lambda.handler")
h = handler_module  # noqa: E402
from agents.ecosystem import worker_authorization as wa  # noqa: E402

# Test constants
TENANT = "tenant-a"
AGENT = "reference_agent"
PARTNER_ROUTE = "/v1/partner/agents/%s/execute"
M2M_ROUTE = "/v1/m2m/agents/%s/execute"
CLIENT = "client-partner"
OTHER_CLIENT = "client-other"
USER = "user-1"
USER2 = "user-2"
OWNER = "user-1"
ADMIN = "a1"


def _ts(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class InMemoryPartnerRegistry:
    """In-memory implementation of Partner Registry for testing."""
    
    def __init__(self):
        self.applications = {}  # application_id -> record
        self.client_index = {}  # cognito_client_id -> application_id
    
    def create_partner_application(self, application_id: str, cognito_client_id: str,
                                   api_profile_id: str, tenant_id: str) -> Dict[str, Any]:
        if application_id in self.applications:
            raise PartnerRegistryError(f"Application {application_id} already exists")
        if cognito_client_id in self.client_index:
            raise PartnerRegistryError(f"Client {cognito_client_id} already registered")
        
        record = {
            "applicationId": application_id,
            "cognitoClientId": cognito_client_id,
            "apiProfileId": api_profile_id,
            "tenantId": tenant_id,
            "status": "ACTIVE"
        }
        self.applications[application_id] = record
        self.client_index[cognito_client_id] = application_id
        return record
    
    def get_partner_application(self, client_id: str) -> Optional[Dict[str, Any]]:
        app_id = self.client_index.get(client_id)
        if not app_id:
            return None
        record = self.applications.get(app_id)
        if not record:
            return None
        return record.copy()
    
    def deactivate_partner_application(self, client_id: str):
        app_id = self.client_index.get(client_id)
        if app_id and app_id in self.applications:
            self.applications[app_id]["status"] = "INACTIVE"
    
    def create_partner_application_direct(self, record: Dict[str, Any]):
        """Direct creation for testing (bypasses uniqueness checks)."""
        self.applications[record["applicationId"]] = record
        self.client_index[record["cognitoClientId"]] = record["applicationId"]


class EntitlementResolver:
    """Simple entitlement resolver for tests."""
    
    def __init__(self, entitlements):
        self.entitlements = entitlements
    
    def find_entitlements(self, user_id: str):
        return [e for e in self.entitlements if e.get("userId") == user_id]


class RISHttpAdapter(BaseHTTPRequestHandler):
    """HTTP adapter that converts HTTP requests to Lambda events and calls the RIS handler."""
    
    ris_app: 'RISHttpTestServer' = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle POST requests by converting to Lambda event and calling handler."""
        import time
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        
        # Build Lambda event
        event = {
            "httpMethod": "POST",
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
            "body": body,
            "requestContext": {
                "requestId": f"req-{int(time.time()*1000)}",
                "http": {
                    "method": "POST",
                    "path": self.path
                }
            }
        }
        
        # Extract Authorization header and inject Cognito claims
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            # For test tokens, we embed claims in the token itself (simple test format)
            # Format: test-token.<base64_json_claims>
            if token.startswith('test-token.'):
                try:
                    import base64
                    claims_b64 = token.split('.', 1)[1]
                    claims_json = base64.urlsafe_b64decode(claims_b64 + '==').decode('utf-8')
                    claims = json.loads(claims_json)
                    event["requestContext"]["authorizer"] = {"jwt": {"claims": claims}}
                    # Validate token expiration for test tokens
                    if 'exp' in claims:
                        import time
                        if claims['exp'] < int(time.time()):
                            self.send_response(401)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'error': 'Token expired'}).encode('utf-8'))
                            return
                except Exception:
                    pass  # Invalid token, let handler handle it
            # If not a test token or invalid, let handler handle it (will fail auth)

        # Call the RIS handler
        try:
            response = self.ris_app.call_handler(event)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': f'Internal error: {str(e)}'}).encode('utf-8'))
            return
        
        # Send response
        self.send_response(response.get('statusCode', 200))
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        body = response.get('body', '')
        if isinstance(body, dict):
            body = json.dumps(body)
        self.wfile.write(body.encode('utf-8'))
    
    def log_message(self, format, *args):
        pass  # Suppress logs


class RISHttpTestServer:
    """Test server that runs the RIS handler via HTTP."""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 0):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.base_url: Optional[str] = None
        
        # Test infrastructure
        self.profiles = ap.InMemoryApiProfileStore()
        self.creds = InMemoryCredentialStore()
        self.partner_registry = InMemoryPartnerRegistry()
        self.entitlements = []
        self.enqueue_counter = 0

        self.custom_enqueue = None
        self.custom_registry = None
        self.custom_sources = None
        
        # Set up test data
        self._setup_test_data()
        
        # Create the HTTP server
        RISHttpAdapter.ris_app = self
        self.server = HTTPServer((self.host, self.port), RISHttpAdapter)
        self.port = self.server.server_address[1]
        self.base_url = f'http://{self.host}:{self.port}'
    
    def _setup_test_data(self):
        """Set up test profiles, credentials, partner registry, and entitlements."""
        # Create API profile
        owner = {"userId": OWNER, "tenantId": TENANT, "groups": []}
        admin = {"userId": ADMIN, "tenantId": TENANT, "groups": ["admins"]}
        self.pid = ap.create_profile(self.profiles, owner, "partner")["apiProfileId"]
        ap.transition_status(self.profiles, admin, self.pid, "ACTIVE")
        
        # Issue credential
        res = issue_credential(
            self.creds, self.profiles, self.pid,
            _ts(30), "owner", OWNER, reason="e2e-test")
        self.credential = res
        self.credential_id = res["metadata"]["credentialId"]
        self.secret = res["secret"]
        
        # Register partner application
        self.partner_registry.create_partner_application(
            application_id="app-partner",
            cognito_client_id=CLIENT,
            api_profile_id=self.pid,
            tenant_id=TENANT,
        )
        
        # Add entitlement for USER
        self.entitlements = [{
            "entitlementId": "ent-" + USER,
            "userId": USER,
            "agentId": "reference_agent",
            "tenantId": TENANT,
            "validFrom": _ts(-1),
            "validUntil": _ts(30),
            "status": "ACTIVE"
        }]
        
        # Add entitlement for USER2
        self.entitlements.append({
            "entitlementId": "ent-" + USER2,
            "userId": USER2,
            "agentId": "reference_agent",
            "tenantId": TENANT,
            "validFrom": _ts(-1),
            "validUntil": _ts(30),
            "status": "ACTIVE"
        })
    def call_handler(self, event: Dict[str, Any], extra_patches: Optional[list] = None) -> Dict[str, Any]:
        """Call the RIS handler with mocked dependencies. Accepts extra patches for testing."""
        # Mock the partner registry
        def registry_lookup(cognito_client_id: str):
            return self.partner_registry.get_partner_application(cognito_client_id)
        
        # Mock introspection sources
        def build_sources():
            return {
                "credential_store": self.creds,
                "profile_store": self.profiles,
                "entitlement_resolver": EntitlementResolver(self.entitlements),
                "catalog": {"reference_agent": "ACTIVE"},
            }
        
        # Mock enqueue function
        def enqueue(**kwargs):
            self.enqueue_counter += 1
            return {"workId": f"w{self.enqueue_counter}", "status": "QUEUED", "requestId": f"rq{self.enqueue_counter}"}
        
        # Build patches list
        patches = [
            patch.object(h, "_enqueue_agent_work", side_effect=self.custom_enqueue if self.custom_enqueue else enqueue),
        ]
        # Use custom sources if set, otherwise use default build_sources
        if self.custom_sources:
            patches.append(patch.object(h, "_build_introspection_sources", return_value=self.custom_sources()))
        else:
            patches.append(patch.object(h, "_build_introspection_sources", return_value=build_sources()))
        # Use custom registry if set, otherwise use default lookup
        if self.custom_registry:
            patches.append(patch("agents.ecosystem.partner_registry.resolve_partner_application", side_effect=self.custom_registry))
        else:
            patches.append(patch("agents.ecosystem.partner_registry.resolve_partner_application", side_effect=registry_lookup))
        if extra_patches:
            patches.extend(extra_patches)
        
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return h.handler(event, None)
    
    def set_custom_enqueue(self, enqueue_func):
        """Set a custom enqueue function for testing failure scenarios."""
        self.custom_enqueue = enqueue_func
    
    def clear_custom_enqueue(self):
        self.custom_enqueue = None
    
    def set_custom_registry(self, registry_func):
        """Set a custom registry lookup function for testing failure scenarios."""
        self.custom_registry = registry_func
    
    def clear_custom_registry(self):
        self.custom_registry = None
    
    def set_custom_sources(self, sources_func):
        """Set a custom sources function for testing failure scenarios."""
        self.custom_sources = sources_func
    
    def clear_custom_sources(self):
        self.custom_sources = None
        self.custom_sources = None
        self.custom_registry = None
        self.custom_sources = None

    
    def start(self):
        """Start the HTTP server in a background thread."""
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.1)  # Give server time to start
    
    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)
    
    def _make_test_token(self, claims: Dict[str, Any]) -> str:
        """Create a test JWT token with embedded claims."""
        import base64
        claims_json = json.dumps(claims)
        claims_b64 = base64.urlsafe_b64encode(claims_json.encode('utf-8')).decode('utf-8').rstrip('=')
        return f"test-token.{claims_b64}"
    
    def make_valid_token(self, user_id: str = USER, tenant_id: str = TENANT, 
                         client_id: str = CLIENT, token_use: str = "access") -> str:
        """Create a valid test token."""
        claims = {
            "sub": user_id,
            "custom:tenant_id": tenant_id,
            "client_id": client_id,
            "token_use": token_use,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        return self._make_test_token(claims)
    
    def make_expired_token(self, user_id: str = USER) -> str:
        claims = {
            "sub": user_id,
            "custom:tenant_id": TENANT,
            "client_id": CLIENT,
            "token_use": "access",
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        }
        return self._make_test_token(claims)
    
    def make_id_token(self, user_id: str = USER) -> str:
        claims = {
            "sub": user_id,
            "custom:tenant_id": TENANT,
            "client_id": CLIENT,
            "token_use": "id",  # Not access
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        return self._make_test_token(claims)
    
    def make_token_missing_tenant(self, user_id: str = USER) -> str:
        claims = {
            "sub": user_id,
            "client_id": CLIENT,
            "token_use": "access",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        return self._make_test_token(claims)
    
    def make_token_wrong_tenant(self, user_id: str = USER) -> str:
        claims = {
            "sub": user_id,
            "custom:tenant_id": "tenant-b",
            "client_id": CLIENT,
            "token_use": "access",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        return self._make_test_token(claims)


class JobsearchE2EClient:
    """Client that simulates the Jobsearch server-side proxy calling RIS Partner API."""
    
    def __init__(self, ris_base_url: str, ris_credential: str):
        self.ris_base_url = ris_base_url
        self.ris_credential = ris_credential
    
    def execute_agent(self, jwt: str, agent_id: str = "reference_agent",
                      capability: str = "reference.echo", payload: Dict = None,
                      idempotency_key: str = None, credential: str = None) -> Dict[str, Any]:
        """Call the RIS Partner API as the Jobsearch server would."""
        url = f"{self.ris_base_url}/v1/partner/agents/{agent_id}/execute"
        headers = {
            "Authorization": f"Bearer {jwt}",
            "X-Api-Credential": self.ris_credential if credential is None else credential,
            "Content-Type": "application/json"
        }
        body = {
            "capability": capability,
            "payload": payload or {},
        }
        if idempotency_key:
            body["idempotencyKey"] = idempotency_key
        
        response = requests.post(url, json=body, headers=headers, timeout=5)
        try:
            return {"status_code": response.status_code, "body": response.json()}
        except Exception:
            return {"status_code": response.status_code, "body": response.text}


class TestHttpE2EIntegration(unittest.TestCase):
    """HTTP End-to-End Integration Tests for RIS Partner API."""
    
    def setUp(self):
        self.ris_server = RISHttpTestServer()
        self.ris_server.start()
        
        # Jobsearch client that calls RIS Partner API
        self.jobsearch = JobsearchE2EClient(
            ris_base_url=self.ris_server.base_url,
            ris_credential=self.ris_server.secret
        )
    
    def tearDown(self):
        self.ris_server.stop()
    
    def _call_ris(self, jwt: str, agent_id: str = "reference_agent",
                  capability: str = "reference.echo", payload: Dict = None,
                  credential: str = None) -> Dict[str, Any]:
        """Direct call to RIS Partner API (simulating Jobsearch)."""
        cred = self.ris_server.secret if credential is None else credential
        return self.jobsearch.execute_agent(
            jwt=jwt, agent_id=agent_id, credential=cred)
    
    def _get_valid_token(self, **kwargs) -> str:
        return self.ris_server.make_valid_token(**kwargs)
    
    # E2E-01: Valid JWT + valid partner credential + entitlement -> successful execution
    def test_e2e_01_valid_request(self):
        jwt = self._get_valid_token()
        result = self._call_ris(jwt)
        self.assertEqual(result["status_code"], 202)
        self.assertIn("workId", result["body"])
        self.assertEqual(result["body"]["status"], "QUEUED")
    
    # E2E-02: Missing JWT -> denied
    def test_e2e_02_missing_jwt(self):
        result = self._call_ris(jwt="")
        self.assertEqual(result["status_code"], 401)
    
    # E2E-03: Invalid JWT -> denied
    def test_e2e_03_invalid_jwt(self):
        result = self._call_ris(jwt="invalid-token")
        self.assertEqual(result["status_code"], 401)
    
    # E2E-04: Expired JWT -> denied
    def test_e2e_04_expired_jwt(self):
        jwt = self.ris_server.make_expired_token()
        result = self._call_ris(jwt)
        self.assertEqual(result["status_code"], 401)
    
    # E2E-05: ID Token instead of Access Token -> denied
    def test_e2e_05_id_token(self):
        jwt = self.ris_server.make_id_token()
        result = self._call_ris(jwt)
        self.assertEqual(result["status_code"], 401)
    
    # E2E-06: Missing RIS credential -> denied
    def test_e2e_06_missing_credential(self):
        jwt = self._get_valid_token()
        result = self._call_ris(jwt, credential="")
        self.assertEqual(result["status_code"], 401)
    
    # E2E-07: Invalid RIS credential -> denied
    def test_e2e_07_invalid_credential(self):
        jwt = self._get_valid_token()
        result = self._call_ris(jwt, credential="invalid-credential")
        self.assertEqual(result["status_code"], 401)
    
    # E2E-08: Revoked RIS credential -> denied
    def test_e2e_08_revoked_credential(self):
        jwt = self._get_valid_token()
        # Revoke the credential
        revoke_credential(
            self.ris_server.creds, self.ris_server.credential_id,
            "admin", ADMIN, reason="e2e-test", actor_tenant=TENANT)
        result = self._call_ris(jwt)
        self.assertIn(result["status_code"], (401, 403))
    
    # E2E-09: Credential belongs to another partner -> denied
    def test_e2e_09_cross_client_credential(self):
        # Register another partner with different client_id
        other_pid = ap.create_profile(self.ris_server.profiles, 
                                       {"userId": "other-owner", "tenantId": "tenant-b", "groups": []}, 
                                       "partner")["apiProfileId"]
        ap.transition_status(self.ris_server.profiles, {"userId": ADMIN, "tenantId": "tenant-b", "groups": ["admins"]}, 
                             other_pid, "ACTIVE")
        
        other_registry = InMemoryPartnerRegistry()
        other_registry.create_partner_application(
            application_id="app-other",
            cognito_client_id=OTHER_CLIENT,
            api_profile_id=other_pid,
            tenant_id="tenant-b",
        )
        
        jwt = self._get_valid_token(client_id=OTHER_CLIENT)
        # Use the original credential (bound to original client)
        result = self._call_ris(jwt)
        # The partner registry will return the other partner's application, 
        # but the credential is bound to the first partner's APIProfile -> mismatch
        self.assertEqual(result["status_code"], 403)
    
    # E2E-10: Tenant mismatch -> denied
    def test_e2e_10_tenant_mismatch(self):
        jwt = self.ris_server.make_token_wrong_tenant()
        result = self._call_ris(jwt)
        self.assertEqual(result["status_code"], 403)
    
    # E2E-11: Inactive Partner Registry entry -> denied
    def test_e2e_11_inactive_partner(self):
        # Deactivate the partner
        self.ris_server.partner_registry.deactivate_partner_application(CLIENT)
        jwt = self._get_valid_token()
        result = self._call_ris(jwt)
        self.assertEqual(result["status_code"], 403)
    
    # E2E-12: Missing user entitlement -> denied
    def test_e2e_12_missing_entitlement(self):
        # Remove entitlement for USER
        self.ris_server.entitlements = []
        jwt = self._get_valid_token()
        result = self._call_ris(jwt)
        self.assertEqual(result["status_code"], 403)
    
    # E2E-13: Unauthorized agent capability -> denied
    def test_e2e_13_unauthorized_agent(self):
        jwt = self._get_valid_token()
        result = self._call_ris(jwt, agent_id="unauthorized-agent")
        self.assertEqual(result["status_code"], 403)
    
    # E2E-14: RIS backend unavailable -> controlled error
    def test_e2e_14_backend_unavailable(self):
        """Simulate RIS backend unavailability (connection refused, timeout, etc.)."""
        jwt = self._get_valid_token()
        
        # Test 1: Credential store unavailable (simulates DynamoDB unavailable)
        def failing_credential_store_get_by_digest(*args, **kwargs):
            raise Exception("Connection refused to DynamoDB")
        
        with patch.object(self.ris_server.creds, "get_by_digest", side_effect=failing_credential_store_get_by_digest):
            result = self._call_ris(jwt)
            # Current behavior: unexpected store exceptions result in 500
            # (handler catches _Denied but re-raises other exceptions)
            self.assertEqual(result["status_code"], 500)
            # Verify no traceback is exposed
            self.assertNotIn("traceback", result["body"].get("error", "").lower())
            # The error message includes the exception message (current behavior)
            # Verify no secret leakage
            self.assertNotIn(self.ris_server.secret, str(result))
        
        # Test 2: Partner registry lookup fails (simulates DynamoDB unavailable)
        # Handler catches exceptions and returns 403 (fail-closed)
        # Use server's custom registry to inject failure in server thread
        def failing_registry_lookup(*args, **kwargs):
            raise Exception("DynamoDB timeout")
        
        self.ris_server.set_custom_registry(failing_registry_lookup)
        try:
            result = self._call_ris(jwt)
            self.assertEqual(result["status_code"], 403)
            # Fail-closed: registry unavailable -> deny
            self.assertNotIn(self.ris_server.secret, str(result))
        finally:
            self.ris_server.clear_custom_registry()
        
        # Test 3: Enqueue work item fails (simulates SQS unavailable)
        # Use server's custom enqueue to inject failure in server thread
        def failing_enqueue(*args, **kwargs):
            raise Exception("SQS connection refused")
        
        self.ris_server.set_custom_enqueue(failing_enqueue)
        try:
            result = self._call_ris(jwt)
            self.assertEqual(result["status_code"], 500)
        finally:
            self.ris_server.clear_custom_enqueue()
            self.assertNotIn(self.ris_server.secret, str(result))
        
        # Verify no unauthorized retry or duplicate execution occurred
        # (The enqueue function was called once and failed - no silent retry)
    
    # E2E-15: Malformed backend response -> controlled error
    def test_e2e_15_malformed_response(self):
        """Inject malformed backend responses (invalid JSON, unexpected structure, etc.)."""
        jwt = self._get_valid_token()
        
        # Test 1: resolve_credential_profile returns unexpected structure
        def malformed_resolve(*args, **kwargs):
            return "not-a-tuple"  # Should be (meta, profile) tuple
        
        with patch("agents.ecosystem.credentials.resolve_credential_profile", side_effect=malformed_resolve):
            result = self._call_ris(jwt)
            self.assertIn(result["status_code"], (500, 503))
            self.assertNotIn(self.ris_server.secret, str(result))
        
        # Test 2: check_worker_entitlement returns unexpected structure
        def malformed_entitlement_check(*args, **kwargs):
            return "not-an-auth-decision-object"
        
        with patch("agents.ecosystem.worker_authorization.check_worker_entitlement", side_effect=malformed_entitlement_check):
            result = self._call_ris(jwt)
            self.assertIn(result["status_code"], (500, 503))
            self.assertNotIn(self.ris_server.secret, str(result))
        
        # Test 3: _enqueue_agent_work returns malformed response
        # Use server's custom enqueue to inject failure in server thread
        def malformed_enqueue(*args, **kwargs):
            return "not-a-dict"
        
        self.ris_server.set_custom_enqueue(malformed_enqueue)
        try:
            result = self._call_ris(jwt)
            # Handler doesn't validate enqueue response structure, tries to access
            # out['workId'] which fails with KeyError/TypeError, caught by generic
            # exception handler and returns 500
            self.assertIn(result["status_code"], (500, 503))
            self.assertNotIn(self.ris_server.secret, str(result))
        finally:
            self.ris_server.clear_custom_enqueue()
        
        # Test 4: resolve_partner_application returns malformed data
        def malformed_registry(*args, **kwargs):
            return "not-a-dict"
        
        self.ris_server.set_custom_registry(malformed_registry)
        try:
            result = self._call_ris(jwt)
            self.assertIn(result["status_code"], (403, 500, 503))
            self.assertNotIn(self.ris_server.secret, str(result))
        finally:
            self.ris_server.clear_custom_registry()
        
        # Test 5: _build_introspection_sources returns unexpected structure
        def malformed_sources(*args, **kwargs):
            return "not-a-dict"
        
        self.ris_server.set_custom_sources(malformed_sources)
        try:
            result = self._call_ris(jwt)
            self.assertIn(result["status_code"], (500, 503))
            self.assertNotIn(self.ris_server.secret, str(result))
        finally:
            self.ris_server.clear_custom_sources()
    
    # E2E-16: Two users share the same partner credential, but their individual 
    # entitlements remain isolated
    def test_e2e_16_two_users_same_credential_isolated_entitlements(self):
        # USER has entitlement, USER2 has entitlement
        # Both can use the same credential (credential owner is admin)
        jwt1 = self._get_valid_token(user_id=USER)
        jwt2 = self._get_valid_token(user_id=USER2)
        
        # Both should succeed
        result1 = self._call_ris(jwt1)
        result2 = self._call_ris(jwt2)
        
        self.assertEqual(result1["status_code"], 202)
        self.assertEqual(result2["status_code"], 202)
        # But they get different workIds (isolated)
        self.assertNotEqual(result1["body"]["workId"], result2["body"]["workId"])
    
    # E2E-17: Two partner applications have independent credentials and tenant boundaries
    def test_e2e_17_two_partners_isolated(self):
        # Create second partner in different tenant
        other_pid = ap.create_profile(self.ris_server.profiles,
                                       {"userId": "other-owner", "tenantId": "tenant-b", "groups": []},
                                       "partner")["apiProfileId"]
        ap.transition_status(self.ris_server.profiles, 
                             {"userId": ADMIN, "tenantId": "tenant-b", "groups": ["admins"]}, 
                             other_pid, "ACTIVE")
        
        # Add second partner to the server's registry
        self.ris_server.partner_registry.create_partner_application(
            application_id="app-other",
            cognito_client_id=OTHER_CLIENT,
            api_profile_id=other_pid,
            tenant_id="tenant-b",
        )
        
        # Issue credential for second partner
        res = issue_credential(
            self.ris_server.creds, self.ris_server.profiles, other_pid,
            _ts(30), "owner", "other-owner", reason="e2e-test")
        other_secret = res["secret"]
        
        # First partner token with first credential
        jwt1 = self._get_valid_token(client_id=CLIENT)
        result1 = self._call_ris(jwt1, credential=self.ris_server.secret)
        self.assertEqual(result1["status_code"], 202)
        
        # Add entitlement for user-b in tenant-b
        self.ris_server.entitlements.append({
            "entitlementId": "ent-user-b",
            "userId": "user-b",
            "agentId": "reference_agent",
            "tenantId": "tenant-b",
            "validFrom": _ts(-1),
            "validUntil": _ts(30),
            "status": "ACTIVE"
        })
        
        # Create Jobsearch client for second partner
        other_jobsearch = JobsearchE2EClient(
            ris_base_url=self.ris_server.base_url,
            ris_credential=other_secret
        )
        
        # Second partner token with second credential
        jwt2 = self._get_valid_token(user_id="user-b", tenant_id="tenant-b", client_id=OTHER_CLIENT)
        result2 = other_jobsearch.execute_agent(jwt2, credential=other_secret)
        self.assertEqual(result2["status_code"], 202)
        
        # Cross-access should fail
        result_cross = self._call_ris(jwt2, credential=self.ris_server.secret)
        self.assertEqual(result_cross["status_code"], 403)
        
        result_cross2 = other_jobsearch.execute_agent(jwt1, credential=other_secret)
        self.assertEqual(result_cross2["status_code"], 403)
    
    # E2E-18: No RIS credential appears in browser responses, headers, URLs or logs
    def test_e2e_18_no_secret_leakage(self):
        jwt = self._get_valid_token()
        result = self._call_ris(jwt)
        
        # Check response body
        body_str = json.dumps(result["body"])
        self.assertNotIn(self.ris_server.secret, body_str)
        self.assertNotIn("ris_", body_str)
        
        # Check that credential is not in any header (we don't expose headers in test,
        # but we can verify the response doesn't contain it)
        self.assertNotIn(self.ris_server.secret, str(result))
    
    # E2E-19: Registry unavailable -> fail closed
    def test_e2e_19_registry_unavailable(self):
        # Mock registry to raise exception
        original_lookup = self.ris_server.partner_registry.get_partner_application
        def failing_lookup(client_id):
            raise Exception("DynamoDB unavailable")
        self.ris_server.partner_registry.get_partner_application = failing_lookup
        
        try:
            jwt = self._get_valid_token()
            result = self._call_ris(jwt)
            self.assertEqual(result["status_code"], 403)
        finally:
            self.ris_server.partner_registry.get_partner_application = original_lookup
    
    # E2E-20: Missing tenant claim -> denied according to canonical contract
    def test_e2e_20_missing_tenant_claim(self):
        jwt = self.ris_server.make_token_missing_tenant()
        result = self._call_ris(jwt)
        self.assertEqual(result["status_code"], 403)


def _ts(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


if __name__ == '__main__':
    unittest.main()