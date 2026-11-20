"""Analysis orchestration agent (capability ``analysis.run``).

Thin wrapper around ``AnalysisOrchestrator``. It performs no parsing and no
comparison itself; it validates the WorkItem, resolves identity/entitlements
from configuration (production must inject a resolver) and returns the
requested result bodies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agents.analysis.contracts import ContractError, Identity
from agents.analysis.orchestrator import AnalysisOrchestrator
from agents.base import AgentBase
from agents.parsers.node_adapter import ParserUnavailable

logger = logging.getLogger(__name__)

ANALYSIS_AGENT_ID = "analysis-agent"
ANALYSIS_AGENT_VERSION = "1.0.0"
ANALYSIS_CAPABILITY = "analysis.run"
ANALYSIS_WORK_TYPE = "agent_analysis_agent"


class AnalysisAgent(AgentBase):
    CAPABILITY = ANALYSIS_CAPABILITY

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 orchestrator: Optional[AnalysisOrchestrator] = None,
                 identity_resolver=None):
        super().__init__(config)
        self.name = ANALYSIS_AGENT_ID
        self.version = ANALYSIS_AGENT_VERSION
        self._orchestrator = orchestrator or AnalysisOrchestrator()
        self._identity_resolver = identity_resolver

    @staticmethod
    def _error(message: str, error_type: str) -> Dict[str, Any]:
        return {"success": False,
                "error": {"message": message, "type": error_type}}

    def _identity(self, work_item: Dict[str, Any]) -> Identity:
        if self._identity_resolver is not None:
            return self._identity_resolver(work_item)
        config = self.config or {}
        entitlements = config.get("entitlements")
        if not entitlements:
            # Fail closed: no configured entitlements means no analysis.
            raise ContractError(
                "analysis_identity_not_configured",
                "analysis entitlements are not configured")
        return Identity(
            tenant_id=str(work_item.get("tenantId") or ""),
            user_id=str(work_item.get("userId") or ""),
            entitlements=frozenset(entitlements),
            consent=bool(config.get("consent", False)),
            partner_application_id=work_item.get("partnerApplicationId"),
            issuer=work_item.get("issuer"),
        )

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
        request = payload.get("request") if isinstance(payload.get("request"), dict) \
            else payload
        try:
            identity = self._identity(work_item)
            response = self._orchestrator.run(
                request, identity,
                request_id=work_item.get("workId"))
        except ContractError as exc:
            return self._error(f"{exc.code}: {exc.message}", "ValidationError")
        except ParserUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - runtime boundary
            logger.error("analysis failed: %s", type(exc).__name__)
            raise

        return {
            "success": True,
            "data": response,
            "metrics": {
                "workId": work_item.get("workId"),
                "agentId": work_item.get("agentId") or ANALYSIS_AGENT_ID,
                "agentVersion": self.version,
                "capability": self.CAPABILITY,
                "requestedResults": response.get("requestedResults", []),
            },
        }

    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        if not isinstance(work_item, dict):
            return False
        for field in ("workId", "type", "tenantId", "idempotencyKey"):
            if field not in work_item:
                return False
        if work_item.get("capability") != self.CAPABILITY:
            return False
        return isinstance(work_item.get("payload"), dict)

    def get_status(self, work_id: str, tenant_id: str) -> Dict[str, Any]:
        return {"workId": work_id, "tenantId": tenant_id,
                "status": "COMPLETED",
                "result": {"message": "Analysis agent has no independent state",
                           "agentId": ANALYSIS_AGENT_ID}}


__all__ = ["ANALYSIS_AGENT_ID", "ANALYSIS_AGENT_VERSION",
           "ANALYSIS_CAPABILITY", "ANALYSIS_WORK_TYPE", "AnalysisAgent"]
