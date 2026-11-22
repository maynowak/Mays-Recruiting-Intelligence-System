"""Persist a verified WorkItem and enqueue it on the shared work queue.

Used by the ORDER_DISPATCH ingress so dispatch work follows the same
persist -> work-queue -> worker path as the API execute path. No new queue,
envelope or WorkItem schema.

Exactly-once is not claimed: persist and SendMessage are two operations.
- persist fails -> caller retries the dispatch (nothing queued);
- send fails -> the WorkItem stays non-terminal and the dispatch retry
  re-sends; the worker's WorkItem idempotency prevents a second business run;
- terminal duplicates (COMPLETED / CANCELLED / DEAD_LETTER) are not re-sent.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TERMINAL_STATES = frozenset({"COMPLETED", "CANCELLED", "DEAD_LETTER"})


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


def enqueue_work_item(work_item: Dict[str, Any], *, table: Any,
                      queue_url: str, sqs_client: Any = None,
                      now: Optional[str] = None) -> Dict[str, Any]:
    """Persist once (fenced) and send to the existing shared work queue."""
    if not isinstance(work_item, dict) or not work_item.get("workId"):
        raise WorkEnqueueError("work item with workId is required")
    if not queue_url:
        raise WorkEnqueueError("WORK_QUEUE_URL is not configured")
    if table is None:
        raise WorkEnqueueError("work items table is not configured")

    from agents.runtime.pipeline import _ddb_client_item
    from agents.runtime.subject_fence import subject_fence_key

    fence_key = subject_fence_key(
        user_id=work_item.get("userId") or "",
        tenant_id=work_item.get("tenantId") or "",
        partner_application_id=work_item.get("partnerApplicationId") or "",
        issuer=work_item.get("issuer") or "",
    )
    client = getattr(getattr(table, "meta", None), "client", None)
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
            inserted = False
    else:
        try:
            table.put_item(Item=work_item,
                           ConditionExpression="attribute_not_exists(workId)")
        except Exception as exc:  # noqa: BLE001 - boundary
            if not _conditional_failed(exc):
                raise
            inserted = False

    if not inserted:
        existing = table.get_item(Key={"workId": work_item["workId"]}).get(
            "Item") or {}
        status = str(existing.get("status") or "")
        if status in TERMINAL_STATES:
            return {"workId": work_item["workId"], "status": status,
                    "duplicate": True, "enqueued": False}
        if existing.get("enqueuedAt"):
            # Already handed to the work queue; a redelivered dispatch must
            # not add a second queue message.
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
