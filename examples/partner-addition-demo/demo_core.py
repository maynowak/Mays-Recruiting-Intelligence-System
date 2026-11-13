"""Partner addition demo — core (no AWS, no network, stdlib only).

RIS-MO-ADDITION-AGENT-E2E-01, gate G01.

Two boundaries, both fakeable and both explicit:

    Browser --(no secrets)--> DemoService --(RIS key)--> RisPort
                                    |
                                    +--> OrdersPort

The RIS key lives only in the server process (environment / constructor). It is
never rendered into HTML, never returned in JSON and never logged.

The adapters are deliberately small ports so the same demo can later be pointed
at the real RIS M2M route and the real Mays-Orders API without touching the
service logic.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class DemoError(Exception):
    """Controlled demo failure with an HTTP status for the transport layer."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------
class OrdersPort:
    """Minimal order surface the demo needs (create / read / attach result)."""

    def create(self, customer: str, capability: str, operands: Dict[str, Any]) -> str:
        raise NotImplementedError

    def get(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def mark_result(self, order_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def mark_failed(self, order_id: str, reason: str) -> Dict[str, Any]:
        raise NotImplementedError


class RisPort:
    """Minimal RIS surface: submit an agent execution, read its status."""

    def submit(self, agent_id: str, capability: str,
               payload: Dict[str, Any], idempotency_key: str) -> str:
        raise NotImplementedError

    def status(self, work_id: str) -> Dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Fake implementations (deterministic, in-memory)
# ---------------------------------------------------------------------------
@dataclass
class FakeOrders:
    """In-memory order store shaped like the public Mays-Orders contract."""

    _orders: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def create(self, customer: str, capability: str,
               operands: Dict[str, Any]) -> str:
        order_id = "ord_" + uuid.uuid4().hex[:16]
        self._orders[order_id] = {
            "orderId": order_id,
            "status": "PENDING",
            "customer": {"name": customer},
            "capability": capability,
            "operands": dict(operands),
            "result": None,
        }
        return order_id

    def get(self, order_id: str) -> Dict[str, Any]:
        order = self._orders.get(order_id)
        if order is None:
            raise DemoError("order not found", status=404)
        return dict(order)

    def mark_result(self, order_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        order = self._orders.get(order_id)
        if order is None:
            raise DemoError("order not found", status=404)
        if order["status"] in ("CANCELLED", "FAILED"):
            # No completion after a terminal negative state.
            raise DemoError("order is terminal", status=409)
        if order.get("result") is not None:
            # Idempotent: a repeated delivery must not change the stored result.
            return dict(order)
        order["result"] = dict(result)
        order["status"] = "DELIVERED"
        return dict(order)

    def mark_failed(self, order_id: str, reason: str) -> Dict[str, Any]:
        order = self._orders.get(order_id)
        if order is None:
            raise DemoError("order not found", status=404)
        if order["status"] == "DELIVERED":
            return dict(order)
        order["status"] = "FAILED"
        order["error"] = reason
        return dict(order)


@dataclass
class FakeRis:
    """In-memory RIS agent execution with a deterministic completion step."""

    api_key: str
    _work: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _polls: Dict[str, int] = field(default_factory=dict)

    def submit(self, agent_id: str, capability: str,
               payload: Dict[str, Any], idempotency_key: str) -> str:
        if not self.api_key:
            raise DemoError("RIS credential is not configured", status=503)
        if capability != "math.add":
            raise DemoError("capability not allowed", status=403)
        for work_id, item in self._work.items():
            if item["idempotencyKey"] == idempotency_key:
                return work_id
        work_id = "work_" + uuid.uuid4().hex[:16]
        self._work[work_id] = {
            "workId": work_id,
            "agentId": agent_id,
            "capability": capability,
            "payload": dict(payload),
            "idempotencyKey": idempotency_key,
            "status": "QUEUED",
        }
        self._polls[work_id] = 0
        return work_id

    def status(self, work_id: str) -> Dict[str, Any]:
        item = self._work.get(work_id)
        if item is None:
            raise DemoError("work item not found", status=404)
        self._polls[work_id] += 1
        if item["status"] == "QUEUED":
            item["status"] = "RUNNING"
        elif item["status"] == "RUNNING":
            left = item["payload"].get("left")
            right = item["payload"].get("right")
            if not isinstance(left, (int, float)) or isinstance(left, bool) \
                    or not isinstance(right, (int, float)) or isinstance(right, bool):
                item["status"] = "FAILED"
                item["error"] = "operands must be finite numbers"
            else:
                item["status"] = "COMPLETED"
                item["result"] = {"left": left, "right": right,
                                  "sum": left + right}
        return dict(item)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
@dataclass
class DemoService:
    """Browser-facing orchestration; owns the server-side RIS credential."""

    ris: RisPort
    orders: OrdersPort
    agent_id: str = "addition_agent"
    capability: str = "math.add"
    # orderId -> workId, kept server-side. The browser never supplies either.
    _links: Dict[str, str] = field(default_factory=dict)

    def _operands(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(body, dict):
            raise DemoError("request body must be an object")
        left = body.get("left")
        right = body.get("right")
        for name, value in (("left", left), ("right", right)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DemoError(f"field '{name}' must be a number")
        return {"left": left, "right": right}

    def create_order(self, body: Dict[str, Any]) -> Dict[str, Any]:
        operands = self._operands(body)
        order_id = self.orders.create("demo-partner", self.capability, operands)
        try:
            work_id = self.ris.submit(
                agent_id=self.agent_id,
                capability=self.capability,
                payload=operands,
                idempotency_key=order_id,
            )
        except DemoError as exc:
            self.orders.mark_failed(order_id, str(exc))
            return {"orderId": order_id, "status": "FAILED", "error": str(exc)}
        self._links[order_id] = work_id
        return {"orderId": order_id, "workId": work_id, "status": "IN_PROGRESS"}

    def read_order(self, order_id: str) -> Dict[str, Any]:
        order = self.orders.get(order_id)
        work_id = self._links.get(order_id)
        if work_id and order.get("result") is None \
                and order["status"] not in ("FAILED", "CANCELLED"):
            work = self.ris.status(work_id)
            if work["status"] == "COMPLETED":
                self.orders.mark_result(order_id, work["result"])
            elif work["status"] == "FAILED":
                self.orders.mark_failed(order_id, work.get("error", "agent failed"))
            elif order["status"] == "PENDING":
                order["status"] = "PROCESSING"
        return self.orders.get(order_id)


def build_service(ris_api_key: Optional[str] = None,
                  ris: Optional[RisPort] = None,
                  orders: Optional[OrdersPort] = None) -> DemoService:
    """Wire the demo. The key comes from the environment if not injected."""
    key = ris_api_key if ris_api_key is not None else os.environ.get("RIS_API_KEY", "")
    return DemoService(
        ris=ris if ris is not None else FakeRis(api_key=key),
        orders=orders if orders is not None else FakeOrders(),
    )
