"""
Development Orders Adapter

A development-stage adapter that provides controlled order processing
without requiring live May's Orders infrastructure.

This adapter:
- Is deterministic and local
- Does not require AWS services
- Does not call real May's Orders
- Provides basic order/result handling for development

Usage (Development - Local Testing):
    from agents.orders import DevelopmentOrdersAdapter
    
    adapter = DevelopmentOrdersAdapter()
    result = adapter.submit_order(work_item, capability="reference.echo", ...)

USAGE (Later Production):
    from agents.orders import RealMaysOrdersAdapter
    
    adapter = RealMaysOrdersAdapter(mays_orders_endpoint="...")
    result = adapter.submit_order(work_item, capability="...", ...)

The Agent code need not change - only the adapter implementation.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

import sys
sys.path.insert(0, '.')

from agents.orders.adapter import OrdersPort, OrderResult, OrdersResultType

logger = logging.getLogger(__name__)


class DevelopmentOrdersAdapter(OrdersPort):
    """
    Development Orders Adapter for local testing and development.
    
    This adapter provides controlled processing without:
    - External service dependencies
    - AWS infrastructure requirements
    - Real May's Orders calls
    
    It is intended for development purposes only and should be replaced
    with RealMaysOrdersAdapter in production.
    """
    
    def __init__(
        self,
        auto_approve: bool = True,
        simulate_delay: float = 0.0,
        simulate_failure_rate: float = 0.0
    ):
        """
        Initialize Development Orders Adapter.
        
        Args:
            auto_approve: If True, auto-approve orders. If False, requires manual check.
            simulate_delay: Artificial delay in seconds for testing timing.
            simulate_failure_rate: Failure rate for testing (0.0 to 1.0).
        """
        self._port_id = "development-orders-adapter"
        self._auto_approve = auto_approve
        self._simulate_delay = simulate_delay
        self._simulate_failure_rate = simulate_failure_rate
        self._orders: Dict[str, OrderResult] = {}
        self._supported_capabilities = [
            "reference.echo",
            # Future: Add more capabilities as they're defined
        ]
    
    @property
    def port_id(self) -> str:
        """Return unique identifier for this adapter."""
        return self._port_id
    
    def submit_order(
        self,
        work_item: Dict[str, Any],
        capability: str,
        payload: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> OrderResult:
        """
        Submit a processing request to development orders system.
        
        DEVELOPMENT IMPLEMENTATION:
        - Creates order record locally
        - Applies configurable delay
        - Optionally simulates failures
        - Auto-approves based on configuration
        
        Args:
            work_item: The work item being processed
            capability: The capability/operation requested
            payload: Input data (used for processing result)
            tenant_id: Tenant context (logged for traceability)
            actor_id: Requesting actor identity
            idempotency_key: For duplicate detection
            
        Returns:
            OrderResult with approval/rejection status
        """
        order_id = idempotency_key or str(uuid.uuid4())
        work_id = work_item.get('workId', 'unknown') if work_item else 'unknown'
        
        logger.info(
            f"DevelopmentOrdersAdapter.submit: "
            f"workId={work_id}, capability={capability}, "
            f"order_id={order_id}, tenant={tenant_id}"
        )
        
        # Check for duplicate processing
        if idempotency_key and idempotency_key in self._orders:
            logger.warning(f"Duplicate order detected: {idempotency_key}")
            return self._orders[idempotency_key]
        
        # Simulate optional delay
        if self._simulate_delay > 0:
            time.sleep(self._simulate_delay)
        
        # Simulate optional failures
        if self._simulate_failure_rate > 0:
            import random
            if random.random() < self._simulate_failure_rate:
                result = OrderResult(
                    success=False,
                    order_id=order_id,
                    result_type=OrdersResultType.ERROR,
                    reason="Simulated failure",
                    data=None
                )
                self._orders[order_id] = result
                return result
        
        # Determine result
        if self._auto_approve:
            result = OrderResult(
                success=True,
                order_id=order_id,
                result_type=OrdersResultType.APPROVED,
                reason="Auto-approved in development mode",
                data={
                    'timestamp': datetime.utcnow().isoformat(),
                    'work_id': work_id,
                    'capability': capability,
                    'tenant_id': tenant_id,
                    'actor_id': actor_id
                }
            )
        else:
            result = OrderResult(
                success=False,
                order_id=order_id,
                result_type=OrdersResultType.PENDING,
                reason="Manual approval required",
                data={'work_id': work_id}
            )
        
        # Store for traceability
        self._orders[order_id] = result
        
        logger.info(f"DevelopmentOrdersAdapter: order {order_id} -> {result.result_type.value}")
        
        return result
    
    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        """Get status of an order from development storage."""
        return self._orders.get(order_id)
    
    def can_handle(self, capability: str) -> bool:
        """Check if this adapter handles the given capability."""
        return capability in self._supported_capabilities


# Global development adapter instance
_dev_adapter = None


def get_development_adapter() -> DevelopmentOrdersAdapter:
    """Get the global development adapter instance."""
    global _dev_adapter
    if _dev_adapter is None:
        _dev_adapter = DevelopmentOrdersAdapter()
    return _dev_adapter


__all__ = [
    'DevelopmentOrdersAdapter',
    'get_development_adapter'
]