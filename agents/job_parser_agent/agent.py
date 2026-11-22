"""Deterministic job-ad parser agent (capability ``parse.job``).

Reuses the shared jobsearch ATS/parser library through the Node adapter. No
second parser engine, no persistence, no credentials, no event subscription.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agents.base import AgentBase
from agents.parsers.node_adapter import (
    MAX_PAYLOAD_CHARS,
    ParserInputError,
    ParserUnavailable,
    parse_via_node,
)

logger = logging.getLogger(__name__)

JOB_PARSER_AGENT_ID = "job-parser-agent"
JOB_PARSER_AGENT_VERSION = "1.0.0"
JOB_PARSER_CAPABILITY = "parse.job"
JOB_PARSER_WORK_TYPE = "agent_job_parser_agent"


class JobParserAgent(AgentBase):
    """RIS agent that parses a job posting into structured requirements."""

    CAPABILITY = JOB_PARSER_CAPABILITY

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 runner=None):
        super().__init__(config)
        self.name = JOB_PARSER_AGENT_ID
        self.version = JOB_PARSER_AGENT_VERSION
        self._runner = runner

    @staticmethod
    def _error(message: str, error_type: str) -> Dict[str, Any]:
        return {"success": False,
                "error": {"message": message, "type": error_type}}

    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(work_item, dict):
            return self._error("Work item must be an object", "ValidationError")
        capability = work_item.get("capability") or self.CAPABILITY
        if capability != self.CAPABILITY:
            return self._error(
                f"Unknown capability: {capability}", "ValidationError")

        payload = work_item.get("payload")
        if not isinstance(payload, dict):
            return self._error(
                "Field 'payload' must be an object", "ValidationError")
        job = payload.get("job")
        if not isinstance(job, dict):
            return self._error(
                "Field 'payload.job' must be an object", "ValidationError")
        title = job.get("title")
        description = job.get("descriptionPlain")
        if not isinstance(title, str) and not isinstance(description, str):
            return self._error(
                "Field 'payload.job' needs a title or descriptionPlain",
                "ValidationError")
        if isinstance(description, str) and len(description) > MAX_PAYLOAD_CHARS:
            return self._error(
                "Field 'payload.job.descriptionPlain' exceeds the parser size "
                "limit", "ValidationError")

        try:
            result = parse_via_node(
                self.CAPABILITY, {"job": job}, runner=self._runner)
        except ParserInputError as exc:
            return self._error(str(exc), "ValidationError")
        except ParserUnavailable:
            raise

        work_id = work_item.get("workId")
        logger.info("job parser processed: workId=%s parserVersion=%s",
                    work_id, result.parser_version)
        return {
            "success": True,
            "data": result.data,
            "confidence": result.confidence,
            "metrics": {
                "workId": work_id,
                "agentId": work_item.get("agentId") or JOB_PARSER_AGENT_ID,
                "agentVersion": self.version,
                "capability": self.CAPABILITY,
                "parserVersion": result.parser_version,
                "stableId": result.data.get("stableId"),
            },
        }

    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        if not isinstance(work_item, dict):
            return False
        for field in ("workId", "type", "tenantId", "idempotencyKey"):
            if field not in work_item:
                logger.warning("job parser: missing required field %s", field)
                return False
        if work_item.get("capability") != self.CAPABILITY:
            logger.warning("job parser: unexpected capability %r",
                           work_item.get("capability"))
            return False
        return isinstance(work_item.get("payload"), dict)

    def get_status(self, work_id: str, tenant_id: str) -> Dict[str, Any]:
        """Status is owned by the runtime, not by this agent."""
        return {
            "workId": work_id,
            "tenantId": tenant_id,
            "status": "COMPLETED",
            "result": {
                "message": "Job parser agent has no independent state store",
                "agentId": JOB_PARSER_AGENT_ID,
            },
        }


__all__ = [
    "JOB_PARSER_AGENT_ID",
    "JOB_PARSER_AGENT_VERSION",
    "JOB_PARSER_CAPABILITY",
    "JOB_PARSER_WORK_TYPE",
    "JobParserAgent",
]
