"""
Agent Event Hook

Provides the entry point from external events into the Agent Ecosystem.

This module implements:
- Event: The inbound event contract
- ProcessingEnvelope: The internal processing representation
- EventHook: The validation and normalization layer

Usage:
    from agents.ecosystem.event_hook import EventHook, Event, ProcessingEnvelope
    
    hook = EventHook()
    envelope = hook.handle_event(event)
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Supported trigger types for processing events."""
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_STATUS = "ORDER_STATUS"
    PREVIOUS_COMPLETED = "PREVIOUS_COMPLETED"
    EVENT = "EVENT"
    SCHEDULE = "SCHEDULE"
    RETRY = "RETRY"
    MANUAL = "MANUAL"
    CONDITION = "CONDITION"
    DEPENDENCY = "DEPENDENCY"
    HEALTH_HEARTBEAT = "HEALTH_HEARTBEAT"
    HEALTH_DEGRADED = "HEALTH_DEGRADED"
    HEALTH_RECOVERED = "HEALTH_RECOVERED"


@dataclass
class Event:
    """
    Inbound event contract for the agent ecosystem.
    
    This is the standardized format for events entering the ecosystem
    from external sources (May's Orders, Schedule, Manual triggers, etc.)
    """
    event_id: str
    event_type: str
    occurred_at: datetime
    tenant_id: str
    order_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent_id: Optional[str] = None
    
    def __post_init__(self):
        self._validate()
    
    def _validate(self):
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.tenant_id:
            raise ValueError("tenant_id is required")


@dataclass
class ProcessingEnvelope:
    """
    Internal processing envelope for agent workflows.
    
    This separates orders from processing executions, maintaining
    clean identity boundaries while preserving traceability.
    
    Identity separation:
    - order_id: The original order identifier
    - processing_id: Unique processing instance
    - execution_id: Specific agent execution
    - attempt_id: Retry attempt counter
    - parent_id: Traceability to parent processing
    """
    order_id: Optional[str]
    processing_id: str
    execution_id: Optional[str] = None
    attempt_id: Optional[str] = None
    parent_id: Optional[str] = None
    
    trigger_type: Optional[TriggerType] = None
    tenant_id: str = ""
    
    agent_id: Optional[str] = None
    agent_version: Optional[str] = None
    body_id: Optional[str] = None
    body_version: Optional[str] = None
    
    runtime: Optional[str] = None
    execution_profile: Optional[str] = None
    
    input: Dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"
    error: Optional[Dict[str, Any]] = None
    result_reference: Optional[str] = None
    
    sequence: int = 1
    attempt: int = 1


class EventHook:
    """
    Transforms external events into processing envelopes.
    
    The hook performs:
    1. Validation of required fields
    2. Normalization of event types
    3. Identity generation for processing
    4. Conversion to ProcessingEnvelope
    
    This implementation is stateless and deterministic.
    """
    
    VALID_TRIGGER_TYPES = {t.value for t in TriggerType}
    
    def __init__(self, default_body_id: str = "1.0.0"):
        self.default_body_id = default_body_id
    
    def validate(self, event: Event) -> bool:
        """
        Validate an event is ready for processing.
        
        Args:
            event: The event to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if not event.event_id:
                logger.warning("Event validation failed: missing event_id")
                return False
            if not event.event_type:
                logger.warning("Event validation failed: missing event_type")
                return False
            if not event.tenant_id:
                logger.warning("Event validation failed: missing tenant_id")
                return False
            if event.event_type not in self.VALID_TRIGGER_TYPES:
                logger.warning(
                    f"Event validation failed: unknown event_type '{event.event_type}'"
                )
                return False
            return True
        except Exception as e:
            logger.warning(f"Event validation error: {e}")
            return False
    
    def normalize(self, event: Event) -> Event:
        """
        Normalize event fields to standard format.
        
        Args:
            event: The event to normalize
            
        Returns:
            Normalized event (modifies in place)
        """
        event.event_type = event.event_type.upper()
        event.tenant_id = event.tenant_id.strip()
        
        if not event.event_id:
            event.event_id = str(uuid.uuid4())
        
        if event.order_id:
            event.order_id = str(event.order_id).strip()
        
        return event
    
    def create_processing_envelope(
        self, 
        event: Event, 
        execution_id: Optional[str] = None
    ) -> ProcessingEnvelope:
        """
        Create a processing envelope from an event.
        
        Args:
            event: The source event
            execution_id: Optional execution ID (for retries/resume)
            
        Returns:
            ProcessingEnvelope ready for discovery/eligibility
        """
        try:
            trigger_type = TriggerType(event.event_type)
        except ValueError:
            logger.warning(f"Unknown trigger type: {event.event_type}")
            trigger_type = TriggerType.EVENT
        
        envelope = ProcessingEnvelope(
            order_id=event.order_id,
            processing_id=str(uuid.uuid4()),
            execution_id=execution_id or str(uuid.uuid4()),
            tenant_id=event.tenant_id,
            trigger_type=trigger_type,
            agent_id=event.agent_id,
            input=event.payload.copy() if event.payload else {},
        )
        
        logger.info(
            f"Created envelope {envelope.processing_id} "
            f"from event {event.event_id} "
            f"[trigger: {trigger_type.value}]"
        )
        
        return envelope
    
    def handle_event(
        self, 
        event: Event, 
        execution_id: Optional[str] = None
    ) -> ProcessingEnvelope:
        """
        Process an event through validation, normalization, and envelope creation.
        
        Args:
            event: The incoming event
            execution_id: Optional execution context
            
        Returns:
            ProcessingEnvelope for discovery/eligibility
            
        Raises:
            ValueError: If event fails validation
        """
        normalized = self.normalize(event)
        
        if not self.validate(normalized):
            raise ValueError(
                f"Event validation failed: event_id={normalized.event_id}, "
                f"event_type={normalized.event_type}"
            )
        
        return self.create_processing_envelope(normalized, execution_id)


def create_processing_envelope_from_event(
    event: Dict[str, Any],
    default_body_id: str = "1.0.0"
) -> ProcessingEnvelope:
    """
    Convenience function to create envelope from raw event dict.
    
    Args:
        event: Raw event dictionary with standard fields
        default_body_id: Default body version
        
    Returns:
        ProcessingEnvelope ready for ecosystem processing
    """
    hook = EventHook(default_body_id=default_body_id)
    
    processed_event = Event(
        event_id=event.get('event_id', str(uuid.uuid4())),
        event_type=event.get('event_type', 'EVENT'),
        occurred_at=datetime.utcnow(),
        tenant_id=event.get('tenant_id', ''),
        order_id=event.get('order_id'),
        payload=event.get('payload', {}),
        metadata=event.get('metadata', {}),
        agent_id=event.get('agent_id'),
    )
    
    return hook.handle_event(processed_event)