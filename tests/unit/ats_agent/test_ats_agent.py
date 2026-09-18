"""
Tests for ATS Agent - HTTP Integration Layer only
"""

import sys
sys.path.insert(0, '.')

import pytest
from unittest.mock import Mock, patch, MagicMock
from agents.ats_agent import ATSAgent, ATSHttpClient, ATSAPIError


class TestATSHttpClient:
    """Tests for the HTTP client (integration layer only)."""
    
    def test_client_initialization_default(self):
        """Test client initializes with default URL."""
        client = ATSHttpClient()
        assert client.base_url == 'https://mays-jobsearch.vercel.app'
    
    def test_client_initialization_custom_url(self):
        """Test client can be configured with custom URL."""
        client = ATSHttpClient(base_url='http://localhost:3000')
        assert client.base_url == 'http://localhost:3000'
    
    def test_client_timeout_configuration(self):
        """Test client timeout can be configured."""
        client = ATSHttpClient(timeout=60)
        assert client.timeout == 60
    
    @patch('requests.post')
    def test_analyze_job_calls_api(self, mock_post):
        """Test analyze_job makes HTTP request to correct endpoint."""
        mock_response = Mock()
        mock_response.json.return_value = {'score': 50}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = ATSHttpClient()
        result = client.analyze({'title': 'Test'}, {'skills': 'python'})
        
        assert result['score'] == 50


class TestATSAgent:
    """Tests for ATS Agent."""
    
    def test_agent_initialization(self):
        """Test agent can be initialized."""
        agent = ATSAgent()
        assert agent.name == 'ats_agent'
        assert agent.version == '1.0.0'
    
    def test_validate_work_valid(self):
        """Test validation of valid work item."""
        agent = ATSAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'ats_process',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1',
            'capability': 'analyze.job',
            'payload': {'job': {'title': 'Test Job'}}
        }
        assert agent.validate_work(work_item) is True
    
    def test_validate_work_missing_field(self):
        """Test validation fails with missing field."""
        agent = ATSAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'ats_process',
            'capability': 'analyze.job'
        }
        assert agent.validate_work(work_item) is False
    
    def test_validate_work_missing_job(self):
        """Test validation fails without job in payload."""
        agent = ATSAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'ats_process',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1',
            'capability': 'analyze.job',
            'payload': {}
        }
        assert agent.validate_work(work_item) is False
    
    @patch.object(ATSAgent, 'client')
    def test_process_work_analyze(self, mock_client):
        """Test analyze capability calls client."""
        mock_client.analyze.return_value = {
            'score': 85,
            'keywordCoverage': {'overall': 85},
            'requirements': [],
            'matches': []
        }
        
        agent = ATSAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'ats_process',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1',
            'capability': 'analyze.job',
            'payload': {
                'job': {'title': 'Test Job'},
                'profile': {'skills': 'python'}
            }
        }
        
        result = agent.process_work(work_item)
        
        assert result['success'] is True
        assert 'data' in result
        assert 'analysis' in result['data']
        assert result['data']['jobTitle'] == 'Test Job'
    
    def test_process_work_unsupported_capability(self):
        """Test processing with unsupported capability."""
        agent = ATSAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'ats_process',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1',
            'capability': 'unknown.capability',
            'payload': {}
        }
        
        result = agent.process_work(work_item)
        
        assert result['success'] is False
    
    def test_get_status(self):
        """Test get_status method."""
        agent = ATSAgent()
        status = agent.get_status('work-123', 'tenant-1')
        assert status['workId'] == 'work-123'
        assert status['status'] == 'COMPLETED'


class TestIntegration:
    """Integration tests for ATS Agent."""
    
    def test_workflow_compatibility(self):
        """Test that agent follows AgentBase contract."""
        agent = ATSAgent()
        assert hasattr(agent, 'process_work')
        assert hasattr(agent, 'validate_work')
        assert hasattr(agent, 'get_status')
        assert callable(agent.process_work)