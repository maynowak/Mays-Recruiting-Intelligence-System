"""Internal Lambda adapter for the dedicated Node parser runtime.

Used instead of the local CLI when ``RIS_PARSER_MODE=lambda``. The payload and
envelope contract is identical to the CLI; no public HTTP endpoint and no
shared transport policy is involved.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from agents.parsers.node_adapter import (
    MAX_PAYLOAD_CHARS,
    SUPPORTED_CAPABILITIES,
    ParserInputError,
    ParserResult,
    ParserUnavailable,
    _validate_envelope,
)

DEFAULT_TIMEOUT_SECONDS = 15


def parse_via_lambda(
    capability: str,
    payload: Dict[str, Any],
    *,
    function_name: Optional[str] = None,
    client: Any = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ParserResult:
    if capability not in SUPPORTED_CAPABILITIES:
        raise ParserInputError(f"unsupported capability: {capability}")
    if not isinstance(payload, dict):
        raise ParserInputError("payload must be an object")
    encoded = json.dumps({"capability": capability, "input": payload},
                         ensure_ascii=False)
    if len(encoded) > MAX_PAYLOAD_CHARS:
        raise ParserInputError("payload exceeds the parser size limit")

    name = function_name or os.environ.get("RIS_PARSER_FUNCTION", "")
    if not name:
        raise ParserUnavailable(
            "RIS_PARSER_FUNCTION is not configured for the Lambda parser mode")
    if client is None:
        import boto3

        client = boto3.client("lambda")

    try:
        response = client.invoke(
            FunctionName=name,
            InvocationType="RequestResponse",
            Payload=encoded.encode("utf-8"),
        )
    except Exception as exc:  # noqa: BLE001 - AWS boundary
        raise ParserUnavailable(
            f"parser Lambda invoke failed: {type(exc).__name__}") from exc

    if int(response.get("StatusCode", 0)) != 200:
        raise ParserUnavailable(
            f"parser Lambda returned HTTP {response.get('StatusCode')}")
    if response.get("FunctionError"):
        raise ParserUnavailable(
            f"parser Lambda error: {response.get('FunctionError')}")

    raw = response.get("Payload")
    if hasattr(raw, "read"):
        raw = raw.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        body = json.loads(raw or "{}")
    except ValueError as exc:
        raise ParserUnavailable("parser Lambda returned invalid JSON") from exc

    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        code = str(body["error"].get("code") or "parser_error")
        message = str(body["error"].get("message") or "parser failed")
        if code in ("invalid_input", "too_large", "unsupported_capability"):
            raise ParserInputError(f"{code}: {message}")
        raise ParserUnavailable(f"{code}: {message}")

    return _validate_envelope(capability, body)


__all__ = ["parse_via_lambda"]
