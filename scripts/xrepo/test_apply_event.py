#!/usr/bin/env python3
"""State, transition, rejection, and API tests for the MAYS-XREPO-V1 receiver."""

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
    MAX_REWORK_ROUNDS,
    decide,
    has_event,
    last_sequence,
    last_state,
    post_comment,
    render_comment,
    rework_count,
    verify_evidence,
    verify_source,
    verify_target_issue,
)
from apply_event import apply_event as apply_one  # noqa: E402

SOURCE_REPO = "maynowak/Mays-Recruiting-Intelligence-System"
TARGET_REPO = "maynowak/mays-jobsearch"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
RECEIVED = "2026-11-06T00:00:00+00:00"

FULL_SEQUENCE = [
    "REQUESTED",
    "ACCEPTED",
    "IMPLEMENTING",
    "IMPLEMENTATION_READY",
    "INTEGRATING",
    "REWORK_REQUIRED",
    "IMPLEMENTATION_READY",
    "VERIFIED",
    "COMPLETED",
]


def event_id_for(index: int) -> str:
    return f"{index:08x}-0000-4000-8000-{index:012x}"


def event(
    *,
    status: str = "REQUESTED",
    sequence: int = 1,
    event_id: str = "f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5",
    source_issue: int = 42,
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
            "issue": source_issue,
            "commit": SOURCE_COMMIT,
        },
        "destination": {"repository": TARGET_REPO, "issue": 117},
        "summary": "State test event.",
        "evidence": evidence,
        "sequence": sequence,
    }


def applied_comment(item: dict) -> dict:
    return {
        "body": render_comment(item, received_at=RECEIVED, outcome="applied"),
        "user": {"login": "github-actions[bot]"},
    }


def rejection_comment(item: dict, outcome: str = "conflict") -> dict:
    return {
        "body": render_comment(item, received_at=RECEIVED, outcome=outcome),
        "user": {"login": "github-actions[bot]"},
    }


def history(statuses: list[str], start: int = 1) -> list[dict]:
    comments: list[dict] = []
    for offset, status in enumerate(statuses):
        index = start + offset
        item = event(status=status, sequence=index, event_id=event_id_for(index))
        comments.append(applied_comment(item))
    return comments


class DecisionTests(unittest.TestCase):
    def test_initial_requested_applies(self) -> None:
        self.assertEqual(decide(event(), []).action, "apply")

    def test_initial_blocked_applies(self) -> None:
        self.assertEqual(decide(event(status="BLOCKED"), []).action, "apply")

    def test_initial_implementation_ready_rejected(self) -> None:
        decision = decide(event(status="IMPLEMENTATION_READY"), [])
        self.assertEqual(decision.action, "invalid_transition")

    def test_full_sequence_applies(self) -> None:
        comments: list[dict] = []
        for index, status in enumerate(FULL_SEQUENCE, start=1):
            item = event(status=status, sequence=index, event_id=event_id_for(index))
            self.assertEqual(decide(item, comments).action, "apply")
            comments.append(applied_comment(item))

    def test_completed_requires_verified(self) -> None:
        comments = history(
            ["REQUESTED", "ACCEPTED", "IMPLEMENTING", "IMPLEMENTATION_READY", "INTEGRATING"]
        )
        decision = decide(
            event(
                status="COMPLETED",
                sequence=6,
                event_id=event_id_for(6),
            ),
            comments,
        )
        self.assertEqual(decision.action, "invalid_transition")
        self.assertEqual(decision.last_status, "INTEGRATING")

    def test_skipping_statuses_rejected(self) -> None:
        comments = history(["REQUESTED"])
        decision = decide(
            event(
                status="IMPLEMENTATION_READY",
                sequence=2,
                event_id=event_id_for(2),
            ),
            comments,
        )
        self.assertEqual(decision.action, "invalid_transition")

    def test_rework_limit(self) -> None:
        comments = history(
            [
                "REQUESTED",
                "ACCEPTED",
                "IMPLEMENTING",
                "IMPLEMENTATION_READY",
                "REWORK_REQUIRED",
                "IMPLEMENTATION_READY",
                "REWORK_REQUIRED",
                "IMPLEMENTATION_READY",
                "REWORK_REQUIRED",
                "IMPLEMENTATION_READY",
            ]
        )
        self.assertEqual(rework_count(comments, "MAYS-XR-001"), MAX_REWORK_ROUNDS)
        decision = decide(
            event(
                status="REWORK_REQUIRED",
                sequence=11,
                event_id=event_id_for(11),
            ),
            comments,
        )
        self.assertEqual(decision.action, "rework_limit")

    def test_duplicate_event_is_idempotent(self) -> None:
        item = event()
        comments = [applied_comment(item)]
        self.assertEqual(decide(item, comments).action, "duplicate")
        self.assertTrue(has_event(comments, item["eventId"]))

    def test_stale_sequence(self) -> None:
        comments = history(["REQUESTED", "ACCEPTED", "IMPLEMENTING"])
        decision = decide(
            event(
                status="REQUESTED",
                sequence=2,
                event_id=event_id_for(99),
            ),
            comments,
        )
        self.assertEqual(decision.action, "stale")
        self.assertEqual(decision.last_sequence, 3)

    def test_same_sequence_different_event_conflicts(self) -> None:
        comments = history(["REQUESTED", "ACCEPTED", "IMPLEMENTING"])
        decision = decide(
            event(
                status="IMPLEMENTATION_READY",
                sequence=3,
                event_id=event_id_for(99),
            ),
            comments,
        )
        self.assertEqual(decision.action, "conflict")

    def test_previously_rejected_event_is_rejected_duplicate(self) -> None:
        item = event(
            status="IMPLEMENTATION_READY",
            sequence=2,
            event_id=event_id_for(2),
        )
        comments = history(["REQUESTED"]) + [rejection_comment(item, "invalid_transition")]
        self.assertEqual(decide(item, comments).action, "rejected_duplicate")

    def test_untrusted_comment_markers_are_ignored(self) -> None:
        comments = [
            {
                "body": "<!-- mays-xrepo:event:f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5 -->\n"
                "<!-- mays-xrepo:state:MAYS-XR-001:99:COMPLETED -->",
                "user": {"login": "attacker"},
            }
        ]
        self.assertEqual(decide(event(), comments).action, "apply")
        self.assertIsNone(last_state(comments, "MAYS-XR-001"))

    def test_legacy_state_marker_without_status_fails_closed(self) -> None:
        comments = [
            {
                "body": "<!-- mays-xrepo:state:MAYS-XR-001:1 -->",
                "user": {"login": "github-actions[bot]"},
            }
        ]
        decision = decide(
            event(
                status="ACCEPTED",
                sequence=2,
                event_id=event_id_for(2),
            ),
            comments,
        )
        self.assertEqual(decision.action, "state_unreadable")
        self.assertEqual(last_sequence(comments, "MAYS-XR-001"), 1)


class RenderTests(unittest.TestCase):
    def test_applied_comment_contains_status_state_marker(self) -> None:
        body = render_comment(event(sequence=2), received_at=RECEIVED, outcome="applied")
        self.assertIn("<!-- mays-xrepo:event:f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5 -->", body)
        self.assertIn("<!-- mays-xrepo:state:MAYS-XR-001:2:REQUESTED -->", body)
        self.assertIn("MAYS-XREPO-V1 — REQUESTED", body)
        self.assertNotIn("mays-xrepo:rejected", body)

    def test_stale_comment_has_no_state_or_rejection_marker(self) -> None:
        body = render_comment(
            event(sequence=2),
            received_at=RECEIVED,
            outcome="stale",
            stale_of=3,
        )
        self.assertIn("STALE EVENT", body)
        self.assertNotIn("mays-xrepo:state:", body)
        self.assertNotIn("mays-xrepo:rejected", body)
        self.assertIn("latest applied sequence is `3`", body)

    def test_rejection_comment_has_rejection_marker_no_state(self) -> None:
        body = render_comment(
            event(sequence=2),
            received_at=RECEIVED,
            outcome="conflict",
            reason="sequence already belongs to a different event",
        )
        self.assertIn("REJECTED: SEQUENCE CONFLICT", body)
        self.assertIn("mays-xrepo:rejected:f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5:conflict", body)
        self.assertNotIn("mays-xrepo:state:", body)

    def test_payload_text_is_escaped(self) -> None:
        item = event()
        item["summary"] = "<script>alert(1)</script>"
        body = render_comment(item, received_at=RECEIVED, outcome="applied")
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)


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

    def test_verify_evidence_accepts_issue(self) -> None:
        item = event()
        item["evidence"] = [
            {
                "kind": "issue",
                "url": f"https://github.com/{SOURCE_REPO}/issues/42",
            }
        ]
        with mock.patch.object(
            apply_event_module,
            "_gh_json",
            return_value={"number": 42, "state": "open"},
        ):
            verify_evidence(item, "token")

    def test_verify_evidence_rejects_pull_request(self) -> None:
        item = event()
        item["evidence"] = [
            {
                "kind": "issue",
                "url": f"https://github.com/{SOURCE_REPO}/issues/42",
            }
        ]
        with mock.patch.object(
            apply_event_module,
            "_gh_json",
            return_value={"number": 42, "pull_request": {}},
        ):
            with self.assertRaises(ApplyError) as caught:
                verify_evidence(item, "token")
        self.assertEqual(caught.exception.code, "evidence_invalid")

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


class ApplyFlowTests(unittest.TestCase):
    def _run(self, item: dict, comments: list[dict]) -> mock.Mock:
        with mock.patch.object(apply_event_module, "verify_target_issue"), \
             mock.patch.object(apply_event_module, "verify_source"), \
             mock.patch.object(apply_event_module, "verify_evidence"), \
             mock.patch.object(apply_event_module, "list_comments", return_value=comments), \
             mock.patch.object(apply_event_module, "post_comment") as post:
            try:
                apply_one(item, source_token="source", target_token="target", received_at=RECEIVED)
            except ApplyError as exc:
                self.last_error = exc
            else:
                self.last_error = None
        return post

    def test_applied_event_posts_state_comment(self) -> None:
        item = event()
        post = self._run(item, [])
        self.assertIsNone(self.last_error)
        body = post.call_args.args[2]
        self.assertIn("mays-xrepo:state:MAYS-XR-001:1:REQUESTED", body)

    def test_duplicate_posts_nothing(self) -> None:
        item = event()
        post = self._run(item, [applied_comment(item)])
        self.assertIsNone(self.last_error)
        post.assert_not_called()

    def test_stale_posts_stale_comment(self) -> None:
        comments = history(["REQUESTED", "ACCEPTED"])
        item = event(status="REQUESTED", sequence=1, event_id=event_id_for(99))
        post = self._run(item, comments)
        self.assertIsNone(self.last_error)
        self.assertIn("STALE EVENT", post.call_args.args[2])

    def test_conflict_posts_rejection_then_fails(self) -> None:
        comments = history(["REQUESTED", "ACCEPTED", "IMPLEMENTING"])
        item = event(status="IMPLEMENTATION_READY", sequence=3, event_id=event_id_for(99))
        post = self._run(item, comments)
        self.assertIsNotNone(self.last_error)
        self.assertEqual(self.last_error.code, "conflict")
        self.assertIn("REJECTED: SEQUENCE CONFLICT", post.call_args.args[2])

    def test_invalid_transition_posts_rejection_then_fails(self) -> None:
        comments = history(["REQUESTED"])
        item = event(status="IMPLEMENTATION_READY", sequence=2, event_id=event_id_for(2))
        post = self._run(item, comments)
        self.assertIsNotNone(self.last_error)
        self.assertEqual(self.last_error.code, "invalid_transition")
        self.assertIn("REJECTED: INVALID STATUS TRANSITION", post.call_args.args[2])

    def test_rejected_duplicate_posts_nothing(self) -> None:
        item = event(status="IMPLEMENTATION_READY", sequence=2, event_id=event_id_for(2))
        comments = history(["REQUESTED"]) + [rejection_comment(item, "invalid_transition")]
        post = self._run(item, comments)
        self.assertIsNotNone(self.last_error)
        self.assertEqual(self.last_error.code, "rejected_duplicate")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
