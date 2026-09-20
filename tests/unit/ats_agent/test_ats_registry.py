"""
Tests for ATS Agent Registry Integration
"""

import sys
sys.path.insert(0, '.')

import pytest
from unittest.mock import Mock, patch
from agents.ats_agent import (
    ATSAgent, ATSHttpClient, ATSAPIError,
    register_ats_agent, get_ats_descriptor, is_ats_registered,
    ATS_ANALYZE_CAPABILITY, ATS_WORK_TYPE
)
from agents.ecosystem.registry import AgentRegistry, AgentDescriptor, AgentStatus


class TestATSRegistryIntegration:
    """Tests for ATS agent registry integration."""
    
    def test_get_ats_descriptor(self):
        """Test getting ATS agent descriptor."""
        descriptor = get_ats_descriptor()
        
        assert isinstance(descriptor, AgentDescriptor)
        assert descriptor.agent_id == 'ats-agent'
        assert descriptor.name == 'ATS Agent'
        assert descriptor.version == '1.0.0'
        assert descriptor.status == AgentStatus.ACTIVE
        assert 'analyze.job' in descriptor.capabilities
    
    def test_register_ats_agent(self):
        """Test registering ATS agent in registry."""
        registry = AgentRegistry()
        
        result = register_ats_agent(registry)
        assert result is True
        
        assert is_ats_registered(registry) is True
        
        descriptor = registry.get('ats-agent')
        assert descriptor is not None
        assert descriptor.agent_id == 'ats-agent'
    
    def test_is_ats_registered(self):
        """Test checking if ATS agent is registered."""
        registry = AgentRegistry()
        
        assert is_ats_registered(registry) is False
        
        register_ats_agent(registry)
        
        assert is_ats_registered(registry) is True
    
    def test_capability_constant(self):
        """Test capability constant is correct."""
        assert ATS_ANALYZE_CAPABILITY == 'analyze.job'
    
    def test_work_type_constant(self):
        """Test work type constant is correct."""
        assert ATS_WORK_TYPE == 'ats_process'


class TestATSAgentIntegration:
    """Integration tests for ATS Agent."""
    
    def test_agent_has_required_methods(self):
        """Test that agent has required AgentBase methods."""
        agent = ATSAgent()
        
        assert hasattr(agent, 'process_work')
        assert hasattr(agent, 'validate_work')
        assert hasattr(agent, 'get_status')
        assert callable(agent.process_work)
        assert callable(agent.validate_work)
        assert callable(agent.get_status)
    
    def test_agent_capacity(self):
        """Test agent capability matches registry."""
        agent = ATSAgent()
        descriptor = get_ats_descriptor()
        
        assert agent.CAPABILITY_ANALYZE_JOB == descriptor.capabilities[0]
    
    @patch.object(ATSAgent, 'client')
    def test_workspace_flow(self, mock_client):
        """Test complete workflow through agent."""
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
                'job': {'title': 'Python Developer', 'tags': ['python']},
                'profile': {'skills': 'python, django'}
            }
        }
        
        # Validate
        assert agent.validate_work(work_item) is True
        
        # Process
        result = agent.process_work(work_item)
        assert result['success'] is True
        assert 'data' in result
        
        # Status
        status = agent.get_status('test-123', 'tenant-1')
        assert status['workId'] == 'test-123'