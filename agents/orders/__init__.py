"""
Development Orders Adapter Package

Provides the adapter interface and development implementation for orders processing.
"""

from agents.orders.adapter import OrdersPort, OrderResult, OrdersResultType
from agents.orders.development import DevelopmentOrdersAdapter, get_development_adapter
from agents.orders.real import (
    RealMaysOrdersAdapter,
    TransientOrdersError,
    DEFAULT_BASE_URL,
)

__all__ = [
    'OrdersPort',
    'OrderResult', 
    'OrdersResultType',
    'DevelopmentOrdersAdapter',
    'get_development_adapter',
    'RealMaysOrdersAdapter',
    'TransientOrdersError',
    'DEFAULT_BASE_URL',
]