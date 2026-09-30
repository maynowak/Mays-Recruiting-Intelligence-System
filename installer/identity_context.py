#!/usr/bin/env python3
"""
AWS execution context for the RIS installer (minimal).

Reference pattern: Mays-Orders-AWS AWSExecutionContext (profile, region,
validated account/identity, env handoff). RIS adaptation: no profile
machinery beyond an optional explicit profile name; no credential storage
anywhere (only the profile NAME plus resolved, non-secret identity data).

Safety rules (hard):
- Validation performs ONLY read-only STS GetCallerIdentity (no mutation).
- Account/identity values are never treated as project identity
  (project_name stays the sole installation identity).
- No secrets are read, stored, logged, or written (only identifiers).
"""

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

DEFAULT_REGION = "eu-central-1"


class AwsValidationError(RuntimeError):
    """Raised when AWS credentials/identity cannot be validated."""


@dataclass
class AwsExecutionContext:
    """Validated AWS execution context (identifiers only, no secrets)."""

    region: str
    account_id: str
    identity_arn: str
    profile: Optional[str] = None
    profile_source: str = "explicit"  # explicit, env, config, iam_role
    validated: bool = True
    validation_timestamp: str = ""

    def __post_init__(self) -> None:
        if self.profile is not None and not self.profile:
            raise ValueError("Profile cannot be empty string")
        if not self.region:
            raise ValueError("Region cannot be empty")
        if not self.account_id:
            raise ValueError("Account ID cannot be empty")
        if not self.identity_arn:
            raise ValueError("Identity ARN cannot be empty")
        if not self.validated:
            raise ValueError("Context must be validated")
        if not self.validation_timestamp:
            self.validation_timestamp = datetime.now(timezone.utc).isoformat()

    def to_env(self) -> Dict[str, str]:
        """Environment for child Terraform processes (no secrets)."""
        env = {"AWS_REGION": self.region}
        if self.profile:
            env["AWS_PROFILE"] = self.profile
        return env


def _run_sts(profile: Optional[str], timeout: int = 60) -> dict:
    """Read-only STS GetCallerIdentity (no mutation possible)."""
    cmd = ["aws", "sts", "get-caller-identity"]
    if profile:
        cmd += ["--profile", profile]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as exc:
        raise AwsValidationError("aws CLI not available") from exc
    except subprocess.TimeoutExpired as exc:
        raise AwsValidationError("STS validation timed out") from exc
    if proc.returncode != 0:
        raise AwsValidationError(
            f"STS validation failed: {proc.stderr.strip()[:200]}"
        )
    try:
        data = json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        raise AwsValidationError("STS returned unparsable output") from exc
    for key in ("UserId", "Account", "Arn"):
        if not data.get(key):
            raise AwsValidationError(f"STS output missing {key}")
    return data


def validate_aws_context(
    profile: Optional[str] = None,
    region: Optional[str] = None,
    timeout: int = 60,
) -> AwsExecutionContext:
    """Validate credentials via read-only STS; resolve region deterministically.

    Region precedence: explicit arg > AWS_REGION env > default.
    Profile source: explicit arg > AWS_PROFILE env > default chain.
    """
    resolved_region = (
        region or os.environ.get("AWS_REGION") or DEFAULT_REGION
    )
    effective_profile = profile
    profile_source = "explicit"
    if effective_profile is None and os.environ.get("AWS_PROFILE"):
        effective_profile = os.environ.get("AWS_PROFILE")
        profile_source = "env"
    if effective_profile is None:
        profile_source = "iam_role"
    identity = _run_sts(effective_profile, timeout=timeout)
    return AwsExecutionContext(
        profile=effective_profile,
        region=resolved_region,
        account_id=identity["Account"],
        identity_arn=identity["Arn"],
        profile_source=profile_source,
    )
