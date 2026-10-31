"""R07-G0 test support: strictly local DynamoDB configuration.

Nothing in this module may reach AWS.  Every entry point refuses anything that
is not an explicit loopback endpoint, and table names must live in the
dedicated ``ris-r07g0-`` namespace.  The guards are used by
``tests/integration/test_partner_profile_dynamodb_local.py`` and are also
unit-tested by ``tests/test_partner_profile_integration_harness.py``.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from typing import Callable, Optional, TypeVar
from urllib.parse import urlsplit

ENDPOINT_ENV = "RIS_TEST_DYNAMODB_ENDPOINT"
TABLE_PREFIX_ENV = "RIS_TEST_TABLE_PREFIX"

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
TABLE_PREFIX = "ris-r07g0-"
TABLE_NAME_RE = re.compile(r"^ris-r07g0-[a-z0-9][a-z0-9-]{1,40}$")

# Names that must never be accepted as a local test table: production/dev
# families, foreign projects and AWS endpoints.
PROTECTED_MARKERS = (
    "amazonaws.com",
    "ris-dev",
    "ris-development",
    "mays-ris",
    "mays-orders",
    "partner-profiles",
    "prod",
)

T = TypeVar("T")


class UnsafeTestConfiguration(RuntimeError):
    """Raised when a local integration test would leave the local sandbox."""


def require_local_endpoint(raw: Optional[str] = None) -> str:
    """Return a normalised loopback endpoint or raise.

    The endpoint must be supplied explicitly (argument or environment
    variable).  There is deliberately no default: an unset variable is a hard
    stop, never an implicit AWS endpoint.
    """
    value = raw if raw is not None else os.environ.get(ENDPOINT_ENV)
    if value is None or not str(value).strip():
        raise UnsafeTestConfiguration(
            f"{ENDPOINT_ENV} is not set; refusing to guess an endpoint")
    value = str(value).strip()
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https"):
        raise UnsafeTestConfiguration(
            f"endpoint scheme must be http(s), got {parts.scheme!r}")
    if parts.username or parts.password:
        raise UnsafeTestConfiguration("endpoint must not embed credentials")
    host = (parts.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        raise UnsafeTestConfiguration(
            f"endpoint host {host!r} is not loopback; AWS is forbidden here")
    if parts.query or parts.fragment:
        raise UnsafeTestConfiguration("endpoint must not carry query/fragment")
    if parts.path not in ("", "/"):
        raise UnsafeTestConfiguration("endpoint must not contain a path")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeTestConfiguration("endpoint port is invalid") from exc
    if port is None:
        raise UnsafeTestConfiguration(
            "endpoint must state an explicit port (e.g. :8000)")
    if not 1 <= port <= 65535:
        raise UnsafeTestConfiguration("endpoint port out of range")
    display_host = f"[{host}]" if ":" in host else host
    return f"{parts.scheme}://{display_host}:{port}"


def require_test_table_name(name: str) -> str:
    """Validate an isolated R07-G0 table name or raise."""
    if not isinstance(name, str) or not name:
        raise UnsafeTestConfiguration("table name must be a non-empty string")
    lowered = name.lower()
    for marker in PROTECTED_MARKERS:
        if marker in lowered:
            raise UnsafeTestConfiguration(
                f"table name {name!r} contains protected marker {marker!r}")
    if not TABLE_NAME_RE.match(name):
        raise UnsafeTestConfiguration(
            f"table name {name!r} is outside the {TABLE_PREFIX} namespace")
    configured = os.environ.get("PARTNER_PROFILE_TABLE")
    if configured and configured == name:
        raise UnsafeTestConfiguration(
            "refusing to use the configured production table name")
    return name


def new_test_table_name() -> str:
    suffix = os.environ.get(TABLE_PREFIX_ENV, "").strip()
    if suffix:
        candidate = require_test_table_name(suffix)
        return candidate
    return require_test_table_name(TABLE_PREFIX + uuid.uuid4().hex[:12])


def build_local_dynamodb(endpoint: Optional[str] = None):
    """Create a boto3 resource pinned to the loopback endpoint.

    Static dummy credentials are used so the SDK cannot fall back to a real
    profile, instance role or environment credential chain.
    """
    url = require_local_endpoint(endpoint)
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise UnsafeTestConfiguration(
            "boto3/botocore is not installed; DynamoDB Local tests are blocked"
        ) from exc
    return boto3.resource(
        "dynamodb",
        endpoint_url=url,
        region_name="us-west-2",
        aws_access_key_id="ris-r07g0-local",
        aws_secret_access_key="ris-r07g0-local",
        config=Config(retries={"max_attempts": 2, "mode": "standard"}),
    )


def poll_until(predicate: Callable[[], T], *, timeout: float = 10.0,
               interval: float = 0.05) -> T:
    """Poll a predicate until it is truthy (GSI eventual consistency)."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    return last
