"""Registry integration for the analysis orchestration agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

from agents.analysis_agent.agent import (
    ANALYSIS_AGENT_ID,
    ANALYSIS_AGENT_VERSION,
    ANALYSIS_CAPABILITY,
    ANALYSIS_WORK_TYPE,
    AnalysisAgent,
)
from agents.ecosystem.registry import (
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
    ExecutionProfile,
)

logger = logging.getLogger(__name__)
BODY_VERSION = "1.0.0"


def get_analysis_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=ANALYSIS_AGENT_ID,
        name=ANALYSIS_AGENT_ID,
        version=ANALYSIS_AGENT_VERSION,
        status=AgentStatus.ACTIVE,
        capabilities=[ANALYSIS_CAPABILITY],
        supported_bodies=[BODY_VERSION],
        supported_runtimes=["python3.14"],
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level="low",
        description=(
            "Dünne Analyse-Orchestrierung (analysis.run): CV-, Job-, ATS-Tags "
            "und deterministischer Vergleich über die vorhandenen Parser"
        ),
    )


def register_analysis_agent(registry: Optional[AgentRegistry] = None,
                            body: Any = None,
                            agent: Optional[AnalysisAgent] = None) -> tuple:
    if registry is None:
        from agents.ecosystem.registry import get_registry

        registry = get_registry()
    if body is None:
        from agents.agent_body import AgentBody

        body = AgentBody()
    if agent is None:
        agent = AnalysisAgent()
    if not registry.is_registered(ANALYSIS_AGENT_ID):
        registry.register(ANALYSIS_AGENT_ID, get_analysis_descriptor())
    body.register_agent(work_type=ANALYSIS_WORK_TYPE, handler=agent.process_work)
    body.register_agent(capability=ANALYSIS_CAPABILITY, handler=agent.process_work)
    body.register_agent(agent_id=ANALYSIS_AGENT_ID, handler=agent.process_work)
    logger.info("analysis agent registered: agentId=%s capability=%s",
                ANALYSIS_AGENT_ID, ANALYSIS_CAPABILITY)
    return registry, body


__all__ = ["get_analysis_descriptor", "register_analysis_agent"]
