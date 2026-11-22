"""Saved-plan apply mode: exact hash, identity, state, shape and bundle gates.

No AWS and no Terraform binary. The runner is a fake; the plan file is a local
temporary file. The central invariant: this path must never call `plan`.
"""

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from installer import ris  # noqa: E402
from installer.terraform_runner import TerraformResult  # noqa: E402

LINEAGE = "a0bd361d-5cd1-a207-a8c0-e6888f0be082"


def completed(args, rc=0, stdout="", stderr=""):
    return TerraformResult(command=list(args), returncode=rc,
                           stdout=stdout, stderr=stderr)


def plan_json(adds=4, changes=3, destroys=0, replacements=0, extra=None):
    items = []
    for index in range(adds):
        items.append({"address": f"aws_x.add{index}", "type": "aws_x",
                      "change": {"actions": ["create"], "after": {}}})
    for index in range(changes):
        items.append({"address": f"aws_x.change{index}", "type": "aws_x",
                      "change": {"actions": ["update"], "after": {}}})
    for index in range(destroys):
        items.append({"address": f"aws_x.delete{index}", "type": "aws_x",
                      "change": {"actions": ["delete"], "after": {}}})
    for index in range(replacements):
        items.append({"address": f"aws_x.replace{index}", "type": "aws_x",
                      "change": {"actions": ["delete", "create"], "after": {}}})
    items.append({"address": "aws_x.noop", "type": "aws_x",
                  "change": {"actions": ["no-op"], "after": {}}})
    if extra:
        items.extend(extra)
    return {"resource_changes": items}


class FakeRunner:
    def __init__(self, state=None):
        self.calls = []
        self.plan_calls = 0
        self.state = state or {"serial": 67, "lineage": LINEAGE}

    def init(self, **kwargs):
        self.calls.append(("init", kwargs))
        return completed(["terraform", "init"])

    def plan(self, **kwargs):
        self.plan_calls += 1
        raise AssertionError("saved-plan apply must never call terraform plan")

    def state_pull(self, ensure_workspace=True):
        self.calls.append(("state_pull", ensure_workspace))
        return completed(["terraform", "state", "pull"],
                         stdout=json.dumps(self.state))

    def run_and_get_result(self, args, ensure_workspace=True):
        self.calls.append(("run", list(args), ensure_workspace))
        return completed(["terraform"] + list(args))


class FakeCtx:
    dry_run = False
    project_name = "ris-dev2"
    workspace = "ris-dev2"
    environment = "dev"
    aws_profile = None
    aws_region = "eu-central-1"
    aws_context = SimpleNamespace(account_id="262370457690",
                                  region="eu-central-1")

    def __init__(self, runner):
        self.runner = runner

    def backend_config(self):
        return object()

    def make_runner(self):
        return self.runner


class SavedPlanHashTest(unittest.TestCase):
    def test_missing_file_and_approval_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.out"
            with self.assertRaisesRegex(RuntimeError, "not found"):
                ris._verify_saved_plan(str(path), "a" * 64, "APP-1")
            path.write_bytes(b"plan")
            with self.assertRaisesRegex(RuntimeError, "approval-ref"):
                ris._verify_saved_plan(str(path), "a" * 64, "")

    def test_wrong_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.out"
            path.write_bytes(b"plan")
            with self.assertRaisesRegex(RuntimeError, "SHA mismatch"):
                ris._verify_saved_plan(str(path), "a" * 64, "APP-1")

    def test_valid_plan_hash_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.out"
            path.write_bytes(b"plan")
            digest = hashlib.sha256(b"plan").hexdigest()
            resolved, actual = ris._verify_saved_plan(
                str(path), digest, "APP-1")
            self.assertEqual(path.resolve(), resolved)
            self.assertEqual(digest, actual)


class SavedPlanShapeTest(unittest.TestCase):
    def test_exact_shape_passes_and_wrong_shape_is_refused(self):
        data = plan_json()
        self.assertEqual(
            {"adds": 4, "changes": 3, "destroys": 0, "replacements": 0},
            ris._verify_plan_shape(data, "4/3/0/0"))
        with self.assertRaisesRegex(RuntimeError, "shape mismatch"):
            ris._verify_plan_shape(data, "4/4/0/0")
        with self.assertRaisesRegex(RuntimeError, "must look like"):
            ris._verify_plan_shape(data, "4/3/0")

    def test_malformed_actions_are_refused(self):
        with self.assertRaisesRegex(RuntimeError, "action shape"):
            ris._plan_shape_counts({"resource_changes": [
                {"address": "x", "change": {"actions": "delete"}}]})


class SavedPlanBundleTest(unittest.TestCase):
    def test_bundle_hash_must_match_the_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "terraform" / "lambda.zip"
            bundle.parent.mkdir(parents=True)
            bundle.write_bytes(b"worker-bundle")
            digest = base64.b64encode(
                hashlib.sha256(b"worker-bundle").digest()).decode()
            data = {"resource_changes": [{
                "address": "module.lambda.aws_lambda_function.agent",
                "type": "aws_lambda_function",
                "change": {"actions": ["update"],
                           "after": {"source_code_hash": digest}},
            }]}
            ris._verify_plan_bundles(data, root)
            bundle.write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "bundle changed"):
                ris._verify_plan_bundles(data, root)

    def test_missing_bundle_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = {"resource_changes": [{
                "address": "module.lambda.aws_lambda_function.agent",
                "type": "aws_lambda_function",
                "change": {"actions": ["update"],
                           "after": {"source_code_hash": "abc"}},
            }]}
            with self.assertRaisesRegex(RuntimeError, "bundle is missing"):
                ris._verify_plan_bundles(data, root)


class SavedPlanIdentityTest(unittest.TestCase):
    def test_state_serial_and_lineage_are_enforced(self):
        runner = FakeRunner()
        state = ris._verify_state_identity(runner, 67, LINEAGE)
        self.assertEqual(67, state["serial"])
        with self.assertRaisesRegex(RuntimeError, "serial mismatch"):
            ris._verify_state_identity(runner, 68, LINEAGE)
        with self.assertRaisesRegex(RuntimeError, "lineage mismatch"):
            ris._verify_state_identity(runner, 67, "other")

    def test_account_region_workspace_are_enforced(self):
        ctx = FakeCtx(FakeRunner())
        ris._verify_aws_identity(ctx, "262370457690", "eu-central-1", "ris-dev2")
        with self.assertRaisesRegex(RuntimeError, "account mismatch"):
            ris._verify_aws_identity(ctx, "000000000000", "eu-central-1",
                                     "ris-dev2")
        with self.assertRaisesRegex(RuntimeError, "region mismatch"):
            ris._verify_aws_identity(ctx, "262370457690", "us-east-1",
                                     "ris-dev2")
        with self.assertRaisesRegex(RuntimeError, "workspace mismatch"):
            ris._verify_aws_identity(ctx, "262370457690", "eu-central-1",
                                     "other")


class SavedPlanCommandTest(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunner()
        self.ctx = FakeCtx(self.runner)
        self.tmp = tempfile.TemporaryDirectory()
        self.plan_path = Path(self.tmp.name) / "plan.out"
        self.plan_path.write_bytes(b"approved plan")
        self.plan_sha = hashlib.sha256(b"approved plan").hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def _call(self, **overrides):
        values = dict(
            out_file=str(self.plan_path),
            approval_ref="APP-16C2",
            approved_plan_sha256=self.plan_sha,
            expected_account="262370457690",
            expected_region="eu-central-1",
            expected_workspace="ris-dev2",
            expected_state_serial=67,
            expected_state_lineage=LINEAGE,
            expected_plan_shape="4/3/0/0",
        )
        values.update(overrides)
        return ris._cmd_apply_saved_plan(self.ctx, **values)

    def _run_safe(self, **overrides):
        with patch.object(ris, "_load_plan_for_guard",
                          return_value=plan_json()), \
             patch.object(ris, "_verify_plan_bundles", return_value=None), \
             patch.object(ris, "is_plan_safe",
                          return_value=(True, "Plan is safe")), \
             patch.object(ris, "_guard_shared_infra",
                          return_value=SimpleNamespace(
                              safe=True, message="NO_SHARED_DESTROY",
                              plan_sha256=self.plan_sha)), \
             patch.object(ris, "_plan_unchanged", return_value=None), \
             patch.object(ris, "mirror_project_state", return_value=None):
            return self._call(**overrides)

    def test_success_never_calls_plan_and_applies_exact_file(self):
        results = self._run_safe()
        self.assertEqual(0, self.runner.plan_calls)
        self.assertEqual(2, len(results))
        apply_calls = [call for call in self.runner.calls
                       if call[0] == "run" and "apply" in call[1]]
        self.assertEqual(1, len(apply_calls))
        self.assertEqual(["apply", str(self.plan_path.resolve())],
                         apply_calls[0][1])

    def test_wrong_hash_or_missing_approval_never_initialises(self):
        with self.assertRaisesRegex(RuntimeError, "SHA mismatch"):
            self._call(approved_plan_sha256="b" * 64)
        with self.assertRaisesRegex(RuntimeError, "approval-ref"):
            self._call(approval_ref="")
        self.assertEqual([], self.runner.calls)

    def test_state_drift_blocks_before_apply(self):
        self.runner.state = {"serial": 68, "lineage": LINEAGE}
        with self.assertRaisesRegex(RuntimeError, "serial mismatch"):
            self._run_safe()
        self.assertFalse([call for call in self.runner.calls
                          if call[0] == "run" and "apply" in call[1]])

    def test_wrong_account_blocks_before_init(self):
        with self.assertRaisesRegex(RuntimeError, "account mismatch"):
            self._run_safe(expected_account="000000000000")
        self.assertEqual([], self.runner.calls)

    def test_wrong_shape_blocks_before_apply(self):
        with self.assertRaisesRegex(RuntimeError, "shape mismatch"):
            self._run_safe(expected_plan_shape="4/4/0/0")
        self.assertFalse([call for call in self.runner.calls
                          if call[0] == "run" and "apply" in call[1]])

    def test_shared_destroy_blocks_before_apply(self):
        with patch.object(ris, "_load_plan_for_guard",
                          return_value=plan_json()), \
             patch.object(ris, "_verify_plan_bundles", return_value=None), \
             patch.object(ris, "is_plan_safe",
                          return_value=(True, "Plan is safe")), \
             patch.object(ris, "_guard_shared_infra",
                          return_value=SimpleNamespace(
                              safe=False,
                              message="SHARED_DESTROY_WITHOUT_INTENT",
                              plan_sha256=self.plan_sha)), \
             patch.object(ris, "mirror_project_state", return_value=None):
            results = self._call()
        self.assertEqual(1, results[-1].returncode)
        self.assertFalse([call for call in self.runner.calls
                          if call[0] == "run" and "apply" in call[1]])

    def test_unexpected_protected_resource_blocks_before_apply(self):
        protected = plan_json(adds=0, changes=0, extra=[{
            "address": "module.x.aws_cognito_user_pool.pool",
            "type": "aws_cognito_user_pool",
            "change": {"actions": ["create"], "after": {}},
        }])
        with patch.object(ris, "_load_plan_for_guard", return_value=protected), \
             patch.object(ris, "_verify_plan_bundles", return_value=None), \
             patch.object(ris, "_guard_shared_infra",
                          return_value=SimpleNamespace(
                              safe=True, message="NO_SHARED_DESTROY",
                              plan_sha256=self.plan_sha)), \
             patch.object(ris, "mirror_project_state", return_value=None):
            results = self._call(expected_plan_shape="1/0/0/0")
        self.assertEqual(1, results[-1].returncode)
        self.assertFalse([call for call in self.runner.calls
                          if call[0] == "run" and "apply" in call[1]])

    def test_plan_toctou_blocks_before_apply(self):
        with patch.object(ris, "_load_plan_for_guard",
                          return_value=plan_json()), \
             patch.object(ris, "_verify_plan_bundles", return_value=None), \
             patch.object(ris, "is_plan_safe",
                          return_value=(True, "Plan is safe")), \
             patch.object(ris, "_guard_shared_infra",
                          return_value=SimpleNamespace(
                              safe=True, message="NO_SHARED_DESTROY",
                              plan_sha256=self.plan_sha)), \
             patch.object(ris, "_plan_unchanged",
                          return_value="plan file changed"), \
             patch.object(ris, "mirror_project_state", return_value=None):
            results = self._call()
        self.assertEqual(1, results[-1].returncode)
        self.assertFalse([call for call in self.runner.calls
                          if call[0] == "run" and "apply" in call[1]])


if __name__ == "__main__":
    unittest.main()
