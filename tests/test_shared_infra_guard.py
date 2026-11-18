"""Shared-infrastructure guard: missing flags must never mean teardown."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from installer.shared_infra_guard import (  # noqa: E402
    evaluate_plan,
)


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
                       "orders_agent_result_enabled": {"value": True}},
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
            change("module.health.aws_cloudwatch_log_group.stale",
                   ["delete"], "aws_cloudwatch_log_group")))
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
            plan(change("module.custom.aws_cloudwatch_log_group.shared-x",
                        ["delete"], "aws_cloudwatch_log_group")),
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


class TestPlanAndApplyWiring(unittest.TestCase):
    def _ctx(self, dry_run=False):
        from installer import ris

        ctx = ris.RisInstallContext(project_name="ris-dev2",
                                    environment="dev", dry_run=dry_run)
        ctx.aws_context = object()
        return ctx, ris

    def _destructive(self):
        return plan(change(TRANSPORT, ["delete"], "aws_sqs_queue"))

    def test_plan_blocks_destructive_transport_plan(self):
        import tempfile

        ctx, ris = self._ctx()

        class Runner:
            def init(self, **kwargs):
                return ris.TerraformResult(["init"], 0)

            def plan(self, **kwargs):
                return ris.TerraformResult(["plan"], 0)

            def show_json(self, path):
                return self._plan

        runner = Runner()
        runner._plan = self._destructive()
        ctx.make_runner = lambda: runner
        with tempfile.NamedTemporaryFile(suffix=".tfplan", delete=False) as fh:
            out = fh.name
        self.addCleanup(lambda: os.unlink(out))
        results = ris._cmd_plan(ctx, out_file=out)
        self.assertEqual(3, len(results))
        self.assertEqual(1, results[-1].returncode)
        self.assertIn("shared infrastructure", results[-1].stderr.lower())

    def test_no_saved_plan_does_not_block(self):
        ctx, ris = self._ctx()

        class Runner:
            def init(self, **kwargs):
                return ris.TerraformResult(["init"], 0)

            def plan(self, **kwargs):
                return ris.TerraformResult(["plan"], 0)

        ctx.make_runner = lambda: Runner()
        results = ris._cmd_plan(ctx)
        self.assertEqual(2, len(results))

    def test_apply_refuses_destructive_plan_before_apply(self):
        ctx, ris = self._ctx(dry_run=False)
        calls = {"apply": 0}

        class Runner:
            def init(self, **kwargs):
                return ris.TerraformResult(["init"], 0)

            def plan(self, **kwargs):
                return ris.TerraformResult(["plan"], 0)

            def run_and_get_result(self, args, **kwargs):
                calls["apply"] += 1
                return ris.TerraformResult(args, 0)

        ctx.make_runner = lambda: Runner()
        original = ris._load_plan_for_guard
        ris._load_plan_for_guard = lambda runner, path: self._destructive()
        self.addCleanup(setattr, ris, "_load_plan_for_guard", original)
        results = ris._cmd_apply(ctx, out_file="ignored.tfplan")
        self.assertEqual(0, calls["apply"])
        self.assertEqual(1, results[-1].returncode)
        self.assertIn("shared", results[-1].stderr.lower())

    def test_apply_allows_normal_plan(self):
        ctx, ris = self._ctx(dry_run=False)
        calls = {"apply": 0}

        class Runner:
            def init(self, **kwargs):
                return ris.TerraformResult(["init"], 0)

            def plan(self, **kwargs):
                return ris.TerraformResult(["plan"], 0)

            def run_and_get_result(self, args, **kwargs):
                calls["apply"] += 1
                return ris.TerraformResult(args, 0)

        ctx.make_runner = lambda: Runner()
        original_load = ris._load_plan_for_guard
        original_mirror = ris.mirror_project_state
        ris._load_plan_for_guard = lambda runner, path: plan()
        ris.mirror_project_state = lambda *a, **k: None
        self.addCleanup(setattr, ris, "_load_plan_for_guard", original_load)
        self.addCleanup(setattr, ris, "mirror_project_state", original_mirror)
        results = ris._cmd_apply(ctx, out_file="ignored.tfplan")
        self.assertEqual(1, calls["apply"])
        self.assertEqual(0, results[-1].returncode)


if __name__ == "__main__":
    unittest.main()
