"""
Tests for Development Orders Adapter (S2.13)

Tests the DevelopmentOrdersAdapter implementation.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orders import DevelopmentOrdersAdapter, OrderResult, OrdersResultType


class TestDevelopmentOrdersAdapter:
    """Tests for DevelopmentOrdersAdapter."""
    
    def test_port_id(self):
        """Adapter has valid port ID."""
        adapter = DevelopmentOrdersAdapter()
        assert adapter.port_id == "development-orders-adapter"
    
    def test_submit_order_defaults(self):
        """Adapter can submit order with defaults."""
        adapter = DevelopmentOrdersAdapter()
        
        result = adapter.submit_order(
            work_item={
                'workId': 'test-123',
                'type': 'test',
                'tenantId': 'tenant-dev'
            },
            capability='reference.echo',
            payload={'key': 'value'},
            tenant_id='tenant-dev',
            actor_id='user-1',
            idempotency_key='key-123'
        )
        
        assert result.success is True
        assert result.result_type == OrdersResultType.APPROVED
        assert result.order_id == 'key-123'
        assert result.data is not None
    
    def test_submit_order_with_order_id(self):
        """Adapter generates order_id if not provided."""
        adapter = DevelopmentOrdersAdapter()
        
        result = adapter.submit_order(
            work_item={'workId': 'test'},
            capability='reference.echo'
        )
        
        assert result.success is True
        assert result.order_id is not None
    
    def test_get_order_status(self):
        """Adapter can retrieve stored order status."""
        adapter = DevelopmentOrdersAdapter()
        
        result = adapter.submit_order(
            work_item={'workId': 'test'},
            capability='reference.echo',
            idempotency_key='status-key'
        )
        
        status = adapter.get_order_status('status-key')
        assert status == result
    
    def test_get_nonexistent_order(self):
        """Adapter returns None for unknown order."""
        adapter = DevelopmentOrdersAdapter()
        
        status = adapter.get_order_status('nonexistent')
        assert status is None
    
    def test_can_handle_supported(self):
        """Adapter claims supported capability."""
        adapter = DevelopmentOrdersAdapter()
        
        assert adapter.can_handle('reference.echo') is True
    
    def test_can_handle_unsupported(self):
        """Adapter rejects unsupported capability."""
        adapter = DevelopmentOrdersAdapter()
        
        assert adapter.can_handle('unknown.capability') is False
    
    def test_idempotency(self):
        """Adapter handles duplicate idempotency keys."""
        adapter = DevelopmentOrdersAdapter()
        
        result1 = adapter.submit_order(
            work_item={'workId': 'test-1'},
            capability='reference.echo',
            idempotency_key='dup-key'
        )
        
        result2 = adapter.submit_order(
            work_item={'workId': 'test-2'},
            capability='reference.echo',
            idempotency_key='dup-key'
        )
        
        assert result1.order_id == result2.order_id


class TestOrderResult:
    """Tests for OrderResult dataclass."""
    
    def test_create_approved_result(self):
        """Can create approved result."""
        result = OrderResult(
            success=True,
            order_id='order-123',
            result_type=OrdersResultType.APPROVED,
            reason='Approved',
            data={'processed': True}
        )
        
        assert result.success is True
        assert result.order_id == 'order-123'
    
    def test_create_rejected_result(self):
        """Can create rejected result."""
        result = OrderResult(
            success=False,
            result_type=OrdersResultType.REJECTED,
            reason='Invalid request'
        )
        
        assert result.success is False
        assert result.result_type == OrdersResultType.REJECTED


if __name__ == '__main__':
    pytest.main([__file__, '-v'])