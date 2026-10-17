"""Dry-run must rehearse the WHOLE chain.

The problem this covers: in a dry run nothing is applied, so the component's
`terraform output` is empty and RIS has no binding to plan against. A dry run
that stops there rehearses nothing.

The fix reads the component's PLAN instead. Measured on a real composite plan
(Terraform v1.16.1):
  dynamodb_table_name -> known
  dynamodb_table_arn  -> unknown=True
Terraform cannot know a computed ARN before creation, so exactly one value is
derived - from the service's fixed ARN format - and everything else that stays
unknown must fail loudly instead of being invented.

These tests use the real captured plan JSON and never touch AWS.
"""

import json

import pytest

from installer.ris import (
    ORDERS_OUTPUT_VAR_MAP,
    _has_consumable_outputs,
    orders_handoff_vars,
    orders_outputs_from_plan,
    orders_plan_path_from_output,
    predict_orders_outputs,
)

REGION = "eu-central-1"
ACCOUNT = "240571105849"
PROJECT = "mays-ris-composite-a-mays-orders"

REAL_ARN = "arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-terraform-locks"


def _plan():
    """A plan shaped like the measured real one."""
    return {
        "output_changes": {
            "dynamodb_table_name": {"after": PROJECT, "after_unknown": False},
            "dynamodb_table_arn": {"after": None, "after_unknown": True},
            "cognito_user_pool_id": {"after": None, "after_unknown": True},
            "lambda_function_name": {
                "after": f"{PROJECT}-handler",
                "after_unknown": False,
            },
        }
    }


class TestExtractFromPlan:
    def test_known_values_are_carried_through(self):
        out = orders_outputs_from_plan(_plan())
        assert out["dynamodb_table_name"] == PROJECT

    def test_unknown_values_become_none_not_guesses(self):
        out = orders_outputs_from_plan(_plan())
        assert out["dynamodb_table_arn"] is None

    def test_unknown_values_are_listed(self):
        out = orders_outputs_from_plan(_plan())
        assert "dynamodb_table_arn" in out["_unknown"]
        assert "dynamodb_table_name" not in out["_unknown"]

    def test_plan_without_output_changes_is_rejected(self):
        """A plan RIS cannot read must fail, not yield an empty handoff."""
        with pytest.raises(RuntimeError, match="output_changes"):
            orders_outputs_from_plan({"format_version": "1.2"})

    def test_list_valued_after_unknown_is_treated_as_unknown(self):
        plan = _plan()
        plan["output_changes"]["dynamodb_table_arn"]["after_unknown"] = ["id"]
        out = orders_outputs_from_plan(plan)
        assert out["dynamodb_table_arn"] is None
        assert "dynamodb_table_arn" in out["_unknown"]


class TestPrediction:
    def test_table_arn_is_derived_with_the_services_format(self):
        out = predict_orders_outputs(
            orders_outputs_from_plan(_plan()), PROJECT, REGION, ACCOUNT
        )
        assert out["dynamodb_table_arn"] == (
            f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{PROJECT}"
        )

    def test_the_format_matches_a_real_table_in_the_account(self):
        """Verified against mays-orders-terraform-locks, not assumed."""
        from installer.ris import derive_orders_table_arn

        name = REAL_ARN.rsplit("/", 1)[1]
        assert derive_orders_table_arn(name, REGION, ACCOUNT) == REAL_ARN

    def test_prediction_is_recorded_not_silent(self):
        out = predict_orders_outputs(
            orders_outputs_from_plan(_plan()), PROJECT, REGION, ACCOUNT
        )
        assert out["_predicted"] == ["dynamodb_table_arn"]

    def test_unconsumed_unknowns_do_not_block_the_rehearsal(self):
        """cognito_user_pool_id is unknown and RIS never reads it."""
        out = predict_orders_outputs(
            orders_outputs_from_plan(_plan()), PROJECT, REGION, ACCOUNT
        )
        assert "cognito_user_pool_id" in out["_unknown"]

    def test_a_required_unknown_that_is_not_derivable_raises(self):
        """The whole point: never invent a binding."""
        plan = _plan()
        # Make the NAME unknown too - now nothing is derivable.
        plan["output_changes"]["dynamodb_table_name"]["after_unknown"] = True
        out = orders_outputs_from_plan(plan)
        with pytest.raises(RuntimeError, match="table name"):
            predict_orders_outputs(out, PROJECT, REGION, ACCOUNT)

    def test_a_consumed_output_staying_unknown_raises_even_when_derivable(self):
        """The general guard, independent of the ARN special case.

        The ARN is always handled before this guard, so on its own it cannot
        fire. Here the ARN is known and the NAME is not: nothing is derivable,
        and the run must stop rather than bind RIS to a name it does not have.
        This is what protects a future output RIS starts consuming.
        """
        plan = _plan()
        plan["output_changes"]["dynamodb_table_arn"] = {
            "after": f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{PROJECT}",
            "after_unknown": False,
        }
        plan["output_changes"]["dynamodb_table_name"]["after_unknown"] = True
        out = orders_outputs_from_plan(plan)
        with pytest.raises(RuntimeError, match="not\\s+deterministically derivable"):
            predict_orders_outputs(out, PROJECT, REGION, ACCOUNT)

    def test_prediction_does_not_mutate_its_input(self):
        out = orders_outputs_from_plan(_plan())
        predict_orders_outputs(out, PROJECT, REGION, ACCOUNT)
        assert out["dynamodb_table_arn"] is None


class TestHandoffFromDryRun:
    def test_a_dry_run_produces_a_complete_binding(self):
        out = predict_orders_outputs(
            orders_outputs_from_plan(_plan()), PROJECT, REGION, ACCOUNT
        )
        handoff = orders_handoff_vars(out, PROJECT, REGION, ACCOUNT)
        for var in ORDERS_OUTPUT_VAR_MAP.values():
            assert handoff[var], f"{var} must not be empty in a dry run"
        assert handoff["orders_queue_url"]
        assert handoff["orders_queue_arn"]

    def test_empty_outputs_are_recognised_as_unbound(self):
        """What a real dry-run `terraform output` gives back."""
        from installer.ris import parse_orders_outputs

        assert _has_consumable_outputs({}) is False
        assert _has_consumable_outputs(parse_orders_outputs("no outputs yet\n{}\n")) is False

    def test_plan_derived_outputs_count_as_bound(self):
        out = predict_orders_outputs(
            orders_outputs_from_plan(_plan()), PROJECT, REGION, ACCOUNT
        )
        assert _has_consumable_outputs(out) is True


class TestPlanPathIsReadNotGuessed:
    def test_path_is_taken_from_the_deploy_instruction(self):
        stdout = (
            "Plan Summary:\n"
            "  Plan file: orders-0003.tfplan\n"
            "  Deploy with: ./Mays-Order-AWS-installer deploy --plan "
            ".mays-installer/runs/20261017-114621/plans/orders-0003.tfplan\n"
        )
        assert orders_plan_path_from_output(stdout) == (
            ".mays-installer/runs/20261017-114621/plans/orders-0003.tfplan"
        )

    def test_last_instruction_wins(self):
        """A re-plan in the same output must not hand back an older plan."""
        stdout = (
            "--plan .mays-installer/runs/OLD/plans/a.tfplan\n"
            "retrying\n"
            "--plan .mays-installer/runs/NEW/plans/b.tfplan\n"
        )
        assert orders_plan_path_from_output(stdout).startswith(
            ".mays-installer/runs/NEW"
        )

    def test_no_instruction_yields_none_not_a_guess(self):
        assert orders_plan_path_from_output("nothing here") is None

    def test_nothing_is_discovered_by_globbing(self):
        """A concurrent run must not make RIS read someone else's plan.

        Checked on the AST, not the source text: the docstring itself says
        "nothing is discovered by globbing", so a substring assertion would pass
        even if the function started globbing.
        """
        import ast
        import inspect
        import textwrap

        from installer import ris

        tree = ast.parse(textwrap.dedent(inspect.getsource(ris.orders_plan_path_from_output)))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        for forbidden in ("glob", "rglob", "listdir", "iterdir", "scandir", "walk"):
            assert forbidden not in called, f"{forbidden} would allow reading another run's plan"


class TestRealPlanFixture:
    """The captured plan from an actual composite run, if it is still around.

    Not required: the synthetic plans above mirror its measured shape. When
    the artefact is present this pins our reading of it against reality.
    """

    @pytest.fixture()
    def real_plan(self):
        import pathlib

        path = pathlib.Path("/tmp/opencode/mo-plan.json")
        if not path.exists():
            pytest.skip("captured real plan not present in this environment")
        return json.loads(path.read_text())

    def test_real_plan_name_is_known_and_arn_is_not(self, real_plan):
        out = orders_outputs_from_plan(real_plan)
        assert out["dynamodb_table_name"] == PROJECT
        assert out["dynamodb_table_arn"] is None
        assert "dynamodb_table_arn" in out["_unknown"]

    def test_real_plan_yields_a_usable_binding(self, real_plan):
        out = predict_orders_outputs(
            orders_outputs_from_plan(real_plan), PROJECT, REGION, ACCOUNT
        )
        handoff = orders_handoff_vars(out, PROJECT, REGION, ACCOUNT)
        assert handoff["orders_table_name"] == PROJECT
        assert handoff["orders_table_arn"].startswith("arn:aws:dynamodb:")
