"""Registry integration for the CV parser agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

from agents.cv_parser_agent.agent import (
    CV_PARSER_AGENT_ID,
    CV_PARSER_AGENT_VERSION,
    CV_PARSER_CAPABILITY,
    CV_PARSER_WORK_TYPE,
    CvParserAgent,
)
from agents.ecosystem.registry import (
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
    ExecutionProfile,
)

logger = logging.getLogger(__name__)

BODY_VERSION = "1.0.0"


def get_cv_parser_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=CV_PARSER_AGENT_ID,
        name=CV_PARSER_AGENT_ID,
        version=CV_PARSER_AGENT_VERSION,
        status=AgentStatus.ACTIVE,
        capabilities=[CV_PARSER_CAPABILITY],
        supported_bodies=[BODY_VERSION],
        supported_runtimes=["python3.14"],
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level="low",
        description=(
            "Deterministischer CV-Parser-Agent (parse.cv) auf der geteilten "
            "Jobsearch-Parserbibliothek; keine Persistenz, keine Queue"
        ),
    )


def register_cv_parser_agent(
    registry: Optional[AgentRegistry] = None,
    body: Any = None,
    agent: Optional[CvParserAgent] = None,
) -> tuple:
    if registry is None:
        from agents.ecosystem.registry import get_registry

        registry = get_registry()
    if body is None:
        from agents.agent_body import AgentBody

        body = AgentBody()
    if agent is None:
        agent = CvParserAgent()

    if not registry.is_registered(CV_PARSER_AGENT_ID):
        registry.register(CV_PARSER_AGENT_ID, get_cv_parser_descriptor())

    body.register_agent(work_type=CV_PARSER_WORK_TYPE, handler=agent.process_work)
    body.register_agent(capability=CV_PARSER_CAPABILITY, handler=agent.process_work)
    body.register_agent(agent_id=CV_PARSER_AGENT_ID, handler=agent.process_work)
    logger.info("cv parser agent registered: agentId=%s capability=%s",
                CV_PARSER_AGENT_ID, CV_PARSER_CAPABILITY)
    return registry, body


__all__ = ["get_cv_parser_descriptor", "register_cv_parser_agent"]
