"""Registry integration for the Addition Agent.

Connects the agent to the EXISTING runtime registry and Agent Body. Selection
stays with the ecosystem (registry/discovery/eligibility/selection); this module
only declares that the agent exists and how it is routed.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from agents.addition_agent.agent import (
    ADDITION_AGENT_ID,
    ADDITION_AGENT_VERSION,
    ADDITION_CAPABILITY,
    ADDITION_WORK_TYPE,
    AdditionAgent,
)
from agents.ecosystem.registry import (
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
    ExecutionProfile,
)

logger = logging.getLogger(__name__)

BODY_VERSION = "1.0.0"
RUNTIME_LAMBDA = "python3.14"


def get_addition_descriptor() -> AgentDescriptor:
    """Descriptor used by registry, discovery and eligibility."""
    return AgentDescriptor(
        agent_id=ADDITION_AGENT_ID,
        name=ADDITION_AGENT_ID,
        version=ADDITION_AGENT_VERSION,
        status=AgentStatus.ACTIVE,
        capabilities=[ADDITION_CAPABILITY],
        supported_bodies=[BODY_VERSION],
        supported_runtimes=[RUNTIME_LAMBDA],
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level="low",
        description=(
            "Deterministischer Additions-Agent (math.add); keine Persistenz, "
            "keine Credentials, keine eigene Queue"
        ),
    )


def register_addition_agent(
    registry: Optional[AgentRegistry] = None,
    body: Any = None,
) -> tuple:
    """Register descriptor and routes in the shared runtime objects.

    Idempotent: re-registration keeps the existing descriptor and only ensures
    the routes exist.
    """
    if registry is None:
        from agents.ecosystem.registry import get_registry

        registry = get_registry()
    if body is None:
        from agents.agent_body import AgentBody

        body = AgentBody()

    if not registry.is_registered(ADDITION_AGENT_ID):
        registry.register(ADDITION_AGENT_ID, get_addition_descriptor())

    agent = AdditionAgent()
    body.register_agent(work_type=ADDITION_WORK_TYPE, handler=agent.process_work)
    body.register_agent(capability=ADDITION_CAPABILITY, handler=agent.process_work)
    body.register_agent(agent_id=ADDITION_AGENT_ID, handler=agent.process_work)

    logger.info(
        "addition agent registered: agentId=%s capability=%s",
        ADDITION_AGENT_ID,
        ADDITION_CAPABILITY,
    )
    return registry, body


def is_addition_registered(registry: Optional[AgentRegistry] = None) -> bool:
    if registry is None:
        from agents.ecosystem.registry import get_registry

        registry = get_registry()
    return registry.is_registered(ADDITION_AGENT_ID)


__all__ = [
    "get_addition_descriptor",
    "register_addition_agent",
    "is_addition_registered",
]
