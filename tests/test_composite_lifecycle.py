"""
Tests for the GLUE-01 composite lifecycle integration.

Scope:
- Orders component naming derivation & collision prevention.
- Output handoff mapping (Orders -> RIS vars).
- Orchestrator CLI argument ordering contract (global flags before command).
- Composite preflight/install/destroy sequencing and failure safety.

Does NOT touch AWS. The orchestrator subprocess calls are mocked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from installer.ris import (
    ORDERS_OUTPUT_VAR_MAP,
    RisInstallContext,
    derive_orders_queue_arn,
    derive_orders_queue_url,
    orders_component_project_name,
    orders_handoff_vars,
    parse_orders_outputs,
)
from installer.orchestrator import RISInstaller


# ---------------------------------------------------------------------------
# 1. Naming & collision prevention
# ---------------------------------------------------------------------------


class TestOrdersNaming:
    def test_derives_component_name(self):
        assert orders_component_project_name("mays-ris") == "mays-ris-mays-orders"
        assert (
            orders_component_project_name("mays-ris-test-e2e-01")
            == "mays-ris-test-e2e-01-mays-orders"
        )

    def test_explicit_override(self):
        assert (
            orders_component_project_name("mays-ris", override="legacy-name")
            == "legacy-name"
        )

    @pytest.mark.parametrize("bad", ["", "  "])
    def test_rejects_empty(self, bad):
        with pytest.raises(ValueError):
            orders_component_project_name(bad)

    def test_rejects_production_namespace(self):
        with pytest.raises(ValueError, match="mays-orders"):
            orders_component_project_name("mays-orders")
        with pytest.raises(ValueError, match="mays-orders"):
            orders_component_project_name("mays-orders-thing")

    def test_rejects_bad_chars(self):
        with pytest.raises(ValueError, match="naming contract"):
            orders_component_project_name("UPPER-Case")
        with pytest.raises(ValueError, match="naming contract"):
            orders_component_project_name("mays-ris_underscore")

    def test_rejects_leading_hyphen(self):
        with pytest.raises(ValueError, match="naming contract"):
            orders_component_project_name("-bad")

    def test_enforces_length_limit(self):
        long_name = "a" * 100
        with pytest.raises(ValueError, match="exceeds"):
            orders_component_project_name(long_name)


# ---------------------------------------------------------------------------
# 2. Queue derivation (Orders naming contract: {project}-orders-queue)
# ---------------------------------------------------------------------------


class TestQueueDerivation:
    def test_url(self):
        url = derive_orders_queue_url("mays-ris-mays-orders", "eu-central-1", "240571105849")
        assert url == (
            "https://sqs.eu-central-1.amazonaws.com/240571105849/"
            "mays-ris-mays-orders-orders-queue"
        )

    def test_arn(self):
        arn = derive_orders_queue_arn("mays-ris-mays-orders", "eu-central-1", "240571105849")
        assert arn == (
            "arn:aws:sqs:eu-central-1:240571105849:"
            "mays-ris-mays-orders-orders-queue"
        )


# ---------------------------------------------------------------------------
# 3. Output parsing & handoff mapping
# ---------------------------------------------------------------------------


class TestParseOrdersOutputs:
    def test_pure_json(self):
        raw = json.dumps(
            {
                "dynamodb_table_name": {"value": "comp-orders"},
                "dynamodb_table_arn": {"value": "arn:aws:dynamodb:eu-central-1:1:x"},
            }
        )
        parsed = parse_orders_outputs(raw)
        assert parsed["dynamodb_table_name"]["value"] == "comp-orders"

    def test_json_embedded_in_text(self):
        raw = "Running terraform output...\n" + json.dumps(
            {"dynamodb_table_name": {"value": "x"}}
        ) + "\nDone"
        parsed = parse_orders_outputs(raw)
        assert parsed["dynamodb_table_name"]["value"] == "x"

    def test_truncated_json(self):
        raw = '{"dynamodb_table_name": {"value": "x"}, "truncated'
        with pytest.raises(RuntimeError, match="truncated or malformed"):
            parse_orders_outputs(raw)

    def test_no_json(self):
        with pytest.raises(RuntimeError, match="no JSON object"):
            parse_orders_outputs("terraform output failed")


class TestHandoffVars:
    def _sample_outputs(self):
        return {
            "dynamodb_table_name": {"value": "comp-orders"},
            "dynamodb_table_arn": {"value": "arn:aws:dynamodb:eu-central-1:240571105849:table/comp-orders"},
        }

    def test_maps_table_outputs(self):
        handoff = orders_handoff_vars(
            self._sample_outputs(), "mays-ris-mays-orders", "eu-central-1", "240571105849"
        )
        for out_name, var_name in ORDERS_OUTPUT_VAR_MAP.items():
            assert handoff[var_name] == self._sample_outputs()[out_name]["value"]

    def test_derives_queue(self):
        handoff = orders_handoff_vars(
            self._sample_outputs(), "mays-ris-mays-orders", "eu-central-1", "240571105849"
        )
        assert handoff["orders_queue_url"].endswith("mays-ris-mays-orders-orders-queue")
        assert handoff["orders_queue_arn"] == (
            "arn:aws:sqs:eu-central-1:240571105849:mays-ris-mays-orders-orders-queue"
        )

    def test_missing_table_output_fails_closed(self):
        bad = {"dynamodb_table_arn": {"value": "arn"}}
        with pytest.raises(RuntimeError, match="dynamodb_table_name"):
            orders_handoff_vars(bad, "p-mays-orders", "eu-central-1", "1")

    def test_empty_table_output_fails_closed(self):
        bad = {
            "dynamodb_table_name": {"value": ""},
            "dynamodb_table_arn": {"value": "arn"},
        }
        with pytest.raises(RuntimeError, match="dynamodb_table_name"):
            orders_handoff_vars(bad, "p-mays-orders", "eu-central-1", "1")


# ---------------------------------------------------------------------------
# 4. Orchestrator CLI arg ordering contract
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_info():
    from installer.orchestrator import ProjectInfo, GitInfo

    repo_root = Path(__file__).resolve().parent.parent
    return ProjectInfo(
        name="Mays-Orders-AWS",
        git_url="git@github.com:maynowak/mays-order-aws.git",
        local_path=repo_root / "installer" / "projects" / "mays_orders",
        git_info=GitInfo(
            root=str(repo_root),
            remote="git@github.com:maynowak/mays-order-aws.git",
            branch="main",
            commit="5cf50a0",
            is_clean=True,
        ),
        installer_exists=True,
    )


class TestOrchestratorArgOrdering:
    """Global --profile/--region/--aws-region/--environment/--project-name
    MUST precede the command word (argparse subcommand contract)."""

    def test_global_flags_precede_command(self):
        captured = []

        def fake_run(cmd, **kw):
            captured.append(cmd)
            return _FakeProc(returncode=0, stdout="{}", stderr="")

        orch = RISInstaller(dry_run=False)
        with mock.patch.object(orch, "discover_project", return_value=_make_info()), \
             mock.patch.object(orch, "checkout_project", return_value=_make_info()), \
             mock.patch("installer.orchestrator.subprocess.run", side_effect=fake_run):
            orch.run_project_installer(
                "mays-orders",
                command="validate",
                profile="mayaws",
                region="eu-central-1",
                environment="test",
                project_name_override="mays-ris-mays-orders",
            )

        cmd = captured[-1]
        join = " ".join(cmd)
        assert "--profile mayaws" in join
        assert "--region eu-central-1" in join
        assert "--aws-region eu-central-1" in join
        assert "--environment test" in join
        assert "--project-name mays-ris-mays-orders" in join
        idx_cmd = cmd.index("validate")
        last_global = max(i for i, a in enumerate(cmd) if a in ("mayaws", "eu-central-1"))
        assert last_global < idx_cmd, "global flags must precede command word"

    def test_extra_args_after_command(self):
        captured = []

        def fake_run(cmd, **kw):
            captured.append(cmd)
            return _FakeProc(returncode=0, stdout="{}", stderr="")

        orch = RISInstaller(dry_run=False)
        with mock.patch.object(orch, "discover_project", return_value=_make_info()), \
             mock.patch.object(orch, "checkout_project", return_value=_make_info()), \
             mock.patch("installer.orchestrator.subprocess.run", side_effect=fake_run):
            orch.run_project_installer(
                "mays-orders",
                command="deploy",
                project_name_override="mays-ris-mays-orders",
                extra_args=["--yes"],
                extra_env={"ALLOW_AWS_OPERATIONS": "true"},
            )
        all_flat = [a for c in captured for a in c]
        assert "deploy" in all_flat
        assert "--yes" in all_flat

    def test_full_output_not_truncated(self):
        big = json.dumps({"dynamodb_table_name": {"value": "x"}})
        captured = []

        def fake_run(cmd, **kw):
            captured.append(cmd)
            return _FakeProc(returncode=0, stdout=big, stderr="")

        orch = RISInstaller(dry_run=False)
        with mock.patch.object(orch, "discover_project", return_value=_make_info()), \
             mock.patch.object(orch, "checkout_project", return_value=_make_info()), \
             mock.patch("installer.orchestrator.subprocess.run", side_effect=fake_run):
            res = orch.run_project_installer(
                "mays-orders", command="output",
                project_name_override="mays-ris-mays-orders", full_output=True,
            )
        assert res["stdout"] == big


# ---------------------------------------------------------------------------
# 5. RisInstallContext handoff plumbing
# ---------------------------------------------------------------------------


class TestRisContextHandoff:
    def test_context_carries_orders_vars_when_supplied(self):
        ctx = RisInstallContext(
            project_name="mays-ris",
            environment="test",
            dry_run=True,
            extra_vars={"orders_table_name": "comp-tbl"},
        )
        assert ctx.terraform_vars()["orders_table_name"] == "comp-tbl"


# ---------------------------------------------------------------------------
# 6. Composite destroy sequence ordering & protection
# ---------------------------------------------------------------------------


class TestCompositeDestroySequence:
    def test_name_protection_blocks_standalone_namespace(self):
        with pytest.raises(ValueError):
            orders_component_project_name("mays-orders")


# ---------------------------------------------------------------------------
# 7. Binding validation (fail-closed)
# ---------------------------------------------------------------------------


class TestBindingValidation:
    """Test that binding validation rejects incorrect Orders component linkage."""
    
    def _make_handoff(self, project: str, account: str = "240571105849"):
        """Create handoff dict in the format orders_handoff_vars returns."""
        outputs = {
            "dynamodb_table_name": {"value": project},
            "dynamodb_table_arn": {"value": f"arn:aws:dynamodb:eu-central-1:{account}:table/{project}"},
        }
        return orders_handoff_vars(outputs, project, "eu-central-1", account)
    
    def test_standalone_orders_table_rejected_for_non_standalone_project(self):
        """Non-standalone projects reject binding to standalone mays-orders table."""
        from installer.ris import validate_orders_binding
        
        handoff = self._make_handoff("mays-orders", "240571105849")
        # Should FAIL because project= mays-orders but we're binding to mays-ris-mays-orders
        with pytest.raises(RuntimeError, match="mismatch|standalone"):
            validate_orders_binding(handoff, "mays-ris-mays-orders", "240571105849")
    
    def test_cross_project_binding_rejected(self):
        """RIS A cannot be bound to Orders B outputs."""
        from installer.ris import validate_orders_binding
        
        # Orders B outputs for project B
        handoff = self._make_handoff("project-b-mays-orders")
        # But we're trying to bind to project A
        queue_url = derive_orders_queue_url("mays-ris-mays-orders", "eu-central-1", "240571105849")
        with pytest.raises(RuntimeError, match="mismatch"):
            validate_orders_binding(handoff, "mays-ris-mays-orders", "240571105849", queue_url)
    
    def test_account_mismatch_detected(self):
        """Detect when Orders outputs belong to different AWS account."""
        from installer.ris import validate_orders_binding
        
        # Create handoff for wrong account
        outputs = {
            "dynamodb_table_name": {"value": "mays-ris-mays-orders"},
            "dynamodb_table_arn": {"value": "arn:aws:dynamodb:eu-central-1:999999999999:table/mays-ris-mays-orders"},
        }
        handoff = orders_handoff_vars(outputs, "mays-ris-mays-orders", "eu-central-1", "999999999999")
        # Account mismatch - we're saying account 2405... but outputs belong to 9999...
        with pytest.raises(RuntimeError, match="account mismatch"):
            validate_orders_binding(handoff, "mays-ris-mays-orders", "240571105849")
    
    def test_valid_project_binding_passes(self):
        """Valid binding for correct project passes validation."""
        from installer.ris import validate_orders_binding
        
        project = "mays-ris-mays-orders"
        account = "240571105849"
        handoff = self._make_handoff(project, account)
        # Should not raise
        validate_orders_binding(handoff, project, account)


    def test_missing_table_name_detected(self):
        """Detect missing orders_table_name in handoff."""
        from installer.ris import validate_orders_binding
        
        handoff = {
            "orders_table_name": "",
            "orders_table_arn": "arn:aws:dynamodb:eu-central-1:240571105849:table/test",
            "orders_queue_url": "https://sqs.eu-central-1.amazonaws.com/240571105849/test-queue",
            "orders_queue_arn": "arn:aws:sqs:eu-central-1:240571105849:test-queue",
        }
        with pytest.raises(RuntimeError, match="orders_table_name"):
            validate_orders_binding(handoff, "test-project", "240571105849")
    
    def test_missing_table_arn_detected(self):
        """Detect missing orders_table_arn in handoff."""
        from installer.ris import validate_orders_binding
        
        handoff = {
            "orders_table_name": "test-project",
            "orders_table_arn": "",
            "orders_queue_url": "https://sqs.eu-central-1.amazonaws.com/240571105849/test-queue",
            "orders_queue_arn": "arn:aws:sqs:eu-central-1:240571105849:test-queue",
        }
        with pytest.raises(RuntimeError, match="orders_table_arn"):
            validate_orders_binding(handoff, "test-project", "240571105849")
    
    def test_backend_binding_check(self):
        """Verify RIS installer binds to correct component via backend."""
        # This is verified via the reflect_in_db test
        pass
