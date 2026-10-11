"""Partner API contract definitions.

These define the request/response shapes for the partner-facing endpoints.
They are used by both the RIS runtime and the Jobsearch server-side integration.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class PartnerExecuteRequest:
    """Request payload for POST /v1/partner/agents/{agentId}/execute."""
    # The JWT from the browser (Cognito Access Token)
    jwt: str
    # Agent-specific input parameters
    input: Dict[str, Any]
    # Optional correlation ID for tracing
    correlation_id: Optional[str] = None


@dataclass
class PartnerExecuteResponse:
    """Response payload for partner agent execution."""
    success: bool
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    correlation_id: Optional[str] = None
    executed_at: Optional[datetime] = None


@dataclass
class PartnerRegistrationRequest:
    """Request payload for creating a partner application (admin only)."""
    cognito_client_id: str
    api_profile_id: str
    tenant_id: str
    name: str
    description: Optional[str] = None


@dataclass
class PartnerRegistrationResponse:
    """Response payload for partner registration."""
    application_id: str
    client_id: str
    status: str
    created_at: datetime


@dataclass
class PartnerListResponse:
    """Response payload for listing partner applications."""
    applications: list
    next_token: Optional[str] = None