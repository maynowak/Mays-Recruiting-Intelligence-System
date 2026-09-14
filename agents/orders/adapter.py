"""
Orders Adapter Pattern

Provides a pluggable adapter interface for order/processing systems.

This module defines the contract for adapters that connect agent
invocations to external processing systems.

Usage:
    from agents.orders.adapter import OrdersPort, OrdersAdapter

    # For development:
    adapter = DevelopmentOrdersAdapter()

    # Later for production:
    adapter = RealMaysOrdersAdapter()

The agent code remains unchanged - only the adapter implementation changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum


class OrdersResultType(Enum):
    """Result types from orders processing."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    ERROR = "ERROR"


@dataclass
class OrderResult:
    """Result from order processing."""
    success: bool
    order_id: Optional[str] = None
    result_type: Optional[OrdersResultType] = None
    reason: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class OrdersPort(ABC):
    """
    Port for orders processing systems.
    
    This is the interface that agents depend on, not implementation details.
    Implementation can be Development adapter or Real May's Orders connector.
    """
    
    @property
    @abstractmethod
    def port_id(self) -> str:
        """Return unique identifier for this orders port."""
        pass
    
    @abstractmethod
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
        Submit a processing request to the orders system.
        
        Args:
            work_item: The work item being processed
            capability: The capability/operation requested
            payload: Input data for the order
            tenant_id: Tenant context for isolation
            actor_id: Identity of requesting actor
            idempotency_key: Key for duplicate prevention
            
        Returns:
            OrderResult with status and metadata
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        """Get status of an order."""
        pass
    
    def can_handle(self, capability: str) -> bool:
        """
        Check if this port can handle the given capability.
        
        Override in subclasses to declare supported capabilities.
        """
        return True


__all__ = ['OrdersPort', 'OrderResult', 'OrdersResultType']