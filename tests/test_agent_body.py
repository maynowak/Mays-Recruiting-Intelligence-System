"""
Tests for Agent Body S2 - Integration Harness

Tests the Agent Body execution path with realistic work items
and the Reference Agent as a domain agent.

This module tests the integration harness that allows the Agent Body
to be tested independently of the SQS/Worker infrastructure.
"""

import pytest
import json
import sys
sys.path.insert(0, '.')

from agents.agent_body import AgentBody, AgentRouter, AgentContext, AgentExecutor, AgentResultHandler
from agents.reference_agent.service import ReferenceAgent


class TestAgentBodyIntegrationHarness:
    """
    Integration tests for Agent Body with Reference Agent.
    
    This tests the full path:
    WorkItem → Agent Body → Context → Router → Executor → Domain Agent
    """

    def test_happy_path_with_reference_agent(self):
        """Full integration path with reference echo capability."""
        router = AgentRouter()
        agent = ReferenceAgent()
        router.register(work_type='agent_reference_agent', handler=agent.process_work)
        
        executor = AgentExecutor(router=router)
        
        work_item = {
            'workId': 'test-123',
            'type': 'agent_reference_agent',
            'tenantId': 'tenant-1',
            'idempotencyKey': 'key-1',
            'agentId': 'reference_agent',
            'capability': 'reference.echo',
            'payload': {'message': 'hello world'}
        }
        
        result = executor.execute(work_item)
        
        assert result['success'] is True
        assert 'data' in result
        assert 'metrics' in result
        assert result['metrics']['workId'] == 'test-123'

    def test_full_agent_body_with_reference_agent(self):
        """Test complete AgentBody with ReferenceAgent."""
        body = AgentBody()
        agent = ReferenceAgent()
        body.register_agent(work_type='agent_reference_agent', handler=agent.process_work)
        
        work_item = {
            'workId': 'test-456',
            'type': 'agent_reference_agent',
            'tenantId': 'tenant-abc',
            'idempotencyKey': 'key-2',
            'agentId': 'reference_agent',
            'capability': 'reference.echo',
            'payload': {'data': 'integration test'}
        }
        
        result = body.execute(work_item)
        
        assert result['success'] is True
        assert result['data']['workId'] == 'test-456'
        assert result['data']['echoed'] == {'data': 'integration test'}

    def test_context_extraction_preserves_all_fields(self):
        """Context extracts all required fields from work item."""
        work_item = {
            'workId': 'test-789',
            'type': 'agent_test',
            'tenantId': 'tenant-xyz',
            'requestedBy': 'user-123',
            'agentId': 'test_agent',
            'capability': 'test.capability',
            'idempotencyKey': 'resp-key',
            'requestId': 'req-456',
            'payload': {'key': 'value'}
        }
        
        context = AgentContext.from_work_item(work_item)
        
        assert context.work_id == 'test-789'
        assert context.tenant_id == 'tenant-xyz'
        assert context.user_id == 'user-123'
        assert context.agent_id == 'test_agent'
        assert context.capability == 'test.capability'
        assert context.idempotency_key == 'resp-key'


class TestAgentRouter:
    """Test Agent Router."""

    def test_route_by_work_type(self):
        """Router can route by work type."""
        router = AgentRouter()
        handler_called = [False]
        
        def test_handler(work_item):
            handler_called[0] = True
            return {'success': True}
        
        router.register(work_type='test_type', handler=test_handler)
        
        work_item = {'type': 'test_type', 'workId': 'test-123'}
        handler = router.route(work_item)
        
        assert handler is test_handler

    def test_route_by_capability(self):
        """Router can route by capability."""
        router = AgentRouter()
        
        def test_handler(work_item):
            return {'success': True}
        
        router.register(capability='test.capability', handler=test_handler)
        
        work_item = {'type': 'any', 'capability': 'test.capability'}
        handler = router.route(work_item)
        
        assert handler is test_handler

    def test_route_by_agent_id(self):
        """Router can route by agent ID."""
        router = AgentRouter()
        
        def test_handler(work_item):
            return {'success': True}
        
        router.register(agent_id='my-agent', handler=test_handler)
        
        work_item = {'agentId': 'my-agent'}
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

    def test_context_dict(self):
        """Context can be returned as dict."""
        work_item = {
            'workId': 'test-123',
            'tenantId': 'tenant-1',
            'agentId': 'agent-1',
            'capability': 'test.cap',
            'payload': {'key': 'value'}
        }
        
        context = AgentContext.from_work_item(work_item)
        ctx_dict = context.get_context_dict()
        
        assert isinstance(ctx_dict, dict)
        assert ctx_dict['workId'] == 'test-123'


class TestAgentExecutor:
    """Test Agent Executor."""

    def test_execute_validates(self):
        """Executor validates work items."""
        executor = AgentExecutor()
        
        result = executor.execute({'invalid': 'work'})
        
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
        assert result['error']['type'] == 'NOT_FOUND'

    def test_executor_adds_metrics(self):
        """Executor adds metric to result."""
        router = AgentRouter()
        router.register(work_type='test', handler=lambda w: {'success': True})
        
        executor = AgentExecutor(router=router)
        
        work_item = {
            'workId': 'metric-test',
            'type': 'test',
            'tenantId': 't1',
            'idempotencyKey': 'k1'
        }
        
        result = executor.execute(work_item)
        
        assert 'metrics' in result
        assert 'durationMs' in result['metrics']
        assert result['metrics']['workId'] == 'metric-test'


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
        
        def my_handler(work_item):
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


class TestReferenceAgentIntegration:
    """Test ReferenceAgent with Agent Body."""

    def test_echo_capability_workflow(self):
        """Test reference.echo capability through Agent Body."""
        router = AgentRouter()
        agent = ReferenceAgent()
        router.register(work_type='agent_work', handler=agent.process_work)
        
        executor = AgentExecutor(router=router)
        
        work_item = {
            'workId': 'echo-test-1',
            'type': 'agent_work',
            'tenantId': 'tenant-echo',
            'idempotencyKey': 'echo-key-1',
            'agentId': 'reference_agent',
            'capability': 'reference.echo',
            'payload': {'message': 'test payload'}
        }
        
        result = executor.execute(work_item)
        
        assert result['success'] is True
        assert result['data']['echoed'] == {'message': 'test payload'}
        assert result['data']['workId'] == 'echo-test-1'

    def test_unknown_capability_returns_error(self):
        """Test handling of unknown capability."""
        router = AgentRouter()
        agent = ReferenceAgent()
        router.register(work_type='agent_work', handler=agent.process_work)
        
        executor = AgentExecutor(router=router)
        
        work_item = {
            'workId': 'unknown-cap-test',
            'type': 'agent_work',
            'tenantId': 'tenant-x',
            'idempotencyKey': 'key-x',
            'agentId': 'reference_agent',
            'capability': 'unknown.capability',
            'payload': {}
        }
        
        result = executor.execute(work_item)
        
        assert result['success'] is False
        assert 'error' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])