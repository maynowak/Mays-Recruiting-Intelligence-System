"""Persist a verified WorkItem and enqueue it on the shared work queue.

Used by the ORDER_DISPATCH ingress so dispatch work follows the same
persist -> work-queue -> worker path as the API execute path. No new queue,
envelope or WorkItem schema.

Exactly-once is not claimed: persist and SendMessage are two operations.
- persist fails -> caller retries the dispatch (nothing queued);
- send fails -> the WorkItem stays non-terminal and the dispatch retry
  re-sends; the worker's WorkItem idempotency prevents a second business run;
- terminal duplicates (COMPLETED / CANCELLED / DEAD_LETTER) are not re-sent.

A conditional cancellation is NOT treated as a duplicate by default. The
existing row is read consistently and must be complete, matching and reusable;
otherwise the call fails closed before any send or marker write.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TERMINAL_STATES = frozenset({"COMPLETED", "CANCELLED", "DEAD_LETTER"})
VALID_STATES = frozenset({
    "QUEUED", "RUNNING", "FAILED",
    "COMPLETED", "CANCELLED", "DEAD_LETTER",
})
IDENTITY_FIELDS = ("tenantId", "userId", "partnerApplicationId", "issuer")
MATCH_FIELDS = IDENTITY_FIELDS + ("agentId", "capability",
                                  "apiProfileId", "type")


class WorkEnqueueError(RuntimeError):
    code = "work_enqueue_error"


def _conditional_failed(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = (response.get("Error") or {}).get("Code")
        if code in ("ConditionalCheckFailedException",
                    "TransactionCanceledException"):
            return True
    return type(exc).__name__ == "ConditionalFailed"


def _cancellation_reasons(exc: Exception) -> List[Dict[str, Any]]:
    """Return only safe index/code pairs (never values or messages)."""
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return []
    reasons = response.get("CancellationReasons") or []
    if not isinstance(reasons, list):
        return []
    safe = []
    for index, reason in enumerate(reasons):
        code = reason.get("Code") if isinstance(reason, dict) else None
        safe.append({"index": index,
                     "code": code if isinstance(code, str) else "Missing"})
    return safe


def _raise_for_cancellation(exc: Exception) -> None:
    """Classify a transaction cancellation without guessing.

    Index 0 is the fence ConditionCheck, index 1 the WorkItem Put. A fence
    rejection must never fall through to the duplicate path; validation or a
    transaction conflict must fail closed without a send. Only a Put condition
    failure is a candidate for the duplicate/reuse check.
    """
    response = getattr(exc, "response", None)
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    error_code = error.get("Code") if isinstance(error, dict) else None

    # A direct conditional failure is the non-transactional conditional-write
    # fallback. It remains eligible for the existing-row duplicate check.
    if error_code == "ConditionalCheckFailedException":
        return

    reasons = _cancellation_reasons(exc)
    if reasons:
        logger.warning("work item transaction cancelled: %s",
                       json.dumps(reasons, sort_keys=True))
    if error_code == "TransactionCanceledException":
        codes = {reason["index"]: reason["code"] for reason in reasons}
        if (len(reasons) == 2
                and codes.get(0) == "None"
                and codes.get(1) == "ConditionalCheckFailed"):
            return
        if codes.get(0) == "ConditionalCheckFailed":
            raise WorkEnqueueError("work item rejected: subject fence is active")
        if "ValidationError" in codes.values():
            raise WorkEnqueueError("work item transaction validation error")
        if "TransactionConflict" in codes.values():
            raise WorkEnqueueError("work item transaction conflict")
        raise WorkEnqueueError("work item transaction cancellation is unclassified")

    raise WorkEnqueueError("work item conditional failure is unclassified")


def _read_existing(table: Any, work_id: str) -> Optional[Dict[str, Any]]:
    try:
        return table.get_item(Key={"workId": work_id},
                              ConsistentRead=True).get("Item")
    except TypeError:
        # Test doubles / older stores may not accept ConsistentRead.
        return table.get_item(Key={"workId": work_id}).get("Item")
    except Exception as exc:  # noqa: BLE001 - boundary
        raise WorkEnqueueError(
            f"work item lookup failed: {type(exc).__name__}") from exc


def _reuse_problem(existing: Any, work_item: Dict[str, Any]) -> Optional[str]:
    """Return a safe reason code when an existing row must not be reused."""
    if not isinstance(existing, dict) or not existing:
        return "missing"
    if existing.get("workId") != work_item["workId"]:
        return "work_id_mismatch"
    status = str(existing.get("status") or "")
    if status not in VALID_STATES:
        return "invalid_status"
    for field in MATCH_FIELDS:
        if str(existing.get(field) or "") != str(work_item.get(field) or ""):
            return f"{field}_mismatch"
    if not isinstance(existing.get("payload"), dict):
        return "payload_missing"
    if existing.get("payload") != work_item.get("payload"):
        return "payload_mismatch"
    existing_key = existing.get("idempotencyKey")
    if not existing_key:
        return "idempotency_missing"
    if existing_key != work_item.get("idempotencyKey"):
        return "idempotency_key_mismatch"
    return None


def enqueue_work_item(work_item: Dict[str, Any], *, table: Any,
                      queue_url: str, sqs_client: Any = None,
                      now: Optional[str] = None) -> Dict[str, Any]:
    """Persist once (fenced) and send to the existing shared work queue."""
    if not isinstance(work_item, dict) or not work_item.get("workId"):
        raise WorkEnqueueError("work item with workId is required")
    if not isinstance(work_item.get("payload"), dict):
        raise WorkEnqueueError("work item payload must be an object")
    if not work_item.get("idempotencyKey"):
        raise WorkEnqueueError("work item idempotencyKey is required")
    if not queue_url:
        raise WorkEnqueueError("WORK_QUEUE_URL is not configured")
    if table is None:
        raise WorkEnqueueError("work items table is not configured")

    from agents.runtime.pipeline import (
        _ddb_client_item,
        _ddb_transaction_client,
    )
    from agents.runtime.subject_fence import subject_fence_key

    fence_key = subject_fence_key(
        user_id=work_item.get("userId") or "",
        tenant_id=work_item.get("tenantId") or "",
        partner_application_id=work_item.get("partnerApplicationId") or "",
        issuer=work_item.get("issuer") or "",
    )
    client = _ddb_transaction_client(table)
    inserted = True
    if client is not None and hasattr(client, "transact_write_items"):
        try:
            client.transact_write_items(TransactItems=[
                {"ConditionCheck": {
                    "TableName": getattr(table, "name", ""),
                    "Key": {"workId": {"S": fence_key}},
                    "ConditionExpression": "attribute_not_exists(workId)",
                }},
                {"Put": {
                    "TableName": getattr(table, "name", ""),
                    "Item": _ddb_client_item(work_item),
                    "ConditionExpression": "attribute_not_exists(workId)",
                }},
            ])
        except Exception as exc:  # noqa: BLE001 - boundary
            if not _conditional_failed(exc):
                raise
            _raise_for_cancellation(exc)
            inserted = False
    else:
        try:
            table.put_item(Item=work_item,
                           ConditionExpression="attribute_not_exists(workId)")
        except Exception as exc:  # noqa: BLE001 - boundary
            if not _conditional_failed(exc):
                raise
            _raise_for_cancellation(exc)
            inserted = False

    if not inserted:
        existing = _read_existing(table, work_item["workId"])
        problem = _reuse_problem(existing, work_item)
        if problem is not None:
            # Fail closed: never send a message when the persisted WorkItem is
            # missing, incomplete or belongs to a different identity.
            logger.warning("work item not enqueued: existing row %s", problem)
            raise WorkEnqueueError(
                f"existing work item is not reusable: {problem}")
        status = str(existing.get("status") or "")
        if status in TERMINAL_STATES or existing.get("enqueuedAt"):
            return {"workId": work_item["workId"], "status": status,
                    "duplicate": True, "enqueued": False}

    if sqs_client is None:
        import boto3

        sqs_client = boto3.client("sqs")
    try:
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(work_item),
            MessageAttributes={
                "workType": {"StringValue": str(work_item.get("type") or ""),
                             "DataType": "String"},
                "agentId": {"StringValue": str(work_item.get("agentId") or ""),
                            "DataType": "String"},
            },
        )
    except Exception as exc:  # noqa: BLE001 - boundary
        # The WorkItem stays non-terminal; the dispatch retry re-sends and the
        # worker de-duplicates by workId.
        raise WorkEnqueueError(
            f"work queue send failed: {type(exc).__name__}") from exc

    marker = now or _utcnow()
    try:
        table.update_item(
            Key={"workId": work_item["workId"]},
            UpdateExpression="SET enqueuedAt = :t",
            # Never create a row with the marker alone.
            ConditionExpression="attribute_exists(workId)",
            ExpressionAttributeValues={":t": marker},
        )
    except Exception as exc:  # noqa: BLE001 - recoverable duplicate window
        logger.warning("enqueue marker not persisted: %s",
                       type(exc).__name__)

    return {"workId": work_item["workId"], "status": "QUEUED",
            "duplicate": not inserted, "enqueued": True}


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = ["WorkEnqueueError", "enqueue_work_item"]
