"""Regression tests for version validation and process-isolated test profiles."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "unified_tests", ROOT / "scripts" / "unified_tests.py"
)
unified = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = unified
SPEC.loader.exec_module(unified)


class ProfileIsolationTests(unittest.TestCase):
    def test_ris_privacy_has_native_jobs_and_explicit_provider_blocks(self):
        jobs = unified.profile_jobs("RIS_PRIVACY", unified.DEFAULT_MAYS)
        by_key = {job.key: job for job in jobs}
        self.assertIn("privacy_capability_and_addition", by_key)
        self.assertIn("orders_jwt_identity_synthetic", by_key)
        self.assertEqual("blocked", by_key["orders_provider_original"].kind)
        self.assertEqual("blocked", by_key["orders_provider_jwt_verifier"].kind)
        self.assertFalse(by_key["privacy_capability_and_addition"].mays_source)
        for required_group in (
                "runtime_result_fence_races", "reference_dummy_originals",
                "ats_originals_and_result_link", "cv_job_parser_originals",
                "analysis_originals", "privacy_policy_approval_gates"):
            self.assertIn(required_group, by_key)
        self.assertEqual("blocked", by_key["privacy_policy_approval_gates"].kind)

    def test_full_has_no_live_jobs_and_only_supported_profiles(self):
        jobs = unified.profile_jobs("FULL", unified.DEFAULT_MAYS)
        self.assertTrue(jobs)
        self.assertNotIn("live", " ".join(job.key.lower() for job in jobs))
        self.assertEqual([], unified.profile_jobs("LIVE", unified.DEFAULT_MAYS))

    def test_mays_and_ris_jobs_have_separate_python_paths(self):
        jobs = unified.profile_jobs("FULL", unified.DEFAULT_MAYS)
        lambda_job = next(job for job in jobs if job.key == "mays_lambda")
        xrepo_job = next(job for job in jobs if job.key == "xrepo_contract")
        native_job = next(job for job in jobs if job.key == "ris_native")
        self.assertIn("lambda", lambda_job.python_path.lower())
        self.assertIn("src", lambda_job.python_path.lower())
        self.assertTrue(xrepo_job.mays_source)
        self.assertFalse(native_job.mays_source)
        self.assertEqual("", native_job.python_path)

    def test_child_environment_removes_ambient_creds_and_paths(self):
        job = unified.profile_jobs("RIS_NATIVE", unified.DEFAULT_MAYS)[0]
        base = {
            "PATH": "safe", "PYTHONPATH": "foreign",
            "MO_ORDERS_SRC": "foreign", "AWS_PROFILE": "mayaws",
            "AWS_ACCESS_KEY_ID": "should-not-inherit", "MODE": "true",
        }
        with tempfile.TemporaryDirectory() as sandbox:
            env = unified.child_environment(
                base, job, mays_source=unified.DEFAULT_MAYS,
                module_dir=None, module_sha="", source_commit="",
                sandbox_dir=Path(sandbox),
            )
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("MO_ORDERS_SRC", env)
        self.assertNotIn("AWS_PROFILE", env)
        self.assertNotIn("AWS_ACCESS_KEY_ID", env)
        self.assertTrue(env["AWS_CONFIG_FILE"].endswith("empty-aws-config"))
        self.assertTrue(env["AWS_SHARED_CREDENTIALS_FILE"].endswith("empty-aws-credentials"))
        self.assertEqual("true", env["MODE"])

    def test_provenance_mismatch_blocks_stale_local_checkout(self):
        _, errors = unified.verify_provenance(
            unified.DEFAULT_MAYS, "upgrade_candidate", unified.load_versions()
        )
        self.assertTrue(any("!= required" in error or "checkout not found" in error
                            for error in errors))

    def test_result_parser_keeps_failed_skipped_and_subtests_separate(self):
        job = unified.Job("example", "RIS", str(ROOT), "pytest", [])
        completed = subprocess.CompletedProcess(
            [], 1, "3 passed, 2 failed, 4 skipped, 5 subtests passed in 1.25s", ""
        )
        row = unified.parse_result(job, completed, 1.3)
        self.assertEqual("FAIL", row["status"])
        self.assertEqual((3, 2, 4, 5), (
            row["passed"], row["failed"], row["skipped"], row["subtests_passed"]
        ))

    def test_result_parser_handles_unittest_error_summary(self):
        job = unified.Job("installer", "MAYS_ORDERS", str(ROOT), "unittest", [])
        completed = subprocess.CompletedProcess(
            [], 1, "", "Ran 81 tests in 1.25s\n\nFAILED (errors=11, skipped=1)\n"
        )
        row = unified.parse_result(job, completed, 1.3)
        self.assertEqual("FAIL", row["status"])
        self.assertEqual((69, 11, 1), (row["passed"], row["failed"], row["skipped"]))

    def test_live_cli_never_runs_a_command_and_marks_blocked(self):
        with patch.object(unified, "DEFAULT_REPORT", ROOT / "target" / "live-test-result.json"), \
             patch.object(unified.subprocess, "run") as run:
            code = unified.main(["LIVE", "--json-report", str(ROOT / "target" / "live-test-result.json")])
        self.assertEqual(1, code)
        run.assert_not_called()
        result_path = ROOT / "target" / "live-test-result.json"
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual("BLOCKED", data["profile_status"])
            self.assertEqual("LOCKED_NOT_EXECUTED", data["live_profile"])
        finally:
            result_path.unlink(missing_ok=True)
            result_path.parent.rmdir()


if __name__ == "__main__":
    unittest.main()
