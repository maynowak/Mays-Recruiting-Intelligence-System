"""Deterministic CV parser agent (capability ``parse.cv``).

Reuses the shared jobsearch parser library through the Node adapter. No second
CV parser, no persistence, no credentials, no event subscription.
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

CV_PARSER_AGENT_ID = "cv-parser-agent"
CV_PARSER_AGENT_VERSION = "1.0.0"
CV_PARSER_CAPABILITY = "parse.cv"
CV_PARSER_WORK_TYPE = "agent_cv_parser_agent"
MIN_CV_CHARS = 20


class CvParserAgent(AgentBase):
    """RIS agent that parses CV plain text into a structured profile."""

    CAPABILITY = CV_PARSER_CAPABILITY

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 runner=None):
        super().__init__(config)
        self.name = CV_PARSER_AGENT_ID
        self.version = CV_PARSER_AGENT_VERSION
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
        text = payload.get("text")
        if not isinstance(text, str):
            return self._error(
                "Field 'payload.text' must be a string", "ValidationError")
        if len(text) < MIN_CV_CHARS:
            return self._error(
                "Field 'payload.text' is too short", "ValidationError")
        if len(text) > MAX_PAYLOAD_CHARS:
            return self._error(
                "Field 'payload.text' exceeds the parser size limit",
                "ValidationError")

        try:
            result = parse_via_node(
                self.CAPABILITY, {"text": text}, runner=self._runner)
        except ParserInputError as exc:
            return self._error(str(exc), "ValidationError")
        except ParserUnavailable:
            # Retryable: the pipeline persists FAILED and re-raises.
            raise

        work_id = work_item.get("workId")
        logger.info("cv parser processed: workId=%s parserVersion=%s",
                    work_id, result.parser_version)
        return {
            "success": True,
            "data": result.data,
            "confidence": result.confidence,
            "metrics": {
                "workId": work_id,
                "agentId": work_item.get("agentId") or CV_PARSER_AGENT_ID,
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
                logger.warning("cv parser: missing required field %s", field)
                return False
        if work_item.get("capability") != self.CAPABILITY:
            logger.warning("cv parser: unexpected capability %r",
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
                "message": "CV parser agent has no independent state store",
                "agentId": CV_PARSER_AGENT_ID,
            },
        }


__all__ = [
    "CV_PARSER_AGENT_ID",
    "CV_PARSER_AGENT_VERSION",
    "CV_PARSER_CAPABILITY",
    "CV_PARSER_WORK_TYPE",
    "CvParserAgent",
]
