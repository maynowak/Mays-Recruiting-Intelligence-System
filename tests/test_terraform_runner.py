"""
Tests for the RIS Terraform execution / workspace isolation layer.

Reference: Mays-Orders-AWS tested pattern (select -> new fallback,
TERRAFORM_WORKSPACE, init separation). All subprocess calls are mocked;
no terraform binary, no AWS, no state is touched.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from installer.terraform_runner import (
    DEFAULT_WORKSPACE,
    TerraformRunner,
    workspace_for_project,
)


def _completed(args, returncode=0, stdout="", stderr=""):
    proc = MagicMock()
    proc.args = args
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def _runner(workspace="default", **kwargs):
    env = {k: v for k, v in os.environ.items() if k != "TERRAFORM_WORKSPACE"}
    with patch.dict(os.environ, env, clear=True):
        return TerraformRunner(working_dir="/tmp/tf-test", workspace=workspace, **kwargs)


# Test 1 — Default: no `workspace new` (and no select either).
def test_default_workspace_performs_no_workspace_commands():
    runner = _runner("default")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "validate"])
        runner.validate()
    called = [" ".join(c.args[0]) for c in run.call_args_list]
    assert not any("workspace new" in c for c in called)
    assert not any("workspace select" in c for c in called)
    assert any(c == "terraform validate" for c in called)


# Test 2 — explicit workspace: `workspace select <workspace>` runs first.
def test_explicit_workspace_selects_before_command():
    runner = _runner("mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform"])
        runner.validate()
    called = [" ".join(c.args[0]) for c in run.call_args_list]
    assert called[0] == "terraform workspace select mays-ris"
    assert called[1] == "terraform validate"


# Test 3 — missing workspace: select fails -> `workspace new` runs.
def test_missing_workspace_is_created():
    runner = _runner("mays-ris")
    select_fail = _completed(
        ["terraform", "workspace", "select", "mays-ris"],
        returncode=1,
        stderr="Workspace \"mays-ris\" doesn't exist",
    )
    with patch("subprocess.run") as run:
        run.side_effect = [select_fail, _completed(["new"]), _completed(["validate"])]
        result = runner.validate()
    called = [" ".join(c.args[0]) for c in run.call_args_list]
    assert called[0] == "terraform workspace select mays-ris"
    assert called[1] == "terraform workspace new mays-ris"
    assert result.returncode == 0


# Test 4 — project_name derives workspace verbatim.
def test_project_name_derives_workspace():
    assert workspace_for_project("mays-ris") == "mays-ris"
    assert _runner(workspace_for_project("mays-ris")).workspace == "mays-ris"


# Test 5 — environment stays separate (never becomes workspace).
def test_environment_never_becomes_workspace():
    runner = _runner(workspace_for_project("mays-ris"))
    assert runner.workspace == "mays-ris"
    assert runner.workspace != "Development"
    assert not hasattr(runner, "environment")


# Test 6 — TERRAFORM_WORKSPACE equals runner.workspace in child env.
def test_child_env_carries_workspace():
    runner = _runner("mays-ris")
    seen = {}

    def fake_run(args, **kwargs):
        seen.update(kwargs.get("env", {}))
        return _completed(args)

    with patch("subprocess.run", side_effect=fake_run):
        runner.validate()
    assert seen.get("TERRAFORM_WORKSPACE") == "mays-ris"
    assert "TERRAFORM_WORKSPACE" not in os.environ  # no global mutation


# Test 7 — init() performs no workspace operation.
def test_init_has_no_workspace_operations():
    for kwargs in ({}, {"backend": False}, {"upgrade": True}, {"reconfigure": True}):
        runner = _runner("mays-ris")
        with patch("subprocess.run") as run:
            run.return_value = _completed(["terraform", "init"])
            result = runner.init(**kwargs)
        called = [" ".join(c.args[0]) for c in run.call_args_list]
        assert not any("workspace" in c for c in called), kwargs
        assert result.command[0:2] == ["terraform", "init"]
