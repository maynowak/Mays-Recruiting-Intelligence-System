"""Thin SQS sender for the existing Transport V1 ORDER_RESULT envelope.

This is a signing/transport primitive, not a second envelope contract. The
HMAC rule is pinned to the Orders consumer:

    serviceSignature = HMAC-SHA256(secret, messageId + "\n" + body)

No queue is created here; the caller supplies the existing result queue URL
and secret ARN. Missing configuration is handled by the caller (fail-closed).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any, Callable, Dict, Optional


def _json_default(value: Any) -> Any:
    """Keep DynamoDB Decimals numeric on the wire (re-emit path).

    Items read back from DynamoDB return every number as ``Decimal``. A plain
    ``default=str`` would sign and send ``"42"`` instead of ``42``, so the first
    body after a crash would differ in type from a fresh execution.
    """
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")



def sign_result(secret: str, message_id: str, body: str) -> str:
    """Return the hex HMAC expected by the Orders result consumer."""
    material = f"{message_id}\n{body}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()


def make_sender(
    queue_url: str,
    secret_arn: str,
    *,
    sqs_client: Any = None,
    secrets_client: Any = None,
) -> Callable[[Dict[str, Any]], None]:
    """Build a sender callable for one configured result queue/secret."""
    cached_secret: Dict[str, str] = {}

    def _secret() -> str:
        if "value" not in cached_secret:
            import boto3

            client = secrets_client or boto3.client("secretsmanager")
            response = client.get_secret_value(SecretId=secret_arn)
            value = response.get("SecretString") or ""
            if not value:
                raise RuntimeError("ORDER_RESULT_SECRET_ARN has no value")
            cached_secret["value"] = value
        return cached_secret["value"]

    def _send(envelope: Dict[str, Any]) -> None:
        body = json.dumps(envelope, separators=(",", ":"), default=_json_default)
        signature = sign_result(_secret(), envelope["messageId"], body)
        client = sqs_client
        if client is None:
            import boto3

            client = boto3.client("sqs")
        client.send_message(
            QueueUrl=queue_url,
            MessageBody=body,
            MessageAttributes={
                "serviceSignature": {
                    "DataType": "String",
                    "StringValue": signature,
                }
            },
        )

    return _send


__all__ = ["make_sender", "sign_result"]
