#!/usr/bin/env python3
"""Contract tests for the MAYS-XREPO-V1 validator and schema."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from validate_event import (  # noqa: E402
    ALLOWED_REPOSITORIES,
    ALLOWED_STATUSES,
    EVENT_ID_RE,
    EVIDENCE_KINDS,
    EXPECTED_KEYS,
    MAX_EVIDENCE_ITEMS,
    MAX_PAYLOAD_BYTES,
    PROTOCOL,
    ValidationError,
    load_event,
    validate_event,
)

FIXTURES = REPO_ROOT / "docs" / "xrepo" / "fixtures"
SCHEMA = REPO_ROOT / "docs" / "xrepo" / "MAYS-XREPO-V1.schema.json"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
SOURCE_REPO = "maynowak/Mays-Recruiting-Intelligence-System"
TARGET_REPO = "maynowak/mays-jobsearch"


def valid_event() -> dict:
    return {
        "protocol": PROTOCOL,
        "taskId": "MAYS-XR-001",
        "eventId": "f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5",
        "status": "IMPLEMENTATION_READY",
        "source": {
            "repository": SOURCE_REPO,
            "issue": 42,
            "commit": SOURCE_COMMIT,
        },
        "destination": {"repository": TARGET_REPO, "issue": 117},
        "summary": "Implementation and tests are available locally.",
        "evidence": [
            {
                "kind": "commit",
                "url": f"https://github.com/{SOURCE_REPO}/commit/{SOURCE_COMMIT}",
            }
        ],
        "sequence": 3,
    }


class ValidatorTests(unittest.TestCase):
    def assert_invalid(self, event: dict, code: str, **kwargs) -> None:
        with self.assertRaises(ValidationError) as caught:
            validate_event(event, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_valid_event(self) -> None:
        event = valid_event()
        self.assertIs(validate_event(event), event)

    def test_missing_field(self) -> None:
        event = valid_event()
        del event["summary"]
        self.assert_invalid(event, "schema")

    def test_extra_field(self) -> None:
        event = valid_event()
        event["unexpected"] = True
        self.assert_invalid(event, "schema")

    def test_wrong_protocol(self) -> None:
        event = valid_event()
        event["protocol"] = "MAYS-XREPO-V2"
        self.assert_invalid(event, "unsupported_protocol")

    def test_invalid_status(self) -> None:
        event = valid_event()
        event["status"] = "DONE"
        self.assert_invalid(event, "invalid_status")

    def test_unauthorized_source(self) -> None:
        event = valid_event()
        event["source"]["repository"] = "maynowak/unknown-repo"
        self.assert_invalid(event, "unauthorized_repository")

    def test_spoofed_source_with_expected_source(self) -> None:
        event = valid_event()
        self.assert_invalid(
            event, "spoofed_source", expected_source="maynowak/mays-jobsearch"
        )

    def test_wrong_target_with_expected_target(self) -> None:
        event = valid_event()
        self.assert_invalid(
            event,
            "wrong_target",
            expected_target="maynowak/Mays-Recruiting-Intelligence-System",
        )

    def test_same_source_and_destination(self) -> None:
        event = valid_event()
        event["destination"]["repository"] = SOURCE_REPO
        self.assert_invalid(event, "wrong_target")

    def test_invalid_commit(self) -> None:
        event = valid_event()
        event["source"]["commit"] = "abc"
        self.assert_invalid(event, "schema")

    def test_invalid_event_id(self) -> None:
        event = valid_event()
        event["eventId"] = "not-a-uuid"
        self.assert_invalid(event, "schema")

    def test_evidence_absent_for_implementation_ready(self) -> None:
        event = valid_event()
        event["evidence"] = []
        self.assert_invalid(event, "evidence_required")

    def test_evidence_absent_for_requested_is_valid(self) -> None:
        event = valid_event()
        event["status"] = "REQUESTED"
        event["evidence"] = []
        validate_event(event)

    def test_spoofed_evidence_repository(self) -> None:
        event = valid_event()
        event["evidence"][0]["url"] = (
            f"https://github.com/{TARGET_REPO}/commit/{SOURCE_COMMIT}"
        )
        self.assert_invalid(event, "spoofed_source")

    def test_commit_evidence_sha_mismatch(self) -> None:
        event = valid_event()
        event["evidence"][0]["url"] = (
            f"https://github.com/{SOURCE_REPO}/commit/"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        self.assert_invalid(event, "invalid_evidence")

    def test_http_evidence_rejected(self) -> None:
        event = valid_event()
        event["evidence"][0]["url"] = (
            f"http://github.com/{SOURCE_REPO}/commit/{SOURCE_COMMIT}"
        )
        self.assert_invalid(event, "invalid_evidence")

    def test_unsupported_evidence_path(self) -> None:
        event = valid_event()
        event["evidence"][0]["kind"] = "test"
        event["evidence"][0]["url"] = f"https://github.com/{SOURCE_REPO}/issues/42"
        self.assert_invalid(event, "invalid_evidence")

    def test_implementation_ready_requires_commit_evidence(self) -> None:
        event = valid_event()
        event["evidence"] = [
            {
                "kind": "test",
                "url": f"https://github.com/{SOURCE_REPO}/actions/runs/12345",
            }
        ]
        self.assert_invalid(event, "evidence_required")

    def test_issue_evidence_requires_numeric_issue(self) -> None:
        event = valid_event()
        event["status"] = "REWORK_REQUIRED"
        event["evidence"] = [
            {
                "kind": "issue",
                "url": f"https://github.com/{SOURCE_REPO}/issues/not-a-number",
            }
        ]
        self.assert_invalid(event, "invalid_evidence")

    def test_actions_run_evidence_requires_numeric_run(self) -> None:
        event = valid_event()
        event["evidence"] = [
            {
                "kind": "test",
                "url": f"https://github.com/{SOURCE_REPO}/actions/runs/not-a-run",
            }
        ]
        self.assert_invalid(event, "invalid_evidence")

    def test_unsafe_summary_marker(self) -> None:
        event = valid_event()
        event["summary"] = "ok <!-- mays-xrepo:state -->"
        self.assert_invalid(event, "unsafe_summary")

    def test_sequence_must_be_positive_integer(self) -> None:
        event = valid_event()
        event["sequence"] = True
        self.assert_invalid(event, "schema")

    def test_issue_must_be_positive_integer(self) -> None:
        event = valid_event()
        event["source"]["issue"] = True
        self.assert_invalid(event, "schema")

    def test_too_many_evidence_items(self) -> None:
        event = valid_event()
        event["evidence"] = [event["evidence"][0]] * (MAX_EVIDENCE_ITEMS + 1)
        self.assert_invalid(event, "schema")

    def test_payload_too_large(self) -> None:
        event = valid_event()
        event["summary"] = "x" * (MAX_PAYLOAD_BYTES + 1)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(event, handle)
            path = handle.name
        try:
            with self.assertRaises(ValidationError) as caught:
                load_event(path)
            self.assertEqual(caught.exception.code, "payload_too_large")
        finally:
            Path(path).unlink()

    def test_duplicate_json_key_rejected(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write('{"protocol":"MAYS-XREPO-V1","protocol":"MAYS-XREPO-V1"}')
            path = handle.name
        try:
            with self.assertRaises(ValidationError) as caught:
                load_event(path)
            self.assertEqual(caught.exception.code, "invalid_json")
        finally:
            Path(path).unlink()

    def test_fixtures(self) -> None:
        valid = [
            "valid-requested.json",
            "valid-implementation-ready.json",
        ]
        for name in valid:
            with self.subTest(name=name):
                validate_event(load_event(str(FIXTURES / name)))

        expected = {
            "invalid-spoofed-source.json": "spoofed_source",
            "invalid-evidence-absent.json": "evidence_required",
        }
        for name, code in expected.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError) as caught:
                    validate_event(load_event(str(FIXTURES / name)))
                self.assertEqual(caught.exception.code, code)

    def test_schema_matches_validator(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["protocol"]["const"], PROTOCOL)
        self.assertEqual(set(schema["required"]), EXPECTED_KEYS)
        self.assertEqual(
            set(schema["properties"]["status"]["enum"]), set(ALLOWED_STATUSES)
        )
        self.assertEqual(
            set(schema["$defs"]["repository"]["enum"]), set(ALLOWED_REPOSITORIES)
        )
        self.assertEqual(
            set(schema["$defs"]["evidence"]["properties"]["kind"]["enum"]),
            set(EVIDENCE_KINDS),
        )
        self.assertEqual(
            schema["properties"]["evidence"]["maxItems"], MAX_EVIDENCE_ITEMS
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["eventId"]["pattern"], EVENT_ID_RE.pattern
        )

    def test_cli_valid(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "validate_event.py"),
                str(FIXTURES / "valid-requested.json"),
                "--expected-source",
                "maynowak/mays-jobsearch",
                "--expected-target",
                SOURCE_REPO,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VALID taskId=MAYS-XR-001", result.stdout)

    def test_cli_invalid(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "validate_event.py"),
                str(FIXTURES / "invalid-evidence-absent.json"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("INVALID evidence_required", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
