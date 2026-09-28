#!/usr/bin/env python3
"""
Terraform execution / workspace isolation layer (RIS).

Reference pattern: Mays-Orders-AWS TerraformRunner (tested parallel
workspace/state isolation). RIS keeps its own architecture; only the
proven execution semantics are mirrored:

    project_name
        -> TERRAFORM_WORKSPACE
        -> terraform workspace select <workspace>
        -> (missing) terraform workspace new <workspace>
        -> actual terraform command

Separation of concerns (hard rule):
- init() runs ONLY `terraform init` (flags allowed) — NEVER workspace ops.
- Workspace resolution happens in run_and_get_result() for non-default
  workspaces before every other command.
- project_name / environment / workspace stay separate dimensions:
  workspace is derived from project_name verbatim, NEVER from environment.
- No global os.environ mutation: TERRAFORM_WORKSPACE is set only in the
  child-process environment of spawned terraform commands.
- No AWS calls, no backend provisioning, no state migration here.
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_WORKSPACE = "default"

#: Substrings (lowercase) identifying a "workspace does not exist" failure
#: of `terraform workspace select`. Only then is `workspace new` attempted.
_MISSING_WORKSPACE_SIGNALS = (
    "doesn't exist",
    "does not exist",
    "not found",
    "no such workspace",
)


def workspace_for_project(project_name: str) -> str:
    """Derive the Terraform workspace name from a project name.

    Identity mapping, verbatim (no prefixes/suffixes, no environment
    mixing). Empty/blank input falls back to DEFAULT_WORKSPACE so behaviour
    stays deterministic.
    """
    if project_name and project_name.strip():
        return project_name.strip()
    return DEFAULT_WORKSPACE


@dataclass
class TerraformResult:
    """Outcome of a terraform invocation."""

    command: List[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class BackendConfig:
    """Explicit S3 backend configuration for `terraform init`.

    Only fields the RIS backend contract needs (mirrors the static values
    in terraform/main.tf). NO defaults: every value must be supplied
    explicitly by the caller — nothing is invented here. In particular NO
    input variables (var.*) and NO -var flags are used for backend values.
    Live values (bucket existence, region reachability) are NOT verified
    by this object; that is a separate gate.
    """

    bucket: Optional[str] = None
    key: str = "terraform.tfstate"
    region: Optional[str] = None
    encrypt: bool = True
    dynamodb_table: str = "mays-ris-tf-lock"

    #: Fields that MUST be set; missing ones raise (no silent invention).
    REQUIRED_FIELDS = ("bucket", "region")

    def missing_fields(self) -> List[str]:
        """Required fields without a value (explicitly unresolved)."""
        return [f for f in self.REQUIRED_FIELDS if not getattr(self, f)]

    def is_resolved(self) -> bool:
        """True when all required fields have explicit values."""
        return not self.missing_fields()

    def to_args(self) -> List[str]:
        """Deterministic `-backend-config=k=v` args (sorted by key)."""
        missing = self.missing_fields()
        if missing:
            raise ValueError(
                "BackendConfig unresolved, missing explicit values for: "
                + ", ".join(missing)
            )
        values = {
            "bucket": self.bucket,
            "key": self.key,
            "region": self.region,
            "encrypt": str(self.encrypt).lower(),
            "dynamodb_table": self.dynamodb_table,
        }
        return [f"-backend-config={k}={values[k]}" for k in sorted(values)]


class TerraformRunner:
    """Minimal Terraform execution layer with workspace isolation.

    Args:
        working_dir: Terraform working directory (repository terraform root).
        workspace: Terraform workspace name (usually workspace_for_project()).
        terraform_bin: Terraform binary name/path.
        env: Extra environment variables for child processes only.
    """

    def __init__(
        self,
        working_dir: str,
        workspace: str = DEFAULT_WORKSPACE,
        terraform_bin: str = "terraform",
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.working_dir = Path(working_dir)
        self.terraform_bin = terraform_bin
        self.extra_env: Dict[str, str] = dict(env or {})
        # Primary source: TERRAFORM_WORKSPACE env override (explicit).
        env_workspace = os.environ.get("TERRAFORM_WORKSPACE")
        if env_workspace and env_workspace.strip():
            self.workspace = env_workspace.strip()
        elif workspace and workspace.strip():
            self.workspace = workspace.strip()
        else:
            self.workspace = DEFAULT_WORKSPACE

    # ------------------------------------------------------------------
    # Environment (child processes only — never mutates os.environ)
    # ------------------------------------------------------------------
    def _terraform_env(self) -> Dict[str, str]:
        env = {**os.environ, **self.extra_env}
        env["TERRAFORM_WORKSPACE"] = self.workspace
        return env

    def _run_process(
        self, args: List[str], timeout: int = 300
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.terraform_bin] + args,
            cwd=str(self.working_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._terraform_env(),
        )

    # ------------------------------------------------------------------
    # Workspace resolution (NOT used by init())
    # ------------------------------------------------------------------
    def _ensure_workspace(self) -> bool:
        """Select the workspace, creating it if it does not exist.

        Returns True when the workspace is selected. Raises RuntimeError
        when selection fails for any other reason (never silently passed).
        No-op for the default workspace (deterministic: no `workspace new`).
        """
        if self.workspace == DEFAULT_WORKSPACE:
            return True
        selected = self._run_process(
            ["workspace", "select", self.workspace], timeout=30
        )
        if selected.returncode == 0:
            return True
        output = f"{selected.stdout}\n{selected.stderr}".lower()
        if not any(sig in output for sig in _MISSING_WORKSPACE_SIGNALS):
            raise RuntimeError(
                f"terraform workspace select failed for "
                f"'{self.workspace}': {selected.stderr.strip()}"
            )
        created = self._run_process(
            ["workspace", "new", self.workspace], timeout=30
        )
        if created.returncode != 0:
            raise RuntimeError(
                f"terraform workspace new failed for "
                f"'{self.workspace}': {created.stderr.strip()}"
            )
        return True

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def run_and_get_result(
        self, args: List[str], ensure_workspace: bool = True, timeout: int = 300
    ) -> TerraformResult:
        """Run a terraform command, resolving the workspace first."""
        if ensure_workspace:
            self._ensure_workspace()
        proc = self._run_process(args, timeout=timeout)
        return TerraformResult(
            command=[self.terraform_bin] + args,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def init(
        self,
        backend: bool = True,
        upgrade: bool = False,
        reconfigure: bool = False,
        backend_config: Optional[BackendConfig] = None,
    ) -> TerraformResult:
        """Run `terraform init` WITHOUT any workspace operation.

        Backend values travel ONLY via `-backend-config=...` (from an
        explicit BackendConfig) — never via input variables or `-var`.
        """
        args = ["init"]
        if not backend:
            args.append("-backend=false")
        elif backend_config is not None:
            args.extend(backend_config.to_args())
        if upgrade:
            args.append("-upgrade")
        if reconfigure:
            args.append("-reconfigure")
        return self.run_and_get_result(args, ensure_workspace=False)

    def validate(self) -> TerraformResult:
        """Run `terraform validate` (workspace resolved first)."""
        return self.run_and_get_result(["validate"])

    def plan(
        self,
        out_file: Optional[str] = None,
        destroy: bool = False,
        var: Optional[Dict[str, str]] = None,
    ) -> TerraformResult:
        """Run `terraform plan` (workspace resolved first)."""
        args = ["plan"]
        if destroy:
            args.append("-destroy")
        if out_file:
            args.extend(["-out", out_file])
        for key, value in (var or {}).items():
            args.extend(["-var", f"{key}={value}"])
        return self.run_and_get_result(args)
