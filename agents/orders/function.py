#!/usr/bin/env python3
"""Orders Agent Function — Delegation an den OrdersPort (Gate 6).

KEIN Domain-Agent (keine Fachlogik): mappt WorkItem auf Port-Operationen
und Port-Result auf Agent-Result. Welche Implementierung hinter dem Port
steht (Development/Real), entscheidet die Verdrahtung, nicht der Agent.

Capabilities: orders.create / orders.status / orders.cancel.
Token: (work_item["auth"] or {}).get("idToken") — Test-/Service-Token,
  wird NIE geloggt; Basis-URL via ORDERS_BASE_URL (Default: eigene API).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional

from agents.orders.real import (
    CAPABILITY_CANCEL,
    CAPABILITY_CREATE,
    CAPABILITY_STATUS,
    DEFAULT_BASE_URL,
    RealMaysOrdersAdapter,
    TransientOrdersError,
)

logger = logging.getLogger(__name__)

ORDERS_AGENT_ID = "orders_function"
ORDERS_WORK_TYPE = "agent_orders"
ORDERS_CAPABILITIES = (CAPABILITY_CREATE, CAPABILITY_STATUS, CAPABILITY_CANCEL)


def _payload(work_item: Dict[str, Any]) -> Dict[str, Any]:
    """Payload normalisieren (Engine-Pfad wrappt einmal: payload.payload).

    Belegt live (Gate 6): Agent sieht Contract-WorkItem, dessen payload das
    Original-WorkItem ist. Ein Level entpacken, aeussere Keys gewinnen.
    """
    payload = work_item.get("payload", {}) or {}
    inner = payload.get("payload")
    if isinstance(inner, dict):
        merged = dict(inner)
        for key, value in payload.items():
            if key != "payload":
                merged.setdefault(key, value)
        return merged
    return payload


def _token(work_item: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]:
    auth = work_item.get("auth") or {}
    token = auth.get("idToken") or (payload.get("auth") or {}).get("idToken")
    return token or os.environ.get("ORDERS_ID_TOKEN")


def _adapter_from_work_item(work_item: Dict[str, Any],
                            adapter_factory: Optional[Callable] = None
                            ) -> RealMaysOrdersAdapter:
    if adapter_factory is not None:
        return adapter_factory(work_item)
    payload = _payload(work_item)
    token = _token(work_item, payload)
    base_url = os.environ.get("ORDERS_BASE_URL", DEFAULT_BASE_URL)
    return RealMaysOrdersAdapter(
        base_url=base_url,
        token_provider=(lambda: token) if token else None,
    )


def process_orders_work(work_item: Dict[str, Any],
                        adapter_factory: Optional[Callable] = None) -> Dict[str, Any]:
    """WorkItem -> Port -> Agent-Result (reine Delegation)."""
    capability = work_item.get("capability", CAPABILITY_STATUS)
    payload = _payload(work_item)
    adapter = _adapter_from_work_item(work_item, adapter_factory)
    logger.info("OrdersFunction: workId=%s capability=%s via %s",
                work_item.get("workId"), capability, adapter.port_id)
    try:
        if capability == CAPABILITY_CREATE:
            order_result = adapter.submit_order(
                work_item, capability, payload,
                tenant_id=work_item.get("tenantId"),
                actor_id=work_item.get("requestedBy") or work_item.get("userId"),
                idempotency_key=work_item.get("idempotencyKey"))
        elif capability == CAPABILITY_CANCEL:
            order_result = adapter.submit_order(
                work_item, capability, payload,
                tenant_id=work_item.get("tenantId"),
                actor_id=work_item.get("requestedBy") or work_item.get("userId"),
                idempotency_key=work_item.get("idempotencyKey"))
        else:
            order_id = payload.get("orderId") or work_item.get("orderId")
            if not order_id:
                return {"success": False, "agentId": ORDERS_AGENT_ID,
                        "error": {"message": "payload.orderId fehlt", "type": "VALIDATION_ERROR"}}
            order_result = adapter.get_order_status(order_id)
            if order_result is None:
                return {"success": False, "agentId": ORDERS_AGENT_ID,
                        "error": {"message": f"Order {order_id} nicht gefunden",
                                  "type": "ORDER_NOT_FOUND"}}
        if order_result.success:
            return {"success": True, "agentId": ORDERS_AGENT_ID,
                    "data": {"order_id": order_result.order_id,
                             "result_type": order_result.result_type.value
                             if order_result.result_type else None,
                             "reason": order_result.reason,
                             "order": (order_result.data or {}).get("order"),
                             "workId": work_item.get("workId")}}
        return {"success": False, "agentId": ORDERS_AGENT_ID,
                "error": {"message": order_result.reason or "Port meldete Fehler",
                          "type": "PORT_ERROR"}}
    except TransientOrdersError as exc:
        # Retrybar -> weiterwerfen (Runtime/SQS entscheidet RETRY).
        raise


def orders_descriptor():
    from agents.ecosystem.registry import (
        AgentDescriptor, AgentStatus, ExecutionProfile)
    return AgentDescriptor(
        agent_id=ORDERS_AGENT_ID, name="orders_function", version="1.0.0",
        status=AgentStatus.ACTIVE, capabilities=list(ORDERS_CAPABILITIES),
        supported_bodies=["1.0.0"], supported_runtimes=["python3.14"],
        execution_profile=ExecutionProfile.LAMBDA, risk_level="low",
        description="Delegiert Order-Operationen an den OrdersPort (keine Fachlogik)",
    )


def register_orders_function(registry, body, adapter_factory=None):
    """Function in Registry + Body-Router verankern (Auswahl bleibt Ecosystem)."""
    if not registry.is_registered(ORDERS_AGENT_ID):
        registry.register(ORDERS_AGENT_ID, orders_descriptor())

    def handler(work_item):
        return process_orders_work(work_item, adapter_factory)

    body.register_agent(work_type=ORDERS_WORK_TYPE, handler=handler)
    for cap in ORDERS_CAPABILITIES:
        body.register_agent(capability=cap, handler=handler)
    body.register_agent(agent_id=ORDERS_AGENT_ID, handler=handler)
    return registry, body


__all__ = ["process_orders_work", "orders_descriptor", "register_orders_function",
           "ORDERS_AGENT_ID", "ORDERS_WORK_TYPE", "ORDERS_CAPABILITIES"]
