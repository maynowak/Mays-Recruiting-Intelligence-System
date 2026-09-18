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

logger = logging.getLogger(__name__)


class ATSAPIError(Exception):
    """Error communicating with ATS API."""
    pass


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
        """Call the ATS analysis endpoint."""
        payload = {'job': job}
        if profile:
            payload['profile'] = profile
        
        url = f"{self.base_url}/api/ats-analysis"
        
        try:
            import requests
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except ImportError:
            raise ATSAPIError('requests library not available')
        except Exception as e:
            logger.error(f"ATS API request failed: {e}")
            raise ATSAPIError(str(e)) from e


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
        work_id = work_item.get('workId', 'unknown')
        
        logger.info(f"ATS Agent processing: capability={capability}, workId={work_id}")
        
        start_time = datetime.utcnow()
        
        if capability == self.CAPABILITY_ANALYZE_JOB:
            result = self._analyze_job(payload)
        else:
            result = {
                'success': False,
                'error': {'message': f'Unsupported capability: {capability}', 'type': 'UnsupportedCapability'}
            }
        
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        result.setdefault('metrics', {})
        result['metrics'].update({
            'durationMs': duration_ms,
            'workId': work_id,
            'agentVersion': self.version
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
            'result': {'message': 'Work completed', 'timestamp': datetime.utcnow().isoformat()}
        }
    
    def _analyze_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze job by calling external ATS API."""
        job = payload.get('job', {})
        profile = payload.get('profile', {})
        
        logger.info(f"Calling ATS API for job: {job.get('title', 'Unknown')}")
        
        try:
            result = self.client.analyze(job, profile)
            
            return {
                'success': True,
                'data': {
                    'analysis': result,
                    'jobTitle': job.get('title', ''),
                    'candidateSkills': profile.get('skills', '')
                }
            }
            
        except ATSAPIError as e:
            logger.error(f"ATS API error: {e}")
            return {
                'success': False,
                'error': {'message': str(e), 'type': 'ATSAPIError'}
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
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
