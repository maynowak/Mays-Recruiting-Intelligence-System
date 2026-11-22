"""Generic remote agent handler for the existing Agent Body.

The Agent Body expects a callable ``process_work(work_item)``. This adapter
implements that contract by invoking a dedicated Lambda synchronously. It adds
no queue, no WorkItem state and no result transport: the worker/ingress keeps
owning WorkItem persistence, attempts, retries and ORDER_RESULT.

The event shape is explicitly execution-only::

    {"executionMode": "agent", "workItem": {...}}

The target Lambda must implement the agent-function entrypoint, not the full
work-item pipeline.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60
MAX_PAYLOAD_BYTES = 512 * 1024


class RemoteAgentError(RuntimeError):
    code = "remote_agent_error"

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        if code:
            self.code = code


class RemoteAgentInputError(RemoteAgentError):
    code = "remote_agent_invalid_input"


class LambdaAgentHandler:
    """Agent Body handler that executes one agent in a dedicated Lambda."""

    def __init__(self, function_name: str, *, client: Any = None,
                 timeout: int = DEFAULT_TIMEOUT_SECONDS,
                 max_payload_bytes: int = MAX_PAYLOAD_BYTES):
        if not function_name:
            raise ValueError("function_name is required")
        self.function_name = function_name
        self._client = client
        self._timeout = int(timeout)
        self._max_payload = int(max_payload_bytes)

    def _lambda(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client("lambda", config=Config(
                connect_timeout=self._timeout,
                read_timeout=self._timeout,
                retries={"max_attempts": 0},
            ))
        return self._client

    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(work_item, dict):
            raise RemoteAgentInputError("work item must be an object")
        encoded = json.dumps(
            {"executionMode": "agent", "workItem": work_item},
            ensure_ascii=False).encode("utf-8")
        if len(encoded) > self._max_payload:
            raise RemoteAgentInputError("work item exceeds the remote limit")

        try:
            response = self._lambda().invoke(
                FunctionName=self.function_name,
                InvocationType="RequestResponse",
                Payload=encoded,
            )
        except Exception as exc:  # noqa: BLE001 - AWS boundary
            raise RemoteAgentError(
                f"remote agent invoke failed: {type(exc).__name__}") from exc

        if int(response.get("StatusCode", 0)) != 200:
            raise RemoteAgentError(
                f"remote agent returned HTTP {response.get('StatusCode')}")
        if response.get("FunctionError"):
            raise RemoteAgentError(
                f"remote agent error: {response.get('FunctionError')}")

        raw = response.get("Payload")
        if hasattr(raw, "read"):
            raw = raw.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            body = json.loads(raw or "{}")
        except ValueError as exc:
            raise RemoteAgentError("remote agent returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise RemoteAgentError("remote agent returned a non-object result")
        error = body.get("error")
        if isinstance(error, dict):
            raise RemoteAgentError(
                str(error.get("message") or "remote agent failed"),
                code=str(error.get("code") or "remote_agent_error"))
        return body


_EXECUTORS: Dict[str, "LambdaAgentHandler"] = {}


def build_analysis_executor(env: Optional[Dict[str, str]] = None):
    """Return the remote analysis handler when configured, else None."""
    env = env or os.environ
    function_name = (env.get("ANALYSIS_FUNCTION_NAME") or "").strip()
    if not function_name:
        return None
    timeout = int(env.get("ANALYSIS_REMOTE_TIMEOUT_SECONDS", "60"))
    key = f"{function_name}:{timeout}"
    handler = _EXECUTORS.get(key)
    if handler is None:
        handler = LambdaAgentHandler(function_name, timeout=timeout)
        _EXECUTORS[key] = handler
    return handler


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "LambdaAgentHandler",
    "MAX_PAYLOAD_BYTES",
    "RemoteAgentError",
    "RemoteAgentInputError",
    "build_analysis_executor",
]
