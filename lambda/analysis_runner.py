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


def _as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: Any) -> List[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


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
    }


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


def handler(event: Any, context: Any = None,
            runtime: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process WorkItems through the existing runtime pipeline.

    Validation failures are permanent rejections; unexpected failures raise so
    the existing retry/attempt semantics stay unchanged.
    """
    runtime = runtime or build_runtime()
    process = runtime.get("process")
    results: List[Dict[str, Any]] = []
    for message_id, work in _items(event):
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
