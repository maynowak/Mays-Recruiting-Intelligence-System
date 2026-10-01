#!/usr/bin/env python3
"""JobSearch Domain Agent — Delegation an bestehendes Repository (Gate 9).

KEINE Fachlogik-Duplikate: CRUD via jobsearch.repository.JobSearchRepository
(Tenant-/User-Isolation dort), Modelle via jobsearch.domain_models. KEINE
Runtime-Verantwortung (kein SQS/Retry/DLQ/Auswahl). KEIN OrdersPort (der
Use-Case braucht keinen Order-Aufruf — wie ATS Gate 7: NOT USED).

Capabilities: jobsearch.create / jobsearch.get / jobsearch.list.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

JOBSEARCH_AGENT_ID = "jobsearch-agent"
JOBSEARCH_WORK_TYPE = "agent_jobsearch"
JOBSEARCH_CAPABILITIES = ("jobsearch.create", "jobsearch.get", "jobsearch.list")


def _repository(table_name: Optional[str] = None, dynamodb: Any = None):
    from jobsearch.repository import JobSearchRepository
    return JobSearchRepository(
        table_name=table_name or os.environ.get("JOBSEARCH_TABLE"),
        dynamodb=dynamodb,
    )


def _user_context(work_item: Dict[str, Any]) -> tuple:
    user_id = work_item.get("userId") or (work_item.get("payload", {}) or {}).get("userId")
    tenant_id = work_item.get("tenantId", "")
    return user_id, tenant_id


def process_jobsearch_work(work_item: Dict[str, Any],
                           repository_factory: Optional[Callable] = None) -> Dict[str, Any]:
    """WorkItem -> Repository -> Agent-Result (reine Delegation)."""
    from jobsearch.domain_models import (
        ATSSearchProfile, JobSearchStatus, SearchConfiguration, create_job_search)

    capability = work_item.get("capability", "jobsearch.get")
    payload = work_item.get("payload", {}) or {}
    # Engine-Wrap (Muster Gate 6/7): eine Ebene entpacken.
    if "name" not in payload and "jobSearchId" not in payload and "status" not in payload:
        inner = payload.get("payload")
        if isinstance(inner, dict):
            payload = inner
    user_id, tenant_id = _user_context(work_item)
    if not user_id or not tenant_id:
        return {"success": False, "agentId": JOBSEARCH_AGENT_ID,
                "error": {"message": "userId/tenantId fehlt", "type": "VALIDATION_ERROR"}}
    repo = repository_factory() if repository_factory else _repository()
    logger.info("JobSearchFunction: workId=%s capability=%s user=%s",
                work_item.get("workId"), capability, user_id)

    if capability == "jobsearch.create":
        name = payload.get("name")
        if not name:
            return {"success": False, "agentId": JOBSEARCH_AGENT_ID,
                    "error": {"message": "payload.name fehlt", "type": "VALIDATION_ERROR"}}
        search = create_job_search(
            job_search_id=payload.get("jobSearchId") or f"js_{uuid.uuid4().hex[:12]}",
            user_id=user_id, tenant_id=tenant_id, name=name,
            search_configuration=SearchConfiguration.from_dict(
                payload.get("searchConfiguration", {})),
            ats_search_profile=ATSSearchProfile.from_dict(
                payload.get("atsSearchProfile", {})),
            metadata=payload.get("metadata", {}))
        if not repo.save(search):
            return {"success": False, "agentId": JOBSEARCH_AGENT_ID,
                    "error": {"message": "Speichern fehlgeschlagen", "type": "PERSISTENCE_ERROR"}}
        return {"success": True, "agentId": JOBSEARCH_AGENT_ID,
                "data": {"jobSearch": search.to_dict(), "workId": work_item.get("workId")}}

    if capability == "jobsearch.get":
        job_search_id = payload.get("jobSearchId")
        if not job_search_id:
            return {"success": False, "agentId": JOBSEARCH_AGENT_ID,
                    "error": {"message": "payload.jobSearchId fehlt", "type": "VALIDATION_ERROR"}}
        found = repo.get(job_search_id, user_id, tenant_id)
        if found is None:
            return {"success": False, "agentId": JOBSEARCH_AGENT_ID,
                    "error": {"message": f"JobSearch {job_search_id} nicht gefunden",
                              "type": "NOT_FOUND"}}
        return {"success": True, "agentId": JOBSEARCH_AGENT_ID,
                "data": {"jobSearch": found.to_dict(), "workId": work_item.get("workId")}}

    if capability == "jobsearch.list":
        items = repo.list_by_user(user_id, tenant_id, payload.get("status"))
        return {"success": True, "agentId": JOBSEARCH_AGENT_ID,
                "data": {"jobSearches": [i.to_dict() for i in items],
                         "count": len(items), "workId": work_item.get("workId")}}

    return {"success": False, "agentId": JOBSEARCH_AGENT_ID,
            "error": {"message": f"Unsupported capability: {capability}",
                      "type": "UnsupportedCapability"}}


def jobsearch_descriptor():
    from agents.ecosystem.registry import (
        AgentDescriptor, AgentStatus, ExecutionProfile)
    return AgentDescriptor(
        agent_id=JOBSEARCH_AGENT_ID, name="jobsearch-agent", version="1.0.0",
        status=AgentStatus.ACTIVE,
        capabilities=list(JOBSEARCH_CAPABILITIES),
        supported_bodies=["1.0.0"], supported_runtimes=["python3.14"],
        execution_profile=ExecutionProfile.LAMBDA, risk_level="low",
        description="Persistenter JobSearch-Domain-Agent (Delegation ans Repository)",
    )


def register_jobsearch_agent(registry, body, handler=None):
    """Agent in Registry + Body-Router verankern (Auswahl bleibt Ecosystem)."""
    if not registry.is_registered(JOBSEARCH_AGENT_ID):
        registry.register(JOBSEARCH_AGENT_ID, jobsearch_descriptor())
    fn = handler or process_jobsearch_work
    body.register_agent(work_type=JOBSEARCH_WORK_TYPE, handler=fn)
    for cap in JOBSEARCH_CAPABILITIES:
        body.register_agent(capability=cap, handler=fn)
    body.register_agent(agent_id=JOBSEARCH_AGENT_ID, handler=fn)
    return registry, body


__all__ = ["process_jobsearch_work", "jobsearch_descriptor",
           "register_jobsearch_agent", "JOBSEARCH_AGENT_ID",
           "JOBSEARCH_WORK_TYPE", "JOBSEARCH_CAPABILITIES"]
