"""
Tests for Agent Body

Unit tests for the reusable Agent Body framework.
"""

import pytest
import json
import sys
sys.path.insert(0, '.')

from agents.agent_body import AgentBody, AgentRouter, AgentContext, AgentExecutor, AgentResultHandler


class TestAgentRouter:
    """Test Agent Router."""

    def test_route_by_work_type(self):
        """Router can route by work type."""
        router = AgentRouter()
        handler_called = [False]
        
        def test_handler(work_item, context):
            handler_called[0] = True
            return {'success': True}
        
        router.register(work_type='test_type', handler=test_handler)
        
        work_item = {'type': 'test_type', 'workId': 'test-123'}
        handler = router.route(work_item)
        
        assert handler is test_handler

    def test_route_by_capability(self):
        """Router can route by capability."""
        router = AgentRouter()
        
        def test_handler(work_item, context):
            return {'success': True}
        
        router.register(capability='test.capability', handler=test_handler)
        
        work_item = {'type': 'any', 'capability': 'test.capability'}
        handler = router.route(work_item)
        
        assert handler is test_handler


class TestAgentContext:
    """Test Agent Context."""

    def test_extract_context(self):
        """Context can extract from work item."""
        work_item = {
            'workId': 'work-123',
            'tenantId': 'tenant-abc',
            'requestedBy': 'user-456',
            'agentId': 'agent-789',
            'type': 'test',
            'idempotencyKey': 'key-1',
        }
        
        context = AgentContext(work_item)
        
        assert context.work_id == 'work-123'
        assert context.tenant_id == 'tenant-abc'
        assert context.user_id == 'user-456'

    def test_validate_context(self):
        """Context validates required fields."""
        valid_item = {
            'workId': 'work-123',
            'tenantId': 'tenant-1',
            'type': 'test',
            'idempotencyKey': 'key-1'
        }
        
        context = AgentContext(valid_item)
        assert context.validate() is True


class TestAgentExecutor:
    """Test Agent Executor."""

    def test_execute_validates(self):
        """Executor validates work items."""
        executor = AgentExecutor()
        
        result = executor.execute({'invalid': 'work'})  # Missing required fields
        
        assert result['success'] is False
        assert result['error']['type'] == 'VALIDATION_ERROR'

    def test_execute_no_handler(self):
        """Executor handles missing handler."""
        executor = AgentExecutor()
        
        work_item = {
            'workId': 'work-123',
            'type': 'unknown_type',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1'
        }
        
        result = executor.execute(work_item)
        
        assert result['success'] is False


class TestAgentResultHandler:
    """Test Agent Result Handler."""

    def test_success_result(self):
        """Create success result."""
        result = AgentResultHandler.success(
            work_id='work-123',
            data={'output': 'done'}
        )
        
        assert result['success'] is True
        assert result['data'] == {'output': 'done'}

    def test_error_result(self):
        """Create error result."""
        result = AgentResultHandler.error(
            work_id='work-123',
            message='Something went wrong',
            error_type='CUSTOM_ERROR'
        )
        
        assert result['success'] is False
        assert result['error']['message'] == 'Something went wrong'


class TestAgentBody:
    """Test full Agent Body."""

    def test_execute_with_handler(self):
        """Agent Body executes with registered handler."""
        body = AgentBody()
        
        def my_handler(work_item, context):
            return {'success': True, 'data': {'processed': True}}
        
        body.register_agent(work_type='my_work', handler=my_handler)
        
        work_item = {
            'workId': 'work-123',
            'type': 'my_work',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1'
        }
        
        result = body.execute(work_item)
        
        assert result['success'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])