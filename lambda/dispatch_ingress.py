"""L01 — SQS dispatch ingress for RIS.

A thin Lambda entrypoint: SQS record -> Generic Transport V1 -> verified context
-> canonical work item -> the **existing** runtime pipeline.

It deliberately contains no agent logic and no second execution path. The
existing worker remains the only place where an agent runs.

Trust boundary: a message that *claims* ``sender = mays-orders`` proves nothing.
The identity context is resolved from the API profile store by ``contextRef``;
a missing or inactive profile is rejected. The queue ARN is pinned via
``DISPATCH_QUEUE_ARN`` so a message from another queue cannot be processed.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from agents.runtime.pipeline import process_record
from agents.transport import VerifiedContext
from agents.transport import order_transport as transport

logger = logging.getLogger(__name__)


class DispatchRejected(Exception):
    """Permanent rejection (consume the message, do not retry)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_context(context_ref: str, profile_store: Any) -> VerifiedContext:
    """Resolve the sender context from a trusted store, never from the message."""
    if not context_ref:
        raise DispatchRejected("missing_context_ref",
                               "Dispatch carries no identity context reference")
    profile = profile_store.get(context_ref)
    if not isinstance(profile, dict):
        raise DispatchRejected("unknown_context",
                               "Identity context reference cannot be resolved")
    if profile.get("status") != "ACTIVE":
        raise DispatchRejected("inactive_context",
                               "Identity context is not active")
    user_id = profile.get("userId")
    tenant_id = profile.get("tenantId")
    if not user_id or not tenant_id:
        raise DispatchRejected("incomplete_context",
                               "Identity context has no owner or tenant")
    return VerifiedContext(
        context_ref=context_ref,
        tenant_id=tenant_id,
        owner_id=user_id,
        api_profile_id=context_ref,
        partner_application_id=profile.get("partnerApplicationId", ""),
        issuer=profile.get("issuer", ""),
    )


def _dependencies() -> Dict[str, Any]:
    """Production wiring; tests inject the same keys."""
    from agents.agent_body import AgentBody
    from agents.ecosystem.api_profiles import DynamoDBApiProfileStore
    from agents.ecosystem.registry import AgentRegistry
    from agents.ecosystem.worker_authorization import DynamoDBEntitlementResolver

    profile_table = os.environ.get("API_PROFILES_TABLE")
    if not profile_table:
        raise RuntimeError("API_PROFILES_TABLE is not configured")
    return {
        "profile_store": DynamoDBApiProfileStore(table_name=profile_table),
        "registry": AgentRegistry(),
        "body": AgentBody(),
        "table": None,  # pipeline resolves WORK_ITEMS_TABLE itself
        "entitlement_resolver": (DynamoDBEntitlementResolver()
                                 if os.environ.get("ENTITLEMENTS_TABLE")
                                 else None),
    }


def _require_bound_work_id(envelope: Dict[str, Any]) -> str:
    """A dispatch must carry the work id bound to the order (A05)."""
    work_id = (envelope.get("execution") or {}).get("workId")
    if not work_id:
        raise DispatchRejected(
            "missing_work_id",
            "Dispatch carries no pre-bound execution.workId")
    return work_id


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """SQS entrypoint. Returns partial batch failures for retryable errors."""
    dependencies = _dependencies()
    expected_queue_arn = os.environ.get("DISPATCH_QUEUE_ARN")

    processed = 0
    rejected = 0
    failures: List[Dict[str, str]] = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")
        event_source = record.get("eventSourceARN")
        if expected_queue_arn and event_source != expected_queue_arn:
            logger.warning("dispatch rejected: unexpected queue binding")
            rejected += 1
            continue

        try:
            raw = json.loads(record.get("body") or "")
            envelope = transport.validate_envelope(
                raw, expected_type=transport.ORDER_DISPATCH)
            _require_bound_work_id(envelope)
            verified = resolve_context(
                envelope["identity"]["contextRef"], dependencies["profile_store"])
            work_item = transport.dispatch_to_work_item(envelope, verified)

            process_record(
                {"messageId": message_id, "body": json.dumps(work_item)},
                table=dependencies.get("table"),
                registry=dependencies["registry"],
                body=dependencies["body"],
                entitlement_resolver=dependencies.get("entitlement_resolver"),
            )
            processed += 1
        except (DispatchRejected, transport.TransportError, ValueError) as exc:
            logger.warning("dispatch rejected: %s",
                           getattr(exc, "code", type(exc).__name__))
            rejected += 1
        except Exception:
            # Transient (store/table) error: let SQS redeliver this record.
            logger.exception("dispatch processing failed; requesting retry")
            if message_id:
                failures.append({"itemIdentifier": message_id})

    logger.info("dispatch batch: processed=%s rejected=%s retry=%s",
                processed, rejected, len(failures))
    return {"batchItemFailures": failures}


__all__ = ["DispatchRejected", "resolve_context", "handler"]
