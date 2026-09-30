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


# --- AWS context integration (FOUNDATION-INSTALLER-INTEGRATION) ---------

from installer.identity_context import (
    AwsExecutionContext,
    AwsValidationError,
    validate_aws_context,
)


def _aws_ctx():
    return AwsExecutionContext(
        region="eu-central-1",
        account_id="123456789012",
        identity_arn="arn:aws:iam::123456789012:user/tester",
        profile="mayaws",
    )


# Test A — profile independent of project_name (same profile, two projects).
def test_same_profile_two_projects_stay_distinct():
    with patch.dict(os.environ, _clean_env(), clear=True):
        first = RisInstallContext(project_name="mays-ris")
        second = RisInstallContext(project_name="mays-ris-test")
    assert first.workspace != second.workspace


# Test G — AWS context reaches terraform child env (no global mutation).
def test_aws_context_flows_to_child_env():
    from installer.terraform_runner import TerraformRunner

    with patch.dict(os.environ, _clean_env(), clear=True):
        runner = TerraformRunner(
            working_dir="terraform", workspace="mays-ris", aws_context=_aws_ctx()
        )
    env = runner._terraform_env()
    assert env["AWS_REGION"] == "eu-central-1"
    assert env["AWS_PROFILE"] == "mayaws"
    assert env["TERRAFORM_WORKSPACE"] == "mays-ris"
    assert "AWS_PROFILE" not in os.environ


# Test G2 — runner without context behaves as before (backward compatible).
def test_runner_without_context_unchanged():
    from installer.terraform_runner import TerraformRunner

    with patch.dict(os.environ, _clean_env(), clear=True):
        runner = TerraformRunner(working_dir="terraform", workspace="mays-ris")
    env = runner._terraform_env()
    assert "AWS_PROFILE" not in env
    assert env["TERRAFORM_WORKSPACE"] == "mays-ris"


# Test preflight — read-only validation prints identifiers, no secrets.
def test_preflight_prints_identity_without_secrets(capsys):
    import installer.ris as ris_mod

    fake = {"UserId": "AIDAX", "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/tester"}
    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris", aws_profile="mayaws")
    with patch("installer.identity_context._run_sts", return_value=fake):
        assert ris_mod._cmd_preflight(ctx) == 0
    out = capsys.readouterr().out
    assert "123456789012" in out and "eu-central-1" in out
    lowered = out.lower()
    assert "secret" not in lowered and "token" not in lowered
    assert ctx.aws_context is not None and ctx.aws_context.validated


# Test preflight failure — error surfaced, exit 1, nothing swallowed.
def test_preflight_failure_returns_error(capsys):
    import installer.ris as ris_mod

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris", aws_profile="nope")
    with patch("installer.identity_context._run_sts",
               side_effect=AwsValidationError("STS validation failed: x")):
        assert ris_mod._cmd_preflight(ctx) == 1
    assert "error" in capsys.readouterr().err.lower()


# --- Install command + backend bootstrap (CALLPATH-05) --------------------

from installer.backend import (
    BackendBootstrap,
    BackendConflictError,
    BackendNames,
)


def _fake_boto_client_factory(existing=None, tags=None):
    """Fake boto3 clients: existing={'s3': bool, 'dynamodb': bool}."""
    existing = existing or {}
    tags = tags if tags is not None else [{"Key": "Project", "Value": "mays-ris"}]
    calls = []

    class FakeS3:
        def head_bucket(self, Bucket):
            calls.append(("head_bucket", Bucket))
            if not existing.get("s3"):
                raise Exception("404 NoSuchBucket")

        def get_bucket_tagging(self, Bucket):
            return {"TagSet": tags}

        def create_bucket(self, **kwargs):
            calls.append(("create_bucket", kwargs.get("Bucket")))
            return {}

        def put_bucket_encryption(self, **kwargs):
            calls.append(("put_bucket_encryption",))
            return {}

        def put_public_access_block(self, **kwargs):
            calls.append(("put_public_access_block",))
            return {}

        def put_bucket_versioning(self, **kwargs):
            calls.append(("put_bucket_versioning",))
            return {}

        def put_bucket_tagging(self, **kwargs):
            calls.append(("put_bucket_tagging",))
            return {}

    class FakeDynamo:
        def describe_table(self, TableName):
            calls.append(("describe_table", TableName))
            if not existing.get("dynamodb"):
                raise Exception("ResourceNotFoundException")
            return {}

        def create_table(self, **kwargs):
            calls.append(("create_table", kwargs.get("TableName")))
            return {}

    def factory(service, region, profile=None):
        assert region == "eu-central-1"
        return FakeS3() if service == "s3" else FakeDynamo()

    factory.calls = calls
    return factory


# Test: naming derives from project_name (isolation), nothing invented.
def test_backend_names_derive_from_project():
    names = BackendNames.for_project("mays-ris", "dev")
    assert names.bucket == "mays-ris-tf-state-dev"
    assert names.lock_table == "mays-ris-tf-lock"
    assert names.key == "terraform.tfstate"
    other = BackendNames.for_project("mays-ris-test", "dev")
    assert other.bucket != names.bucket and other.lock_table != names.lock_table


# Test: idempotency — existing owned resources cause no create calls.
def test_bootstrap_idempotent_when_owned():
    factory = _fake_boto_client_factory(existing={"s3": True, "dynamodb": True})
    boot = BackendBootstrap(
        BackendNames.for_project("mays-ris", "dev"),
        project_name="mays-ris",
        profile="mayaws",
        client_factory=factory,
    )
    result = boot.ensure_all()
    assert result["bucket"]["created"] is False
    assert result["lock_table"]["created"] is False
    assert not any(c[0] in ("create_bucket", "create_table") for c in factory.calls)


# Test: conflict — foreign bucket is never adopted.
def test_bootstrap_conflict_on_foreign_bucket():
    factory = _fake_boto_client_factory(
        existing={"s3": True, "dynamodb": False},
        tags=[{"Key": "Project", "Value": "someone-else"}],
    )
    boot = BackendBootstrap(
        BackendNames.for_project("mays-ris", "dev"),
        project_name="mays-ris",
        client_factory=factory,
    )
    with pytest.raises(BackendConflictError):
        boot.ensure_bucket()


# Test: missing values fail before any AWS contact (installer level).
def test_install_dry_run_performs_no_mutation(capsys):
    import installer.ris as ris_mod

    fake_ctx = {"UserId": "AIDAX", "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/tester"}
    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris")
    with patch("installer.ris.validate_aws_context") as v:
        v.return_value = MagicMock(account_id="123456789012", region="eu-central-1")
        with patch("subprocess.run") as run:
            assert ris_mod._cmd_install(ctx, out_file=None) == 0
            run.assert_not_called()
    out = capsys.readouterr().out
    assert "mays-ris-tf-state-dev" in out and "mays-ris-tf-lock" in out
    assert "secret" not in out.lower()


# Test: install --yes order is preflight-gated then bootstrap->init->validate->plan->apply.
def test_install_full_order_with_yes():
    import installer.ris as ris_mod

    order = []
    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris", dry_run=False)
    with patch("installer.ris.validate_aws_context") as v, \
         patch("installer.backend.BackendBootstrap.ensure_all") as boot, \
         patch("subprocess.run") as run:
        v.return_value = MagicMock(account_id="1", region="eu-central-1")
        boot.return_value = {"bucket": {}, "lock_table": {}}
        run.return_value = _completed(["terraform"])
        assert ris_mod._cmd_install(ctx, out_file="tfplan") == 0
    cmds = [" ".join(c.args[0]) for c in run.call_args_list]
    assert any("terraform init -backend-config=" in c for c in cmds)
    assert any(c == "terraform validate" for c in cmds)
    assert any("terraform plan" in c and "-var project_name=mays-ris" in c for c in cmds)
    assert any("terraform apply -auto-approve" in c for c in cmds)
    # init before validate before plan before apply (workspace selects ignored)
    kinds = ["init" if " init " in f" {c} " else
             "validate" if c.endswith("validate") else
             "plan" if " plan " in f" {c} " else
             "workspace" if " workspace " in f" {c} " else "apply" for c in cmds]
    seq = [k for k in kinds if k != "workspace"]
    assert seq.index("init") < seq.index("validate") < seq.index("plan") < seq.index("apply")


# Test: preflight failure stops installation before any mutation.
def test_install_stops_when_preflight_fails():
    import installer.ris as ris_mod

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris", dry_run=False)
    with patch("installer.ris.validate_aws_context",
               side_effect=__import__("installer.identity_context", fromlist=["AwsValidationError"]).AwsValidationError("bad")):
        with patch("subprocess.run") as run:
            assert ris_mod._cmd_install(ctx) == 1
            run.assert_not_called()


# --- State commands (MO statefile approach consolidated) ------------------

# Test: list/show/pull pass through with workspace resolution.
def test_state_read_commands_passthrough():
    import installer.ris as ris_mod

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform"])
        assert ris_mod._cmd_state(ctx, "list") == 0
        assert ris_mod._cmd_state(ctx, "show", address="aws_s3_bucket.data") == 0
        assert ris_mod._cmd_state(ctx, "pull") == 0
    called = [" ".join(c.args[0]) for c in run.call_args_list]
    assert any("terraform state list" in c for c in called)
    assert any("terraform state show aws_s3_bucket.data" in c for c in called)
    assert any("terraform state pull" in c for c in called)
    # workspace ensured (non-default) for state commands
    assert any("workspace select mays-ris" in c for c in called)


# Test: show without address fails cleanly.
def test_state_show_requires_address(capsys):
    import installer.ris as ris_mod

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris")
    assert ris_mod._cmd_state(ctx, "show") == 2


# Test: push refused in dry-run (no mutation).
def test_state_push_refused_without_yes(capsys):
    import installer.ris as ris_mod

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris")
    with patch("subprocess.run") as run:
        assert ris_mod._cmd_state(ctx, "push", state_file="s.tfstate") == 1
        run.assert_not_called()
    assert "mutat" in capsys.readouterr().err.lower()


# Test: push requires state file even with --yes.
def test_state_push_requires_state_file():
    import installer.ris as ris_mod

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris", dry_run=False)
    with patch("subprocess.run") as run:
        assert ris_mod._cmd_state(ctx, "push") == 2
        run.assert_not_called()


# Test: push with --yes and file issues the command.
def test_state_push_with_yes_and_file():
    import installer.ris as ris_mod

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris", dry_run=False)
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform"])
        assert ris_mod._cmd_state(ctx, "push", state_file="s.tfstate") == 0
    called = [" ".join(c.args[0]) for c in run.call_args_list]
    assert any("terraform state push s.tfstate" in c for c in called)


# --- Run artifacts (MO statefile routine consolidated) --------------------

from installer.artifacts import RunArtifacts, sanitize_plan_json


# Test: sanitization redacts secrets, never mutates input.
def test_sanitize_plan_json_redacts_without_mutation():
    plan = {"resource_changes": [
        {"change": {"after": {"password": "p@ss", "name": "x"},
                     "before": {"api_key": "k", "size": 3}}},
        {"change": {"after": None, "before": "scalar"}},
        "not-a-dict",
    ]}
    clean = sanitize_plan_json(plan)
    after = clean["resource_changes"][0]["change"]["after"]
    before = clean["resource_changes"][0]["change"]["before"]
    assert after["password"] == "***REDACTED***" and after["name"] == "x"
    assert before["api_key"] == "***REDACTED***" and before["size"] == 3
    assert plan["resource_changes"][0]["change"]["after"]["password"] == "p@ss"


# Test: sanitize handles missing/non-dict shapes.
def test_sanitize_plan_json_robust_shapes():
    assert sanitize_plan_json({}) == {}
    assert sanitize_plan_json({"resource_changes": "x"}) == {"resource_changes": "x"}


# Test: run dir lifecycle in isolated base (no repo pollution).
def test_run_artifacts_lifecycle_tmp(tmp_path):
    store = RunArtifacts(base_dir=str(tmp_path / "runs"))
    run_dir = store.create_run_dir("r1")
    assert (run_dir / "logs").is_dir() and (run_dir / "plans").is_dir()
    ctx_file = store.save_context(run_dir, {"project_name": "mays-ris"})
    assert ctx_file.is_file()
    plan_file = store.save_plan_copy(run_dir, {"resource_changes": []})
    assert plan_file.is_file()
    log_file = store.save_log(run_dir, "line1\n")
    assert log_file.is_file()
    store.create_run_dir("r2")
    assert [p.name for p in store.list_runs()] == ["r2", "r1"]
    assert store.cleanup_old_runs(keep_last=1) == 1
    assert [p.name for p in store.list_runs()] == ["r2"]


# Test: backend-less validate skips workspace ops (no backend to select in).
def test_validate_skips_workspace_without_backend():
    import installer.ris as ris_mod

    with patch.dict(os.environ, _clean_env(), clear=True):
        ctx = RisInstallContext(project_name="mays-ris")
    with patch("subprocess.run") as run:
        run.return_value = _completed(["terraform"])
        results = ris_mod._cmd_validate(ctx)
    called = [" ".join(c.args[0]) for c in run.call_args_list]
    assert not any("workspace" in c for c in called)
    assert all(r.returncode == 0 for r in results)
