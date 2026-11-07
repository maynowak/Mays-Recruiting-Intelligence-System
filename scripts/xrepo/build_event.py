#!/usr/bin/env python3
"""Build one MAYS-XREPO-V1 event from explicit workflow_dispatch inputs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_event import ValidationError, validate_event  # noqa: E402


class BuildError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def build_event(
    *,
    task_id: str,
    status: str,
    source_repository: str,
    source_issue: int,
    source_commit: str,
    destination_repository: str,
    destination_issue: int,
    summary: str,
    evidence: list[dict[str, Any]],
    sequence: int,
    event_id: str | None = None,
) -> dict[str, Any]:
    event = {
        "protocol": "MAYS-XREPO-V1",
        "taskId": task_id,
        "eventId": event_id or str(uuid.uuid4()),
        "status": status,
        "source": {
            "repository": source_repository,
            "issue": source_issue,
            "commit": source_commit,
        },
        "destination": {
            "repository": destination_repository,
            "issue": destination_issue,
        },
        "summary": summary,
        "evidence": evidence,
        "sequence": sequence,
    }
    validate_event(event, expected_source=source_repository)
    return event


def _positive_int(value: str, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BuildError("invalid_input", f"{field} must be an integer") from exc
    if parsed < 1:
        raise BuildError("invalid_input", f"{field} must be positive")
    return parsed


def _parse_evidence(value: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise BuildError("invalid_evidence", "evidence JSON is invalid") from exc
    if not isinstance(parsed, list):
        raise BuildError("invalid_evidence", "evidence must be a JSON array")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a MAYS-XREPO-V1 event.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument(
        "--source-repository",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
    )
    parser.add_argument("--source-issue", required=True)
    parser.add_argument(
        "--source-commit",
        default=os.environ.get("GITHUB_SHA", ""),
    )
    parser.add_argument("--target-repository", required=True)
    parser.add_argument("--target-issue", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--evidence-json", default="[]")
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--event-id")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    try:
        event = build_event(
            task_id=args.task_id,
            status=args.status,
            source_repository=args.source_repository,
            source_issue=_positive_int(args.source_issue, "source-issue"),
            source_commit=args.source_commit,
            destination_repository=args.target_repository,
            destination_issue=_positive_int(args.target_issue, "target-issue"),
            summary=args.summary,
            evidence=_parse_evidence(args.evidence_json),
            sequence=_positive_int(args.sequence, "sequence"),
            event_id=args.event_id,
        )
    except (ValidationError, BuildError) as exc:
        print(f"INVALID {exc}", file=sys.stderr)
        return 2

    output = Path(args.output)
    output.write_text(
        json.dumps(event, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "BUILT "
        f"taskId={event['taskId']} "
        f"eventId={event['eventId']} "
        f"status={event['status']} "
        f"sequence={event['sequence']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
