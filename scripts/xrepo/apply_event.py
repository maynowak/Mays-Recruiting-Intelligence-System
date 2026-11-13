#!/usr/bin/env python3
"""Apply one validated MAYS-XREPO-V1 event to the destination issue.

The module deliberately uses argument lists (never a shell) and JSON files for
request bodies. Payload text is escaped before it becomes Markdown.

State is reconstructed from trusted bot comments:
- applied events carry a status-bearing state marker;
- rejected events carry a rejection marker and never change state;
- stale events are logged but never change state.
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
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_event import ValidationError, load_event, validate_event  # noqa: E402

STATE_MARKER_RE = re.compile(
    r"<!-- mays-xrepo:state:([A-Z][A-Z0-9-]{2,63}):([0-9]+)(?::([A-Z_]+))? -->"
)
EVENT_MARKER_RE = re.compile(r"<!-- mays-xrepo:event:([0-9a-f-]{36}) -->")
REJECTION_PREFIX = "<!-- mays-xrepo:rejected:"
REJECTION_MARKER_RE = re.compile(
    r"<!-- mays-xrepo:rejected:([0-9a-f-]{36}):([a-z_]+) -->"
)
TRUSTED_MARKER_AUTHORS = frozenset({"github-actions[bot]"})
MAX_REWORK_ROUNDS = 3

INITIAL_STATUSES = frozenset({"REQUESTED", "BLOCKED"})
STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "REQUESTED": frozenset({"ACCEPTED", "BLOCKED"}),
    "ACCEPTED": frozenset({"IMPLEMENTING", "BLOCKED"}),
    "IMPLEMENTING": frozenset({"IMPLEMENTATION_READY", "BLOCKED"}),
    "IMPLEMENTATION_READY": frozenset({"INTEGRATING", "VERIFIED", "REWORK_REQUIRED", "BLOCKED"}),
    "INTEGRATING": frozenset({"VERIFIED", "REWORK_REQUIRED", "BLOCKED"}),
    "REWORK_REQUIRED": frozenset({"IMPLEMENTATION_READY", "BLOCKED"}),
    "VERIFIED": frozenset({"COMPLETED", "BLOCKED"}),
    "COMPLETED": frozenset(),
    "BLOCKED": frozenset(),
}
REJECTION_OUTCOMES = frozenset({"conflict", "invalid_transition", "rework_limit"})


class ApplyError(RuntimeError):
    """A fail-closed receiver error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class State:
    sequence: int
    status: str | None
    event_id: str | None = None


@dataclass(frozen=True)
class Decision:
    action: str
    last_sequence: int | None = None
    last_status: str | None = None
    reason: str | None = None


def _event_marker(event_id: str) -> str:
    return f"<!-- mays-xrepo:event:{event_id} -->"


def _state_marker(task_id: str, sequence: int, status: str) -> str:
    return f"<!-- mays-xrepo:state:{task_id}:{sequence}:{status} -->"


def _rejection_marker(event_id: str, reason: str) -> str:
    return f"{REJECTION_PREFIX}{event_id}:{reason} -->"


def _comment_body(comment: Any) -> str:
    if isinstance(comment, dict):
        body = comment.get("body", "")
        return body if isinstance(body, str) else ""
    return ""


def _is_trusted_marker(comment: Any) -> bool:
    """Only bot-authored comments may define event/state markers.

    Issue comment text is user-controlled. Without this check a third party
    could inject a high sequence or an event marker and suppress real events.
    """

    if not isinstance(comment, dict):
        return False
    user = comment.get("user")
    if not isinstance(user, dict):
        return False
    return user.get("login") in TRUSTED_MARKER_AUTHORS


def _trusted_comments(comments: Iterable[Any]) -> Iterable[Any]:
    return (comment for comment in comments if _is_trusted_marker(comment))


def last_state(comments: Iterable[Any], task_id: str) -> State | None:
    best: State | None = None
    for comment in _trusted_comments(comments):
        body = _comment_body(comment)
        event_ids = [match.group(1) for match in EVENT_MARKER_RE.finditer(body)]
        state_matches = [
            match for match in STATE_MARKER_RE.finditer(body)
            if match.group(1) == task_id
        ]
        if len(event_ids) > 1 or len(state_matches) > 1:
            # A single trusted comment may not declare multiple events or
            # multiple states for one task. Preserve a sequence number for
            # diagnostics but fail closed on the status.
            sequences = [int(match.group(2)) for match in state_matches]
            if sequences:
                seq = max(sequences)
                if best is None or seq > best.sequence:
                    best = State(sequence=seq, status=None)
            elif best is not None:
                best = State(sequence=best.sequence, status=None)
            continue
        for match in state_matches:
            sequence = int(match.group(2))
            status = match.group(3)
            event_id = event_ids[0] if len(event_ids) == 1 else None
            if best is None or sequence > best.sequence:
                best = State(sequence=sequence, status=status, event_id=event_id)
            elif sequence == best.sequence:
                if status != best.status or (
                        best.event_id is not None and event_id is not None
                        and best.event_id != event_id):
                    # Same sequence with different statuses or different
                    # event identities is not a usable history.
                    best = State(sequence=sequence, status=None)
                elif best.event_id is None and event_id is not None:
                    best = State(sequence=sequence, status=status, event_id=event_id)
    return best


def last_sequence(comments: Iterable[Any], task_id: str) -> int | None:
    state = last_state(comments, task_id)
    return state.sequence if state else None


def has_event(comments: Iterable[Any], event_id: str) -> bool:
    marker = _event_marker(event_id)
    return any(marker in _comment_body(comment) for comment in _trusted_comments(comments))


def event_consistent(comments: Iterable[Any], event: dict[str, Any]) -> bool:
    """A replay of an event id must carry the same task/sequence/status."""
    marker = _event_marker(event["eventId"])
    found = False
    for comment in _trusted_comments(comments):
        body = _comment_body(comment)
        if marker not in body:
            continue
        found = True
        states = [m for m in STATE_MARKER_RE.finditer(body) if m.group(1) == event["taskId"]]
        if not states:
            continue
        if len(states) != 1:
            return False
        state = states[0]
        if int(state.group(2)) != event["sequence"] or state.group(3) != event["status"]:
            return False
    return found


def has_rejected(comments: Iterable[Any], event_id: str) -> bool:
    prefix = f"{REJECTION_PREFIX}{event_id}:"
    return any(
        prefix in _comment_body(comment) for comment in _trusted_comments(comments)
    )


def rework_count(comments: Iterable[Any], task_id: str) -> int:
    count = 0
    for comment in _trusted_comments(comments):
        for match in STATE_MARKER_RE.finditer(_comment_body(comment)):
            if match.group(1) == task_id and match.group(3) == "REWORK_REQUIRED":
                count += 1
    return count


def decide(event: dict[str, Any], comments: Iterable[Any]) -> Decision:
    """Decide without mutating anything.

    Actions: apply, duplicate, rejected_duplicate, stale, conflict,
    invalid_transition, rework_limit, state_unreadable.
    """

    comments = list(comments)
    if has_rejected(comments, event["eventId"]):
        return Decision("rejected_duplicate", reason="event was already rejected")
    if has_event(comments, event["eventId"]):
        if not event_consistent(comments, event):
            return Decision("conflict", reason="event id appears with a different state")
        return Decision("duplicate")

    state = last_state(comments, event["taskId"])
    if state is None:
        if event["status"] not in INITIAL_STATUSES:
            return Decision(
                "invalid_transition",
                reason=f"initial status must be one of {sorted(INITIAL_STATUSES)}",
            )
        return Decision("apply")

    if event["sequence"] < state.sequence:
        return Decision("stale", last_sequence=state.sequence, last_status=state.status)
    if event["sequence"] == state.sequence:
        return Decision(
            "conflict",
            last_sequence=state.sequence,
            last_status=state.status,
            reason="sequence already belongs to a different event",
        )
    if state.status is None:
        return Decision(
            "state_unreadable",
            last_sequence=state.sequence,
            reason="latest state marker has no status",
        )

    allowed = STATUS_TRANSITIONS.get(state.status, frozenset())
    if event["status"] not in allowed:
        return Decision(
            "invalid_transition",
            last_sequence=state.sequence,
            last_status=state.status,
            reason=f"{state.status} -> {event['status']} is not allowed",
        )
    if event["status"] == "REWORK_REQUIRED" and rework_count(
        comments, event["taskId"]
    ) >= MAX_REWORK_ROUNDS:
        return Decision(
            "rework_limit",
            last_sequence=state.sequence,
            last_status=state.status,
            reason=f"maximum of {MAX_REWORK_ROUNDS} rework rounds reached",
        )
    return Decision("apply", last_sequence=state.sequence, last_status=state.status)


def _escaped(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_comment(
    event: dict[str, Any],
    *,
    received_at: str,
    outcome: str = "applied",
    stale_of: int | None = None,
    reason: str | None = None,
) -> str:
    markers = [_event_marker(event["eventId"])]
    if outcome == "applied":
        markers.append(
            _state_marker(event["taskId"], event["sequence"], event["status"])
        )
    elif outcome in REJECTION_OUTCOMES:
        markers.append(_rejection_marker(event["eventId"], outcome))

    evidence_lines = []
    for item in event["evidence"]:
        evidence_lines.append(
            f"- `{_escaped(item['kind'])}`: `{_escaped(item['url'])}`"
        )
    if not evidence_lines:
        evidence_lines.append("- none")

    if outcome == "stale":
        heading = "MAYS-XREPO-V1 — STALE EVENT (not applied)"
        detail = (
            f"Stale sequence `{event['sequence']}`; latest applied sequence is "
            f"`{stale_of}`. No state change was applied."
        )
    elif outcome == "conflict":
        heading = "MAYS-XREPO-V1 — REJECTED: SEQUENCE CONFLICT"
        detail = (
            f"{_escaped(reason or 'sequence already belongs to a different event')}. "
            "No state change was applied."
        )
    elif outcome == "invalid_transition":
        heading = "MAYS-XREPO-V1 — REJECTED: INVALID STATUS TRANSITION"
        detail = (
            f"{_escaped(reason or 'status transition is not allowed')}. "
            "No state change was applied."
        )
    elif outcome == "rework_limit":
        heading = "MAYS-XREPO-V1 — REJECTED: REWORK LIMIT REACHED"
        detail = (
            f"{_escaped(reason or 'maximum rework rounds reached')}. "
            "No state change was applied."
        )
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
            f"- Status: `{_escaped(event['status'])}`",
            f"- Source: `{_escaped(event['source']['repository'])}#{event['source']['issue']}`",
            f"- Source commit: `{_escaped(event['source']['commit'])}`",
            f"- Destination: `{_escaped(event['destination']['repository'])}#{event['destination']['issue']}`",
            f"- Sequence: `{event['sequence']}`",
            f"- Received: `{_escaped(received_at)}`",
            "",
            f"**Summary:** {_escaped(event['summary'])}",
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


def _issue_matches_task(issue: dict[str, Any], task_id: str) -> bool:
    title = issue.get("title")
    body = issue.get("body")
    text = "\n".join(value for value in (title, body) if isinstance(value, str))
    return bool(task_id) and task_id in text


def verify_source(event: dict[str, Any], token: str, *,
                  task_id: str | None = None) -> None:
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
    if task_id is not None and not _issue_matches_task(issue, task_id):
        raise ApplyError("issue_binding_invalid", "source issue is not bound to the task")

    commit_data = _gh_json(["api", f"repos/{repo}/commits/{commit}"], token)
    if not isinstance(commit_data, dict) or commit_data.get("sha") != commit:
        raise ApplyError("source_not_found", "source commit could not be verified")


def verify_evidence(event: dict[str, Any], token: str) -> None:
    """Verify issue evidence through the source API.

    Commit evidence is already anchored to the verified source SHA. Test and
    document evidence remain repository-bound references; they are not executed
    and are not treated as independent test proof.
    """

    source_repo = event["source"]["repository"]
    for item in event["evidence"]:
        if item["kind"] != "issue":
            continue
        parsed = urlsplit(item["url"])
        prefix = f"/{source_repo}/issues/"
        if not parsed.path.startswith(prefix):
            raise ApplyError("evidence_invalid", "issue evidence is outside the source repository")
        number_text = parsed.path[len(prefix) :]
        if not number_text.isdigit() or int(number_text) < 1:
            raise ApplyError("evidence_invalid", "issue evidence has no valid issue number")
        issue = _gh_json(
            ["api", f"repos/{source_repo}/issues/{int(number_text)}"],
            token,
        )
        if not isinstance(issue, dict) or "pull_request" in issue:
            raise ApplyError("evidence_invalid", "issue evidence could not be verified")


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


def verify_target_issue(repo: str, issue_number: int, token: str, *,
                        task_id: str | None = None) -> None:
    issue = _gh_json(["api", f"repos/{repo}/issues/{issue_number}"], token)
    if not isinstance(issue, dict):
        raise ApplyError("target_not_found", "destination issue lookup returned no object")
    if "pull_request" in issue:
        raise ApplyError("target_not_found", "destination is a pull request, not an issue")
    if task_id is not None and not _issue_matches_task(issue, task_id):
        raise ApplyError("issue_binding_invalid", "destination issue is not bound to the task")


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
    timestamp = received_at or _now()

    task_id = event["taskId"]
    verify_target_issue(repo, issue_number, target_token, task_id=task_id)
    verify_source(event, source_token, task_id=task_id)
    verify_evidence(event, source_token)

    target_comments = list_comments(repo, issue_number, target_token)
    source = event["source"]
    source_comments = list_comments(
        source["repository"], source["issue"], source_token)
    comments = target_comments + source_comments
    decision = decide(event, comments)
    if decision.action == "duplicate":
        return decision
    if decision.action == "rejected_duplicate":
        raise ApplyError(
            "rejected_duplicate",
            "event was previously rejected; no state change",
        )
    if decision.action == "state_unreadable":
        raise ApplyError(
            "state_unreadable",
            "latest state marker has no status; manual recovery required",
        )
    if decision.action == "stale":
        body = render_comment(
            event,
            received_at=timestamp,
            outcome="stale",
            stale_of=decision.last_sequence,
        )
        post_comment(repo, issue_number, body, target_token)
        return decision
    if decision.action in REJECTION_OUTCOMES:
        body = render_comment(
            event,
            received_at=timestamp,
            outcome=decision.action,
            reason=decision.reason,
        )
        post_comment(repo, issue_number, body, target_token)
        raise ApplyError(decision.action, decision.reason or decision.action)

    body = render_comment(event, received_at=timestamp, outcome="applied")
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
