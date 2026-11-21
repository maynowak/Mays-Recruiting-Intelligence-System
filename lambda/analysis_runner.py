"""Dedicated internal analysis Lambda.

A separate compute identity for the internal partner ``ris-internal-analysis``.
It reuses the existing WorkItem, entitlement and result-persistence contracts
through ``agents.runtime.pipeline`` and registers only the AnalysisAgent on the
existing AgentBody.

Contract:
    event = {workId, type, tenantId, idempotencyKey, ...}  (direct WorkItem)
          | {"workItem": {...}}
          | {"Records": [SQS record, ...]}

No public HTTP endpoint, no second queue system and no shared transport policy.

Fail-closed configuration: entitlements, consent and notice approval are
environment values that default to empty/false. A deployment without explicit
operator values performs no analysis.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

PERMANENT_ERRORS = (ValueError,)

#: The dedicated function executes analysis WorkItems only.
ANALYSIS_AGENT_ID = "analysis-agent"
ANALYSIS_CAPABILITY = "analysis.run"
ANALYSIS_WORK_TYPE = "agent_analysis_agent"


def _is_analysis_work(work: Dict[str, Any]) -> bool:
    """Reject every non-analysis WorkItem before the runtime pipeline.

    The pipeline also registers existing ecosystem agents (including the
    Mays-Orders function); the dedicated analysis compute must never be used
    to execute order work.
    """
    if work.get("type") != ANALYSIS_WORK_TYPE:
        return False
    if work.get("capability") != ANALYSIS_CAPABILITY:
        return False
    agent_id = work.get("agentId")
    return agent_id in (None, "", ANALYSIS_AGENT_ID)


def _as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: Any) -> List[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _synthetic_profile(env: Dict[str, str]) -> Dict[str, Any]:
    """Exact-match synthetic test profile; disabled on any ambiguity."""
    enabled = _as_bool(env.get("ANALYSIS_SYNTHETIC_MODE"))
    if not enabled:
        return {"enabled": False}
    fields = {
        "tenant_id": (env.get("ANALYSIS_SYNTHETIC_TENANT_ID") or "").strip(),
        "user_id": (env.get("ANALYSIS_SYNTHETIC_USER_ID") or "").strip(),
        "partner_application_id": (
            env.get("ANALYSIS_SYNTHETIC_PARTNER_APPLICATION_ID") or "").strip(),
        "issuer": (env.get("ANALYSIS_SYNTHETIC_ISSUER") or "").strip(),
    }
    installation = (env.get("ANALYSIS_SYNTHETIC_INSTALLATION") or "").strip()
    project = (env.get("PROJECT_NAME") or "").strip()
    entitlements = _as_list(env.get("ANALYSIS_SYNTHETIC_ENTITLEMENTS"))
    expires_raw = (env.get("ANALYSIS_SYNTHETIC_EXPIRES_AT") or "").strip()
    if (installation != "ris-dev2" or project != "ris-dev2"
            or not all(fields.values()) or not entitlements or not expires_raw):
        return {"enabled": False, "reason": "incomplete_or_wrong_installation"}
    try:
        from datetime import datetime, timezone

        expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return {"enabled": False, "reason": "expired"}
    except ValueError:
        return {"enabled": False, "reason": "invalid_expiry"}
    return {
        "enabled": True,
        **fields,
        "entitlements": entitlements,
        "expires_at": expires.isoformat(),
    }


def analysis_config_from_env(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Explicit, approval-driven analysis configuration (defaults deny)."""
    env = env or os.environ
    from agents.analysis.contracts import (
        ANALYSIS_CONSENT_PURPOSE,
        ANALYSIS_NOTICE_VERSION,
    )

    return {
        "entitlements": _as_list(env.get("ANALYSIS_ENTITLEMENTS")),
        "consent": _as_bool(env.get("ANALYSIS_CONSENT")),
        "consent_notice_approved": _as_bool(
            env.get("ANALYSIS_NOTICE_APPROVED")),
        "caller_partner_id": env.get("ANALYSIS_CALLER_PARTNER_ID",
                                     "ris-internal"),
        "consent_purpose": env.get("ANALYSIS_CONSENT_PURPOSE",
                                   ANALYSIS_CONSENT_PURPOSE),
        "consent_notice_version": env.get("ANALYSIS_NOTICE_VERSION",
                                          ANALYSIS_NOTICE_VERSION),
        "synthetic": _synthetic_profile(env),
    }


def _build_synthetic_verifier(env: Dict[str, str]):
    """Verify the synthetic identity against the persisted RUNNING WorkItem.

    The event payload is not authoritative. Only a row written by the trusted
    ingress/worker with the same identity and status RUNNING authorizes the
    synthetic profile.
    """
    table_name = (env.get("WORK_ITEMS_TABLE") or "").strip()
    if not table_name:
        return None
    try:
        import boto3

        table = boto3.resource("dynamodb").Table(table_name)
    except Exception:  # noqa: BLE001 - fail closed
        return None

    def verify(work_id: str, identity: Dict[str, str]) -> bool:
        if not work_id:
            return False
        try:
            item = table.get_item(
                Key={"workId": work_id}, ConsistentRead=True).get("Item")
        except Exception:  # noqa: BLE001 - fail closed
            return False
        if not isinstance(item, dict) or item.get("status") != "RUNNING":
            return False
        return all(
            str(item.get(field) or "") == identity[field]
            for field in ("tenantId", "userId", "partnerApplicationId",
                          "issuer")
        ) and all(identity[field] for field in
                  ("tenant_id", "user_id", "partner_application_id",
                   "issuer"))

    return verify


def build_orchestrator(env: Optional[Dict[str, str]] = None) -> Any:
    from agents.analysis.cv_bridge import build_cv_resolver
    from agents.analysis.job_store import S3JobStore
    from agents.analysis.orchestrator import AnalysisOrchestrator, NodeParser

    env = env or os.environ
    bucket = env.get("ANALYSIS_JOBS_BUCKET", "").strip()
    job_store = S3JobStore(bucket) if bucket else None
    parser = NodeParser(
        mode=env.get("RIS_PARSER_MODE", "lambda"),
        function_name=env.get("RIS_PARSER_FUNCTION") or None,
        timeout=int(env.get("RIS_PARSER_TIMEOUT_SECONDS", "15")),
    )
    # Defaults stay lazy: documents bucket + partner profile table from env.
    return AnalysisOrchestrator(
        parser=parser,
        cv_resolver=build_cv_resolver({}),
        job_store=job_store,
    )


def build_runtime(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """AgentBody/registry wired with only the configured analysis agent."""
    from agents.agent_body import AgentBody
    from agents.analysis_agent.agent import AnalysisAgent
    from agents.analysis_agent.registry import register_analysis_agent
    from agents.ecosystem.registry import AgentRegistry
    from agents.runtime.pipeline import process_record

    env = env or os.environ
    registry = AgentRegistry()
    body = AgentBody()
    agent = AnalysisAgent(analysis_config_from_env(env),
                          orchestrator=build_orchestrator(env))
    register_analysis_agent(registry, body, agent=agent)

    resolver = None
    table = env.get("ENTITLEMENTS_TABLE", "").strip()
    if table:
        from agents.ecosystem.worker_authorization import (
            DynamoDBEntitlementResolver,
        )

        resolver = DynamoDBEntitlementResolver(table_name=table)

    return {
        "registry": registry,
        "body": body,
        "entitlement_resolver": resolver,
        "analysis_agent": agent,
        "process": process_record,
    }


def _items(event: Any) -> Iterator[Tuple[Optional[str], Dict[str, Any]]]:
    if not isinstance(event, dict):
        raise ValueError("analysis event must be an object")
    if isinstance(event.get("Records"), list):
        for record in event["Records"]:
            body = record.get("body") or "{}"
            work = json.loads(body) if isinstance(body, str) else body
            if not isinstance(work, dict):
                raise ValueError("SQS body is not a WorkItem object")
            yield record.get("messageId"), work
        return
    if isinstance(event.get("workItem"), dict):
        yield event.get("messageId"), event["workItem"]
        return
    if "workId" in event:
        yield event.get("messageId"), event
        return
    raise ValueError("analysis event carries no WorkItem")


def _execute_agent(work: Any) -> Dict[str, Any]:
    """Execution-only entrypoint used by the shared worker adapter.

    No WorkItem registration, no attempt/retry, no result transport: the
    worker owns those. The function only runs the analysis agent.
    """
    from agents.analysis_agent.agent import AnalysisAgent

    if not isinstance(work, dict):
        return {"success": False,
                "error": {"message": "work item must be an object",
                          "type": "ValidationError"}}
    if not _is_analysis_work(work):
        logger.warning("analysis work rejected: work_type_not_allowed")
        return {"success": False,
                "error": {"message": "analysis work type required",
                          "type": "ValidationError"}}
    config = analysis_config_from_env()
    config["synthetic_verifier"] = _build_synthetic_verifier(os.environ)
    agent = AnalysisAgent(config, orchestrator=build_orchestrator())
    return agent.process_work(work)


def handler(event: Any, context: Any = None,
            runtime: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process WorkItems through the existing runtime pipeline.

    ``executionMode == "agent"`` runs only the agent function for the shared
    worker (no WorkItem state, no result transport). Otherwise the standalone
    runner path manages WorkItem persistence itself.
    """
    if isinstance(event, dict) and event.get("executionMode") == "agent":
        return _execute_agent(event.get("workItem"))

    runtime = runtime or build_runtime()
    process = runtime.get("process")
    results: List[Dict[str, Any]] = []
    for message_id, work in _items(event):
        if not _is_analysis_work(work):
            logger.warning("analysis work rejected: work_type_not_allowed")
            results.append({"workId": work.get("workId"),
                            "status": "REJECTED",
                            "reason": "work_type_not_allowed"})
            continue
        record = {"body": json.dumps(work)}
        if message_id:
            record["messageId"] = message_id
        try:
            results.append(process(
                record,
                table=runtime.get("table"),
                registry=runtime.get("registry"),
                body=runtime.get("body"),
                entitlement_resolver=runtime.get("entitlement_resolver"),
                analysis_agent=runtime.get("analysis_agent"),
            ))
        except PERMANENT_ERRORS as exc:
            logger.warning("analysis work rejected: %s",
                           type(exc).__name__)
            results.append({"workId": work.get("workId"),
                            "status": "REJECTED",
                            "reason": type(exc).__name__})
    return {"processed": len(results), "results": results}


__all__ = ["analysis_config_from_env", "build_orchestrator", "build_runtime",
           "handler"]
