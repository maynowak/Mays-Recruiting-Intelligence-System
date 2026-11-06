#!/usr/bin/env python3
"""Fail-closed validator for the MAYS-XREPO-V1 handoff protocol.

Stdlib only: GitHub runners and both repositories can run this without adding
dependencies. The JSON schema is the documented contract; this module is the
executable validator and is kept in sync by test_validate_event.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROTOCOL = "MAYS-XREPO-V1"
ALLOWED_REPOSITORIES = frozenset(
    {
        "maynowak/mays-jobsearch",
        "maynowak/Mays-Recruiting-Intelligence-System",
    }
)
ALLOWED_STATUSES = (
    "REQUESTED",
    "ACCEPTED",
    "IMPLEMENTING",
    "IMPLEMENTATION_READY",
    "INTEGRATING",
    "REWORK_REQUIRED",
    "VERIFIED",
    "COMPLETED",
    "BLOCKED",
)
EVIDENCE_KINDS = ("commit", "test", "issue", "document", "workflow")
EXPECTED_KEYS = frozenset(
    {
        "protocol",
        "taskId",
        "eventId",
        "status",
        "source",
        "destination",
        "summary",
        "evidence",
        "sequence",
    }
)
SOURCE_KEYS = frozenset({"repository", "issue", "commit"})
DESTINATION_KEYS = frozenset({"repository", "issue"})
EVIDENCE_KEYS = frozenset({"kind", "url"})
REQUIRE_EVIDENCE_STATUSES = frozenset(
    {"IMPLEMENTATION_READY", "VERIFIED", "COMPLETED", "REWORK_REQUIRED"}
)
# A commit URL is anchored to the verified source SHA; test-only evidence is
# not enough to claim an implementation or completion.
REQUIRE_COMMIT_EVIDENCE_STATUSES = frozenset(
    {"IMPLEMENTATION_READY", "VERIFIED", "COMPLETED"}
)
REQUIRE_REWORK_EVIDENCE = frozenset({"commit", "issue"})
MAX_PAYLOAD_BYTES = 65_535
MAX_EVIDENCE_ITEMS = 10
MAX_SUMMARY_LENGTH = 500
TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9-]{2,63}$")
EVENT_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ISSUE_EVIDENCE_RE = re.compile(r"^issues/[1-9][0-9]*$")
RUN_EVIDENCE_RE = re.compile(r"^actions/runs/[1-9][0-9]*$")
DOCUMENT_EVIDENCE_RE = re.compile(r"^(blob|tree)/[^/].+$")


class ValidationError(ValueError):
    """A protocol violation with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _fail(code: str, message: str) -> None:
    raise ValidationError(code, message)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_exact_keys(value: dict[str, Any], expected: frozenset[str], field: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        _fail("schema", f"{field} missing required keys: {', '.join(missing)}")
    if extra:
        _fail("schema", f"{field} contains unknown keys: {', '.join(extra)}")


def _check_repository(value: Any, field: str, allowlist: frozenset[str]) -> str:
    if not isinstance(value, str) or not value:
        _fail("schema", f"{field}.repository must be a non-empty string")
    if value not in allowlist:
        _fail("unauthorized_repository", f"{field}.repository is not allowlisted: {value}")
    return value


def _check_issue(value: Any, field: str) -> int:
    if not _is_int(value) or value < 1:
        _fail("schema", f"{field}.issue must be a positive integer")
    return value


def _check_commit(value: Any) -> str:
    if not isinstance(value, str) or not COMMIT_RE.match(value):
        _fail("schema", "source.commit must be a 40-character lowercase hexadecimal SHA")
    return value


def _check_summary(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("schema", "summary must be a non-empty string")
    if len(value) > MAX_SUMMARY_LENGTH:
        _fail("schema", f"summary exceeds {MAX_SUMMARY_LENGTH} characters")
    if "<!--" in value:
        _fail("unsafe_summary", "summary must not contain HTML comment markers")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        _fail("unsafe_summary", "summary contains unsupported control characters")
    return value


def _check_evidence_url(url: Any, source_repo: str, source_commit: str, kind: str) -> str:
    if not isinstance(url, str) or not url:
        _fail("schema", "evidence.url must be a non-empty string")
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        _fail("invalid_evidence", "evidence.url must use https")
    if parsed.hostname != "github.com":
        _fail("invalid_evidence", "evidence.url must point to github.com")
    if parsed.username or parsed.password:
        _fail("invalid_evidence", "evidence.url must not contain credentials")
    if parsed.query or parsed.fragment:
        _fail("invalid_evidence", "evidence.url must not contain query or fragment")
    expected_prefix = f"/{source_repo}/"
    if not parsed.path.startswith(expected_prefix):
        _fail("spoofed_source", "evidence.url does not belong to the source repository")
    remainder = parsed.path[len(expected_prefix) :]
    if kind == "commit":
        expected_path = f"{source_repo}/commit/{source_commit}"
        if parsed.path != f"/{expected_path}":
            _fail(
                "invalid_evidence",
                "commit evidence URL must match source repository and source commit",
            )
        return url
    if kind == "issue" and not ISSUE_EVIDENCE_RE.fullmatch(remainder):
        _fail("invalid_evidence", "issue evidence must point to /issues/<number>")
    if kind in {"test", "workflow"}:
        if not (RUN_EVIDENCE_RE.fullmatch(remainder) or
                (kind == "workflow" and DOCUMENT_EVIDENCE_RE.fullmatch(remainder))):
            _fail(
                "invalid_evidence",
                "test/workflow evidence must point to a numeric actions run or a workflow file",
            )
    if kind == "document" and not DOCUMENT_EVIDENCE_RE.fullmatch(remainder):
        _fail("invalid_evidence", "document evidence must point to /blob/ or /tree/")
    return url


def _check_evidence(
    value: Any,
    source_repo: str,
    source_commit: str,
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        _fail("schema", "evidence must be an array")
    if len(value) > MAX_EVIDENCE_ITEMS:
        _fail("schema", f"evidence exceeds {MAX_EVIDENCE_ITEMS} items")
    checked: list[dict[str, str]] = []
    for index, item in enumerate(value):
        field = f"evidence[{index}]"
        if not isinstance(item, dict):
            _fail("schema", f"{field} must be an object")
        _check_exact_keys(item, EVIDENCE_KEYS, field)
        kind = item.get("kind")
        if kind not in EVIDENCE_KINDS:
            _fail("schema", f"{field}.kind is not supported")
        url = _check_evidence_url(item.get("url"), source_repo, source_commit, kind)
        checked.append({"kind": kind, "url": url})
    return checked


def validate_event(
    event: Any,
    *,
    expected_source: str | None = None,
    expected_target: str | None = None,
    allowlist: frozenset[str] = ALLOWED_REPOSITORIES,
) -> dict[str, Any]:
    """Validate one decoded event and return it unchanged on success.

    Raises ValidationError on the first violation. Never executes or evaluates
    strings from the event.
    """

    if not isinstance(event, dict):
        _fail("schema", "event must be a JSON object")
    _check_exact_keys(event, EXPECTED_KEYS, "event")

    if event["protocol"] != PROTOCOL:
        _fail("unsupported_protocol", f"protocol must be {PROTOCOL}")

    task_id = event["taskId"]
    if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id):
        _fail("schema", "taskId must match ^[A-Z][A-Z0-9-]{2,63}$")

    event_id = event["eventId"]
    if not isinstance(event_id, str) or not EVENT_ID_RE.match(event_id):
        _fail("schema", "eventId must be a canonical lowercase UUID v4")

    status = event["status"]
    if status not in ALLOWED_STATUSES:
        _fail("invalid_status", f"status is not supported: {status}")

    source = event["source"]
    if not isinstance(source, dict):
        _fail("schema", "source must be an object")
    _check_exact_keys(source, SOURCE_KEYS, "source")
    source_repo = _check_repository(source["repository"], "source", allowlist)
    _check_issue(source["issue"], "source")
    source_commit = _check_commit(source["commit"])

    destination = event["destination"]
    if not isinstance(destination, dict):
        _fail("schema", "destination must be an object")
    _check_exact_keys(destination, DESTINATION_KEYS, "destination")
    destination_repo = _check_repository(destination["repository"], "destination", allowlist)
    _check_issue(destination["issue"], "destination")

    if source_repo == destination_repo:
        _fail("wrong_target", "source and destination repositories must differ")
    if expected_source is not None and source_repo != expected_source:
        _fail("spoofed_source", "source.repository does not match the expected sender")
    if expected_target is not None and destination_repo != expected_target:
        _fail("wrong_target", "destination.repository does not match the receiving repository")

    _check_summary(event["summary"])
    evidence = _check_evidence(event["evidence"], source_repo, source_commit)

    if status in REQUIRE_EVIDENCE_STATUSES and not evidence:
        _fail("evidence_required", f"status {status} requires at least one evidence item")
    if status in REQUIRE_COMMIT_EVIDENCE_STATUSES and not any(
        item["kind"] == "commit" for item in evidence
    ):
        _fail("evidence_required", f"status {status} requires commit evidence")
    if status == "REWORK_REQUIRED" and not any(
        item["kind"] in REQUIRE_REWORK_EVIDENCE for item in evidence
    ):
        _fail("evidence_required", "REWORK_REQUIRED requires commit, test, or issue evidence")

    if not _is_int(event["sequence"]) or event["sequence"] < 1:
        _fail("schema", "sequence must be a positive integer")

    return event


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("invalid_json", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_event(path: str) -> dict[str, Any]:
    """Read and decode one event, enforcing the size limit before parsing."""

    try:
        raw = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
    except OSError as exc:
        _fail("io_error", f"cannot read event: {exc.__class__.__name__}")
    if len(raw) > MAX_PAYLOAD_BYTES:
        _fail("payload_too_large", f"payload exceeds {MAX_PAYLOAD_BYTES} bytes")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail("invalid_json", "event is not valid UTF-8")
    try:
        return json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        _fail("invalid_json", f"invalid JSON at line {exc.lineno} column {exc.colno}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a MAYS-XREPO-V1 event.")
    parser.add_argument("event", help="Path to the event JSON, or - for stdin")
    parser.add_argument("--expected-source", help="Require this source repository")
    parser.add_argument("--expected-target", help="Require this destination repository")
    args = parser.parse_args(argv)

    try:
        event = validate_event(
            load_event(args.event),
            expected_source=args.expected_source,
            expected_target=args.expected_target,
        )
    except ValidationError as exc:
        print(f"INVALID {exc}", file=sys.stderr)
        return 2

    print(
        "VALID "
        f"taskId={event['taskId']} "
        f"eventId={event['eventId']} "
        f"status={event['status']} "
        f"sequence={event['sequence']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
