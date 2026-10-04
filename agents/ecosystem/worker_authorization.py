"""
Worker entitlement re-check (execution-time authorization).

Contract: PROMPT 08 / Gate RIS-WORKER-ENTITLEMENT-RECHECK-08.

SQS is ACTIVATION, not authorization. Immediately before the actual
agent execution, the worker re-validates the entitlement server-side
against the registered entitlement store:

    check_worker_entitlement(userId, tenantId, agentId, workId, requestTime)

Result is AUTHORIZED or DENIED — never fail-open. Infrastructure
failures of the entitlement store are NOT denials: they propagate
so the existing retry semantics apply (SQS redelivery -> new attempt).

Validity semantics mirror the sync API path (handler entitlement
gates: user-wide rows, tenant match, validFrom/validUntil window).
No second permission world is introduced here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkerAuthDecision:
    """Outcome of the worker entitlement re-check."""

    authorized: bool
    reason: str
    entitlement_id: Optional[str] = None


def is_entitlement_valid(entitlement: Dict[str, Any],
                         now: Optional[datetime] = None) -> bool:
    """Temporal validity of one entitlement row (handler contract).

    validFrom / validUntil are optional ISO timestamps. Unparsable
    values are ignored with a warning (same contract as the sync
    handler gates) — absence of a bound means no bound.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    def _parse(value: Any) -> Optional[datetime]:
        try:
            from dateutil.parser import parse
            parsed = parse(value)
        except Exception:
            try:
                parsed = datetime.fromisoformat(value)
            except Exception:
                logger.warning("Ignoring unparsable entitlement bound: %r", value)
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    valid_from = entitlement.get("validFrom")
    if valid_from:
        start = _parse(valid_from)
        if start is not None and now < start:
            return False
    valid_until = entitlement.get("validUntil")
    if valid_until:
        end = _parse(valid_until)
        if end is not None and now > end:
            return False
    return True


def _row_matches(row: Dict[str, Any], agent_id: str,
                 tenant_id: Optional[str]) -> bool:
    """Agent + tenant match (handler contract: rows without tenantId
    are tenant-global)."""
    if row.get("agentId") != agent_id:
        return False
    if tenant_id and row.get("tenantId") is not None \
            and row.get("tenantId") != tenant_id:
        return False
    return True


def check_worker_entitlement(
    user_id: Optional[str],
    tenant_id: Optional[str],
    agent_id: Optional[str],
    work_id: Optional[str],
    request_time: Optional[datetime] = None,
    resolver: Any = None,
    api_profile_id: Optional[str] = None,
) -> WorkerAuthDecision:
    """Re-validate entitlement for one imminent agent execution.

    Identity comes from the validated WorkItem (claim), the agent from
    the post-selection decision (registry truth). Both are VERIFIED
    here against the registered entitlement store — never trusted.

    User-wide rows (no apiProfileId) match on user/tenant/agent.
    Profile-bound rows match ONLY when api_profile_id equals the
    asserted profile context (Gate P11; default None preserves the
    user-wide behavior exactly).

    Missing identity fields are DENIED (never guessed). Store
    infrastructure errors propagate (transient, NOT denials).
    """
    if resolver is None:
        raise ValueError("entitlement resolver is required")
    if not user_id or not tenant_id or not agent_id:
        return WorkerAuthDecision(
            authorized=False, reason="missing-identity")

    rows: List[Dict[str, Any]] = resolver.find_entitlements(user_id)

    now = request_time or datetime.now(timezone.utc)
    tenant_hit = False
    time_hit = False
    profile_hit = False
    for row in rows or []:
        if row.get("agentId") != agent_id:
            continue
        if row.get("apiProfileId") is not None \
                and row.get("apiProfileId") != api_profile_id:
            profile_hit = True
            continue
        if tenant_id and row.get("tenantId") is not None \
                and row.get("tenantId") != tenant_id:
            tenant_hit = True
            continue
        if not is_entitlement_valid(row, now):
            time_hit = True
            continue
        return WorkerAuthDecision(
            authorized=True, reason="authorized",
            entitlement_id=row.get("entitlementId"))

    if time_hit:
        # Distinguish expired vs. not-yet-valid for audit (no secrets).
        return WorkerAuthDecision(authorized=False, reason="time-window")
    if tenant_hit:
        return WorkerAuthDecision(authorized=False, reason="tenant-mismatch")
    if profile_hit:
        return WorkerAuthDecision(authorized=False, reason="profile-mismatch")
    return WorkerAuthDecision(authorized=False, reason="no-entitlement")


class DynamoDBEntitlementResolver:
    """Production entitlement source (DynamoDB, lazy, read-only).

    Mirrors the sync handler query: rows by userId (existing GSI),
    filtered in code by agent + tenant + time window. No writes,
    no new tables, no new indexes.
    """

    def __init__(self, table: Any = None, table_name: Optional[str] = None) -> None:
        self._table = table
        self._table_name = table_name

    def _table_obj(self) -> Any:
        if self._table is not None:
            return self._table
        import os

        name = self._table_name or os.environ.get("ENTITLEMENTS_TABLE")
        if not name:
            raise RuntimeError("ENTITLEMENTS_TABLE is not configured")
        import boto3

        return boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "eu-central-1"),
        ).Table(name)

    def find_entitlements(self, user_id: str) -> List[Dict[str, Any]]:
        """All entitlement rows for one user (exceptions propagate)."""
        from boto3.dynamodb.conditions import Key

        response = self._table_obj().query(
            KeyConditionExpression=Key("userId").eq(user_id))
        return list(response.get("Items", []))


__all__ = [
    "WorkerAuthDecision",
    "check_worker_entitlement",
    "is_entitlement_valid",
    "DynamoDBEntitlementResolver",
]
