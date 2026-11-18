"""Shared-infrastructure guard: missing flags must never mean teardown."""

import os
import sys
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from installer.shared_infra_guard import (  # noqa: E402
    evaluate_plan,
)
from installer import ris  # noqa: E402


def plan(*changes, variables=None):
    return {
        "resource_changes": list(changes),
        "variables": variables or {},
    }


def change(address, actions, resource_type=None, before=None):
    return {
        "address": address,
        "type": resource_type or address.rsplit(".", 1)[-1],
        "change": {"actions": list(actions), "before": before,
                   "after": {} if "delete" in actions else {"x": 1}},
    }


TRANSPORT = "module.agent_transport[0].aws_sqs_queue.dispatch"


class TestSharedInfraGuard(unittest.TestCase):
    def test_no_changes_is_safe(self):
        decision = evaluate_plan(plan())
        self.assertTrue(decision.safe)
        self.assertEqual("NO_SHARED_DESTROY", decision.code)

    def test_reader_update_is_safe(self):
        decision = evaluate_plan(plan(
            change("module.orders_reader[0].aws_lambda_function.reader",
                   ["update"], "aws_lambda_function"),
            change("module.orders_reader[0].aws_iam_role_policy.reader",
                   ["update"], "aws_iam_role_policy"),
        ))
        self.assertTrue(decision.safe)

    def test_transport_delete_with_missing_flags_blocks(self):
        decision = evaluate_plan(plan(
            change(TRANSPORT, ["delete"], "aws_sqs_queue"),
            change("module.agent_transport[0].aws_lambda_function.dispatch_ingress",
                   ["delete"], "aws_lambda_function"),
            variables={"orders_agent_result_enabled": {"value": True}},
        ))
        self.assertFalse(decision.safe)
        self.assertEqual("MISSING_OR_FALSE_TRANSPORT_FLAG", decision.code)
        self.assertIn("enable_agent_transport", decision.message)
        self.assertIn(TRANSPORT, decision.message)
        self.assertEqual(2, len(decision.findings))
        self.assertFalse(decision.authorized_teardown)

    def test_transport_delete_with_true_flags_still_needs_intent(self):
        decision = evaluate_plan(plan(
            change(TRANSPORT, ["delete"], "aws_sqs_queue"),
            variables={"enable_agent_transport": {"value": True},
                       "orders_agent_result_enabled": {"value": True},
                       "orders_lifecycle": {"value": "managed"}},
        ))
        self.assertFalse(decision.safe)
        self.assertEqual("SHARED_DESTROY_WITHOUT_INTENT", decision.code)

    def test_explicit_intent_allows_teardown_and_is_recorded(self):
        decision = evaluate_plan(
            plan(change(TRANSPORT, ["delete"], "aws_sqs_queue")),
            "CHG-4711 approved transport teardown",
        )
        self.assertTrue(decision.safe)
        self.assertEqual("SHARED_TEARDOWN_AUTHORIZED", decision.code)
        self.assertTrue(decision.authorized_teardown)
        self.assertEqual("CHG-4711 approved transport teardown",
                         decision.teardown_intent)

    def test_replace_of_shared_queue_blocks(self):
        decision = evaluate_plan(plan(
            change("module.mays_orders[0].module.sqs.aws_sqs_queue.orders",
                   ["delete", "create"], "aws_sqs_queue")))
        self.assertFalse(decision.safe)

    def test_unrelated_delete_is_safe(self):
        decision = evaluate_plan(plan(
            change("aws_s3_object.stale", ["delete"], "aws_s3_object")))
        self.assertTrue(decision.safe)

    def test_shared_table_delete_blocks_even_outside_module(self):
        decision = evaluate_plan(plan(
            change("aws_dynamodb_table.work_items", ["delete"],
                   "aws_dynamodb_table")))
        self.assertFalse(decision.safe)

    def test_protected_names_catch_renamed_resources(self):
        decision = evaluate_plan(
            plan(change("module.custom.aws_sqs_queue.queue", ["delete"],
                        "aws_sqs_queue")))
        # generic type already protected
        self.assertFalse(decision.safe)
        decision = evaluate_plan(
            plan(change("module.custom.aws_s3_object.shared-x",
                        ["delete"], "aws_s3_object")),
            protected_names=["shared-x"])
        self.assertFalse(decision.safe)
        self.assertTrue(any(f.protection == "explicit:protected_name"
                            for f in decision.findings))

    def test_orders_result_flag_false_blocks_result_teardown(self):
        decision = evaluate_plan(plan(
            change("module.mays_orders[0].module.sqs.aws_sqs_queue.results",
                   ["delete"], "aws_sqs_queue"),
            variables={"enable_agent_transport": {"value": True},
                       "orders_agent_result_enabled": {"value": False}},
        ))
        self.assertFalse(decision.safe)
        self.assertIn("orders_agent_result_enabled", decision.message)

    def test_orders_lifecycle_external_blocks_and_names_flag(self):
        decision = evaluate_plan(plan(
            change("module.mays_orders[0].aws_lambda_function.handler",
                   ["delete"], "aws_lambda_function"),
            variables={"enable_agent_transport": {"value": True},
                       "orders_agent_result_enabled": {"value": True},
                       "orders_lifecycle": {"value": "external"}},
        ))
        self.assertFalse(decision.safe)
        self.assertIn("orders_lifecycle", decision.message)

    def test_malformed_actions_shape_is_refused(self):
        decision = evaluate_plan({
            "resource_changes": [{
                "address": TRANSPORT, "type": "aws_sqs_queue",
                "change": {"actions": "delete"}}],
        })
        self.assertFalse(decision.safe)
        self.assertEqual("PLAN_SHAPE_INVALID", decision.code)

    def test_missing_resource_changes_is_refused(self):
        decision = evaluate_plan({"values": {}})
        self.assertFalse(decision.safe)
        self.assertEqual("PLAN_SHAPE_INVALID", decision.code)

    def test_null_change_is_refused(self):
        decision = evaluate_plan({
            "resource_changes": [{"address": TRANSPORT, "change": None}]})
        self.assertFalse(decision.safe)
        self.assertEqual("PLAN_SHAPE_INVALID", decision.code)

    def test_errored_plan_is_refused(self):
        decision = evaluate_plan({"resource_changes": [], "errored": True})
        self.assertFalse(decision.safe)
        self.assertEqual("PLAN_SHAPE_INVALID", decision.code)

    def test_forget_requires_intent(self):
        decision = evaluate_plan(plan(
            change(TRANSPORT, ["forget"], "aws_sqs_queue")))
        self.assertFalse(decision.safe)
        self.assertIn("shared infrastructure", decision.message.lower())

    def test_create_before_destroy_replace_blocks(self):
        decision = evaluate_plan(plan(
            change(TRANSPORT, ["create", "delete"], "aws_sqs_queue")))
        self.assertFalse(decision.safe)

    def test_editing_iam_module_is_protected(self):
        decision = evaluate_plan(plan(
            change("module.iam.aws_iam_role.lambda_role", ["delete"],
                   "aws_iam_role")))
        self.assertFalse(decision.safe)

    def test_lambda_permission_delete_is_protected(self):
        decision = evaluate_plan(plan(
            change("aws_lambda_permission.api_invoke", ["delete"],
                   "aws_lambda_permission")))
        self.assertFalse(decision.safe)

    def test_underscore_marker_matches_terraform_labels(self):
        decision = evaluate_plan(plan(
            change("aws_s3_object.work_items_export", ["delete"],
                   "aws_s3_object")))
        self.assertFalse(decision.safe)

    def test_short_intent_is_rejected(self):
        decision = evaluate_plan(
            plan(change(TRANSPORT, ["delete"], "aws_sqs_queue")), "x")
        self.assertFalse(decision.safe)
        self.assertEqual("TEARDOWN_INTENT_INVALID", decision.code)

    def test_zero_width_intent_is_rejected(self):
        decision = evaluate_plan(
            plan(change(TRANSPORT, ["delete"], "aws_sqs_queue")),
            "CHG-\u200b-001")
        self.assertFalse(decision.safe)
        self.assertEqual("TEARDOWN_INTENT_INVALID", decision.code)

    def test_blank_intent_is_not_authorization(self):
        decision = evaluate_plan(
            plan(change(TRANSPORT, ["delete"], "aws_sqs_queue"),
                 variables={"enable_agent_transport": {"value": True},
                            "orders_agent_result_enabled": {"value": True},
                            "orders_lifecycle": {"value": "managed"}}),
            "   ")
        self.assertFalse(decision.safe)
        self.assertEqual("SHARED_DESTROY_WITHOUT_INTENT", decision.code)

    def test_valid_intent_records_plan_digest(self):
        decision = evaluate_plan(
            plan(change(TRANSPORT, ["delete"], "aws_sqs_queue")),
            "CHG-RIS-001 teardown",
            plan_sha256="a" * 64)
        self.assertTrue(decision.safe)
        self.assertEqual("a" * 64, decision.plan_sha256)
        self.assertIn("a" * 64, decision.message)
        self.assertTrue(decision.authorized_teardown)


class FakeRunner:
    """Minimal runner that writes a real plan file into `working_dir`."""

    def __init__(self, working_dir, plan_json=None):
        self.working_dir = str(working_dir)
        self.plan_json = plan_json or {"resource_changes": []}
        self.applies = 0
        self.last_plan = None

    def _write(self, out_file):
        if not out_file:
            return
        path = Path(out_file)
        if not path.is_absolute():
            path = Path(self.working_dir) / path
        path.write_text("plan-bytes", encoding="utf-8")
        self.last_plan = path

    def init(self, **kwargs):
        return ris.TerraformResult(["init"], 0)

    def plan(self, out_file=None, **kwargs):
        self._write(out_file)
        return ris.TerraformResult(["plan"], 0)

    def show_json(self, path):
        return self.plan_json

    def run_and_get_result(self, args, **kwargs):
        if args and args[0] == "apply":
            self.applies += 1
        return ris.TerraformResult(args, 0)


class TestPlanAndApplyWiring(unittest.TestCase):
    def setUp(self):
        import tempfile
        from installer import ris as ris_module

        self.ris = ris_module
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _ctx(self, dry_run=False):
        ctx = self.ris.RisInstallContext(project_name="ris-dev2",
                                         environment="dev", dry_run=dry_run)
        ctx.aws_context = object()
        return ctx

    def _destructive(self):
        return plan(change(TRANSPORT, ["delete"], "aws_sqs_queue"))

    def test_plan_blocks_destructive_transport_plan(self):
        ctx = self._ctx()
        runner = FakeRunner(self.tmp.name, self._destructive())
        ctx.make_runner = lambda: runner
        results = self.ris._cmd_plan(ctx, out_file="p.tfplan")
        self.assertEqual(3, len(results))
        self.assertEqual(1, results[-1].returncode)
        self.assertIn("shared infrastructure", results[-1].stderr.lower())

    def test_plan_without_out_still_writes_and_guards(self):
        ctx = self._ctx()
        runner = FakeRunner(self.tmp.name, self._destructive())
        ctx.make_runner = lambda: runner
        results = self.ris._cmd_plan(ctx)
        self.assertEqual(3, len(results))
        self.assertEqual(1, results[-1].returncode)
        self.assertIsNotNone(runner.last_plan)
        self.assertTrue(runner.last_plan.name.endswith("-plan.tfplan"))

    def test_plan_reads_relative_out_from_runner_workdir(self):
        ctx = self._ctx()
        runner = FakeRunner(self.tmp.name, self._destructive())
        ctx.make_runner = lambda: runner
        results = self.ris._cmd_plan(ctx, out_file="relative.tfplan")
        self.assertEqual(1, results[-1].returncode)
        self.assertEqual(Path(self.tmp.name) / "relative.tfplan",
                         runner.last_plan)

    def test_apply_refuses_destructive_plan_before_apply(self):
        ctx = self._ctx(dry_run=False)
        runner = FakeRunner(self.tmp.name, self._destructive())
        ctx.make_runner = lambda: runner
        results = self.ris._cmd_apply(ctx, out_file="apply.tfplan")
        self.assertEqual(0, runner.applies)
        self.assertEqual(1, results[-1].returncode)
        self.assertIn("shared", results[-1].stderr.lower())

    def test_apply_allows_normal_plan(self):
        ctx = self._ctx(dry_run=False)
        runner = FakeRunner(self.tmp.name, plan())
        ctx.make_runner = lambda: runner
        original_mirror = self.ris.mirror_project_state
        self.ris.mirror_project_state = lambda *a, **k: None
        self.addCleanup(setattr, self.ris, "mirror_project_state",
                        original_mirror)
        results = self.ris._cmd_apply(ctx, out_file="apply.tfplan")
        self.assertEqual(1, runner.applies)
        self.assertEqual(0, results[-1].returncode)

    def test_apply_refuses_changed_plan_file(self):
        ctx = self._ctx(dry_run=False)
        runner = FakeRunner(self.tmp.name, plan())
        ctx.make_runner = lambda: runner
        original_mirror = self.ris.mirror_project_state
        self.ris.mirror_project_state = lambda *a, **k: None
        self.addCleanup(setattr, self.ris, "mirror_project_state",
                        original_mirror)
        original_guard = self.ris._guard_shared_infra

        def guard_then_tamper(r, path, c, required=False):
            decision = original_guard(r, path, c, required=required)
            p = self.ris._resolve_plan_path(r, path)
            p.write_text("tampered", encoding="utf-8")
            return decision

        self.ris._guard_shared_infra = guard_then_tamper
        self.addCleanup(setattr, self.ris, "_guard_shared_infra",
                        original_guard)
        results = self.ris._cmd_apply(ctx, out_file="apply.tfplan")
        self.assertEqual(0, runner.applies)
        self.assertEqual(1, results[-1].returncode)
        self.assertIn("changed", results[-1].stderr.lower())

    def test_apply_missing_plan_is_refused(self):
        ctx = self._ctx(dry_run=False)
        runner = FakeRunner(self.tmp.name, plan())
        ctx.make_runner = lambda: runner
        original = self.ris._load_plan_for_guard
        self.ris._load_plan_for_guard = lambda r, p, required=False: {
            "_guardError": "plan file not found"}
        self.addCleanup(setattr, self.ris, "_load_plan_for_guard", original)
        results = self.ris._cmd_apply(ctx, out_file="apply.tfplan")
        self.assertEqual(0, runner.applies)
        self.assertEqual(1, results[-1].returncode)


if __name__ == "__main__":
    unittest.main()
