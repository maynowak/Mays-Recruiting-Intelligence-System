"""
Reference Agent Package

A minimal technical agent that demonstrates the G0.4 Agent API boundary.
This agent provides an echo capability that passes through input unchanged.

NOT a business agent - this is purely for technical demonstration.
"""

from .service import ReferenceAgent

__all__ = ['ReferenceAgent']