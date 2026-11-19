"""CV parser agent package."""

from agents.cv_parser_agent.agent import CvParserAgent
from agents.cv_parser_agent.registry import (
    get_cv_parser_descriptor,
    register_cv_parser_agent,
)

__all__ = ["CvParserAgent", "get_cv_parser_descriptor",
           "register_cv_parser_agent"]
