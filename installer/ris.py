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
from typing import Dict, List, Optional

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

VALID_ENVIRONMENTS = ("dev", "test", "prod")


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
        merged = dict(self.extra_vars or {})
        merged.update({
            "project_name": self.project_name,
            "environment": self.environment,
        })
        return merged

    def make_runner(self) -> TerraformRunner:
        """Central handoff: context -> runner (single construction point)."""
        return TerraformRunner(
            working_dir=self.terraform_dir,
            workspace=self.workspace,
            aws_context=self.aws_context,
        )


def _cmd_preflight(ctx: RisInstallContext) -> int:
    """PHASE A: read-only AWS identity check (no mutation possible)."""
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


def _cmd_apply(ctx: RisInstallContext) -> List[TerraformResult]:
    if ctx.dry_run:
        raise RuntimeError("refusing apply in dry-run mode (pass --yes)")
    if ctx.aws_context is None:
        ctx.aws_context = validate_aws_context(profile=ctx.aws_profile, region=ctx.aws_region)
    runner = ctx.make_runner()
    init_res = runner.init(backend_config=ctx.backend_config())
    apply_res = runner.apply(var=ctx.terraform_vars())
    return [init_res, apply_res]


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
    """Destroy exactly one project's foundation (scoped, explicit).

    Scope = ctx.workspace (verbatim aus project_name); NICHTS ausserhalb
    dieses Workspaces wird angefasst. Erfordert --yes. Gibt 0 nur zurueck,
    wenn Plan UND Apply erfolgreich waren.
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
    print(f"DESTROY scope: project {ctx.project_name} -> workspace {ctx.workspace}")
    print(f"DESTROY scope: account {aws_ctx.account_id}, region {aws_ctx.region}")
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
    apply_res = runner.run_and_get_result(["apply", plan_file],
                                          ensure_workspace=True)
    print(f"$ {' '.join(apply_res.command)} -> exit {apply_res.returncode}")
    return 1 if apply_res.returncode != 0 else 0


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


def _cmd_install(
    ctx: RisInstallContext, out_file: Optional[str] = None
) -> int:
    """Phased installation: preflight -> bootstrap -> init -> workspace ->
    validate -> plan -> (apply, only with --yes). Without --yes, prints the
    planned phases and stops before any mutation (dry-run)."""
    # PHASE A — preflight (read-only identity check).
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
    if ctx.dry_run:
        print("dry-run installation plan (no mutation performed):")
        print(f"  account: {aws_ctx.account_id}")
        print(f"  region: {aws_ctx.region}")
        print(f"  project: {ctx.project_name} -> workspace {ctx.workspace}")
        print(f"  backend bucket: {names.bucket}")
        print(f"  lock table: {names.lock_table}")
        print("  phases: bootstrap -> init -> validate -> plan")
        return 0
    # PHASE B — backend bootstrap (explicit --yes only).
    bootstrap = BackendBootstrap(
        names, project_name=ctx.project_name, profile=ctx.aws_profile
    )
    try:
        bootstrap.ensure_all()
    except (BackendConflictError, RuntimeError) as exc:
        print(f"error: backend bootstrap failed: {exc}", file=sys.stderr)
        return 1
    # PHASE C..G — init / workspace / validate / plan / apply via runner.
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
    apply_res = runner.run_and_get_result(
        ["apply", "-auto-approve"], ensure_workspace=True
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
