#!/usr/bin/env python3
"""State/idempotency tests for the MAYS-XREPO-V1 receiver."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import apply_event as apply_event_module  # noqa: E402
from apply_event import (  # noqa: E402
    ApplyError,
    decide,
    last_sequence,
    post_comment,
    render_comment,
    verify_source,
    verify_target_issue,
)

SOURCE_REPO = "maynowak/Mays-Recruiting-Intelligence-System"
TARGET_REPO = "maynowak/mays-jobsearch"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def event(
    *,
    event_id: str = "f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5",
    sequence: int = 1,
    status: str = "REQUESTED",
) -> dict:
    evidence = []
    if status in {"IMPLEMENTATION_READY", "VERIFIED", "COMPLETED", "REWORK_REQUIRED"}:
        evidence = [
            {
                "kind": "commit",
                "url": f"https://github.com/{SOURCE_REPO}/commit/{SOURCE_COMMIT}",
            }
        ]
    return {
        "protocol": "MAYS-XREPO-V1",
        "taskId": "MAYS-XR-001",
        "eventId": event_id,
        "status": status,
        "source": {
            "repository": SOURCE_REPO,
            "issue": 42,
            "commit": SOURCE_COMMIT,
        },
        "destination": {"repository": TARGET_REPO, "issue": 117},
        "summary": "State test event.",
        "evidence": evidence,
        "sequence": sequence,
    }


def applied_comment(item: dict, received_at: str = "2026-11-06T00:00:00+00:00") -> dict:
    return {
        "body": render_comment(item, received_at=received_at, applied=True),
        "user": {"login": "github-actions[bot]"},
    }


class DecisionTests(unittest.TestCase):
    def test_first_event_applies(self) -> None:
        self.assertEqual(decide(event(), []).action, "apply")

    def test_duplicate_event_id_is_ignored(self) -> None:
        item = event()
        comments = [applied_comment(item)]
        self.assertEqual(decide(item, comments).action, "duplicate")

    def test_older_sequence_is_stale(self) -> None:
        comments = [applied_comment(event(sequence=3))]
        decision = decide(
            event(
                event_id="9a7c2d41-6b3e-4f80-9c1d-2e3f4a5b6c7d",
                sequence=2,
            ),
            comments,
        )
        self.assertEqual(decision.action, "stale")
        self.assertEqual(decision.last_sequence, 3)

    def test_same_sequence_with_different_event_conflicts(self) -> None:
        comments = [applied_comment(event(sequence=3))]
        newer = event(
            event_id="9a7c2d41-6b3e-4f80-9c1d-2e3f4a5b6c7d",
            sequence=3,
        )
        self.assertEqual(decide(newer, comments).action, "conflict")

    def test_newer_sequence_applies(self) -> None:
        comments = [applied_comment(event(sequence=3))]
        self.assertEqual(
            decide(
                event(
                    event_id="9a7c2d41-6b3e-4f80-9c1d-2e3f4a5b6c7d",
                    sequence=4,
                ),
                comments,
            ).action,
            "apply",
        )

    def test_last_sequence_is_scoped_to_task(self) -> None:
        comments = [
            {
                "body": "<!-- mays-xrepo:event:11111111-1111-4111-8111-111111111111 -->\n"
                "<!-- mays-xrepo:state:OTHER-TASK:9 -->",
                "user": {"login": "github-actions[bot]"},
            },
            {
                "body": "<!-- mays-xrepo:event:22222222-2222-4222-8222-222222222222 -->\n"
                "<!-- mays-xrepo:state:MAYS-XR-001:2 -->",
                "user": {"login": "github-actions[bot]"},
            },
        ]
        self.assertEqual(last_sequence(comments, "MAYS-XR-001"), 2)
        self.assertIsNone(last_sequence(comments, "MAYS-XR-999"))

    def test_untrusted_comment_markers_are_ignored(self) -> None:
        comments = [
            {
                "body": "<!-- mays-xrepo:event:f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5 -->\n"
                "<!-- mays-xrepo:state:MAYS-XR-001:99 -->",
                "user": {"login": "attacker"},
            }
        ]
        self.assertEqual(decide(event(), comments).action, "apply")
        self.assertIsNone(last_sequence(comments, "MAYS-XR-001"))

    def test_retry_cycle(self) -> None:
        comments: list[dict] = []
        first = event(sequence=1)
        self.assertEqual(decide(first, comments).action, "apply")
        comments.append(applied_comment(first))

        self.assertEqual(decide(first, comments).action, "duplicate")

        second = event(
            event_id="9a7c2d41-6b3e-4f80-9c1d-2e3f4a5b6c7d",
            sequence=2,
            status="IMPLEMENTATION_READY",
        )
        self.assertEqual(decide(second, comments).action, "apply")
        comments.append(applied_comment(second))

        self.assertEqual(decide(first, comments).action, "duplicate")
        self.assertEqual(
            decide(
                event(
                    event_id="33333333-3333-4333-8333-333333333333",
                    sequence=1,
                ),
                comments,
            ).action,
            "stale",
        )
        self.assertEqual(
            decide(
                event(
                    event_id="44444444-4444-4444-8444-444444444444",
                    sequence=2,
                ),
                comments,
            ).action,
            "conflict",
        )


class RenderTests(unittest.TestCase):
    def test_applied_comment_contains_event_and_state_markers(self) -> None:
        body = render_comment(
            event(sequence=2),
            received_at="2026-11-06T00:00:00+00:00",
            applied=True,
        )
        self.assertIn("<!-- mays-xrepo:event:f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5 -->", body)
        self.assertIn("<!-- mays-xrepo:state:MAYS-XR-001:2 -->", body)
        self.assertIn("MAYS-XREPO-V1 — REQUESTED", body)

    def test_stale_comment_has_no_state_marker(self) -> None:
        body = render_comment(
            event(sequence=2),
            received_at="2026-11-06T00:00:00+00:00",
            applied=False,
            stale_of=3,
        )
        self.assertIn("STALE EVENT", body)
        self.assertNotIn("mays-xrepo:state:", body)
        self.assertIn("latest applied sequence is `3`", body)

    def test_payload_text_is_escaped(self) -> None:
        item = event()
        item["summary"] = "<script>alert(1)</script>"
        body = render_comment(
            item,
            received_at="2026-11-06T00:00:00+00:00",
            applied=True,
        )
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_evidence_is_rendered(self) -> None:
        item = event(status="IMPLEMENTATION_READY", sequence=3)
        body = render_comment(
            item,
            received_at="2026-11-06T00:00:00+00:00",
            applied=True,
        )
        self.assertIn("Source commit", body)
        self.assertIn(SOURCE_COMMIT, body)
        self.assertIn(f"https://github.com/{SOURCE_REPO}/commit/{SOURCE_COMMIT}", body)


class ApiTests(unittest.TestCase):
    def test_verify_source_accepts_issue_and_commit(self) -> None:
        with mock.patch.object(
            apply_event_module,
            "_gh_json",
            side_effect=[
                {"number": 42, "state": "open"},
                {"sha": SOURCE_COMMIT},
            ],
        ):
            verify_source(event(), "token")

    def test_verify_source_rejects_pull_request(self) -> None:
        with mock.patch.object(
            apply_event_module,
            "_gh_json",
            return_value={"number": 42, "state": "open", "pull_request": {}},
        ):
            with self.assertRaises(ApplyError) as caught:
                verify_source(event(), "token")
        self.assertEqual(caught.exception.code, "source_not_found")

    def test_verify_source_rejects_missing_commit(self) -> None:
        with mock.patch.object(
            apply_event_module,
            "_gh_json",
            side_effect=[
                {"number": 42, "state": "open"},
                {"sha": "a" * 40},
            ],
        ):
            with self.assertRaises(ApplyError) as caught:
                verify_source(event(), "token")
        self.assertEqual(caught.exception.code, "source_not_found")

    def test_verify_target_issue_rejects_pull_request(self) -> None:
        with mock.patch.object(
            apply_event_module,
            "_gh_json",
            return_value={"number": 117, "pull_request": {}},
        ):
            with self.assertRaises(ApplyError) as caught:
                verify_target_issue(TARGET_REPO, 117, "token")
        self.assertEqual(caught.exception.code, "target_not_found")

    def test_post_comment_uses_json_file_not_shell_arguments(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(
            apply_event_module, "_run_gh", return_value=completed
        ) as run:
            post_comment(TARGET_REPO, 117, "<script>alert(1)</script>", "token")
        args = run.call_args.args[0]
        self.assertIn("--input", args)
        self.assertNotIn("<script>alert(1)</script>", args)

    def test_missing_source_token_is_blocked_for_live(self) -> None:
        fixture = REPO_ROOT / "docs" / "xrepo" / "fixtures" / "valid-requested.json"
        with mock.patch.dict(
            os.environ,
            {"XREPO_SOURCE_TOKEN": "", "GITHUB_TOKEN": "", "GH_TOKEN": ""},
            clear=False,
        ), contextlib.redirect_stderr(io.StringIO()):
            code = apply_event_module.main([str(fixture)])
        self.assertEqual(code, 3)


class EndToEndShapeTests(unittest.TestCase):
    def test_a_to_b_to_a_status_sequence_is_monotonic(self) -> None:
        statuses = [
            ("REQUESTED", "f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5"),
            ("ACCEPTED", "9a7c2d41-6b3e-4f80-9c1d-2e3f4a5b6c7d"),
            ("IMPLEMENTATION_READY", "33333333-3333-4333-8333-333333333333"),
            ("INTEGRATING", "44444444-4444-4444-8444-444444444444"),
            ("REWORK_REQUIRED", "55555555-5555-4555-8555-555555555555"),
            ("IMPLEMENTATION_READY", "66666666-6666-4666-8666-666666666666"),
            ("VERIFIED", "77777777-7777-4777-8777-777777777777"),
            ("COMPLETED", "88888888-8888-4888-8888-888888888888"),
        ]
        comments: list[dict] = []
        for index, (status, event_id) in enumerate(statuses, start=1):
            item = event(event_id=event_id, sequence=index, status=status)
            self.assertEqual(decide(item, comments).action, "apply")
            comments.append(applied_comment(item))
        self.assertEqual(
            decide(
                event(
                    event_id="99999999-9999-4999-8999-999999999999",
                    sequence=1,
                ),
                comments,
            ).action,
            "stale",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
