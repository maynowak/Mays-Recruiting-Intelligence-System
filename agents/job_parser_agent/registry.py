"""Registry integration for the job parser agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

from agents.ecosystem.registry import (
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
    ExecutionProfile,
)
from agents.job_parser_agent.agent import (
    JOB_PARSER_AGENT_ID,
    JOB_PARSER_AGENT_VERSION,
    JOB_PARSER_CAPABILITY,
    JOB_PARSER_WORK_TYPE,
    JobParserAgent,
)

logger = logging.getLogger(__name__)

BODY_VERSION = "1.0.0"


def get_job_parser_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=JOB_PARSER_AGENT_ID,
        name=JOB_PARSER_AGENT_ID,
        version=JOB_PARSER_AGENT_VERSION,
        status=AgentStatus.ACTIVE,
        capabilities=[JOB_PARSER_CAPABILITY],
        supported_bodies=[BODY_VERSION],
        supported_runtimes=["python3.14"],
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level="low",
        description=(
            "Deterministischer Stellenanzeigen-Parser (parse.job) auf der "
            "geteilten Jobsearch-ATS-Parserbibliothek; keine Persistenz"
        ),
    )


def register_job_parser_agent(
    registry: Optional[AgentRegistry] = None,
    body: Any = None,
    agent: Optional[JobParserAgent] = None,
) -> tuple:
    if registry is None:
        from agents.ecosystem.registry import get_registry

        registry = get_registry()
    if body is None:
        from agents.agent_body import AgentBody

        body = AgentBody()
    if agent is None:
        agent = JobParserAgent()

    if not registry.is_registered(JOB_PARSER_AGENT_ID):
        registry.register(JOB_PARSER_AGENT_ID, get_job_parser_descriptor())

    body.register_agent(work_type=JOB_PARSER_WORK_TYPE, handler=agent.process_work)
    body.register_agent(capability=JOB_PARSER_CAPABILITY, handler=agent.process_work)
    body.register_agent(agent_id=JOB_PARSER_AGENT_ID, handler=agent.process_work)
    logger.info("job parser agent registered: agentId=%s capability=%s",
                JOB_PARSER_AGENT_ID, JOB_PARSER_CAPABILITY)
    return registry, body


__all__ = ["get_job_parser_descriptor", "register_job_parser_agent"]
