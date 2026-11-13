"""Canonical RIS WorkItem construction (single source of truth).

Extracted from ``lambda/handler.py::_enqueue_agent_work`` so that every entry
point — the human route, the M2M route and the generic order transport — builds
the SAME work item shape. There is deliberately no second schema: a transport
envelope is mapped onto this function, it does not define a parallel one.

The function is pure: it builds and returns the dict, it does not persist or
enqueue anything.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

PAYLOAD_VERSION = "1.0"
DEFAULT_AGENT_VERSION = "1.0.0"
DEFAULT_EXPIRY_DAYS = 30
WORK_ITEM_STATUS_QUEUED = "QUEUED"


def build_work_item(
    *,
    agent_id: str,
    capability: Optional[str],
    payload: Dict[str, Any],
    tenant_id: Optional[str],
    user_id: Optional[str],
    agent_version: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    requested_by: Optional[str] = None,
    work_id: Optional[str] = None,
    request_id: Optional[str] = None,
    now: Optional[datetime] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one work item in the canonical runtime shape.

    Args:
        agent_id: Target agent (registry identity).
        capability: Requested capability, stored as declared by the caller.
        payload: Fachlich opake payload for the agent.
        tenant_id: Verified tenant context (never a request-supplied guess).
        user_id: Execution subject (APIProfile owner on the machine path).
        agent_version: Version from the catalog, defaults to 1.0.0.
        idempotency_key: Stable dedup key; generated when absent.
        requested_by: Actor that requested the work; defaults to ``user_id``.
        work_id: Pre-allocated work id (correlation); generated when absent.
        request_id: Transport correlation id; generated when absent.
        now: Injectable clock for deterministic tests.
        extra: Additional already-validated fields (e.g. orderId, apiProfileId).
    """
    stamp = now or datetime.now(timezone.utc)
    item: Dict[str, Any] = {
        "workId": work_id or str(uuid.uuid4()),
        "type": f"agent_{agent_id}",
        "tenantId": tenant_id,
        "userId": user_id,
        "requestedBy": requested_by if requested_by is not None else user_id,
        "agentId": agent_id,
        "capability": capability,
        "idempotencyKey": idempotency_key or str(uuid.uuid4()),
        "payloadVersion": PAYLOAD_VERSION,
        "agentVersion": agent_version or DEFAULT_AGENT_VERSION,
        "requestId": request_id or str(uuid.uuid4()),
        "status": WORK_ITEM_STATUS_QUEUED,
        "attempt": 0,
        "payload": payload,
        "createdAt": stamp.isoformat(),
        "expiresAt": (stamp + timedelta(days=DEFAULT_EXPIRY_DAYS)).isoformat(),
    }
    if extra:
        item.update(extra)
    return item


__all__ = [
    "PAYLOAD_VERSION",
    "DEFAULT_AGENT_VERSION",
    "DEFAULT_EXPIRY_DAYS",
    "WORK_ITEM_STATUS_QUEUED",
    "build_work_item",
]
