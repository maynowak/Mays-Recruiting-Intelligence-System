"""
Tests for Reference Agent

Unit and integration tests for the Reference Agent that demonstrates
G0.4 Agent API boundary and May's Orders integration.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, '.')

from agents.reference_agent.service import ReferenceAgent, create_reference_handler


class TestReferenceAgentInitialization:
    """Test ReferenceAgent initialization."""

    def test_agent_creates_successfully(self):
        """Agent can be instantiated."""
        agent = ReferenceAgent()
        assert agent is not None
        assert agent.name == 'reference_agent'
        assert agent.version == '1.0.0'

    def test_agent_with_config(self):
        """Agent can be created with config."""
        config = {'timeout': 30}
        agent = ReferenceAgent(config=config)
        assert agent.config == config


class TestReferenceAgentValidation:
    """Test work validation."""

    def test_valid_work_item(self):
        """Valid work item passes validation."""
        agent = ReferenceAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'agent_work',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1'
        }
        assert agent.validate_work(work_item) is True

    def test_missing_work_id(self):
        """Work item without workId fails validation."""
        agent = ReferenceAgent()
        work_item = {
            'type': 'agent_work',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1'
        }
        assert agent.validate_work(work_item) is False

    def test_wrong_type(self):
        """Work item with wrong type fails validation."""
        agent = ReferenceAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'wrong_type',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1'
        }
        assert agent.validate_work(work_item) is False

    def test_null_work_item(self):
        """Null work item fails validation."""
        agent = ReferenceAgent()
        assert agent.validate_work(None) is False


class TestReferenceAgentProcessing:
    """Test work processing."""

    def test_echo_capability(self):
        """Echo capability processes successfully."""
        agent = ReferenceAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'agent_work',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1',
            'agentId': 'reference_agent',
            'capability': 'reference.echo',
            'payload': {'message': 'hello', 'count': 5}
        }
        
        result = agent.process_work(work_item)
        
        assert result['success'] is True
        assert 'data' in result
        assert result['data']['echoed'] == {'message': 'hello', 'count': 5}
        assert result['data']['workId'] == 'test-123'
        assert result['data']['capability'] == 'reference.echo'

    def test_echo_empty_payload(self):
        """Echo handles empty payload."""
        agent = ReferenceAgent()
        work_item = {
            'workId': 'test-456',
            'type': 'agent_work',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-2',
            'agentId': 'reference_agent',
            'capability': 'reference.echo',
            'payload': {}
        }
        
        result = agent.process_work(work_item)
        
        assert result['success'] is True
        assert result['data']['echoed'] == {}

    def test_unknown_capability(self):
        """Unknown capability returns error."""
        agent = ReferenceAgent()
        work_item = {
            'workId': 'test-789',
            'type': 'agent_work',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-3',
            'agentId': 'reference_agent',
            'capability': 'unknown.capability',
            'payload': {}
        }
        
        result = agent.process_work(work_item)
        
        assert result['success'] is False
        assert 'error' in result

    def test_status_method(self):
        """Get status returns valid response."""
        agent = ReferenceAgent()
        status = agent.get_status('work-123', 'tenant-abc')
        
        assert status['workId'] == 'work-123'
        assert status['status'] == 'COMPLETED'
        assert 'result' in status


class TestReferenceAgentLambdaHandler:
    """Test Lambda handler for reference agent."""

    def test_handler_processes_valid_records(self):
        """Handler processes valid SQS records."""
        handler = create_reference_handler()
        
        event = {
            'Records': [
                {
                    'body': json.dumps({
                        'workId': 'test-123',
                        'type': 'agent_work',
                        'tenantId': 'tenant-1',
                        'idempotencyKey': 'key-1',
                        'agentId': 'reference_agent',
                        'capability': 'reference.echo',
                        'payload': {'message': 'hello'}
                    })
                }
            ]
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['processed'] == 1
        assert len(body['results']) == 1

    def test_handler_handles_multiple_records(self):
        """Handler processes multiple records."""
        handler = create_reference_handler()
        
        event = {
            'Records': [
                {
                    'body': json.dumps({'workId': 'test-1'})
                },
                {
                    'body': json.dumps({'workId': 'test-2'})
                }
            ]
        }
        
        result = handler(event, None)
        
        body = json.loads(result['body'])
        assert body['processed'] == 2

    def test_handler_handles_invalid_json(self):
        """Handler handles invalid JSON gracefully."""
        handler = create_reference_handler()
        
        event = {
            'Records': [
                {
                    'body': 'not valid json'
                }
            ]
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert len(body['results']) == 1
        assert 'error' in body['results'][0]


class TestReferenceAgentContract:
    """Test that ReferenceAgent follows the Agent Contract."""

    def test_has_process_work(self):
        """Agent has process_work method."""
        agent = ReferenceAgent()
        assert hasattr(agent, 'process_work')
        assert callable(getattr(agent, 'process_work'))

    def test_has_validate_work(self):
        """Agent has validate_work method."""
        agent = ReferenceAgent()
        assert hasattr(agent, 'validate_work')
        assert callable(getattr(agent, 'validate_work'))

    def test_has_get_status(self):
        """Agent has get_status method."""
        agent = ReferenceAgent()
        assert hasattr(agent, 'get_status')
        assert callable(getattr(agent, 'get_status'))

    def test_process_work_returns_dict(self):
        """process_work returns dictionary."""
        agent = ReferenceAgent()
        work_item = {
            'workId': 'test',
            'type': 'agent_work',
            'tenantId': 't1',
            'idempotencyKey': 'k1'
        }
        result = agent.process_work(work_item)
        assert isinstance(result, dict)

    def test_validate_work_returns_bool(self):
        """validate_work returns boolean."""
        agent = ReferenceAgent()
        result = agent.validate_work({'workId': 'test'})
        assert isinstance(result, bool)


class TestReferenceAgentLocalStorage:
    """Test Lambda handler with local DynamoDB mocking."""

    def test_work_item_structure(self):
        """Work item has all required fields for May's Orders."""
        agent = ReferenceAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'agent_work',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1',
            'agentId': 'reference_agent',
            'capability': 'reference.echo',
            'payload': {'data': 'value'},
            'requestedBy': 'user-123'
        }
        
        # Verify all required fields for May's Orders exist
        required = ['workId', 'type', 'tenantId', 'idempotencyKey']
        for field in required:
            assert field in work_item

    def test_result_structure(self):
        """Result has contract-compliant structure."""
        agent = ReferenceAgent()
        work_item = {
            'workId': 'test-123',
            'type': 'agent_work',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1',
            'payload': {'message': 'test'}
        }
        
        result = agent.process_work(work_item)
        
        # Result contains success flag
        assert 'success' in result
        
        # Result contains data on success
        assert 'data' in result
        
        # Metrics present
        assert 'metrics' in result
        assert 'durationMs' in result['metrics']
        assert 'workId' in result['metrics']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])