#!/usr/bin/env python3
"""Dummy Agents A/B — Gate 8 Multi-Agent-Nachweis (DEV/TEST ONLY).

Bewusst triviale fachliche Funktion (Marker + Input-Echo), KEINE externe
API, KEINE AWS-Anbindung, KEINE Mays-Orders-Anbindung. Zweck ausschliesslich:
Ecosystem, Discovery, Eligibility, Selection und Multi-Agent-Execution
mit mehreren gleichzeitig registrierten Agents nachweisen.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agents.base import AgentBase

logger = logging.getLogger(__name__)


class DummyAgentBase(AgentBase):
    """Gemeinsame Dummy-Basis (AgentBase-Contract, kemampuan pro Agent)."""

    AGENT_ID = "dummy-base"
    CAPABILITY = "dummy-base"
    WORK_TYPE = "agent_dummy_base"
    VERSION = "0.0.1-dev"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = self.AGENT_ID
        self.version = self.VERSION

    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        payload = work_item.get("payload", {}) or {}
        logger.info("Dummy %s processing: workId=%s", self.AGENT_ID, work_item.get("workId"))
        return {
            "success": True,
            "data": {
                "processed_by": self.AGENT_ID,
                "capability": self.CAPABILITY,
                "input": payload,
                "workId": work_item.get("workId"),
                "processedAt": datetime.now(timezone.utc).isoformat(),
            },
            "metrics": {
                "durationMs": 0,
                "workId": work_item.get("workId"),
                "agentVersion": self.version,
            },
        }

    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        if not isinstance(work_item, dict):
            return False
        for field in ("workId", "type", "tenantId", "idempotencyKey"):
            if field not in work_item:
                return False
        return work_item.get("capability") == self.CAPABILITY

    def get_status(self, work_id: str, tenant_id: str) -> Dict[str, Any]:
        return {"workId": work_id, "status": "COMPLETED",
                "result": {"processed_by": self.AGENT_ID}}


class DummyAgentA(DummyAgentBase):
    AGENT_ID = "dummy-a"
    CAPABILITY = "dummy-a"
    WORK_TYPE = "agent_dummy_a"


class DummyAgentB(DummyAgentBase):
    AGENT_ID = "dummy-b"
    CAPABILITY = "dummy-b"
    WORK_TYPE = "agent_dummy_b"


def dummy_descriptor(agent_id: str, capability: str, work_type: str):
    from agents.ecosystem.registry import (
        AgentDescriptor, AgentStatus, ExecutionProfile)
    return AgentDescriptor(
        agent_id=agent_id, name=agent_id, version="0.0.1-dev",
        status=AgentStatus.ACTIVE, capabilities=[capability],
        supported_bodies=["1.0.0"], supported_runtimes=["python3.14"],
        execution_profile=ExecutionProfile.LAMBDA, risk_level="low",
        description=f"Gate-8-Dummy-Agent (DEV/TEST ONLY): {capability}",
    )


def register_dummy_agents(registry, body):
    """Beide Dummies in Registry + Body-Router verankern."""
    for cls in (DummyAgentA, DummyAgentB):
        if not registry.is_registered(cls.AGENT_ID):
            registry.register(cls.AGENT_ID,
                              dummy_descriptor(cls.AGENT_ID, cls.CAPABILITY, cls.WORK_TYPE))
        agent = cls()
        body.register_agent(work_type=cls.WORK_TYPE, handler=agent.process_work)
        body.register_agent(capability=cls.CAPABILITY, handler=agent.process_work)
        body.register_agent(agent_id=cls.AGENT_ID, handler=agent.process_work)
    return registry, body


__all__ = ["DummyAgentA", "DummyAgentB", "dummy_descriptor", "register_dummy_agents"]
