#!/usr/bin/env python3
"""Apply one validated MAYS-XREPO-V1 event to the destination issue.

The module deliberately uses argument lists (never a shell) and JSON files for
request bodies. Payload text is escaped before it becomes Markdown.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_event import ValidationError, load_event, validate_event  # noqa: E402

STATE_MARKER_RE = re.compile(
    r"<!-- mays-xrepo:state:([A-Z][A-Z0-9-]{2,63}):([0-9]+) -->"
)


class ApplyError(RuntimeError):
    """A fail-closed receiver error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class Decision:
    action: str
    last_sequence: int | None = None


def _event_marker(event_id: str) -> str:
    return f"<!-- mays-xrepo:event:{event_id} -->"


def _state_marker(task_id: str, sequence: int) -> str:
    return f"<!-- mays-xrepo:state:{task_id}:{sequence} -->"


def _comment_body(comment: Any) -> str:
    if isinstance(comment, dict):
        body = comment.get("body", "")
        return body if isinstance(body, str) else ""
    return ""


def last_sequence(comments: Iterable[Any], task_id: str) -> int | None:
    highest: int | None = None
    for comment in comments:
        for match in STATE_MARKER_RE.finditer(_comment_body(comment)):
            if match.group(1) != task_id:
                continue
            sequence = int(match.group(2))
            if highest is None or sequence > highest:
                highest = sequence
    return highest


def has_event(comments: Iterable[Any], event_id: str) -> bool:
    marker = _event_marker(event_id)
    return any(marker in _comment_body(comment) for comment in comments)


def decide(event: dict[str, Any], comments: Iterable[Any]) -> Decision:
    """Decide without mutating anything: apply, duplicate, stale, or conflict."""

    comments = list(comments)
    if has_event(comments, event["eventId"]):
        return Decision("duplicate")
    highest = last_sequence(comments, event["taskId"])
    if highest is None:
        return Decision("apply")
    if event["sequence"] < highest:
        return Decision("stale", highest)
    if event["sequence"] == highest:
        return Decision("conflict", highest)
    return Decision("apply", highest)


def _escaped(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_comment(
    event: dict[str, Any],
    *,
    received_at: str,
    applied: bool,
    stale_of: int | None = None,
) -> str:
    markers = [_event_marker(event["eventId"])]
    if applied:
        markers.append(_state_marker(event["taskId"], event["sequence"]))

    evidence_lines = []
    for item in event["evidence"]:
        evidence_lines.append(
            f"- `{_escaped(item['kind'])}`: `{_escaped(item['url'])}`"
        )
    if not evidence_lines:
        evidence_lines.append("- none")

    summary = _escaped(event["summary"])
    if stale_of is not None:
        heading = "MAYS-XREPO-V1 — STALE EVENT (not applied)"
        detail = f"Stale sequence `{event['sequence']}`; latest applied sequence is `{stale_of}`."
    else:
        heading = f"MAYS-XREPO-V1 — {_escaped(event['status'])}"
        detail = "Applied to the destination issue."

    return "\n".join(
        [
            *markers,
            f"### {heading}",
            "",
            detail,
            "",
            f"- Task: `{_escaped(event['taskId'])}`",
            f"- Event: `{_escaped(event['eventId'])}`",
            f"- Source: `{_escaped(event['source']['repository'])}#{event['source']['issue']}`",
            f"- Source commit: `{_escaped(event['source']['commit'])}`",
            f"- Destination: `{_escaped(event['destination']['repository'])}#{event['destination']['issue']}`",
            f"- Sequence: `{event['sequence']}`",
            f"- Received: `{_escaped(received_at)}`",
            "",
            f"**Summary:** {summary}",
            "",
            "**Evidence:**",
            *evidence_lines,
        ]
    )


def _run_gh(args: list[str], token: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    try:
        return subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ApplyError("github_cli_missing", "gh CLI is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise ApplyError("github_timeout", "gh CLI timed out") from exc


def _gh_json(args: list[str], token: str) -> Any:
    result = _run_gh(args, token)
    if result.returncode != 0:
        raise ApplyError(
            "github_api_error",
            f"gh api failed with exit code {result.returncode}",
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ApplyError("github_api_error", "gh api returned invalid JSON") from exc


def _gh_jsonl(args: list[str], token: str) -> list[Any]:
    result = _run_gh(args, token)
    if result.returncode != 0:
        raise ApplyError(
            "github_api_error",
            f"gh api failed with exit code {result.returncode}",
        )
    items: list[Any] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ApplyError("github_api_error", "gh api returned invalid JSONL") from exc
    return items


def verify_source(event: dict[str, Any], token: str) -> None:
    """Verify the source issue and commit through the source repository API."""

    source = event["source"]
    repo = source["repository"]
    issue_number = source["issue"]
    commit = source["commit"]

    issue = _gh_json(
        ["api", f"repos/{repo}/issues/{issue_number}"],
        token,
    )
    if not isinstance(issue, dict):
        raise ApplyError("source_not_found", "source issue lookup returned no object")
    if "pull_request" in issue:
        raise ApplyError("source_not_found", "source reference is a pull request, not an issue")
    if issue.get("state") not in {"open", "closed"}:
        raise ApplyError("source_not_found", "source issue has no usable state")

    commit_data = _gh_json(["api", f"repos/{repo}/commits/{commit}"], token)
    if not isinstance(commit_data, dict) or commit_data.get("sha") != commit:
        raise ApplyError("source_not_found", "source commit could not be verified")


def list_comments(repo: str, issue_number: int, token: str) -> list[Any]:
    return _gh_jsonl(
        [
            "api",
            "--paginate",
            "--jq",
            ".[]",
            f"repos/{repo}/issues/{issue_number}/comments",
        ],
        token,
    )


def verify_target_issue(repo: str, issue_number: int, token: str) -> None:
    issue = _gh_json(["api", f"repos/{repo}/issues/{issue_number}"], token)
    if not isinstance(issue, dict):
        raise ApplyError("target_not_found", "destination issue lookup returned no object")
    if "pull_request" in issue:
        raise ApplyError("target_not_found", "destination is a pull request, not an issue")


def post_comment(repo: str, issue_number: int, body: str, token: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump({"body": body}, handle, ensure_ascii=False)
        path = handle.name
    try:
        result = _run_gh(
            [
                "api",
                "--method",
                "POST",
                f"repos/{repo}/issues/{issue_number}/comments",
                "--input",
                path,
            ],
            token,
        )
        if result.returncode != 0:
            raise ApplyError(
                "github_api_error",
                f"comment creation failed with exit code {result.returncode}",
            )
    finally:
        Path(path).unlink(missing_ok=True)


def apply_event(
    event: dict[str, Any],
    *,
    source_token: str,
    target_token: str,
    received_at: str | None = None,
) -> Decision:
    destination = event["destination"]
    repo = destination["repository"]
    issue_number = destination["issue"]

    verify_target_issue(repo, issue_number, target_token)
    verify_source(event, source_token)

    comments = list_comments(repo, issue_number, target_token)
    decision = decide(event, comments)
    if decision.action == "duplicate":
        return decision
    if decision.action == "conflict":
        raise ApplyError(
            "sequence_conflict",
            f"sequence {event['sequence']} already has a different event",
        )
    if decision.action == "stale":
        body = render_comment(
            event,
            received_at=received_at or _now(),
            applied=False,
            stale_of=decision.last_sequence,
        )
        post_comment(repo, issue_number, body, target_token)
        return decision

    body = render_comment(
        event,
        received_at=received_at or _now(),
        applied=True,
    )
    post_comment(repo, issue_number, body, target_token)
    return decision


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply a MAYS-XREPO-V1 event.")
    parser.add_argument("event", help="Path to the event JSON")
    parser.add_argument(
        "--expected-target",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="Require this destination repository (default: GITHUB_REPOSITORY)",
    )
    args = parser.parse_args(argv)

    source_token = os.environ.get("XREPO_SOURCE_TOKEN", "")
    target_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")

    try:
        if not source_token:
            raise ApplyError(
                "blocked_for_live",
                "BLOCKED FOR LIVE: XREPO_SOURCE_TOKEN is missing",
            )
        if not target_token:
            raise ApplyError(
                "blocked_for_live",
                "BLOCKED FOR LIVE: GITHUB_TOKEN is missing",
            )
        event = validate_event(
            load_event(args.event),
            expected_target=args.expected_target,
        )
        decision = apply_event(
            event,
            source_token=source_token,
            target_token=target_token,
        )
    except ValidationError as exc:
        print(f"INVALID {exc}", file=sys.stderr)
        return 2
    except ApplyError as exc:
        print(f"FAILED {exc}", file=sys.stderr)
        return 3

    print(
        f"{decision.action.upper()} "
        f"taskId={event['taskId']} "
        f"eventId={event['eventId']} "
        f"status={event['status']} "
        f"sequence={event['sequence']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
