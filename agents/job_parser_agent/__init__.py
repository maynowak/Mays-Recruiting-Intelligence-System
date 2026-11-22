"""Job parser agent package."""

from agents.job_parser_agent.agent import JobParserAgent
from agents.job_parser_agent.registry import (
    get_job_parser_descriptor,
    register_job_parser_agent,
)

__all__ = ["JobParserAgent", "get_job_parser_descriptor",
           "register_job_parser_agent"]
