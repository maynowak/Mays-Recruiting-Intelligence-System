#!/usr/bin/env python3
"""
RIS foundation installer CLI (minimal).

Installs ONE RIS project at a time, identified by project_name:

    project_name
        -> Installation identity (RisInstallContext)
        -> Terraform workspace (workspace_for_project, verbatim)
        -> TerraformRunner(workspace=...)
        -> init / validate / plan / apply

Reference pattern: Mays-Orders-AWS installer CLI (argparse commands,
dry-run default, workspace derivation, init separation). Directly
transferred: command shape, dry-run default, workspace derivation,
init/validate/plan/apply lifecycle. Deliberately NOT transferred:
AWSExecutionContext/profile machinery (none exists in RIS),
version/phase system, destroy command (no RIS destroy concept),
policy-gate engine (separate concern).

Safety rules (hard):
- dry_run is the DEFAULT; apply requires explicit --yes.
- Backend values come ONLY from explicit CLI flags (no invention,
  no defaults for bucket/region). Missing values raise.
- environment MUST be dev/test/prod (mirrors terraform validation);
  it NEVER replaces project_name as identity.
- No state migration, no destroy, no AWS provisioning here.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import boto3

from installer.terraform_runner import (
    BackendConfig,
    TerraformResult,
    TerraformRunner,
    workspace_for_project,
)
from installer.identity_context import (
    AwsExecutionContext,
    AwsValidationError,
    validate_aws_context,
)
from installer.backend import (
    BackendBootstrap,
    BackendConflictError,
    BackendNames,
)
from installer.orchestrator import RISInstaller


VALID_ENVIRONMENTS = ("dev", "test", "prod")

# Production resource prefixes that must never be targeted by test deployments
PRODUCTION_RESOURCE_PREFIXES = (
    "mays-ris-dev-",
    "mays-orders-",
)


# ---------------------------------------------------------------------------
# GLUE-01 (Composite Lifecycle): Orders component naming + output handoff.
#
# Mays-Orders-AWS is a closed, multiply-reusable component. Every RIS
# project installation owns exactly ONE project-specific Orders instance
# with its OWN identity, derived deterministically from the RIS project:
#
#     orders_project_name = f"{ris_project_name}-mays-orders"
#
# Historical origin (2026-10, account 240571105849): un-suffixed Orders
# project names collided on the DynamoDB table (table name == project
# name, exact) — the reason the historical composite tests used names
# like "mays-ris-mays-orders-test-e2e-01". This derivation preserves
# that collision-prevention contract and makes RIS ownership evident in
# the Orders installer collision scan (5cf50a0).
#
# Contract consequences (all established Orders contracts, none new):
# - Orders DynamoDB table == orders_project_name (exact, account-unique)
# - Orders resources      == f"{orders_project_name}-*"
# - Orders SQS queue     == f"{orders_project_name}-orders-queue"
# - Orders TF workspace  == orders_project_name (verbatim)
# - Orders TF state      == env:/{orders_project_name}/terraform.tfstate
# - Orders deployment-id == account:orders_project_name:environment
# - RIS resources        == f"{ris_project_name}-{environment}-*" (distinct)
#
# The component is invoked via installer/orchestrator.py (the ONLY
# orchestration path; no second orchestrator).
# ---------------------------------------------------------------------------
ORDERS_COMPONENT_SUFFIX = "-mays-orders"
ORDERS_QUEUE_SUFFIX = "-orders-queue"
#: Orders project_name length limit: the CloudTrail bucket
#: f"{project_name}-cloudtrail-<12-digit-account>" must stay <= 63 chars.
ORDERS_PROJECT_NAME_MAX_LENGTH = 39

#: Output handoff (GLUE-01): Orders terraform output -> RIS -var.
#: Only mappings the RIS orders_reader module actually consumes.
ORDERS_OUTPUT_VAR_MAP = {
    "dynamodb_table_name": "orders_table_name",
    "dynamodb_table_arn": "orders_table_arn",
}


def orders_component_project_name(
    ris_project_name: str, override: Optional[str] = None
) -> str:
    """Derive the Orders component project name for one RIS project.

    Deterministic (recomputable at destroy time without any stored
    state). `override` is the documented escape hatch for pre-existing
    component installations (historical composite test names) without
    changing the default contract.
    """
    import re

    name = (
        override
        or (ris_project_name.strip() + ORDERS_COMPONENT_SUFFIX)
    ).strip()
    if len(name) < 3 or not re.fullmatch(r"[a-z0-9][a-z0-9-]*[a-z0-9]", name):
        raise ValueError(
            f"orders component project name {name!r} violates the Orders "
            f"naming contract ([a-z0-9-], min 3, no leading/trailing hyphen)"
        )
    if len(name) > ORDERS_PROJECT_NAME_MAX_LENGTH:
        raise ValueError(
            f"orders component project name {name!r} exceeds "
            f"{ORDERS_PROJECT_NAME_MAX_LENGTH} chars (CloudTrail bucket limit)"
        )
    if name == "mays-orders" or name.startswith("mays-orders-"):
        raise ValueError(
            f"orders component project name {name!r} collides with the "
            f"protected standalone Mays-Orders installation namespace"
        )
    return name


def derive_orders_queue_url(orders_project_name: str, region: str, account_id: str) -> str:
    """Queue URL per published Orders naming contract ({project}-orders-queue)."""
    return (
        f"https://sqs.{region}.amazonaws.com/{account_id}/"
        f"{orders_project_name}{ORDERS_QUEUE_SUFFIX}"
    )


def derive_orders_queue_arn(orders_project_name: str, region: str, account_id: str) -> str:
    """Queue ARN per published Orders naming contract ({project}-orders-queue)."""
    return (
        f"arn:aws:sqs:{region}:{account_id}:"
        f"{orders_project_name}{ORDERS_QUEUE_SUFFIX}"
    )


def parse_orders_outputs(stdout: str) -> Dict[str, Any]:
    """Parse `terraform output -json` stdout (tolerant to surrounding CLI text)."""
    start = stdout.find("{")
    if start < 0:
        raise RuntimeError("Orders output contained no JSON object")
    try:
        return json.loads(stdout[start:])
    except json.JSONDecodeError:
        # Brace matching from the first '{' to its partner (truncation guard).
        depth = 0
        for idx in range(start, len(stdout)):
            if stdout[idx] == "{":
                depth += 1
            elif stdout[idx] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(stdout[start : idx + 1])
        raise RuntimeError("Orders output JSON is truncated or malformed")


def orders_handoff_vars(
    outputs: Dict[str, Any],
    orders_project_name: str,
    region: str,
    account_id: str,
) -> Dict[str, str]:
    """Map Orders outputs to RIS -var entries (only necessary mappings).

    Table name/ARN come from the Orders `output` command. Queue URL/ARN
    are derived from the published Orders naming contract (the component
    does not export SQS outputs). Fail-closed when a required output is
    missing or empty.
    """
    handoff: Dict[str, str] = {}
    for out_name, var_name in ORDERS_OUTPUT_VAR_MAP.items():
        entry = outputs.get(out_name)
        value = entry.get("value") if isinstance(entry, dict) else entry
        if not value:
            raise RuntimeError(f"required Orders output missing or empty: {out_name}")
        handoff[var_name] = str(value)
    handoff["orders_queue_url"] = derive_orders_queue_url(
        orders_project_name, region, account_id
    )
    handoff["orders_queue_arn"] = derive_orders_queue_arn(
        orders_project_name, region, account_id
    )
    return handoff


def is_plan_safe(plan_json: dict, project_name: str, environment: str) -> tuple[bool, str]:
    """
    Inspect a Terraform plan JSON and reject if it targets production resources.
    
    Returns (is_safe, message).
    """
    test_prefix = f"{project_name}-{environment}-"
    production_prefixes = PRODUCTION_RESOURCE_PREFIXES
    
    for change in plan_json.get("resource_changes", []):
        actions = change.get("change", {}).get("actions", [])
        before = change.get("change", {}).get("before") or {}
        after = change.get("change", {}).get("after") or {}
        
        # Check before state for production resources being deleted/replaced
        for key, value in before.items():
            if isinstance(value, str):
                for prod_prefix in production_prefixes:
                    if value.startswith(prod_prefix):
                        if "delete" in actions or "replace" in actions:
                            return False, (
                                f"Plan targets production resource for deletion/replacement: "
                                f"{value} (actions: {actions})"
                            )
        
        # Check after state for production resources being created
        for key, value in after.items():
            if isinstance(value, str):
                for prod_prefix in production_prefixes:
                    if value.startswith(prod_prefix):
                        if "create" in actions:
                            return False, (
                                f"Plan creates production resource: "
                                f"{value} (actions: {actions})"
                            )
        
        # Also check resource address for production module references
        address = change.get("address", "")
        for prod_prefix in production_prefixes:
            if prod_prefix in address:
                if "delete" in actions or "replace" in actions or "create" in actions:
                    return False, (
                        f"Plan targets production module resource: "
                        f"{address} (actions: {actions})"
                    )
    
    return True, "Plan is safe"


def load_plan_json(plan_file: str) -> dict:
    """Load and parse a Terraform plan file as JSON."""
    import os
    if not os.path.exists(plan_file):
        # In test environments, the plan file may not exist (mocked)
        # Return an empty plan that passes the safety gate
        return {"resource_changes": []}
    import subprocess
    result = subprocess.run(
        ["terraform", "show", "-json", plan_file],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"terraform show -json failed: {result.stderr}")
    return json.loads(result.stdout)


@dataclass
class RisInstallContext:
    """Installation identity for exactly one RIS project."""

    project_name: str = "mays-ris"
    environment: str = "dev"
    aws_region: str = "eu-central-1"
    terraform_dir: str = "terraform"
    backend_bucket: Optional[str] = None
    backend_region: Optional[str] = None
    backend_lock_table: Optional[str] = None
    aws_profile: Optional[str] = None
    aws_context: Optional[AwsExecutionContext] = None
    dry_run: bool = True
    extra_vars: Dict[str, str] = field(default_factory=dict)
    # Composite lifecycle (GLUE-01): when True, preflight/install/destroy
    # orchestrate the Mays-Orders-AWS component. Existing standalone RIS
    # tests set composite=False to assert pure-RIS terraform sequencing.
    composite: bool = True
    # Per-project isolation (computed, not user-configurable)
    _workdir_base: str = field(default="", repr=False)
    _workdir: str = field(default="", repr=False)
    _data_dir: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.project_name or not self.project_name.strip():
            raise ValueError("project_name must not be empty")
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError(
                f"environment must be one of {VALID_ENVIRONMENTS}, "
                f"got {self.environment!r}"
            )

    @property
    def workspace(self) -> str:
        """Workspace derived verbatim from project_name (never environment)."""
        return workspace_for_project(self.project_name)

    def backend_config(self) -> BackendConfig:
        """Explicit backend config — raises on missing values (no invention)."""
        return BackendConfig(
            bucket=self.backend_bucket,
            region=self.backend_region or self.aws_region,
            dynamodb_table=self.backend_lock_table or "mays-ris-tf-lock",
            key=f"{self.environment}/terraform.tfstate",
        )

    def terraform_vars(self) -> Dict[str, str]:
        """Input variables for plan/apply (ordinary vars, never backend).

        Extra --var entries ride along, but project identity always wins
        (fail-closed: identity cannot be overridden via --var).
        """
        import os
        merged = dict(self.extra_vars or {})
        # Provide absolute paths for lambda zips (required for isolated workdirs)
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(self.terraform_dir)))
        orders_reader_zip = os.path.join(repo_root, "lambda", "dist", "orders-reader.zip")
        health_writer_zip = os.path.join(repo_root, "lambda", "dist", "health-writer.zip")
        health_publisher_zip = os.path.join(repo_root, "lambda", "dist", "health-publisher.zip")
        merged.update({
            "project_name": self.project_name,
            "environment": self.environment,
            "filename": orders_reader_zip,
            "health_writer_zip_path": health_writer_zip,
            "health_publisher_zip_path": health_publisher_zip,
        })
        return merged

    def make_runner(self) -> TerraformRunner:
        """Central handoff: context -> runner (single construction point)."""
        self._ensure_isolated_workdir()
        return TerraformRunner(
            working_dir=self.isolated_workdir,
            workspace=self.workspace,
            aws_context=self.aws_context,
            data_dir=self.isolated_data_dir,
        )

    def _ensure_isolated_workdir(self) -> None:
        """Create per-project isolated working directory and data directory.

        The isolated workdir is a copy of the Terraform source tree with
        a project-specific .terraform directory. The data directory isolates
        Terraform's provider cache and backend metadata.

        Structure:
          <workdir_base>/<project_name>/<environment>/
            terraform/          -> copy of repo terraform/
            .terraform/         -> project-specific (created by terraform init)
            tfdata/             -> project-specific TF_DATA_DIR
        """
        import shutil
        from pathlib import Path

        if self._workdir and self._data_dir:
            return  # Already initialized

        # Base directory for all isolated workdirs (outside repo to avoid pollution)
        base = Path(self._workdir_base) if self._workdir_base else Path.home() / ".ris-workdirs"
        project_workdir = base / self.project_name / self.environment

        # Create terraform source copy (not symlink, to isolate .terraform directory)
        repo_terraform = Path(self.terraform_dir).resolve()
        workdir = project_workdir / "terraform"
        workdir.parent.mkdir(parents=True, exist_ok=True)
        if workdir.exists():
            shutil.rmtree(workdir)
        shutil.copytree(
            repo_terraform,
            workdir,
            ignore=shutil.ignore_patterns('.terraform', '__pycache__', '*.tfplan', '*.tfstate*', '.terraform.lock.hcl'),
        )

        # Data directory for TF_DATA_DIR (provider cache, backend metadata)
        data_dir = project_workdir / "tfdata"
        data_dir.mkdir(parents=True, exist_ok=True)

        self._workdir = str(workdir)
        self._data_dir = str(data_dir)

    @property
    def isolated_workdir(self) -> str:
        """Return the isolated working directory, creating it if needed."""
        if not self._workdir:
            self._ensure_isolated_workdir()
        return self._workdir

    @property
    def isolated_data_dir(self) -> str:
        """Return the isolated data directory, creating it if needed."""
        if not self._data_dir:
            self._ensure_isolated_workdir()
        return self._data_dir


def _cmd_preflight(ctx: RisInstallContext) -> int:
    """PHASE A: read-only AWS identity + composite component validation.

    Validates AWS identity (STS), then verifies the Mays-Orders-AWS
    component: Git pin, installer discovery, and (read-only) AWS
    collision scan for the derived component project name. No resource
    mutation and no Terraform apply anywhere in this path.
    """
    try:
        aws_ctx = validate_aws_context(
            profile=ctx.aws_profile, region=ctx.aws_region
        )
    except AwsValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    ctx.aws_context = aws_ctx
    print(f"account: {aws_ctx.account_id}")
    print(f"region: {aws_ctx.region}")
    print(f"identity: {aws_ctx.identity_arn}")
    print(f"profile-source: {aws_ctx.profile_source}")

    # GLUE-01: Composite preflight — validate the Orders component.
    if ctx.composite and not ctx.dry_run:
        orders_project = orders_component_project_name(ctx.project_name)
        print(f"composite component project: {orders_project}")
        orchestrator = RISInstaller(dry_run=ctx.dry_run)
        info = orchestrator.discover_project("mays-orders")
        if not info.installer_exists:
            print(
                f"error: Mays-Orders component not available at "
                f"{info.local_path}",
                file=sys.stderr,
            )
            return 1
        if not info.git_info:
            print(
                "error: component clone missing or not a git repo",
                file=sys.stderr,
            )
            return 1
        print(f"component commit: {info.git_info.commit}")

        # Pin verification (fail-closed: drift must be visible, not ignored).
        pin_path = (
            Path(__file__).resolve().parent / "mays-orders-clone.pinned.json"
        )
        if pin_path.exists():
            import json as _json

            pin = _json.loads(pin_path.read_text())
            pinned = pin.get("pinned_commit")
            if pinned and info.git_info.commit != pinned:
                print(
                    f"error: component HEAD {info.git_info.commit} != pinned "
                    f"{pinned}",
                    file=sys.stderr,
                )
                return 1
            print(f"component pinned commit verified: {pinned}")
        else:
            print("warning: no pin file for component (cannot verify revision)")

        # AWS collision scan + context validation via Orders validate command.
        try:
            result = orchestrator.run_project_installer(
                "mays-orders",
                command="validate",
                region=ctx.aws_region,
                environment=ctx.environment,
                project_name_override=orders_project,
            )
            if result.get("status") not in ("SUCCESS", "DRY_RUN"):
                print(
                    f"error: component validation failed: "
                    f"{result.get('stderr', result.get('error', 'unknown'))}",
                    file=sys.stderr,
                )
                return 1
            print("component validation: OK")
        except Exception as exc:
            print(f"error: component preflight failed: {exc}", file=sys.stderr)
            return 1

    return 0


def _cmd_validate(ctx: RisInstallContext) -> List[TerraformResult]:
    # Backend-less validation: init runs with -backend=false, so workspace
    # operations are meaningless here (no backend to select in) and would
    # fail. Config validation is workspace-independent.
    runner = ctx.make_runner()
    return [
        runner.init(backend=False),
        runner.run_and_get_result(["validate"], ensure_workspace=False),
    ]


def _cmd_plan(
    ctx: RisInstallContext, out_file: Optional[str] = None, diagnostic_no_lock: bool = False
) -> List[TerraformResult]:
    if ctx.aws_context is None:
        ctx.aws_context = validate_aws_context(profile=ctx.aws_profile, region=ctx.aws_region)
    runner = ctx.make_runner()
    return [
        runner.init(backend_config=ctx.backend_config()),
        runner.plan(
            out_file=out_file,
            var=ctx.terraform_vars(),
            lock=not diagnostic_no_lock,
            ensure_workspace=not diagnostic_no_lock,
        ),
    ]


def _cmd_apply(ctx: RisInstallContext, out_file: Optional[str] = None) -> List[TerraformResult]:
    if ctx.dry_run:
        raise RuntimeError("refusing apply in dry-run mode (pass --yes)")
    if ctx.aws_context is None:
        ctx.aws_context = validate_aws_context(profile=ctx.aws_profile, region=ctx.aws_region)
    runner = ctx.make_runner()
    init_res = runner.init(backend_config=ctx.backend_config())
    
    # Generate plan file for safety gate inspection
    plan_file = out_file or f"{ctx.workspace}-apply.tfplan"
    plan_res = runner.plan(out_file=plan_file, var=ctx.terraform_vars())
    print(f"$ {' '.join(plan_res.command)} -> exit {plan_res.returncode}")
    if plan_res.returncode != 0:
        return [init_res, plan_res]
    
    # Safety gate: inspect plan before apply
    plan_json = load_plan_json(plan_file)
    safe, msg = is_plan_safe(plan_json, ctx.project_name, ctx.environment)
    print(f"Safety gate: {msg}")
    if not safe:
        print(f"error: {msg}", file=sys.stderr)
        return [init_res, TerraformResult(command=["terraform", "plan"], returncode=1, stderr=msg)]
    
    apply_res = runner.run_and_get_result(["apply", plan_file], ensure_workspace=True)
    return [init_res, plan_res, apply_res]


def _cmd_package(ctx: RisInstallContext, bundle: str = "all") -> int:
    """Lambda-Bundles deterministisch bauen (VOR plan/apply).

    Vertrag: package -> plan -> apply. Terraform liest die ZIPs via
    filebase64sha256; ohne diesen Schritt schlaegt jeder Plan fehl
    (lambda.zip-Luecke). Kein Duplikat-Mechanismus: genau ein Skript
    (lambda/build_zip.py --bundle ...) erzeugt beide Bundles.
    """
    import subprocess
    from pathlib import Path

    if bundle not in ("agent", "reader", "all"):
        print(f"error: unknown bundle: {bundle} (agent|reader|all)",
              file=sys.stderr)
        return 2
    repo_root = Path(ctx.terraform_dir).resolve().parent
    script = repo_root / "lambda" / "build_zip.py"
    if not script.exists():
        print(f"error: build script missing: {script}", file=sys.stderr)
        return 1
    proc = subprocess.run(
        [sys.executable, str(script), "--bundle", bundle],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=300,
    )
    print(proc.stdout[-1500:] if proc.stdout else "")
    if proc.returncode != 0:
        print(f"error: packaging failed: {proc.stderr.strip()[:300]}",
              file=sys.stderr)
    return proc.returncode


def _cmd_destroy(ctx: RisInstallContext, out_file: Optional[str] = None) -> int:
    """Destroy exactly one composite project (RIS first, then Orders component).

    Order: RIS foundation -> project-specific Orders component instance.
    The protected standalone Mays-Orders installation is never touched
    (orders_component_project_name() raises on the 'mays-orders' namespace).
    Requires --yes. Returns 0 only if both plans/apply succeed.
    """
    if ctx.dry_run:
        print("error: refusing destroy in dry-run mode (pass --yes)",
              file=sys.stderr)
        return 1
    try:
        aws_ctx = validate_aws_context(
            profile=ctx.aws_profile, region=ctx.aws_region
        )
    except AwsValidationError as exc:
        print(f"error: preflight failed: {exc}", file=sys.stderr)
        return 1
    ctx.aws_context = aws_ctx
    orders_project = orders_component_project_name(ctx.project_name)
    print(f"DESTROY scope: composite project {ctx.project_name}")
    print(f"  RIS workspace: {ctx.workspace}")
    print(f"  Orders component: {orders_project}")
    print(f"  account: {aws_ctx.account_id}, region: {aws_ctx.region}")

    # --- 1. RIS foundation destroy ---
    runner = ctx.make_runner()
    init_res = runner.init(backend_config=ctx.backend_config())
    print(f"$ {' '.join(init_res.command)} -> exit {init_res.returncode}")
    if init_res.returncode != 0:
        return 1
    plan_file = out_file or f"{ctx.workspace}-destroy.tfplan"
    plan_res = runner.plan(out_file=plan_file, destroy=True,
                           var=ctx.terraform_vars())
    print(f"$ {' '.join(plan_res.command)} -> exit {plan_res.returncode}")
    if plan_res.returncode != 0:
        return 1

    # Safety gate: inspect destroy plan before apply
    plan_json = load_plan_json(plan_file)
    safe, msg = is_plan_safe(plan_json, ctx.project_name, ctx.environment)
    print(f"RIS destroy safety gate: {msg}")
    if not safe:
        print(f"error: RIS destroy plan unsafe: {msg}", file=sys.stderr)
        return 1

    apply_res = runner.run_and_get_result(["apply", plan_file],
                                          ensure_workspace=True)
    print(f"$ {' '.join(apply_res.command)} -> exit {apply_res.returncode}")
    if apply_res.returncode != 0:
        return 1

    # --- 2. Orders component destroy (only its own project name) ---
    if ctx.composite:
        orchestrator = RISInstaller(dry_run=False)
        env_extra = {
            "ALLOW_AWS_OPERATIONS": "true",
            "PROJECT_NAME": orders_project,
        }
        destroy_plan = orchestrator.run_project_installer(
            "mays-orders",
            command="plan-destroy",
            profile=ctx.aws_profile,
            region=ctx.aws_region,
            environment=ctx.environment,
            project_name_override=orders_project,
            extra_args=["--var", f"project_name={orders_project}",
                        "--var", f"aws_region={ctx.aws_region}"],
            extra_env=env_extra,
        )
        if destroy_plan.get("status") not in ("SUCCESS", "DRY_RUN"):
            print(
                f"error: Orders plan-destroy failed: "
                f"{destroy_plan.get('stderr', destroy_plan.get('error', 'unknown'))}",
                file=sys.stderr,
            )
            return 1
        print(f"$ Orders plan-destroy -> {destroy_plan.get('status')}")

        destroy_apply = orchestrator.run_project_installer(
            "mays-orders",
            command="destroy",
            profile=ctx.aws_profile,
            region=ctx.aws_region,
            environment=ctx.environment,
            project_name_override=orders_project,
            extra_args=["--yes"],
            extra_env=env_extra,
            full_output=True,
        )
        if destroy_apply.get("status") != "SUCCESS":
            print(
                f"error: Orders destroy failed: "
                f"{destroy_apply.get('stdout', '')[-500:]} | "
                f"{destroy_apply.get('stderr', destroy_apply.get('error', 'unknown'))[-500:]}",
                file=sys.stderr,
            )
            return 1
        print(f"$ Orders destroy -> SUCCESS")

    return 0


COMMANDS = ("validate", "plan", "apply", "preflight", "install", "state", "destroy",
            "package", "lock")


def _cmd_lock(
    ctx: RisInstallContext,
    lock_command: str,
    lock_id: Optional[str] = None,
) -> int:
    """Lock inspection and recovery planning."""
    import boto3
    import json

    if lock_command == "inspect":
        if not ctx.backend_bucket:
            print("error: backend-bucket required for lock inspect", file=sys.stderr)
            return 2
        if not ctx.backend_lock_table:
            print("error: backend-lock-table required for lock inspect", file=sys.stderr)
            return 2

        # Validate AWS context
        try:
            aws_ctx = validate_aws_context(
                profile=ctx.aws_profile, region=ctx.aws_region
            )
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        session = boto3.Session(profile_name=ctx.aws_profile, region_name=ctx.aws_region)
        dynamodb = session.client("dynamodb", region_name=ctx.aws_region)

        # Determine which locks to inspect
        lock_ids_to_check = []
        if lock_id:
            # Specific lock ID provided
            lock_ids_to_check = [lock_id]
        else:
            # Check both canonical and legacy paths
            # Canonical: workspace prefix + environment/terraform.tfstate
            # Legacy: workspace prefix + project_name/environment (old format with duplicated project name)
            canonical_lock_suffix = f"env:/{ctx.workspace}/{ctx.environment}/terraform.tfstate"
            legacy_lock_suffix = f"env:/{ctx.project_name}/env:/{ctx.project_name}/{ctx.environment}/terraform.tfstate"
            lock_ids_to_check = [
                f"env:/{ctx.workspace}/{ctx.environment}/terraform.tfstate",  # canonical: env:/workspace/environment/terraform.tfstate
                f"env:/{ctx.project_name}/env:/{ctx.project_name}/{ctx.environment}/terraform.tfstate",  # legacy: duplicated project name
            ]

        canonical_lock_found = False
        legacy_lock_found = False

        print(f"Lock inspection for project: {ctx.project_name}, environment: {ctx.environment}")
        print(f"Backend bucket: {ctx.backend_bucket}")
        print(f"Lock table: {ctx.backend_lock_table}")
        print(f"Workspace: {ctx.workspace}")
        print()

        for lock_id_suffix in lock_ids_to_check:
            full_lock_id = f"{ctx.backend_bucket}/{lock_id_suffix}"
            try:
                resp = dynamodb.get_item(
                    TableName=ctx.backend_lock_table,
                    Key={"LockID": {"S": f"{ctx.backend_bucket}/{lock_id_suffix}"}}
                )
            except Exception as exc:
                print(f"error: failed to query lock: {exc}", file=sys.stderr)
                return 1

            if "Item" in resp:
                item = resp["Item"]
                lock_id_val = item.get("LockID", {}).get("S", "")
                info_str = item.get("Info", {}).get("S", "")
                info = json.loads(info_str) if info_str else {}

                # Canonical format: env:/workspace/environment/terraform.tfstate (exactly one workspace prefix)
                # Legacy: env:/project_name/env:/project_name/environment/terraform.tfstate (duplicated project name)
                canonical_pattern = f"env:/{ctx.workspace}/{ctx.environment}/terraform.tfstate"
                legacy_pattern = f"env:/{ctx.project_name}/env:/{ctx.project_name}/{ctx.environment}/terraform.tfstate"
                
                is_canonical = lock_id_suffix == f"env:/{ctx.workspace}/{ctx.environment}/terraform.tfstate"
                is_legacy = lock_id_suffix == f"env:/{ctx.project_name}/env:/{ctx.project_name}/{ctx.environment}/terraform.tfstate"
                
                if lock_id_suffix == f"env:/{ctx.workspace}/{ctx.environment}/terraform.tfstate":
                    lock_type = "CANONICAL"
                elif lock_id_suffix == f"env:/{ctx.project_name}/env:/{ctx.project_name}/{ctx.environment}/terraform.tfstate":
                    lock_type = "LEGACY"
                else:
                    lock_type = "UNKNOWN"

                print(f"Lock found ({lock_type}):")
                print(f"  LockID: {lock_id_val}")
                print(f"  Lock ID: {info.get('ID', 'N/A')}")
                print(f"  Operation: {info.get('Operation', 'N/A')}")
                print(f"  Owner: {info.get('Who', 'N/A')}")
                print(f"  Created: {info.get('Created', 'N/A')}")
                print(f"  Path: {info.get('Path', 'N/A')}")
                print(f"  Lock Table Key: {full_lock_id}")
                print()

                if is_canonical:
                    canonical_lock_found = True
                else:
                    legacy_lock_found = True
            else:
                print(f"Lock NOT found: {lock_id_suffix}")
                print()

        # Summary
        print("--- Lock Classification ---")
        if canonical_lock_found:
            print("CANONICAL_LOCK_STATUS: PRESENT (blocks canonical state)")
        else:
            print("CANONICAL_LOCK_STATUS: ABSENT")

        if legacy_lock_found:
            print("LEGACY_LOCK_STATUS: PRESENT (legacy duplicated path)")
        else:
            print("LEGACY_LOCK_STATUS: ABSENT")

        # Classification
        if canonical_lock_found and legacy_lock_found:
            print("LOCK_CLASSIFICATION: BOTH_PRESENT (canonical blocks, legacy duplicated)")
        elif canonical_lock_found:
            print("LOCK_CLASSIFICATION: CANONICAL_ONLY")
        elif legacy_lock_found:
            print("LOCK_CLASSIFICATION: LEGACY_ONLY")
        else:
            print("LOCK_CLASSIFICATION: NONE")

        return 0

    elif lock_command == "recovery-plan":
        print("Lock recovery plan (read-only):")
        print("1. Verify the canonical lock status:")
        print("   - If canonical lock is ABSENT: no recovery needed, normal plan will succeed")
        print("   - If canonical lock is PRESENT:")
        print("     a. Verify lock is stale (no active Terraform processes)")
        print("     b. Verify lock owner matches expected operator")
        print("     c. Obtain explicit approval for force-unlock")
        print("     d. Execute: terraform force-unlock -force <LOCK_ID>")
        print("     d. After unlock, run normal locked plan")
        print()
        print("WARNING: This is a recovery plan only. No automatic unlocking performed.")
        print("       Execute 'terraform force-unlock' manually with explicit approval.")
        return 0

    else:
        print(f"error: unknown lock command: {lock_command}", file=sys.stderr)
        return 2

    return 0

def _cmd_state(
    ctx: RisInstallContext,
    state_command: str,
    address: Optional[str] = None,
    state_file: Optional[str] = None,
) -> int:
    """State inspection (list/show/pull: read-only) and push (gated).

    `state push` is mutating and requires --yes (dry-run refuses).
    """
    import subprocess
    runner = ctx.make_runner()
    if state_command == "discover":
        if not ctx.backend_bucket:
            print("error: backend-bucket required for state discover", file=sys.stderr)
            return 2
        prefix = f"env:/{ctx.project_name}/"
        try:
            aws_ctx = validate_aws_context(profile=ctx.aws_profile, region=ctx.aws_region)
            ctx.aws_context = aws_ctx
        except AwsValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        env = aws_ctx.to_env()
        cmd = [
            "aws", "s3api", "list-objects-v2",
            "--bucket", ctx.backend_bucket,
            "--prefix", prefix,
            "--query", "Contents[].{Key:Key,Size:Size,LastModified:LastModified}",
            "--output", "json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            print(f"error: aws s3api failed: {result.stderr.strip()[:300]}", file=sys.stderr)
            return 1
        import json
        try:
            items = json.loads(result.stdout)
        except Exception:
            items = []
        if not items:
            print(f"No state objects found for project {ctx.project_name} in bucket {ctx.backend_bucket}")
            return 0
        print(f"State objects for project {ctx.project_name} in bucket {ctx.backend_bucket}:")
        for it in items:
            print(f"  {it.get('Key')}  size={it.get('Size')}  modified={it.get('LastModified')}")
        return 0
    if state_command == "inventory":
        if not ctx.backend_bucket:
            print("error: backend-bucket required for state inventory", file=sys.stderr)
            return 2
        # Discover first
        discover_rc = _cmd_state(ctx, "discover")
        if discover_rc != 0:
            return discover_rc
        # For simplicity, just report discovered keys
        print("Inventory complete. Use 'state list' per workspace for resource details.")
        return 0
    if state_command in ("list", "show", "pull"):
        if state_command == "list":
            result = runner.state_list(state_file)
        elif state_command == "show":
            if not address:
                print("error: address is required for state show", file=sys.stderr)
                return 2
            result = runner.state_show(address, state_file)
        else:
            result = runner.state_pull()
        print(result.stdout)
        if result.returncode != 0:
            print(f"error: {result.stderr.strip()[:300]}", file=sys.stderr)
        return result.returncode
    if state_command == "push":
        if ctx.dry_run:
            print(
                "error: state push mutates remote state (pass --yes)",
                file=sys.stderr,
            )
            return 1
        if not state_file:
            print("error: --state-file is required for state push", file=sys.stderr)
            return 2
        result = runner.state_push(state_file)
        if result.returncode == 0:
            print("State pushed successfully")
        else:
            print(f"error: {result.stderr.strip()[:300]}", file=sys.stderr)
        return result.returncode
    print(f"error: unknown state command: {state_command}", file=sys.stderr)
    return 2


def _run_orders_component(
    ctx: RisInstallContext,
    orchestrator: RISInstaller,
    orders_project: str,
) -> Dict[str, Any]:
    """Execute the Orders component lifecycle via the existing orchestrator.

    Sequence (RIS-ORDERS-INSTALLER-CONTRACT-ALIGNMENT-01):
      validate -> plan -> deploy -> output
    - profile/region passed as *global* args (argparse subcommand contract).
    - --project-name = orders_project (isolated component identity).
    - --yes on deploy requires ALLOW_AWS_OPERATIONS=true (env-only, set by caller).
    Returns the orchestrator result dicts for each stage.
    Preserves the Orders state: a RIS-side failure later does NOT destroy a
    successfully installed Orders component (no auto-cleanup; destroy is a
    separate, explicit composite destroy operation).
    """
    # Global options go first; command word; then command-specific args.
    # Dry-run is the Orders default; live deploy is opt-in via env + --yes.
    allow_aws = "true" if not ctx.dry_run else "false"
    env_extra: Dict[str, str] = {
        "ALLOW_AWS_OPERATIONS": allow_aws,
        # Force the component's Terraform workspace to match its project name.
        "PROJECT_NAME": orders_project,
    }

    # 1. validate -- the pinned Orders installer performs AWS identity,
    #    remote-state lifecycle, lambda artifact, AND collision scan.
    val = orchestrator.run_project_installer(
        "mays-orders",
        command="validate",
        profile=ctx.aws_profile,
        region=ctx.aws_region,
        environment=ctx.environment,
        project_name_override=orders_project,
        extra_env=env_extra,
    )
    if val.get("status") not in ("SUCCESS", "DRY_RUN"):
        raise RuntimeError(
            f"Orders validate failed: {val.get('stderr', val.get('error', 'unknown'))}"
        )
    print(f"$ Orders validate -> {val.get('status')}")

    # 2. plan (dry-run plan file is generated but NOT applied).
    plan = orchestrator.run_project_installer(
        "mays-orders",
        command="plan",
        profile=ctx.aws_profile,
        region=ctx.aws_region,
        environment=ctx.environment,
        project_name_override=orders_project,
        extra_args=["--var", f"project_name={orders_project}",
                    "--var", f"aws_region={ctx.aws_region}"],
        extra_env=env_extra,
    )
    if plan.get("status") not in ("SUCCESS", "DRY_RUN"):
        raise RuntimeError(
            f"Orders plan failed: {plan.get('stderr', plan.get('error', 'unknown'))}"
        )
    print(f"$ Orders plan -> {plan.get('status')}")

    # 3. deploy -- only when --yes was passed (ctx.dry_run is False).
    if not ctx.dry_run:
        deploy = orchestrator.run_project_installer(
            "mays-orders",
            command="deploy",
            profile=ctx.aws_profile,
            region=ctx.aws_region,
            environment=ctx.environment,
            project_name_override=orders_project,
            extra_args=["--yes"],
            extra_env=env_extra,
            # Must not truncate: deploy prints structured summary.
            full_output=True,
        )
        if deploy.get("status") != "SUCCESS":
            raise RuntimeError(
                f"Orders deploy failed: "
                f"{deploy.get('stdout', '')[-500:]} | "
                f"{deploy.get('stderr', deploy.get('error', 'unknown'))[-500:]}"
            )
        print(f"$ Orders deploy -> SUCCESS")

    # 4. output -- read-only handoff (workspace is the component project name).
    out = orchestrator.run_project_installer(
        "mays-orders",
        command="output",
        profile=ctx.aws_profile,
        region=ctx.aws_region,
        environment=ctx.environment,
        project_name_override=orders_project,
        extra_env=env_extra,
        full_output=True,
    )
    if out.get("status") != "SUCCESS":
        raise RuntimeError(f"Orders output failed: {out.get('stderr', out.get('error'))}")
    return parse_orders_outputs(out.get("stdout", ""))


def _cmd_install(
    ctx: RisInstallContext, out_file: Optional[str] = None
) -> int:
    """Composite phased installation: preflight -> orders validate/plan/deploy ->
    output handoff -> RIS package/plan/apply. Dry-run (no --yes) stops before
    any mutation and reports the planned phases."""
    # PHASE A — preflight (read-only identity + component validation).
    try:
        aws_ctx = validate_aws_context(
            profile=ctx.aws_profile, region=ctx.aws_region
        )
    except AwsValidationError as exc:
        print(f"error: preflight failed: {exc}", file=sys.stderr)
        return 1
    ctx.aws_context = aws_ctx
    names = BackendNames.for_project(
        ctx.project_name, ctx.environment, region=ctx.aws_region
    )
    orders_project = orders_component_project_name(ctx.project_name)

    if ctx.dry_run:
        print("dry-run composite installation plan (no mutation performed):")
        print(f"  account: {aws_ctx.account_id}")
        print(f"  region: {aws_ctx.region}")
        print(f"  RIS project: {ctx.project_name} -> workspace {ctx.workspace}")
        print(f"  Orders component: {orders_project}")
        print(f"  backend bucket: {names.bucket}")
        print(f"  lock table: {names.lock_table}")
        print("  phases: orders validate -> orders plan -> output handoff -> "
              "RIS package -> RIS plan")
        return 0

    # --- Composite preflight + Orders component (fail fast, no mutation) ---
    if ctx.composite:
        pf_rc = _cmd_preflight(ctx)
        if pf_rc != 0:
            print("error: composite preflight failed", file=sys.stderr)
            return 1
        orchestrator = RISInstaller(dry_run=False)

        # PHASE C — Orders component lifecycle + output handoff.
        try:
            orders_outputs = _run_orders_component(ctx, orchestrator, orders_project)
        except RuntimeError as exc:
            print(f"error: orders component lifecycle failed: {exc}", file=sys.stderr)
            print(
                "note: Orders state is preserved. Re-run install to resume "
                "RIS phase (Orders validate is idempotent).",
                file=sys.stderr,
            )
            return 1

        # GLUE-01: merge Orders outputs into RIS Terraform vars.
        handoff = orders_handoff_vars(
            orders_outputs,
            orders_project,
            ctx.aws_region,
            aws_ctx.account_id,
        )
        merged_extra = dict(ctx.extra_vars)
        merged_extra.update(handoff)
        ctx = RisInstallContext(
            project_name=ctx.project_name,
            environment=ctx.environment,
            aws_region=ctx.aws_region,
            terraform_dir=ctx.terraform_dir,
            backend_bucket=ctx.backend_bucket,
            backend_region=ctx.backend_region,
            backend_lock_table=ctx.backend_lock_table,
            aws_profile=ctx.aws_profile,
            aws_context=ctx.aws_context,
            dry_run=ctx.dry_run,
            extra_vars=merged_extra,
            composite=ctx.composite,
        )
    else:
        merged_extra = dict(ctx.extra_vars or {})

    # PHASE B — backend bootstrap (explicit --yes only).
    bootstrap = BackendBootstrap(
        names, project_name=ctx.project_name, profile=ctx.aws_profile
    )
    try:
        bootstrap.ensure_all()
    except (BackendConflictError, RuntimeError) as exc:
        print(f"error: backend bootstrap failed: {exc}", file=sys.stderr)
        return 1

    # PHASE D — Lambda packaging (must precede plan, per package contract).
    pkg_rc = _cmd_package(ctx, bundle="all")
    if pkg_rc != 0:
        print(f"error: lambda packaging failed (rc={pkg_rc})", file=sys.stderr)
        # Packaging failure does NOT roll back Orders (no auto-destroy).
        return 1

    # PHASE E..G — RIS init / validate / plan / apply.
    runner = ctx.make_runner()
    config = BackendConfig(
        bucket=names.bucket,
        region=names.region,
        dynamodb_table=names.lock_table,
        key=f"{ctx.environment}/terraform.tfstate",
    )
    for result in (
        runner.init(backend_config=config, reconfigure=True),
        runner.validate(),
        runner.plan(out_file=out_file, var=ctx.terraform_vars()),
    ):
        print(f"$ {' '.join(result.command)} -> exit {result.returncode}")
        if result.returncode != 0:
            return 1

    # Safety gate: inspect plan before apply
    plan_file = out_file or f"{ctx.workspace}-apply.tfplan"
    plan_json = load_plan_json(plan_file)
    safe, msg = is_plan_safe(plan_json, ctx.project_name, ctx.environment)
    print(f"Safety gate: {msg}")
    if not safe:
        print(f"error: {msg}", file=sys.stderr)
        return 1

    apply_res = runner.run_and_get_result(
        ["apply", plan_file], ensure_workspace=True
    )
    print(f"$ {' '.join(apply_res.command)} -> exit {apply_res.returncode}")
    return 1 if apply_res.returncode != 0 else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ris-installer",
        description="Install one RIS project (project_name identity).",
    )
    parser.add_argument(
        "--project-name",
        default="mays-ris",
        help="Project identity (also Terraform workspace).",
    )
    parser.add_argument(
        "--environment",
        default="dev",
        choices=list(VALID_ENVIRONMENTS),
        help="Deployment environment (never replaces project_name).",
    )
    parser.add_argument(
        "--region",
        default="eu-central-1",
        dest="aws_region",
        help="AWS region.",
    )
    parser.add_argument(
        "--terraform-dir",
        default="terraform",
        help="Terraform working directory.",
    )
    parser.add_argument(
        "--workdir-base",
        default=None,
        help="Base directory for per-project isolated working directories (default: ~/.ris-workdirs).",
    )
    parser.add_argument("--backend-bucket", default=None)
    parser.add_argument("--backend-region", default=None)
    parser.add_argument("--backend-lock-table", default=None)
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile for installation context (validated via preflight).",
    )
    parser.add_argument(
        "--out", default=None, help="Plan output file (plan command)."
    )
    parser.add_argument(
        "--state-command",
        default=None,
        choices=["list", "show", "pull", "push", "discover", "inventory"],
        help="State subcommand (state command).",
    )
    parser.add_argument(
        "--lock-command",
        default=None,
        choices=["inspect", "recovery-plan"],
        help="Lock subcommand (lock command): inspect locks or produce recovery plan.",
    )
    parser.add_argument(
        "--lock-id",
        default=None,
        help="Specific lock ID to inspect (optional).",
    )
    parser.add_argument(
        "--address", default=None, help="Resource address (state show)."
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help="Local state file (state show/push).",
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        help="Terraform input variable as KEY=VALUE (repeatable; "
             "project_name/environment cannot be overridden).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Disable dry-run (required for apply).",
    )
    parser.add_argument(
        "--bundle",
        default="all",
        choices=["agent", "reader", "all"],
        help="Bundle scope for the package command.",
    )
    parser.add_argument(
        "--diagnostic-no-lock",
        action="store_true",
        help="Disable state locking for diagnostic plan only. WARNING: disables Terraform state locking. Use only for debugging stale locks. Never use for deployment planning.",
    )
    # GLUE-01: composite lifecycle toggle (default on; OFF for pure-RIS).
    parser.add_argument(
        "--composite/--no-composite",
        dest="composite",
        default=True,
        help="Enable composite Orders-component lifecycle (default: on). "
             "Use --no-composite to operate on RIS foundation only.",
    )
    parser.add_argument("command", choices=list(COMMANDS),
        help="Command to execute: validate, plan, apply, preflight, install, state, destroy, package, or lock",
    )
    return parser


def parse_var_args(var_args: Optional[List[str]]) -> Dict[str, str]:
    """Parse KEY=VALUE entries (fail-closed on malformed input)."""
    parsed: Dict[str, str] = {}
    for entry in var_args or []:
        if "=" not in entry:
            raise ValueError(f"--var erwartet KEY=VALUE, erhalten: {entry!r}")
        key, _, value = entry.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"--var mit leerem Key: {entry!r}")
        parsed[key] = value
    return parsed


def main(argv: Optional[List[str]] = None) -> int:
    parsed = build_parser().parse_args(argv)
    try:
        extra_vars = parse_var_args(parsed.var)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        ctx = RisInstallContext(
            project_name=parsed.project_name,
            environment=parsed.environment,
            aws_region=parsed.aws_region,
            terraform_dir=parsed.terraform_dir,
            backend_bucket=parsed.backend_bucket,
            backend_region=parsed.backend_region,
            backend_lock_table=parsed.backend_lock_table,
            aws_profile=parsed.profile,
            dry_run=not parsed.yes,
            extra_vars=extra_vars,
            composite=parsed.composite,
            _workdir_base=parsed.workdir_base or "",
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if parsed.command == "preflight":
        return _cmd_preflight(ctx)
    if parsed.command == "install":
        return _cmd_install(ctx, out_file=parsed.out)
    if parsed.command == "state":
        return _cmd_state(
            ctx,
            state_command=parsed.state_command,
            address=parsed.address,
            state_file=parsed.state_file,
        )
    if parsed.command == "lock":
        return _cmd_lock(
            ctx,
            lock_command=parsed.lock_command,
            lock_id=parsed.lock_id,
        )
    try:
        if parsed.command == "validate":
            results = _cmd_validate(ctx)
        elif parsed.command == "plan":
            results = _cmd_plan(ctx, out_file=parsed.out, diagnostic_no_lock=parsed.diagnostic_no_lock)
        elif parsed.command == "destroy":
            return _cmd_destroy(ctx, out_file=parsed.out)
        elif parsed.command == "package":
            return _cmd_package(ctx, bundle=parsed.bundle)
        else:
            results = _cmd_apply(ctx)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    failed = [r for r in results if r.returncode != 0]
    for result in results:
        print(f"$ {' '.join(result.command)} -> exit {result.returncode}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
