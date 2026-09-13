"""
Agent Invocation Tests

Tests for the Agent Invocation contract and mechanism.
"""

import pytest
import sys
sys.path.insert(0, '.')

from agents.agent_body.invocation import InvocationContract, AgentInvoker, invoke_agent


class TestInvocationContract:
    """Test the Invocation Contract."""
    
    def test_contract_creation(self):
        """Can create a valid invocation contract."""
        contract = InvocationContract(
            target_agent_id="test-agent",
            capability="test.action",
            payload={"data": "value"}
        )
        
        assert contract.target_agent_id == "test-agent"
        assert contract.capability == "test.action"
        assert contract.payload == {"data": "value"}
    
    def test_contract_to_work_item(self):
        """Contract can be converted to work item."""
        contract = InvocationContract(
            target_agent_id="test-agent",
            capability="test.action",
            payload={"key": "val"},
            tenant_id="tenant-1",
            parent_work_id="parent-123"
        )
        
        work_item = contract.to_work_item()
        
        assert work_item["agentId"] == "test-agent"
        assert work_item["capability"] == "test.action"
        assert work_item["tenantId"] == "tenant-1"
        assert work_item["parentWorkId"] == "parent-123"
        assert work_item["type"] == "invocation_test-agent"
    
    def test_contract_validation(self):
        """Contract validates required fields."""
        contract = InvocationContract(
            capability="test.action"
        )
        
        with pytest.raises(ValueError, match="Must specify target_agent_id or capability"):
            contract._validate()
    
    def test_contract_mode_validation(self):
        """Contract validates mode."""
        contract = InvocationContract(
            target_agent_id="test",
            mode="INVALID"
        )
        
        with pytest.raises(ValueError, match="Invalid mode"):
            contract._validate()


class TestAgentInvoker:
    """Test the Agent Invoker."""
    
    def test_invoke_creates_work_item(self):
        """Invoker can create work item for invocation."""
        invoker = AgentInvoker()
        
        contract = InvocationContract(
            target_agent_id="reference_agent",
            capability="reference.echo",
            payload={"test": "data"}
        )
        
        work_item = contract.to_work_item()
        
        assert "workId" in work_item
        assert work_item["agentId"] == "reference_agent"


class TestInvokeAgent:
    """Test the convenience invoke function."""
    
    def test_invoke_function_exists(self):
        """invoke_agent function is available."""
        assert callable(invoke_agent)


# Integration test with actual agents would go here
# but we don't want to create actual agent-to-agent chains
# for minimal S2.8

if __name__ == '__main__':
    pytest.main([__file__, '-v'])