#!/usr/bin/env python3
"""RealMaysOrdersAdapter — OrdersPort gegen live Mays-Orders (Gate 6).

Gleicher Contract wie DevelopmentOrdersAdapter (submit_order,
get_order_status, can_handle, port_id). Der Agent kennt nur den Port:
keine URLs, kein Transport, keine AWS-Details im Agent-Code.

Integrationsziel (Default): EIGENE Orders-Routen auf UNSERER API
(fronten die live Mays-Orders-Tabelle; eigenes JWT, keine fremden
Credentials/Artefakte). base_url + token_provider sind injizierbar,
der Adapter ist transport-agnostisch.

Fehlerklassifizierung (fuer bestehenden Runtime-Mechanismus):
  kontrolliert (kein Retry): 400/401/403/404/409 + Fachfehler +
    POST-Timeout (Antwort unbekannt -> kein blindes Re-POST;
    safe_to_retry=False, Reconciliation OPEN, s. Report).
  retrybar (Raise TransientOrdersError): 429/502/503/504,
    Verbindungsfehler, GET-/PATCH-Timeouts (GET idempotent;
    PATCH konvergiert via Status-Guard -> 409 statt Doppelwirkung).
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any, Callable, Dict, Optional, Tuple

from agents.orders.adapter import OrdersPort, OrderResult, OrdersResultType

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://aboqolpm0f.execute-api.eu-central-1.amazonaws.com"

CAPABILITY_CREATE = "orders.create"
CAPABILITY_STATUS = "orders.status"
CAPABILITY_CANCEL = "orders.cancel"

SUPPORTED_CAPABILITIES = frozenset({CAPABILITY_CREATE, CAPABILITY_STATUS, CAPABILITY_CANCEL})

#: Root fields of the Mays-Orders OrderV1 create contract. A create payload is
#: forwarded verbatim for exactly these fields, so an agent execution order
#: (orderType + agentOrder) and the MO `orderDescription` reach the API
#: unchanged. Nothing is invented and unknown caller keys are never sent.
#: Mays-Orders forbids combining customer/items/currency with an agentOrder,
#: so the agent branch never adds retail fields.
MO_ORDER_FIELDS = frozenset({
    "orderType",
    "agentOrder",
    "orderDescription",
    "customer",
    "items",
    "currency",
    "totalAmount",
})

#: Retail fields that must not accompany an agent execution order.
MO_RETAIL_FIELDS = ("customer", "items", "currency", "totalAmount")

# HTTP-Status, die zu kontrollierten (nicht retrybaren) Ergebnissen werden.
_CLIENT_ERRORS = {400, 401, 403, 404, 405, 409, 410, 422}
# HTTP-Status, die retrybar sind (Raise).
_RETRYABLE_STATUS = {408, 425, 429, 502, 503, 504}


class TransientOrdersError(Exception):
    """Retrybarer Adapter-Fehler (Runtime entscheidet RETRY)."""

    def __init__(self, message: str, operation: str, status: Optional[int] = None):
        super().__init__(message)
        self.operation = operation
        self.status = status


def _default_request(
    method: str, url: str, headers: Dict[str, str], body: Optional[Dict], timeout: float
) -> Tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if hasattr(exc, "read") else "{}"
        try:
            payload = json.loads(raw or "{}")
        except ValueError:
            payload = {"error": {"code": "HTTP_ERROR", "message": raw[:200]}}
        return exc.code, payload


class RealMaysOrdersAdapter(OrdersPort):
    """OrdersPort gegen live Mays-Orders-HTTP-Contract."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        token_provider: Optional[Callable[[], str]] = None,
        timeout: float = 10.0,
        request_fn: Optional[Callable] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._timeout = timeout
        self._request = request_fn or _default_request
        self._port_id = "real-mays-orders-adapter"

    @property
    def port_id(self) -> str:
        return self._port_id

    def can_handle(self, capability: str) -> bool:
        return capability in SUPPORTED_CAPABILITIES

    # -- intern ---------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token_provider is not None:
            headers["Authorization"] = f"Bearer {self._token_provider()}"
        return headers

    def _call(
        self, operation: str, method: str, path: str, body: Optional[Dict] = None
    ) -> Tuple[int, Any]:
        url = f"{self._base_url}{path}"
        try:
            return self._request(method, url, self._headers(), body, self._timeout)
        except TransientOrdersError:
            raise
        except TimeoutError as exc:
            raise TransientOrdersError(f"{operation} timeout: {exc}", operation) from exc
        except (ConnectionError, OSError) as exc:
            raise TransientOrdersError(f"{operation} connection failed: {exc}", operation) from exc
        except Exception as exc:
            if type(exc).__name__ in ("TimeoutError", "socket.timeout") or "timed out" in str(exc):
                raise TransientOrdersError(f"{operation} timeout: {exc}", operation) from exc
            raise

    @staticmethod
    def _error_result(order_id: Optional[str], code: str, message: str,
                      data: Optional[Dict] = None) -> OrderResult:
        return OrderResult(success=False, order_id=order_id,
                           result_type=OrdersResultType.ERROR,
                           reason=f"{code}: {message}", data=data or {})

    @staticmethod
    def _status_result(status: int, order: Dict[str, Any],
                       context: Dict) -> OrderResult:
        """Separate technical HTTP success from the order's business state.

        ``OrderResult.success`` stays True for a valid 2xx response. The
        business state is ``result_type``: only a terminal
        ``processing.status=COMPLETED`` with a result body is APPROVED. An
        accepted-but-unprocessed order is PENDING, never APPROVED.
        """
        processing = order.get("processing")
        processing = processing if isinstance(processing, dict) else {}
        processing_status = str(processing.get("status") or "").upper()
        order_status = str(order.get("status") or "").upper()
        order_type = str(order.get("orderType") or "").lower()
        is_agent_order = order_type == "agent.execution"
        order_id = order.get("orderId")
        data: Dict[str, Any] = {
            "order": order,
            "http_status": status,
            "order_status": order_status,
            "order_type": order_type,
            "processing": processing,
            "processing_status": processing_status,
            **context,
        }
        if processing_status == "COMPLETED":
            result = processing.get("result")
            if isinstance(result, dict):
                return OrderResult(
                    success=True, order_id=order_id,
                    result_type=OrdersResultType.APPROVED,
                    reason="processing completed", data=data)
            return OrderResult(
                success=True, order_id=order_id,
                result_type=OrdersResultType.ERROR,
                reason="processing completed without a result body",
                data={**data, "contract_error": "missing_processing_result"})
        if processing_status == "FAILED":
            error = processing.get("error")
            message = (str(error.get("message"))
                       if isinstance(error, dict) and error.get("message")
                       else "agent execution failed")
            return OrderResult(
                success=True, order_id=order_id,
                result_type=OrdersResultType.REJECTED,
                reason=f"processing failed: {message}", data=data)
        if order_status == "CANCELLED":
            return OrderResult(
                success=True, order_id=order_id,
                result_type=OrdersResultType.REJECTED,
                reason="order cancelled", data=data)
        if order_status == "DELIVERED":
            if is_agent_order:
                # A terminal agent-execution order without a processing result
                # is a contract inconsistency, not a successful execution.
                return OrderResult(
                    success=True, order_id=order_id,
                    result_type=OrdersResultType.ERROR,
                    reason=("agent execution delivered without a processing "
                            "result"),
                    data={**data,
                          "contract_error": "missing_processing_result"})
            return OrderResult(
                success=True, order_id=order_id,
                result_type=OrdersResultType.APPROVED,
                reason="order delivered", data=data)
        return OrderResult(
            success=True, order_id=order_id,
            result_type=OrdersResultType.PENDING,
            reason=f"processing {processing_status or 'not started'}",
            data=data)

    def _map_response(self, operation: str, status: int, payload: Any,
                      order_id: Optional[str], context: Dict) -> OrderResult:
        if 200 <= status < 300 and isinstance(payload, dict) and payload.get("orderId"):
            order = payload
            if operation == "status":
                return self._status_result(status, order, context)
            order_status = str(order.get("status") or "").upper()
            rtype = (OrdersResultType.PENDING if operation == "create"
                     and order_status == "PENDING"
                     else OrdersResultType.APPROVED)
            return OrderResult(success=True, order_id=order.get("orderId"),
                               result_type=rtype, reason=f"{operation} ok",
                               data={"order": order, "http_status": status,
                                     "order_status": order_status, **context})
        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"] or {}
            code = err.get("code", f"HTTP_{status}")
            msg = err.get("message", "")
            if status in _CLIENT_ERRORS:
                return self._error_result(order_id or payload.get("orderId"),
                                          code, msg, {"http_status": status, **context})
        if status in _RETRYABLE_STATUS:
            raise TransientOrdersError(f"{operation} HTTP {status}", operation, status)
        if 500 <= status < 600:
            raise TransientOrdersError(f"{operation} HTTP {status}", operation, status)
        # Never echo an unexpected response body: it may contain foreign or
        # credential-shaped data. Only the HTTP status/context is retained.
        return self._error_result(order_id, f"HTTP_{status}",
                                  f"Unerwartete Antwort ({status})",
                                  {"http_status": status, **context})

    # -- Port -----------------------------------------------------------
    def submit_order(self, work_item: Dict[str, Any], capability: str,
                     payload: Optional[Dict[str, Any]] = None,
                     tenant_id: Optional[str] = None,
                     actor_id: Optional[str] = None,
                     idempotency_key: Optional[str] = None) -> OrderResult:
        work_id = (work_item or {}).get("workId", "unknown")
        context = {"work_id": work_id, "tenant_id": tenant_id,
                   "actor_id": actor_id, "capability": capability}
        logger.info("RealMaysOrdersAdapter.submit: workId=%s capability=%s tenant=%s",
                    work_id, capability, tenant_id)
        payload = payload or {}
        if capability == CAPABILITY_CREATE:
            # Forward the complete MO OrderV1 payload: retail fields plus an
            # optional agent execution order and its root-level
            # `orderDescription`. Only contract fields are sent; caller keys
            # outside the MO contract are dropped, never forwarded.
            order = {key: payload[key] for key in MO_ORDER_FIELDS if key in payload}
            agent_execution = (
                payload.get("agentOrder") is not None
                or str(payload.get("orderType") or "").lower() == "agent.execution"
            )
            if agent_execution:
                # Mays-Orders rejects customer/items/currency together with an
                # agentOrder; forwarding them would make the call invalid.
                for retail in MO_RETAIL_FIELDS:
                    order.pop(retail, None)
            else:
                order["customer"] = payload.get("customer")
                order["items"] = payload.get("items")
                order["currency"] = payload.get("currency", "EUR")
            try:
                status, resp = self._call("create", "POST", "/orders", order)
                if 200 <= status < 300 and isinstance(resp, dict) and resp.get("orderId"):
                    return self._map_response("create", status, resp, None, context)
                return self._map_response("create", status, resp, None, context)
            except TransientOrdersError as exc:
                # POST-Antwort unbekannt (429/5xx/Timeout/Transport) ->
                # kontrolliert, kein blindes Re-POST (Doppel-Order-Risiko).
                logger.warning("RealMaysOrdersAdapter.create unsicher (%s): kein Retry", exc)
                return self._error_result(
                    None, "POST_UNKNOWN",
                    f"Create-Antwort unbekannt ({exc}); "
                    "kein automatisches Re-POST (Doppel-Order-Risiko)",
                    {"safe_to_retry": False, **context})
        if capability == CAPABILITY_CANCEL:
            order_id = payload.get("orderId")
            if not order_id:
                return self._error_result(None, "VALIDATION_ERROR",
                                          "payload.orderId fehlt", context)
            status, resp = self._call("cancel", "PATCH", f"/orders/{order_id}/status",
                                      {"status": "CANCELLED"})
            return self._map_response("cancel", status, resp, order_id, context)
        return self._error_result(None, "UNSUPPORTED_CAPABILITY",
                                  f"Capability nicht unterstuetzt: {capability}", context)

    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        status, resp = self._call("status", "GET", f"/orders/{order_id}", None)
        if status == 404:
            return None
        result = self._map_response("status", status, resp, order_id, {})
        return result


__all__ = [
    "RealMaysOrdersAdapter",
    "TransientOrdersError",
    "DEFAULT_BASE_URL",
    "CAPABILITY_CREATE",
    "CAPABILITY_STATUS",
    "CAPABILITY_CANCEL",
    "MO_ORDER_FIELDS",
]
