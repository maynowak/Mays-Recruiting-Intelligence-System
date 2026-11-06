#!/usr/bin/env python3
"""Tests for the sender-side event builder."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from build_event import BuildError, build_event  # noqa: E402
from validate_event import ValidationError, load_event, validate_event  # noqa: E402

SOURCE_REPO = "maynowak/mays-jobsearch"
TARGET_REPO = "maynowak/Mays-Recruiting-Intelligence-System"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def make_event(**overrides):
    values = {
        "task_id": "MAYS-XR-001",
        "status": "REQUESTED",
        "source_repository": SOURCE_REPO,
        "source_issue": 117,
        "source_commit": SOURCE_COMMIT,
        "destination_repository": TARGET_REPO,
        "destination_issue": 42,
        "summary": "Sender test event.",
        "evidence": [],
        "sequence": 1,
    }
    values.update(overrides)
    return build_event(**values)


class BuildTests(unittest.TestCase):
    def test_builds_valid_event_with_uuid_v4(self) -> None:
        event = make_event()
        self.assertEqual(uuid.UUID(event["eventId"]).version, 4)
        self.assertEqual(validate_event(event), event)

    def test_implementation_ready_requires_evidence(self) -> None:
        with self.assertRaises(ValidationError) as caught:
            make_event(status="IMPLEMENTATION_READY", evidence=[])
        self.assertEqual(caught.exception.code, "evidence_required")

    def test_implementation_ready_with_commit_evidence(self) -> None:
        event = make_event(
            status="IMPLEMENTATION_READY",
            evidence=[
                {
                    "kind": "commit",
                    "url": f"https://github.com/{SOURCE_REPO}/commit/{SOURCE_COMMIT}",
                }
            ],
        )
        validate_event(event)

    def test_same_source_and_target_rejected(self) -> None:
        with self.assertRaises(ValidationError) as caught:
            make_event(destination_repository=SOURCE_REPO)
        self.assertEqual(caught.exception.code, "wrong_target")

    def test_invalid_status_rejected(self) -> None:
        with self.assertRaises(ValidationError) as caught:
            make_event(status="DONE")
        self.assertEqual(caught.exception.code, "invalid_status")

    def test_invalid_source_commit_rejected(self) -> None:
        with self.assertRaises(ValidationError) as caught:
            make_event(source_commit="abc")
        self.assertEqual(caught.exception.code, "schema")

    def test_cli_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "event.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "build_event.py"),
                    "--task-id",
                    "MAYS-XR-001",
                    "--status",
                    "REQUESTED",
                    "--source-repository",
                    SOURCE_REPO,
                    "--source-issue",
                    "117",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--target-repository",
                    TARGET_REPO,
                    "--target-issue",
                    "42",
                    "--summary",
                    "CLI test.",
                    "--sequence",
                    "1",
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("BUILT taskId=MAYS-XR-001", result.stdout)
            event = load_event(str(output))
            validate_event(event)
            self.assertEqual(event["source"]["issue"], 117)

    def test_cli_invalid_evidence_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "build_event.py"),
                    "--task-id",
                    "MAYS-XR-001",
                    "--status",
                    "REQUESTED",
                    "--source-repository",
                    SOURCE_REPO,
                    "--source-issue",
                    "117",
                    "--source-commit",
                    SOURCE_COMMIT,
                    "--target-repository",
                    TARGET_REPO,
                    "--target-issue",
                    "42",
                    "--summary",
                    "CLI test.",
                    "--evidence-json",
                    "not-json",
                    "--sequence",
                    "1",
                    "--output",
                    str(Path(directory) / "event.json"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("INVALID invalid_evidence", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
