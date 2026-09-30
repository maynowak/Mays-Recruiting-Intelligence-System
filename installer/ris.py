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
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

from installer.terraform_runner import (
    BackendConfig,
    TerraformResult,
    TerraformRunner,
    workspace_for_project,
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
    dry_run: bool = True

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
        )

    def terraform_vars(self) -> Dict[str, str]:
        """Input variables for plan/apply (ordinary vars, never backend)."""
        return {
            "project_name": self.project_name,
            "environment": self.environment,
        }

    def make_runner(self) -> TerraformRunner:
        """Central handoff: context -> runner (single construction point)."""
        return TerraformRunner(
            working_dir=self.terraform_dir,
            workspace=self.workspace,
        )


def _cmd_validate(ctx: RisInstallContext) -> List[TerraformResult]:
    runner = ctx.make_runner()
    return [runner.init(backend=False), runner.validate()]


def _cmd_plan(
    ctx: RisInstallContext, out_file: Optional[str] = None
) -> List[TerraformResult]:
    runner = ctx.make_runner()
    return [
        runner.init(backend_config=ctx.backend_config()),
        runner.plan(out_file=out_file, var=ctx.terraform_vars()),
    ]


def _cmd_apply(ctx: RisInstallContext) -> List[TerraformResult]:
    if ctx.dry_run:
        raise RuntimeError("refusing apply in dry-run mode (pass --yes)")
    runner = ctx.make_runner()
    init_res = runner.init(backend_config=ctx.backend_config())
    apply_res = runner.run_and_get_result(
        ["apply", "-auto-approve"], ensure_workspace=True
    )
    return [init_res, apply_res]


COMMANDS = ("validate", "plan", "apply")


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
        "--out", default=None, help="Plan output file (plan command)."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Disable dry-run (required for apply).",
    )
    parser.add_argument("command", choices=list(COMMANDS))
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parsed = build_parser().parse_args(argv)
    try:
        ctx = RisInstallContext(
            project_name=parsed.project_name,
            environment=parsed.environment,
            aws_region=parsed.aws_region,
            terraform_dir=parsed.terraform_dir,
            backend_bucket=parsed.backend_bucket,
            backend_region=parsed.backend_region,
            backend_lock_table=parsed.backend_lock_table,
            dry_run=not parsed.yes,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        if parsed.command == "validate":
            results = _cmd_validate(ctx)
        elif parsed.command == "plan":
            results = _cmd_plan(ctx, out_file=parsed.out)
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
