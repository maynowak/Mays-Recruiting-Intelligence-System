"""
ATS Agent - Integration Adapter for ATS Core HTTP API

This module provides a thin integration layer between the Agent Runtime
and the existing ATS Core API from the mays-jobsearch repository.

IMPORTANT: This agent does NOT implement any ATS business logic.
All ATS functionality is delegated to the external ATS API.
"""

import logging
import json
import os
from typing import Dict, Any, Optional

if '.' not in __import__('sys').path:
    __import__('sys').path.insert(0, '.')

from agents.base import AgentBase

from agents.ats_agent.contract import (
    ATSContractError,
    CONTRACT_VERSION,
    validate_analysis_response,
)
from agents.ats_agent.result_body import (
    RESULT_BODY_VERSION,
    build_ats_analysis_result_body,
)

logger = logging.getLogger(__name__)

from agents.timeutil import utcnow, utcnow_naive_iso



class ATSAPIError(Exception):
    """Error communicating with ATS API."""

    def __init__(
        self,
        message: str,
        code: str = "ATS_UPSTREAM_ERROR",
        status: Optional[int] = None,
    ):
        super().__init__(message)
        self.code = code
        self.status = status


def _classify_transport_error(error: Exception) -> str:
    name = type(error).__name__.lower()
    if "timeout" in name:
        return "ATS_TIMEOUT"
    if "connection" in name or "network" in name:
        return "ATS_UNAVAILABLE"
    return "ATS_UPSTREAM_ERROR"


def _check_http_status(response: Any) -> None:
    status = getattr(response, "status_code", 200)
    if status >= 500:
        raise ATSAPIError(f"ATS API HTTP {status}", "ATS_UPSTREAM_ERROR", status)
    if status >= 400:
        raise ATSAPIError(f"ATS API HTTP {status}", "ATS_BAD_REQUEST", status)


class ATSHttpClient:
    """
    HTTP client for calling the ATS Core API.
    
    This client implements the thin integration layer - it does NOT
    perform any ATS analysis itself. It simply forwards requests
    to the external ATS service.
    """
    
    DEFAULT_BASE_URL = os.environ.get('ATS_API_BASE_URL', 
        'https://mays-jobsearch.vercel.app')
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        """Initialize the HTTP client."""
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout
        self._session = None
        self._http_lib = None
        
        try:
            import httpx
            self._session = httpx.Client(base_url=self.base_url, timeout=timeout)
            self._http_lib = 'httpx'
        except ImportError:
            try:
                import requests
                self._session = requests.Session()
                self._http_lib = 'requests'
            except ImportError:
                self._session = None
                self._http_lib = None
    
    def analyze(self, job: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call the ATS analysis endpoint.

        Transport-Reihenfolge: httpx -> requests -> stdlib-urllib (Gate 7:
        Lambda-Runtime stellt weder httpx noch requests sicher bereit).
        """
        payload = {'job': job}
        if profile:
            payload['profile'] = profile

        url = f"{self.base_url}/api/ats-analysis"

        if self._http_lib == 'httpx' and self._session is not None:
            try:
                response = self._session.post(url, json=payload)
                _check_http_status(response)
                return response.json()
            except ATSAPIError:
                raise
            except Exception as e:
                logger.error("ATS API request failed: %s", type(e).__name__)
                raise ATSAPIError(str(e), _classify_transport_error(e)) from e
        try:
            import requests
            response = requests.post(url, json=payload, timeout=self.timeout)
            _check_http_status(response)
            return response.json()
        except ImportError:
            pass
        except ATSAPIError:
            raise
        except Exception as e:
            logger.error("ATS API request failed: %s", type(e).__name__)
            raise ATSAPIError(str(e), _classify_transport_error(e)) from e

        # Stdlib-Fallback (keine Drittabhaengigkeit).
        import json as _json
        import urllib.error as _urlerror
        import urllib.request as _urllib

        try:
            req = _urllib.Request(
                url,
                data=_json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _urllib.urlopen(req, timeout=self.timeout) as resp:
                return _json.loads(resp.read().decode("utf-8") or "{}")
        except _urlerror.HTTPError as e:
            code = "ATS_BAD_REQUEST" if e.code < 500 else "ATS_UPSTREAM_ERROR"
            raise ATSAPIError(f"ATS API HTTP {e.code}", code, e.code) from e
        except Exception as e:
            logger.error("ATS API request failed: %s", type(e).__name__)
            raise ATSAPIError(str(e), _classify_transport_error(e)) from e


class ATSAgent(AgentBase):
    """
    ATS Agent for job matching through existing HTTP API.
    
    This agent:
    1. Validates work items according to AgentBase contract
    2. Calls the external ATS API via HTTP
    3. Returns results through Agent Runtime
    
    NO ATS LOGIC IS IMPLEMENTED HERE.
    """
    
    CAPABILITY_ANALYZE_JOB = 'analyze.job'
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ATS agent."""
        super().__init__(config)
        self.name = 'ats_agent'
        self.version = '1.0.0'
        self._client = None
    
    @property
    def client(self) -> ATSHttpClient:
        """Get or create HTTP client."""
        if self._client is None:
            config = self.config or {}
            base_url = config.get('api_base_url')
            timeout = config.get('timeout', 30)
            self._client = ATSHttpClient(base_url=base_url, timeout=timeout)
        return self._client
    
    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Process a work item by calling the external ATS API."""
        from datetime import datetime
        
        capability = work_item.get('capability')
        payload = work_item.get('payload', {})
        # Engine-Pfad wrappt: payload enthaelt das Original-WorkItem
        # (Muster wie Orders-Function, Gate 6). Eine Ebene entpacken.
        if isinstance(payload, dict) and 'job' not in payload:
            inner = payload.get('payload')
            if isinstance(inner, dict):
                payload = inner
        work_id = work_item.get('workId', 'unknown')
        
        logger.info(f"ATS Agent processing: capability={capability}, workId={work_id}")
        
        start_time = utcnow()
        
        if capability == self.CAPABILITY_ANALYZE_JOB:
            result = self._analyze_job(payload)
        else:
            result = {
                'success': False,
                'error': {'message': f'Unsupported capability: {capability}', 'type': 'UnsupportedCapability'}
            }
        
        duration_ms = (utcnow() - start_time).total_seconds() * 1000
        result.setdefault('metrics', {})
        result['metrics'].update({
            'durationMs': duration_ms,
            'workId': work_id,
            'agentVersion': self.version,
            'contractVersion': CONTRACT_VERSION,
            'resultBodyVersion': RESULT_BODY_VERSION,
        })
        
        return result
    
    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        """Validate work item before processing."""
        if not isinstance(work_item, dict):
            return False
        
        required_fields = ['workId', 'type', 'tenantId', 'idempotencyKey']
        for field in required_fields:
            if field not in work_item:
                logger.warning(f"Missing required field: {field}")
                return False
        
        capability = work_item.get('capability')
        if capability != self.CAPABILITY_ANALYZE_JOB:
            logger.warning(f"Unsupported capability: {capability}")
            return False

        payload = work_item.get('payload', {})
        if isinstance(payload, dict) and 'job' not in payload:
            inner = payload.get('payload')
            if isinstance(inner, dict):
                payload = inner
        if 'job' not in payload:
            logger.warning("Missing 'job' in payload")
            return False

        return True
    
    def get_status(self, work_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get work item status."""
        from datetime import datetime
        return {
            'workId': work_id,
            'status': 'COMPLETED',
            'result': {'message': 'Work completed', 'timestamp': utcnow_naive_iso()}
        }
    
    def _analyze_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze job by calling external ATS API."""
        job = payload.get('job', {})
        profile = payload.get('profile', {})
        
        logger.info(f"Calling ATS API for job: {job.get('title', 'Unknown')}")
        
        try:
            result = self.client.analyze(job, profile)
            result = validate_analysis_response(result)
            body = build_ats_analysis_result_body(
                result, job_title=job.get('title') or None
            )

            return {
                'success': True,
                'data': body,
            }

        except ATSContractError as e:
            logger.error("ATS contract mismatch: %s", e)
            return {
                'success': False,
                'error': {
                    'message': str(e),
                    'type': 'ATSContractError',
                    'code': e.code,
                },
            }
        except ATSAPIError as e:
            logger.error("ATS API error: %s", type(e).__name__)
            return {
                'success': False,
                'error': {
                    'message': str(e),
                    'type': 'ATSAPIError',
                    'code': e.code,
                },
            }
        except Exception as e:
            logger.error("Unexpected error: %s", type(e).__name__)
            return {
                'success': False,
                'error': {'message': str(e), 'type': type(e).__name__}
            }


def create_ats_handler(config: Optional[Dict[str, Any]] = None):
    """Factory function to create Lambda handler."""
    agent = ATSAgent(config)
    
    def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        results = []
        
        for record in event.get('Records', []):
            try:
                body = json.loads(record['body'])
                work_item = body
                
                if agent.validate_work(work_item):
                    result = agent.process_work(work_item)
                    results.append({'workId': work_item.get('workId'), 'result': result})
                else:
                    results.append({'workId': work_item.get('workId'), 'error': 'Validation failed'})
            except Exception as e:
                logger.error(f"Error: {e}")
                results.append({'error': str(e), 'messageId': record.get('messageId')})
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed': len(event.get('Records', [])),
                'results': results
            })
        }
    
    return handler


lambda_handler = create_ats_handler()
