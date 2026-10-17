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
    BackendConfig,
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


# --- Backend-config handoff (IMPLEMENTATION-01) -------------------------

EXAMPLE_CONFIG = BackendConfig(bucket="mays-ris-tf-state-dev", region="eu-central-1")


# Test 1 — init without backend config still works (plain `terraform init`).
def test_init_without_backend_config():
    runner = _runner("default")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "init"])
        result = runner.init()
    assert result.command == ["terraform", "init"]
    assert not any("workspace" in " ".join(c.args[0]) for c in run.call_args_list)


# Test 2 — init with backend config emits `-backend-config=...`.
def test_init_with_backend_config():
    runner = _runner("default")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "init"])
        result = runner.init(backend_config=EXAMPLE_CONFIG)
    joined = " ".join(result.command)
    assert "-backend-config=bucket=mays-ris-tf-state-dev" in joined
    assert "-backend-config=region=eu-central-1" in joined
    assert "-backend-config=key=terraform.tfstate" in joined
    assert "-backend-config=dynamodb_table=mays-ris-tf-lock" in joined


# Test 3 — backend values never travel via `-var` to init.
def test_init_backend_never_uses_var_flags():
    runner = _runner("default")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "init"])
        result = runner.init(backend_config=EXAMPLE_CONFIG)
    assert not any(a.startswith("-var") for a in result.command)


# Test 4 — init performs no workspace operations (existing separation).
def test_init_backend_config_has_no_workspace_operations():
    runner = _runner("mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "init"])
        runner.init(backend_config=EXAMPLE_CONFIG)
    called = [" ".join(c.args[0]) for c in run.call_args_list]
    assert not any("workspace" in c for c in called)


# Test 5 — deterministic argument order for identical config.
def test_backend_config_args_deterministic():
    first = BackendConfig(bucket="b", region="r").to_args()
    second = BackendConfig(bucket="b", region="r").to_args()
    assert first == second
    assert first == sorted(first, key=lambda a: a.split("=", 1)[1].split("=", 1)[0])


# Test 6 — child environment semantics preserved with backend config.
def test_child_env_preserved_with_backend_config():
    runner = _runner("mays-ris")
    seen = {}

    def fake_run(args, **kwargs):
        seen.update(kwargs.get("env", {}))
        return _completed(args)

    with patch("subprocess.run", side_effect=fake_run):
        runner.init(backend_config=EXAMPLE_CONFIG)
    assert seen.get("TERRAFORM_WORKSPACE") == "mays-ris"
    assert "TERRAFORM_WORKSPACE" not in os.environ


# Test 7 — unknown backend value: explicit error, nothing invented.
def test_unresolved_backend_config_raises():
    assert not BackendConfig().is_resolved()
    assert set(BackendConfig().missing_fields()) == {"bucket", "region"}
    assert not BackendConfig(bucket="b").is_resolved()
    with pytest.raises(ValueError, match="bucket"):
        BackendConfig(region="r").to_args()


# --- TF_WORKSPACE: the variable Terraform actually honours -----------------
# Regression guard. TERRAFORM_WORKSPACE is NOT a Terraform variable; measured
# on v1.16.1 it is ignored by the CLI. TF_WORKSPACE is the real one and is
# what makes two projects sharing one working directory safe.

def test_tf_workspace_is_set_for_child_processes():
    runner = _runner("mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "version", "-json"])
        runner.version()
    assert run.call_args.kwargs["env"]["TF_WORKSPACE"] == "mays-ris"


def test_terraform_workspace_still_set_for_component_context():
    """The component's InstallationContext.from_env() reads THIS name."""
    runner = _runner("mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "version", "-json"])
        runner.version()
    env = run.call_args.kwargs["env"]
    assert env["TERRAFORM_WORKSPACE"] == "mays-ris"
    assert env["TF_WORKSPACE"] == "mays-ris"


def test_tf_workspace_not_mutated_globally():
    """Child env only, never os.environ."""
    before = os.environ.get("TF_WORKSPACE")
    runner = _runner("mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "version", "-json"])
        runner.version()
    assert os.environ.get("TF_WORKSPACE") == before


def test_tf_workspace_survives_stale_environment_file():
    """The contamination case: a shared .terraform/environment names another
    project. The process-local override must still win, and the file must not
    be rewritten by us."""
    runner = _runner("mays-ris-composite-a-mays-orders")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform", "version", "-json"])
        runner.version()
    env = run.call_args.kwargs["env"]
    assert env["TF_WORKSPACE"] == "mays-ris-composite-a-mays-orders"
    assert env["TF_WORKSPACE"] != "mays-orders"


# --- workspace management must run WITHOUT the TF_WORKSPACE override -------
# Terraform refuses `workspace select` while TF_WORKSPACE is set (measured exit
# 1, "The selected workspace is currently overridden using the TF_WORKSPACE
# environment variable"). Without this, every non-default workspace command
# (state list, plan, apply) failed after TF_WORKSPACE was introduced.

def test_workspace_select_runs_without_tf_workspace_override():
    runner = _runner("mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform"])
        runner.validate()
    select_call = run.call_args_list[0]
    assert select_call.args[0][:3] == ["terraform", "workspace", "select"]
    assert "TF_WORKSPACE" not in select_call.kwargs["env"]


def test_workspace_new_runs_without_tf_workspace_override():
    runner = _runner("mays-ris")
    select_fail = _completed(
        ["terraform", "workspace", "select", "mays-ris"],
        returncode=1,
        stderr='Workspace "mays-ris" doesn\'t exist',
    )
    with patch("subprocess.run") as run:
        run.side_effect = [select_fail, _completed(["new"]), _completed(["validate"])]
        runner.validate()
    new_call = run.call_args_list[1]
    assert new_call.args[0][:3] == ["terraform", "workspace", "new"]
    assert "TF_WORKSPACE" not in new_call.kwargs["env"]


def test_real_terraform_commands_keep_tf_workspace():
    """Only workspace MANAGEMENT drops the override. State reads and writes
    must keep it, that is the entire point of the fix."""
    runner = _runner("mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform"])
        runner.plan()
    last = run.call_args_list[-1]
    assert last.args[0][:2] == ["terraform", "plan"]
    assert last.kwargs["env"]["TF_WORKSPACE"] == "mays-ris"
