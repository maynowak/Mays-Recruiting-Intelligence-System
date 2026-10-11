"""Mock Jobsearch server for integration testing.

This mock simulates the Jobsearch server-side endpoint that:
1. Receives a request from the browser (with Cognito JWT)
2. Calls the RIS Partner API with its server-side RIS API Credential
3. Returns the result to the browser (without exposing the credential)

This mock is used only for integration testing within the RIS repository.
"""
import json
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any
import requests


class JobsearchMockHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the mock Jobsearch server."""
    
    def __init__(self, *args, ris_partner_url: str, ris_api_credential: str, **kwargs):
        self.ris_partner_url = ris_partner_url
        self.ris_api_credential = ris_api_credential
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle POST requests from the browser."""
        parsed = urlparse(self.path)
        
        if parsed.path == '/jobsearch/submit':
            # Simulate browser submitting a job search request with JWT
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                jwt = data.get('jwt')
                search_params = data.get('params', {})
                
                if not jwt:
                    self._send_error(400, 'Missing JWT')
                    return
                
                # Call RIS Partner API on behalf of the user
                ris_response = self._call_ris_partner(jwt, search_params)
                
                self._send_json(200, ris_response)
            except json.JSONDecodeError:
                self._send_error(400, 'Invalid JSON')
            except Exception as e:
                self._send_error(500, f'Internal error: {str(e)}')
        else:
            self._send_error(404, 'Not found')
    
    def _call_ris_partner(self, jwt: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call the RIS Partner API with the server-side credential."""
        headers = {
            'Authorization': f'Bearer {jwt}',
            'X-Api-Credential': self.ris_api_credential,
            'Content-Type': 'application/json'
        }
        payload = {
            'input': params
        }
        # The RIS partner endpoint is /v1/partner/agents/{agentId}/execute
        # We'll use a default agent ID for testing
        agent_id = 'jobsearch-agent'
        url = f'{self.ris_partner_url}/v1/partner/agents/{agent_id}/execute'
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        return response.json()
    
    def _send_json(self, status: int, data: Dict[str, Any]):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def _send_error(self, status: int, message: str):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode('utf-8'))
    
    def log_message(self, format, *args):
        # Suppress default log messages
        pass


class JobsearchMockServer:
    """Mock Jobsearch server that runs in a background thread."""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 0,
                 ris_partner_url: str = 'http://127.0.0.1:8080',
                 ris_api_credential: str = 'test-credential'):
        self.host = host
        self.port = port
        self.ris_partner_url = ris_partner_url
        self.ris_api_credential = ris_api_credential
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.base_url: Optional[str] = None
    
    def start(self):
        """Start the mock server in a background thread."""
        def handler(*args, **kwargs):
            return JobsearchMockHandler(
                *args,
                ris_partner_url=self.ris_partner_url,
                ris_api_credential=self.ris_api_credential,
                **kwargs
            )
        
        self.server = HTTPServer((self.host, self.port), handler)
        self.port = self.server.server_address[1]
        self.base_url = f'http://{self.host}:{self.port}'
        
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        # Give the server a moment to start
        time.sleep(0.1)
    
    def stop(self):
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)
    
    def submit_job(self, jwt: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to submit a job search request directly."""
        url = f'{self.base_url}/jobsearch/submit'
        response = requests.post(url, json={'jwt': jwt, 'params': params}, timeout=5)
        return response.json()


# For standalone testing
if __name__ == '__main__':
    # This allows running the mock server standalone for manual testing
    server = JobsearchMockServer(port=8081)
    server.start()
    print(f'Mock Jobsearch server running on {server.base_url}')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print('Server stopped')