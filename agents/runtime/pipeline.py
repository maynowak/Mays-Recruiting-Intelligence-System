#!/usr/bin/env python3
"""Worker → Agent Body Runtime-Verdrahtung (Gate 5, unser Bereich).

Verbindet den vorhandenen SQS-/Worker-Eingang mit dem vorhandenen
Agent-Body-Pfad ueber das vorhandene Ecosystem — ohne neues
Queue-/Retry-/DLQ-/Idempotency-System:

  SQS-Record
    -> WorkItem validieren (agents.base, bestehend)
    -> Event -> ProcessingEnvelope (event_hook, bestehend)
    -> Discovery -> Eligibility (ecosystem, bestehend)
    -> Auswahl (ecosystem AgentRouter, bestehend; kein hartcodierter Agent)
    -> Ausfuehrung (ExecutionEngine -> AgentInvoker -> AgentBody, bestehend)
    -> ReferenceAgent.process_work (bestehend)
    -> Result persistieren (Work-Items-Tabelle, bestehend)

Idempotency (bestehende Tabelle, Conditional Write, kein neues System):
  ERSTE Registrierung (workId neu) -> Verarbeitung startet (Attempt 1).
  DUPLIKAT (workId bekannt, COMPLETED) -> kein neuer fachlicher Run.
  FEHLER NACH REGISTRIERUNG (FAILED) -> Redelivery = neuer Attempt
    (attempt+1, neue execution_id, gleicher Processing-Kontext).
  FEHLER VOR REGISTRIERUNG (ungueltiges WorkItem) -> keine Ausfuehrung,
    Exception -> SQS-Redelivery -> bestehende DLQ nach maxReceiveCount.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from agents.base import WorkItem
from agents.ecosystem.discovery import AgentDiscovery
from agents.ecosystem.eligibility import EligibilityPipeline
from agents.ecosystem.event_hook import Event, EventHook, ProcessingEnvelope, TriggerType
from agents.ecosystem.health_plane import (
    Component,
    REASON_AGENT_ERROR,
    REASON_ENTITLEMENT_UNAVAILABLE,
)
from agents.ecosystem.registry import (
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
    ExecutionProfile,
    get_registry,
)
from agents.ecosystem.routing import AgentRouter as EcosystemRouter
from agents.ecosystem.routing import ExecutionEngine

logger = logging.getLogger(__name__)

BODY_VERSION = "1.0.0"
RUNTIME_LAMBDA = "python3.14"

REFERENCE_AGENT_ID = "reference_agent"
REFERENCE_CAPABILITY = "reference.echo"
REFERENCE_WORK_TYPE = "agent_reference_agent"

TERMINAL_DUPLICATE_STATES = {"COMPLETED"}

# Fehlercodes, die einen KONTROLLIERTEN Fehlschlag bedeuten (kein Retry:
# die Nachricht wird konsumiert). Alle anderen Fehlertypen (unerwartete
# Exceptions wie RuntimeError, ClientError, ...) fuehren nach Persistenz
# zu einem Raise, damit SQS erneut zustellt (Retry -> neuer Attempt;
# Begrenzung ueber bestehende DLQ/maxReceiveCount, kein neues System).
PERMANENT_ERROR_CODES = frozenset({
    "VALIDATION_ERROR",
    "ValidationError",
    "NOT_FOUND",
    "ORDER_NOT_FOUND",
    "INVALID_TRANSITION",
    "CONFLICT",
})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_reference_agent(
    registry: Optional[AgentRegistry] = None,
    body: Any = None,
) -> Tuple[AgentRegistry, Any]:
    """ReferenceAgent (+ Orders-Function) in Registry + Body-Router verankern.

    Harness-Muster; kein hartcodierter Agent im Worker: Die Auswahl trifft
    das Ecosystem; hier wird nur registriert, WAS es gibt (Descriptoren +
    Handler). Die Orders-Function delegiert an den OrdersPort (Gate 6).
    """
    from agents.agent_body import AgentBody
    from agents.ats_agent.agent import ATSAgent
    from agents.ats_agent.registry import (
        ATS_ANALYZE_CAPABILITY,
        ATS_WORK_TYPE,
        get_ats_descriptor,
    )
    from agents.orders.function import register_orders_function
    from agents.reference_agent.service import ReferenceAgent

    registry = registry or get_registry()
    if not registry.is_registered(REFERENCE_AGENT_ID):
        registry.register(
            REFERENCE_AGENT_ID,
            AgentDescriptor(
                agent_id=REFERENCE_AGENT_ID,
                name="reference_agent",
                version="1.0.0",
                status=AgentStatus.ACTIVE,
                capabilities=[REFERENCE_CAPABILITY],
                supported_bodies=[BODY_VERSION],
                supported_runtimes=[RUNTIME_LAMBDA],
                execution_profile=ExecutionProfile.LAMBDA,
                risk_level="low",
                description="Technischer Nachweis-Agent (Echo, keine Domain-Logik)",
            ),
        )
    body = body or AgentBody()
    agent = ReferenceAgent()
    body.register_agent(work_type=REFERENCE_WORK_TYPE, handler=agent.process_work)
    body.register_agent(capability=REFERENCE_CAPABILITY, handler=agent.process_work)
    body.register_agent(agent_id=REFERENCE_AGENT_ID, handler=agent.process_work)
    register_orders_function(registry, body)
    # Gate 8: Dummy Agents A/B (DEV/TEST-Nachweis, keine Fachlogik).
    from agents.dummy.agents import register_dummy_agents
    register_dummy_agents(registry, body)
    # Gate 9: JobSearch Domain Agent (persistent, Delegation ans Repository).
    from agents.jobsearch_agent.agent import register_jobsearch_agent
    register_jobsearch_agent(registry, body)
    # Gate 7: ATS als erster echter Domain Agent (Descriptor + Routen aus
    # bestehender Registry-Anbindung; Auswahl bleibt beim Ecosystem).
    if not registry.is_registered("ats-agent"):
        registry.register("ats-agent", get_ats_descriptor())
    ats = ATSAgent()
    body.register_agent(work_type=ATS_WORK_TYPE, handler=ats.process_work)
    body.register_agent(capability=ATS_ANALYZE_CAPABILITY, handler=ats.process_work)
    body.register_agent(agent_id="ats-agent", handler=ats.process_work)
    return registry, body


def _parse_record(record: Dict[str, Any]) -> Dict[str, Any]:
    raw = record.get("body", "{}")
    work = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(work, dict):
        raise ValueError("SQS body ist kein WorkItem-Objekt")
    return work


def _to_event(work: Dict[str, Any], message_id: Optional[str]) -> Event:
    trigger = str(work.get("trigger_type") or work.get("event_type") or "EVENT").upper()
    if trigger not in {t.value for t in TriggerType}:
        trigger = TriggerType.EVENT.value
    payload = dict(work)
    return Event(
        event_id=message_id or work.get("event_id") or str(uuid.uuid4()),
        event_type=trigger,
        occurred_at=datetime.now(timezone.utc),
        tenant_id=work.get("tenantId") or work.get("tenant_id") or "",
        order_id=work.get("orderId") or work.get("order_id"),
        payload=payload,
        metadata={"messageId": message_id} if message_id else {},
        agent_id=work.get("agentId") or work.get("agent_id"),
    )


class _ConditionalFailed(Exception):
    """Lokaler Marker fuer fehlgeschlagenen Conditional Write (Tests)."""


def _is_conditional_failed(exc: Exception) -> bool:
    if isinstance(exc, _ConditionalFailed):
        return True
    resp = getattr(exc, "response", None)
    if isinstance(resp, dict):
        return resp.get("Error", {}).get("Code") == "ConditionalCheckFailedException"
    return False


def _register_processing(
    table: Any,
    work: Dict[str, Any],
    envelope: ProcessingEnvelope,
    agent_id: str,
) -> Tuple[Dict[str, Any], bool]:
    """WorkItem registrieren (Conditional Write) oder Duplikat feststellen.

    Returns (item, is_duplicate). Duplikat -> kein neuer fachlicher Run.
    """
    now = _utcnow()
    # G5 (D2): the requesting user must survive onto the PERSISTED row.
    # The ingress writers set `userId` (and `requestedBy`); work that
    # reaches the worker without a pre-written item is registered here, and
    # this block used to omit the user entirely -- so such items would be
    # invisible to any per-user lookup. `requestedBy` is accepted as a
    # fallback because _create_work writes only that field.
    user_id = work.get("userId") or work.get("requestedBy") or ""
    item = {
        "workId": work["workId"],
        "tenantId": work.get("tenantId", ""),
        "userId": user_id,
        "requestedBy": user_id,
        "idempotencyKey": work.get("idempotencyKey", ""),
        "type": work.get("type", ""),
        "capability": work.get("capability", ""),
        "agentId": agent_id,
        "processing_id": envelope.processing_id,
        "execution_id": envelope.execution_id or str(uuid.uuid4()),
        "attempt_id": f"{envelope.processing_id}#1",
        "parent_id": envelope.parent_id or work.get("parentWorkId") or "",
        "sequence_no": envelope.sequence,
        "attempt_no": 1,
        "body_id": envelope.body_id or BODY_VERSION,
        "body_version": envelope.body_version or BODY_VERSION,
        "runtime": RUNTIME_LAMBDA,
        "execution_profile": ExecutionProfile.LAMBDA.value,
        "status": "RUNNING",
        "createdAt": now,
        "updatedAt": now,
    }
    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(workId)",
        )
        return item, False
    except Exception as exc:
        if not _is_conditional_failed(exc):
            raise
        existing = table.get_item(Key={"workId": work["workId"]}).get("Item", {})
        return existing, True


def _to_dynamo(value: Any) -> Any:
    """Python-Werte DDB-sicher machen (DDB kennt keine Floats).

    Nur Float -> Decimal; Ints/Strings/IDs/Timestamps bleiben unveraendert.
    Betrifft nur die Persistenz — API-/Result-Contract unberuehrt.
    """
    from decimal import Decimal

    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_dynamo(v) for v in value]
    return value


def _persist_result(table: Any, work_id: str, attempt: int, result: Dict[str, Any]) -> None:
    table.update_item(
        Key={"workId": work_id},
        UpdateExpression="SET #status = :s, result_reference = :r, #result = :res, updatedAt = :u",
        ExpressionAttributeNames={"#status": "status", "#result": "result"},
        ExpressionAttributeValues={
            ":s": "COMPLETED",
            ":r": f"work:{work_id}:attempt:{attempt}",
            ":res": _to_dynamo(result),
            ":u": _utcnow(),
        },
    )


def _persist_failure(table: Any, work_id: str, attempt: int, error: Dict[str, Any]) -> None:
    table.update_item(
        Key={"workId": work_id},
        UpdateExpression="SET #status = :s, #error = :e, updatedAt = :u",
        ExpressionAttributeNames={"#status": "status", "#error": "error"},
        ExpressionAttributeValues={":s": "FAILED", ":e": _to_dynamo(error), ":u": _utcnow()},
    )


def _start_retry_attempt(table: Any, existing: Dict[str, Any]) -> Dict[str, Any]:
    """Bestehendes FAILED-Processing als neuer Attempt fortfuehren."""
    attempt = int(existing.get("attempt_no", 1)) + 1
    execution_id = str(uuid.uuid4())
    table.update_item(
        Key={"workId": existing["workId"]},
        UpdateExpression=(
            "SET #status = :s, attempt_no = :a, execution_id = :e, "
            "attempt_id = :aid, updatedAt = :u REMOVE #error"
        ),
        ExpressionAttributeNames={"#status": "status", "#error": "error"},
        ExpressionAttributeValues={
            ":s": "RUNNING",
            ":a": attempt,
            ":e": execution_id,
            ":aid": f"{existing.get('processing_id', '')}#{attempt}",
            ":u": _utcnow(),
        },
    )
    resumed = dict(existing)
    resumed.update({"attempt_no": attempt, "execution_id": execution_id, "status": "RUNNING"})
    return resumed


def process_record(
    record: Dict[str, Any],
    table: Any = None,
    registry: Optional[AgentRegistry] = None,
    body: Any = None,
    entitlement_resolver: Any = None,
    health_tracker: Any = None,
) -> Dict[str, Any]:
    """Einen SQS-Record durch den Runtime-Pfad fuehren (Worker-Einstieg).

    Args:
        entitlement_resolver: Entitlement-Quelle fuer den
            Execution-Time-Re-check (Gate 08). None = kein Re-check
            (nur Test-/Harness-Modus, debug-geloggt); Produktion
            injiziert immer einen Resolver (Handler-SQS-Pfad).
        health_tracker: Optionaler HealthTracker (Gate-02 P3). Emittiert
            HEALTH_DEGRADED/HEALTH_RECOVERED an den echten Grenzen der
            Verarbeitung. None = keine Health-Events (best existing
            behaviour). Health-Instrumentierung darf den Work-Pfad NIE
            fehlschlagen; Fehler werden verschluckt.
    """
    work = _parse_record(record)
    validated = WorkItem(work)  # wirft bei fehlenden Pflichtfeldern (keine Registrierung)
    work = validated.to_dict()

    # Gate-02 P3: Health-Events an den echten Grenzen der Verarbeitung.
    # Jede Aufzeichnung ist defensiv gekapselt -- Observability darf den
    # Work-Pfad nicht zum Fehlschlagen bringen.
    def _health(fn_name, *args, **kwargs):
        if health_tracker is None:
            return
        try:
            getattr(health_tracker, fn_name)(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensiv
            logger.warning("health instrumentation failed: %s", exc)

    tenant_id = work.get("tenantId")
    work_id = work.get("workId")

    table = table if table is not None else _resolve_table()
    registry, body = ensure_reference_agent(registry, body)

    hook = EventHook()
    envelope = hook.handle_event(_to_event(work, record.get("messageId")))

    discovery = AgentDiscovery(registry)
    candidates = discovery.find_from_envelope(envelope)
    if not candidates:
        candidates = discovery.find(
            capability=work.get("capability"),
            agent_id=work.get("agentId"),
            status=AgentStatus.ACTIVE,
        )
    pipeline = EligibilityPipeline(registry).check_candidates(candidates, envelope)
    eligible_ids = {c.agent_id for c in pipeline.eligible}
    eligible = [c for c in candidates if c.agent_id in eligible_ids]
    decision = EcosystemRouter().select(eligible)
    if decision is None:
        raise ValueError(
            f"Kein geeigneter Agent (eligible={len(pipeline.eligible)}, "
            f"rejected={len(pipeline.rejected)})"
        )

    item, is_duplicate = _register_processing(table, work, envelope, decision.agent_id)
    if is_duplicate:
        if item.get("status") in TERMINAL_DUPLICATE_STATES:
            logger.info(
                "Duplikat erkannt (workId=%s, status=%s): kein neuer AgentRun",
                work["workId"],
                item.get("status"),
            )
            return {
                "workId": work["workId"],
                "status": item.get("status"),
                "duplicate": True,
                "attempt_no": item.get("attempt_no", 1),
                "result_reference": item.get("result_reference"),
            }
        resumed = _start_retry_attempt(table, item)
        item = resumed

    attempt = int(item.get("attempt_no", 1))

    # Execution-Time-Entitlement-Re-check (Gate 08): SQS ist
    # Aktivierung, keine Autorisierung. Geprueft wird der ENTSCHIEDENE
    # Agent (Registry-Wahrheit) gegen den registrierten Entitlement-
    # Bestand — unmittelbar vor der fachlichen Ausfuehrung.
    if entitlement_resolver is None:
        logger.debug(
            "worker entitlement re-check disabled (no resolver; "
            "workId=%s) — test/harness mode only", work["workId"])
    else:
        from agents.ecosystem.worker_authorization import (
            check_worker_entitlement,
        )
        try:
            auth = check_worker_entitlement(
                user_id=work.get("userId"),
                tenant_id=work.get("tenantId"),
                agent_id=decision.agent_id,
                work_id=work["workId"],
                resolver=entitlement_resolver,
                # Profile context passthrough (P11): None preserves the
                # user-wide behavior exactly; asserted contexts are verified
                # against profile-bound rows (never trusted blindly).
                api_profile_id=work.get("apiProfileId"),
            )
        except Exception as exc:
            # Transienter Infrastrukturfehler (Store unerreichbar) ist
            # KEIN Denied: FAILED persistieren + Raise -> bestehende
            # Retry-Semantik (SQS-Redelivery -> neuer Attempt). Kein
            # Fail-Open, kein falsches DENIED.
            _health("record_failure",
                    Component.AGENT_EXECUTION,
                    tenant_id=tenant_id,
                    reason=REASON_ENTITLEMENT_UNAVAILABLE,
                    work_id=work_id,
                    agent_id=decision.agent_id,
                    attempt_id=str(attempt))
            _persist_failure(
                table, work["workId"], attempt,
                {"message": f"Entitlement store unreachable: {exc}",
                 "type": type(exc).__name__})
            raise
        if not auth.authorized:
            # Permanent DENIED: kontrolliert beenden (FAILED persistieren,
            # Nachricht konsumieren — KEIN Retry-Loop, KEIN Raise).
            # Ein DENIED ist KEINE Laufzeit-Degradierung: die Ablehnung ist
            # das korrekte Verhalten, kein Ausfall. Deshalb wird hier KEIN
            # HEALTH_DEGRADED emittiert.
            _persist_failure(
                table, work["workId"], attempt,
                {"message": f"Worker entitlement denied [{auth.reason}]",
                 "type": "ENTITLEMENT_DENIED"})
            logger.warning(
                "worker entitlement DENIED (workId=%s, agent=%s, reason=%s, "
                "attempt=%s)", work["workId"], decision.agent_id,
                auth.reason, attempt)
            return {
                "workId": work["workId"],
                "status": "FAILED",
                "duplicate": False,
                "attempt_no": attempt,
                "agent_id": decision.agent_id,
                "denied": True,
                "reason": auth.reason,
                "result_reference": f"work:{work['workId']}:attempt:{attempt}",
            }

    engine = ExecutionEngine(agent_body=body)
    try:
        result = engine.execute_from_decision(decision, envelope)
    except Exception as exc:
        _health("record_failure",
                Component.AGENT_EXECUTION,
                tenant_id=tenant_id,
                reason=REASON_AGENT_ERROR,
                work_id=work_id,
                agent_id=decision.agent_id,
                attempt_id=str(attempt))
        _persist_failure(
            table,
            work["workId"],
            attempt,
            {"message": str(exc), "type": type(exc).__name__},
        )
        raise

    if not result.get("success", False):
        error = result.get("error", {"message": "Agent meldete Fehler"})
        _health("record_failure",
                Component.AGENT_EXECUTION,
                tenant_id=tenant_id,
                reason=REASON_AGENT_ERROR,
                work_id=work_id,
                agent_id=decision.agent_id,
                attempt_id=str(attempt))
        _persist_failure(table, work["workId"], attempt, error)
        if isinstance(error, dict) and error.get("type") not in PERMANENT_ERROR_CODES:
            # Unerwarteter Fehler -> Retry via SQS-Redelivery (neuer Attempt).
            raise RuntimeError(
                f"Agent {decision.agent_id} fehlgeschlagen "
                f"[{error.get('type')}]: {error.get('message')} "
                f"(workId={work['workId']}, attempt={attempt})"
            )
    else:
        _health("record_success",
                Component.AGENT_EXECUTION,
                tenant_id=tenant_id,
                work_id=work_id,
                agent_id=decision.agent_id,
                attempt_id=str(attempt))
        _persist_result(table, work["workId"], attempt, result)

    return {
        "workId": work["workId"],
        "status": "COMPLETED" if result.get("success", False) else "FAILED",
        "duplicate": False,
        "attempt_no": attempt,
        "agent_id": decision.agent_id,
        "processing_id": item.get("processing_id"),
        "result_reference": f"work:{work['workId']}:attempt:{attempt}",
        "result": result,
    }


def _resolve_table() -> Any:  # pragma: no cover - live Pfad (Env), Tests injizieren Fake
    import os

    import boto3

    name = os.environ.get("WORK_ITEMS_TABLE", "mays-ris-dev-work-items")
    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-central-1")).Table(name)


__all__ = [
    "process_record",
    "ensure_reference_agent",
    "REFERENCE_AGENT_ID",
    "REFERENCE_CAPABILITY",
]
