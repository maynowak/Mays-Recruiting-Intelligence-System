"""
Tests for the RIS foundation installer CLI (no AWS, no terraform binary).

All TerraformRunner subprocess calls are mocked. Verifies project_name
identity, workspace derivation/collision-freedom, backend-config handoff,
dry-run safety, and preservation of existing mechanisms (CWD, init).
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from installer import ris
from installer.ris import RisInstallContext, build_parser, main
from installer.terraform_runner import workspace_for_project


def _completed(args, returncode=0):
    proc = MagicMock()
    proc.args = args
    proc.returncode = returncode
    proc.stdout = ""
    proc.stderr = ""
    return proc


def _clean_env():
    return {k: v for k, v in os.environ.items() if k != "TERRAFORM_WORKSPACE"}


def test_project_name_is_identity_and_workspace():
    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris")
    assert ctx.workspace == "mays-ris"
    assert ctx.workspace == workspace_for_project("mays-ris")


def test_two_projects_do_not_collide():
    with patch.dict(os.environ, _clean_env(), clear=True):
        first = RisInstallContext(project_name="mays-ris")
        second = RisInstallContext(project_name="mays-ris-test")
    assert first.workspace != second.workspace
    assert first.terraform_vars()["project_name"] != second.terraform_vars()["project_name"]


def test_environment_never_replaces_project_name():
    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris", environment="test")
    assert ctx.workspace == "mays-ris"
    assert ctx.terraform_vars() == {"project_name": "mays-ris", "environment": "test"}
    with pytest.raises(ValueError):
        RisInstallContext(project_name="mays-ris", environment="prod2")


def test_backend_config_from_explicit_flags_only():
    ctx = RisInstallContext(
        project_name="mays-ris",
        backend_bucket="my-bucket",
        backend_region="eu-central-1",
    )
    args = ctx.backend_config().to_args()
    assert "-backend-config=bucket=my-bucket" in args
    assert not any(a.startswith("-var") for a in args)


def test_missing_backend_values_raise_not_invented():
    ctx = RisInstallContext(project_name="mays-ris")
    with pytest.raises(ValueError, match="bucket"):
        ctx.backend_config().to_args()


def test_apply_requires_yes_dry_run_default():
    ctx = RisInstallContext(project_name="mays-ris")
    assert ctx.dry_run is True
    with pytest.raises(RuntimeError, match="dry-run"):
        ris._cmd_apply(ctx)


def test_plan_wires_runner_cwd_vars_and_backend():
    seen = {}

    def fake_run(args, **kwargs):
        seen.setdefault("cmds", []).append(list(args))
        seen["cwd"] = str(kwargs.get("cwd", ""))
        seen.update(kwargs.get("env", {}))
        return _completed(args)

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(
            project_name="mays-ris",
            terraform_dir="terraform",
            backend_bucket="b",
            backend_region="r",
        )
    with patch("subprocess.run", side_effect=fake_run):
        results = ris._cmd_plan(ctx, out_file="tfplan")
    flat = [" ".join(c) for c in seen["cmds"]]
    assert any(c.startswith("terraform init -backend-config=") for c in flat)
    assert any("terraform plan" in c and "-var project_name=mays-ris" in c for c in flat)
    assert any("-var environment=dev" in c for c in flat)
    assert "tfplan" in flat[[i for i, c in enumerate(flat) if "terraform plan" in c][0]]
    assert seen["cwd"].endswith("terraform")
    assert seen.get("TERRAFORM_WORKSPACE") == "mays-ris"
    assert all(r.returncode == 0 for r in results)


def test_cli_parsing_defaults():
    parsed = build_parser().parse_args(["validate"])
    assert (parsed.project_name, parsed.environment, parsed.command) == (
        "mays-ris",
        "dev",
        "validate",
    )
