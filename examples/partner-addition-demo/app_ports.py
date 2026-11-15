"""Real application ports for the partner demo (A07).

The demo (``demo_core.DemoService`` and ``app.py``) is unchanged. Only the two
fakes are replaced:

- ``OrdersApplicationAdapter`` calls the **real** Mays-Orders Lambda handler
  (API Gateway v2 event with verified JWT claims) and then performs the A05
  dispatch step (bind work id -> ORDER_DISPATCH -> local queue).
- ``RisApplicationAdapter`` consumes the dispatch message with the **real**
  transport parser, runs registry/discovery/eligibility/entitlement and the
  existing Agent Body, then emits ORDER_RESULT through the **real** A06 consumer
  (signed SQS record).

SQS is simulated by ``LocalSqsBus``: same message shapes, same consumer entry
points, no AWS.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

# Mays-Orders must be importable for the real application code.
_MO_SRC = os.environ.get("MO_ORDERS_SRC")
if _MO_SRC and _MO_SRC not in sys.path:
    sys.path.insert(0, _MO_SRC)

from demo_core import DemoError, OrdersPort, RisPort  # noqa: E402,F401

DEFAULT_CONTEXT_REF = "ctx-partner-a"


class LocalSqsBus:
    """In-memory stand-in for SQS: same payloads, explicit queue names."""

    def __init__(self) -> None:
        self._queues: Dict[str, List[Dict[str, Any]]] = {}

    def send(self, queue: str, message: Dict[str, Any]) -> None:
        self._queues.setdefault(queue, []).append(message)

    def receive_all(self, queue: str) -> List[Dict[str, Any]]:
        return self._queues.pop(queue, [])

    def depth(self, queue: str) -> int:
        return len(self._queues.get(queue, []))


class _ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class InMemoryOrdersTable:
    """DynamoDB table double with the conditional semantics the code relies on.

    This is a storage double for local runs, not a second order persistence:
    every rule (ownership, fingerprint, dispatch binding, result idempotency)
    lives in the application code above it.
    """

    def __init__(self) -> None:
        self.items: Dict[str, Dict[str, Any]] = {}

    def put_item(self, **kwargs):
        self.items[kwargs["Item"]["orderId"]] = dict(kwargs["Item"])

    def get_item(self, Key):
        order_id = Key["pk"][len("ord_"):]
        item = self.items.get(order_id)
        return {"Item": dict(item)} if item else {}

    def query(self, **kwargs):
        owner = kwargs.get("ExpressionAttributeValues", {}).get(":owner")
        return {"Items": [dict(i) for i in self.items.values()
                          if i.get("gsi3pk") == owner]}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, **kwargs):
        order_id = Key["pk"][len("ord_"):]
        item = self.items[order_id]
        values = ExpressionAttributeValues or {}
        if ConditionExpression:
            if ("attribute_not_exists(expectedWorkId)" in ConditionExpression
                    and "expectedWorkId" in item):
                raise _ConditionalFailed()
            if ("attribute_not_exists(#p)" in ConditionExpression
                    and "processing" in item):
                raise _ConditionalFailed()
            if ("expectedWorkId = :w" in ConditionExpression
                    and item.get("expectedWorkId") != values.get(":w")):
                raise _ConditionalFailed()
        for key, field in ((":w", "expectedWorkId"), (":p", "processing"),
                           (":d", "dispatch")):
            if key in values:
                item[field] = values[key]
        return {"Attributes": dict(item)}


class OrdersApplicationAdapter(OrdersPort):
    """Orders side: real handler + A05 dispatch."""

    def __init__(self, service: Any, identity: Any, bus: LocalSqsBus, *,
                 context_ref: str = DEFAULT_CONTEXT_REF,
                 agent_id: str = "addition_agent",
                 capability: str = "math.add") -> None:
        self._service = service
        self._identity = identity
        self._bus = bus
        self._context_ref = context_ref
        self._agent_id = agent_id
        self._capability = capability
        self.last_dispatch: Optional[Dict[str, Any]] = None

    # -- event helpers ---------------------------------------------------
    def _claims(self) -> Dict[str, Any]:
        return {
            "iss": self._identity.issuer,
            "sub": self._identity.subject,
            "client_id": self._identity.client_id,
            "token_use": "access",
        }

    def _event(self, route: str, **kwargs) -> Dict[str, Any]:
        event = {
            "routeKey": route,
            "requestContext": {"authorizer": {"jwt": {"claims": self._claims()}}},
        }
        event.update(kwargs)
        return event

    def _call_handler(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Run the real Lambda handler against the injected local service.

        The handler normally builds its own boto3 table; the local E2E injects
        an in-memory one instead. Single-threaded demo only.
        """
        import index

        original = index.create_order_service
        index.create_order_service = lambda **kwargs: self._service
        try:
            return index.handler(event, None)
        finally:
            index.create_order_service = original

    # -- OrdersPort ------------------------------------------------------
    def create(self, customer: str, capability: str, operands: Dict[str, Any]) -> str:
        order_body = {
            "orderType": "agent.execution",
            "agentOrder": {
                "schemaVersion": "1.0",
                "target": {"agentId": self._agent_id,
                           "capability": capability},
                "input": {"schemaVersion": "1.0", "data": dict(operands)},
                "metadata": {
                    "source": "partner-demo",
                    "requestId": f"req-{uuid.uuid4().hex}",
                    "apiProfileRef": self._context_ref,
                    "idempotencyKey": f"idem-{uuid.uuid4().hex}",
                },
            },
        }
        response = self._call_handler(
            self._event("POST /orders", body=json.dumps(order_body)))
        if response["statusCode"] != 201:
            raise DemoError("order rejected", status=response["statusCode"])
        order_id = json.loads(response["body"])["orderId"]

        # A05 dispatch worker: bind once, build from the stored order, enqueue.
        bound = self._service.prepare_dispatch(order_id, self._identity)
        envelope = self._service.dispatch_envelope(order_id, bound["workId"])
        self.last_dispatch = envelope
        self._bus.send("agent-dispatch", envelope)
        return order_id

    def get(self, order_id: str) -> Dict[str, Any]:
        response = self._call_handler(
            self._event("GET /orders/{orderId}",
                        pathParameters={"orderId": order_id}))
        if response["statusCode"] != 200:
            raise DemoError("order not found", status=404)
        order = json.loads(response["body"])
        processing = order.get("processing") or {}
        # The fachliche order status is never rewritten; the demo displays the
        # effective state separately from it.
        return {
            "orderId": order["orderId"],
            "status": processing.get("status") or order["status"],
            "orderStatus": order["status"],
            "result": processing.get("result"),
            "error": (processing.get("error") or {}).get("message"),
            "agentOrder": order.get("agentOrder"),
        }

    def mark_result(self, order_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        # A06 is the only writer; the demo must not write results directly.
        return self.get(order_id)

    def mark_failed(self, order_id: str, reason: str) -> Dict[str, Any]:
        return self.get(order_id)


class RisApplicationAdapter(RisPort):
    """RIS side: real transport parser + registry/eligibility + Agent Body."""

    def __init__(self, bus: LocalSqsBus, context: Any, *,
                 result_secret: str, orders_consumer: Callable[[Dict[str, Any]],
                                                               Any],
                 resolver: Any = None) -> None:
        self._bus = bus
        self._context = context
        self._secret = result_secret
        self._orders_consumer = orders_consumer
        self._resolver = resolver
        self._outcomes: Dict[str, Dict[str, Any]] = {}

    # -- RIS internals ---------------------------------------------------
    def _entitlement_allowed(self, item: Dict[str, Any]) -> bool:
        from agents.ecosystem.worker_authorization import check_worker_entitlement

        if self._resolver is None:
            return True
        decision = check_worker_entitlement(
            user_id=item.get("userId"), tenant_id=item.get("tenantId"),
            agent_id=item.get("agentId"), work_id=item.get("workId"),
            resolver=self._resolver,
            api_profile_id=item.get("apiProfileId"))
        return bool(decision.authorized)

    def _execute(self, item: Dict[str, Any]) -> Dict[str, Any]:
        from agents.addition_agent import register_addition_agent
        from agents.agent_body import AgentBody
        from agents.ecosystem.discovery import AgentDiscovery
        from agents.ecosystem.eligibility import EligibilityPipeline
        from agents.ecosystem.event_hook import ProcessingEnvelope
        from agents.ecosystem.registry import AgentRegistry, AgentStatus
        from agents.ecosystem.routing import AgentRouter, ExecutionEngine

        registry = AgentRegistry()
        body = AgentBody()
        register_addition_agent(registry, body)

        # Real discovery + eligibility (active status, capability match).
        discovery = AgentDiscovery(registry)
        candidates = discovery.find(capability=item.get("capability"),
                                    agent_id=item.get("agentId"),
                                    status=AgentStatus.ACTIVE)
        envelope = ProcessingEnvelope(
            order_id=item.get("orderId"),
            processing_id=str(uuid.uuid4()),
            tenant_id=item.get("tenantId") or "",
            agent_id=item.get("agentId"),
            body_version="1.0.0",
            runtime="python3.14",
            execution_profile="LAMBDA",
            input=dict(item),
        )
        pipeline = EligibilityPipeline(registry).check_candidates(candidates,
                                                                  envelope)
        eligible_ids = {c.agent_id for c in pipeline.eligible}
        eligible = [c for c in candidates if c.agent_id in eligible_ids]
        decision = AgentRouter(registry=registry).select(eligible)
        if decision is None:
            raise DemoError("no eligible agent for this capability", status=403)
        if not self._entitlement_allowed(item):
            raise DemoError("agent is not entitled for this caller", status=403)
        return ExecutionEngine(agent_body=body).execute_from_decision(
            decision, envelope)

    def _deliver(self, envelope: Dict[str, Any]) -> None:
        from result_envelope import sign

        body = json.dumps(envelope)
        record = {
            "messageId": envelope["messageId"],
            "body": body,
            "messageAttributes": {"serviceSignature": {
                "stringValue": sign(self._secret, envelope["messageId"], body)}},
        }
        self._orders_consumer({"Records": [record]})

    # -- RisPort ---------------------------------------------------------
    def submit(self, agent_id: str, capability: str,
               payload: Dict[str, Any], idempotency_key: str) -> str:
        from agents.transport import dispatch_to_work_item, validate_envelope

        messages = self._bus.receive_all("agent-dispatch")
        if not messages:
            # Never report success without a delivered message (E03).
            raise DemoError("no dispatch message available", status=503)
        dispatch = validate_envelope(messages[0],
                                     expected_type="ORDER_DISPATCH")
        # The receiver resolves the context reference server-side and applies
        # its own trust; the envelope value is only compared.
        item = dispatch_to_work_item(dispatch, self._context)
        try:
            result = self._execute(item)
        except DemoError:
            raise
        except Exception as exc:  # noqa: BLE001 - mapped to a controlled state
            raise DemoError(f"agent execution failed: {type(exc).__name__}",
                            status=500) from exc

        from agents.transport import ORDER_FAILED, ORDER_RESULT, result_from_work_item

        success = bool(result.get("success"))
        work_row = {
            "workId": item["workId"],
            "status": "COMPLETED" if success else "FAILED",
            "attempt_no": 1,
            "result": result.get("data"),
            "error": result.get("error"),
        }
        out = result_from_work_item(
            dispatch, work_row,
            message_type=ORDER_RESULT if success else ORDER_FAILED)
        self._outcomes[item["workId"]] = out
        self._deliver(out)
        return item["workId"]

    def status(self, work_id: str) -> Dict[str, Any]:
        out = self._outcomes.get(work_id)
        if out is None:
            raise DemoError("work item not found", status=404)
        failed = out["messageType"] == "ORDER_FAILED"
        return {
            "status": "FAILED" if failed else "COMPLETED",
            "result": None if failed else out["payload"],
            "error": out["payload"].get("error") if failed else None,
        }


__all__ = [
    "LocalSqsBus",
    "InMemoryOrdersTable",
    "OrdersApplicationAdapter",
    "RisApplicationAdapter",
    "build_real_service",
]


def build_real_service():
    """Wire the demo against the real Orders and RIS components.

    Requires ``MO_ORDERS_SRC`` plus the usual Orders identity environment.
    SQS stays local (``LocalSqsBus``); nothing is deployed.
    """
    import identity as mo_identity
    import order_service as mo_orders
    import result_handler as mo_result_handler

    from agents.transport import VerifiedContext
    from demo_core import DemoService

    context_ref = os.environ.get("DEMO_CONTEXT_REF", DEFAULT_CONTEXT_REF)
    identity = mo_identity.OwnerIdentity(
        issuer=os.environ["ORDERS_COGNITO_ISSUER"],
        subject=os.environ.get("DEMO_SUBJECT", "partner-a-user"),
        client_id=os.environ["ORDERS_COGNITO_CLIENT_ID"],
    )
    table = InMemoryOrdersTable()
    service = mo_orders.OrderService(os.environ.get("ORDERS_TABLE", "orders"),
                                     client=table)
    bus = LocalSqsBus()
    orders = OrdersApplicationAdapter(service, identity, bus,
                                      context_ref=context_ref)
    context = VerifiedContext(
        context_ref=context_ref,
        tenant_id=os.environ.get("DEMO_TENANT", "tenant-a"),
        owner_id=identity.subject,
        api_profile_id=os.environ.get("DEMO_API_PROFILE", "profile-a"),
        partner_application_id=os.environ.get("DEMO_PARTNER", "partner-a"),
        issuer="https://cognito.internal",
    )
    ris = RisApplicationAdapter(
        bus, context,
        result_secret=os.environ["ORDER_RESULT_SERVICE_SECRET"],
        orders_consumer=mo_result_handler.handler,
    )
    return DemoService(ris=ris, orders=orders)
