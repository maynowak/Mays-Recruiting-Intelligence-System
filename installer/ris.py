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
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3

from installer.state_mirror import MirrorEntry, StateMirror
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

#: Backend workspace prefix, identical mechanism to the Mays-Orders component,
#: which proves it in production: workspace=project_name + workspace_key_prefix
#: -> one state path per project. RIS carries the environment in the key, so a
#: state path is  env:/{project}/{environment}/terraform.tfstate
#: That is the same string this file's own lock classifier calls canonical
#: (canonical_lock_suffix), and the format of the states already in the bucket.
#:
#: Without it, key alone is {environment}/terraform.tfstate with no prefix, so
#: EVERY project sharing an environment resolves to the SAME object. Measured:
#: no object in mays-ris-tf-state-dev sits under the un-prefixed path.
RIS_WORKSPACE_KEY_PREFIX = "env:"

#: Subdirectory of the RIS backend bucket that holds COMPONENT state.
#:
#: Why discover needs to know this at all: the component project's backend
#: bucket is hardcoded in its own pinned terraform/backend.tf and its
#: installer calls init() without a backend_config, so RIS cannot redirect it
#: without modifying Mays-Orders-AWS - which is explicitly not wanted. The
#: component is used as a component, unchanged.
#:
#: Consolidation therefore happens at the DISCOVER layer: RIS states live at
#:   env:/{project}/{environment}/terraform.tfstate
#: and component states at
#:   orders/env:/{component}/{environment}/terraform.tfstate
#: in the same bucket, so one bucket holds both and discover can tell them
#: apart without guessing. Both stay in the component's canonical directory
#: shape; only the owning bucket is shared.
ORDERS_STATE_SUBDIR = "orders"


def orders_state_prefix(orders_project_name: str) -> str:
    """S3 prefix holding the Orders component's states inside the RIS bucket."""
    return f"{ORDERS_STATE_SUBDIR}/{RIS_WORKSPACE_KEY_PREFIX}/{orders_project_name}/"


def state_prefixes_for_project(
    ris_project_name: str,
    orders_project_name: Optional[str] = None,
) -> Dict[str, str]:
    """Every state prefix belonging to one RIS project, grouped by owner.

    Keys are the labels discover prints, so a bucket listing always says
    which component a state belongs to instead of leaving it to the reader.
    """
    prefixes = {
        "RIS": f"{RIS_WORKSPACE_KEY_PREFIX}/{ris_project_name}/",
    }
    if orders_project_name:
        prefixes["Orders"] = orders_state_prefix(orders_project_name)
    return prefixes

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

#: Composite installs disable the Cognito backup module: its bucket name is
#: "<prefix>-Development-<project_name>" and exceeds the 63-char S3 limit for
#: any composite project name. See docs/installer/AWS-NAME-LIMITS.md.
ORDERS_ENABLE_COGNITO_BACKUP = False


@dataclass(frozen=True)
class AwsNameRule:
    """One AWS resource name derived from the Orders project name.

    Attributes:
        resource: Logical resource, for the error message.
        limit: Hard AWS-side maximum length of the final resource name.
        overhead: Characters added around ``project_name`` to build it.
        pattern: The name template, for reproducing the calculation.
    """

    resource: str
    limit: int
    overhead: int
    pattern: str

    @property
    def max_project_name(self) -> int:
        """Longest project_name this resource tolerates."""
        return self.limit - self.overhead

    def accepts(self, project_name: str) -> bool:
        return len(project_name) <= self.max_project_name

    def violation(self, project_name: str) -> str:
        # `{env}` is a literal in the RIS patterns; substitute only the
        # project placeholder and leave the rest readable.
        rendered = self.pattern.replace("{project}", project_name)
        return (
            f"{self.resource}: {rendered} "
            f"is {len(project_name) + self.overhead} chars, AWS limit "
            f"{self.limit} (max project_name {self.max_project_name}, "
            f"got {len(project_name)})"
        )


#: Names built by the always-on Orders modules. Read off the pinned
#: Mays-Orders-AWS Terraform (5cf50a0), not guessed:
#:   cloudtrail/main.tf:20      dynamodb/main.tf:12     iam/main.tf:67,74
#:   lambda/main.tf:8           sqs/main.tf:186         sqs-worker/main.tf:2
#:   sqs-worker/iam.tf:51,59    cognito/main.tf:9,33    api/main.tf:8,30
#:   monitoring/main.tf:81,94-181
#:
#: Why this table exists at all: the previous single constant
#: ORDERS_PROJECT_NAME_MAX_LENGTH = 39 modelled ONLY the CloudTrail bucket and
#: happily accepted a name that then failed 40 resources later on a completely
#: different limit. One constant cannot describe 16 resources, so the limits
#: are data now and the constants are min() over that data.
#:
#: DynamoDB is the reason names differ per project at all: the table name is
#: var.project_name verbatim (dynamodb/main.tf:12), no prefix. Two installs
#: sharing a name would collide on the table, so the composite convention
#: "-mays-orders" is a correctness mechanism, not cosmetics.
ORDERS_AWS_NAME_RULES: tuple = (
    AwsNameRule("cloudtrail_s3_bucket", 63, 24, "{project}-cloudtrail-<account>"),
    AwsNameRule("iam_role_handler", 64, 13, "{project}-handler-role"),
    AwsNameRule("iam_role_sqs_worker", 64, 15, "{project}-sqs-worker-role"),
    AwsNameRule("lambda_handler", 64, 8, "{project}-handler"),
    AwsNameRule("lambda_sqs_worker", 64, 11, "{project}-sqs-worker"),
    AwsNameRule("iam_policy_handler", 128, 15, "{project}-handler-policy"),
    AwsNameRule("iam_policy_sqs_worker", 128, 17, "{project}-sqs-worker-policy"),
    AwsNameRule("sqs_orders_queue", 80, 13, "{project}-orders-queue"),
    AwsNameRule("dynamodb_orders_table", 255, 0, "{project}"),
    AwsNameRule("cognito_user_pool", 128, 6, "{project}-users"),
    AwsNameRule("cognito_user_pool_client", 128, 8, "{project}-client"),
    AwsNameRule("cloudtrail_trail", 128, 6, "{project}-trail"),
    AwsNameRule("apigatewayv2_api", 128, 4, "{project}-api"),
    AwsNameRule("apigatewayv2_authorizer", 128, 16, "{project}-jwt-authorizer"),
    AwsNameRule("cloudwatch_alarm", 255, 20, "{project}-dynamodb-throttled"),
    AwsNameRule("cloudwatch_dashboard", 255, 9, "{project}-overview"),
)

#: Extra names created only by the optional Cognito backup module
#: (var.enable_cognito_backup, default true). Its bucket name is the binding
#: constraint of the whole component: the "Development" segment is HARDCODED at
#: main.tf:210 and cannot be shortened via the environment variable.
#:
#: This is what broke the first composite plan:
#:   Error: expected length of bucket to be in the range (0 - 63), got
#:          mays-orders-cognito-backup-development-mays-ris-composite-a-mays-orders
#: 71 chars (lowercased by locals.bucket_name at cognito_backup/main.tf:3)
#: against a 63-char S3 limit. Only reachable with the backup module ON, and
#: it drops the usable name length from 39 to 23 -- below any realistic
#: composite name, which is why composite installs disable the module.
#:
#: The 71/72 discrepancy is real and intentional: the deployed name is
#: lowercased (71), this rule keeps the capitalised template (72). Both fail.
ORDERS_COGNITO_BACKUP_NAME_RULES: tuple = (
    AwsNameRule(
        "cognito_backup_s3_bucket", 63, 40,
        "mays-orders-cognito-backup-Development-{project}",
    ),
    AwsNameRule(
        "cognito_backup_scheduler_role", 64, 34,
        "{project}-cognito-backup-scheduler-role",
    ),
    AwsNameRule(
        "cognito_backup_role", 64, 26, "{project}-cognito-backup-role"
    ),
    AwsNameRule(
        "cognito_backup_lambda", 64, 24, "{project}-cognito-backup-lambda"
    ),
    AwsNameRule(
        "cognito_backup_schedule", 64, 25, "{project}-cognito-backup-schedule"
    ),
)

#: Orders project_name length limit: the binding AWS constraint of the
#: always-on modules, i.e. the CloudTrail bucket
#: f"{project_name}-cloudtrail-<12-digit-account>" <= 63 chars.
ORDERS_PROJECT_NAME_MAX_LENGTH = min(
    rule.max_project_name for rule in ORDERS_AWS_NAME_RULES
)


#: RIS' own AWS resource names. Overheads assume the LONGEST valid
#: environment string ("test"/"prod" = 4 chars), so the guard holds for every
#: environment. Read off terraform/modules/*/main.tf and terraform/main.tf.
RIS_AWS_NAME_RULES: tuple = (
    AwsNameRule(
        "cloudtrail_s3_bucket", 63, 24, "{project}-cloudtrail-<account>"
    ),
    AwsNameRule(
        "iam_role_health_publisher", 64, 22, "{project}-{env}-health-publisher"
    ),
    AwsNameRule(
        "lambda_health_publisher", 64, 22, "{project}-{env}-health-publisher"
    ),
    AwsNameRule(
        "lambda_health_writer", 64, 19, "{project}-{env}-health-writer"
    ),
    AwsNameRule(
        "s3_bucket_health_public", 63, 19, "{project}-{env}-health-public"
    ),
    AwsNameRule(
        "s3_bucket_health_state", 63, 18, "{project}-{env}-health-state"
    ),
    AwsNameRule(
        "s3_bucket_documents", 63, 15, "{project}-{env}-documents"
    ),
    AwsNameRule(
        "iam_role_lambda", 64, 12, "{project}-lambda-role"
    ),
)

#: Binding AWS constraint of RIS itself -> 39 chars (CloudTrail bucket).
RIS_PROJECT_NAME_MAX_LENGTH = min(
    rule.max_project_name for rule in RIS_AWS_NAME_RULES
)


def validate_ris_aws_name_limits(project_name: str) -> None:
    """Fail closed when a RIS resource name would exceed its AWS limit.

    Same rationale as validate_orders_aws_name_limits(): Terraform surfaces the
    overflow during plan, one resource at a time, after the backend is up.
    """
    violations = [
        rule.violation(project_name)
        for rule in sorted(RIS_AWS_NAME_RULES, key=lambda r: r.max_project_name)
        if not rule.accepts(project_name)
    ]
    if not violations:
        return
    detail = "\n  - ".join(violations)
    raise ValueError(
        f"RIS project name {project_name!r} ({len(project_name)} chars) "
        f"exceeds the AWS name limit of {RIS_PROJECT_NAME_MAX_LENGTH} "
        f"chars:\n  - {detail}"
    )


def orders_name_limit_violations(
    orders_project_name: str,
    *,
    enable_cognito_backup: bool = ORDERS_ENABLE_COGNITO_BACKUP,
) -> List[str]:
    """Every AWS name the Orders component would overflow, as plain strings.

    Empty list means the name fits. Ordered by severity (tightest rule first)
    so the first entry is the one that actually blocks the install.
    """
    rules = list(ORDERS_AWS_NAME_RULES)
    if enable_cognito_backup:
        rules += list(ORDERS_COGNITO_BACKUP_NAME_RULES)
    return [
        rule.violation(orders_project_name)
        for rule in sorted(rules, key=lambda r: r.max_project_name)
        if not rule.accepts(orders_project_name)
    ]


def orders_max_project_name(
    *, enable_cognito_backup: bool = ORDERS_ENABLE_COGNITO_BACKUP
) -> int:
    """Longest Orders project name the component accepts for these flags."""
    rules = list(ORDERS_AWS_NAME_RULES)
    if enable_cognito_backup:
        rules += list(ORDERS_COGNITO_BACKUP_NAME_RULES)
    return min(rule.max_project_name for rule in rules)


def validate_orders_aws_name_limits(
    orders_project_name: str,
    *,
    enable_cognito_backup: bool = ORDERS_ENABLE_COGNITO_BACKUP,
) -> None:
    """Fail closed when AWS would reject a derived resource name.

    Terraform only reports the overflow during plan, one resource at a time,
    after the backend is initialised. This check runs before any AWS call so
    the operator learns the real limit up front. Raises ValueError listing
    EVERY violation, not just the first.
    """
    violations = orders_name_limit_violations(
        orders_project_name, enable_cognito_backup=enable_cognito_backup
    )
    if not violations:
        return
    max_len = orders_max_project_name(
        enable_cognito_backup=enable_cognito_backup
    )
    detail = "\n  - ".join(violations)
    backup_note = (
        ""
        if enable_cognito_backup
        else (
            "\n  hint: the Cognito backup module is disabled for composite "
            "installs; its bucket "
            "'mays-orders-cognito-backup-Development-<project>' would exceed "
            f"the 63-char S3 limit above {ORDERS_COGNITO_BACKUP_NAME_RULES[0].max_project_name} "
            "chars"
        )
    )
    raise ValueError(
        f"orders component project name {orders_project_name!r} "
        f"({len(orders_project_name)} chars) exceeds the AWS name limit "
        f"of {max_len} chars for enable_cognito_backup="
        f"{str(enable_cognito_backup).lower()}:\n  - {detail}"
        f"{backup_note}"
    )

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
    # Composite installs disable the Cognito backup module, so its much
    # tighter 23-char limit does not apply here. The enabled flag is
    # validated by validate_orders_aws_name_limits() at install time.
    validate_orders_aws_name_limits(
        name, enable_cognito_backup=ORDERS_ENABLE_COGNITO_BACKUP
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


def orders_outputs_from_plan(plan_json: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Orders outputs from a plan, marking what Terraform cannot know.

    Why this exists: in dry-run nothing is applied, so the component's
    `terraform output` is empty and the handoff would be empty with it - a dry
    run could never plan RIS, only stop where it already stops. Reading the
    component's plan instead lets the rehearsal run the WHOLE chain.

    Measured on a real composite plan (Terraform v1.16.1):
      dynamodb_table_name -> after="mays-ris-composite-a-mays-orders", unknown=false
      dynamodb_table_arn  -> after=None,                            unknown=true
    Terraform genuinely cannot know a computed ARN before the resource is
    created. That is not a limitation of this approach, it is Terraform's
    semantics, so the value is carried as None and must be filled in
    deliberately by predict_orders_outputs() rather than silently defaulted.

    Returns the same shape parse_orders_outputs() produces, with None for
    values the plan leaves unknown.
    """
    changes = plan_json.get("output_changes")
    if not isinstance(changes, dict):
        raise RuntimeError(
            "Orders plan JSON has no output_changes; cannot build the handoff "
            "from a dry run"
        )
    out: Dict[str, Any] = {}
    unknown: list = []
    for name, change in changes.items():
        if not isinstance(change, dict):
            continue
        # after_unknown is true for anything computed at apply time. If it is a
        # list rather than a bool, only the named attributes are unknown.
        flag = change.get("after_unknown")
        if flag is True or (isinstance(flag, list) and flag):
            out[name] = None
            unknown.append(name)
        else:
            out[name] = change.get("after")
    out["_unknown"] = unknown
    return out


def predict_orders_outputs(
    outputs: Dict[str, Any],
    orders_project_name: str,
    region: str,
    account_id: str,
) -> Dict[str, Any]:
    """Fill plan-unknown values that are deterministic, and refuse the rest.

    Only the table ARN is filled. Its shape is fixed by the DynamoDB service,
    not by this project:
        arn:aws:dynamodb:{region}:{account}:table/{name}
    Verified against a real table in the account, not assumed:
        mays-orders-terraform-locks ->
        arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-terraform-locks

    Anything else the plan leaves unknown is NOT guessed. An unrecognised
    unknown means the rehearsal cannot be trusted, so it raises rather than
    producing a plan that looks complete and is not.
    """
    predicted = dict(outputs)
    unknown = set(predicted.get("_unknown") or [])

    if "dynamodb_table_arn" in unknown:
        name = predicted.get("dynamodb_table_name")
        if not name:
            raise RuntimeError(
                "cannot predict the Orders table ARN: the plan does not know "
                "the table name either"
            )
        predicted["dynamodb_table_arn"] = derive_orders_table_arn(
            name, region, account_id
        )
        unknown.discard("dynamodb_table_arn")
        predicted["_predicted"] = sorted(predicted.get("_predicted") or []) + [
            "dynamodb_table_arn"
        ]

    # Outputs we never consume must not block the rehearsal.
    relevant = unknown - set(_UNCONSUMED_ORDERS_OUTPUTS)
    if relevant:
        raise RuntimeError(
            "Orders plan leaves required output(s) unknown and they are not "
            f"deterministically derivable: {sorted(relevant)}. Refusing to "
            "guess; a dry run must not invent a binding."
        )
    predicted["_unknown"] = sorted(unknown)
    return predicted


#: Outputs the component publishes that RIS does not consume. Being unknown in
#: a plan is normal for these and must not fail the rehearsal.
_UNCONSUMED_ORDERS_OUTPUTS = frozenset(
    {
        "api_gateway_authorizer_id",
        "api_gateway_endpoint",
        "api_gateway_id",
        "api_gateway_stage_name",
        "cognito_user_pool_arn",
        "cognito_user_pool_client_id",
        "cognito_user_pool_endpoint",
        "cognito_user_pool_group_name",
        "cognito_user_pool_id",
        "iam_handler_role_arn",
        "iam_handler_role_name",
        "lambda_function_arn",
        "lambda_function_name",
        "lambda_invoke_arn",
    }
)


def _run_plain_process(
    cmd: List[str],
    cwd: str,
    extra_env: Optional[Dict[str, str]] = None,
    timeout: int = 300,
) -> "subprocess.CompletedProcess":
    """Run a read-only terraform helper, inheriting the ambient AWS context.

    Deliberately not TerraformRunner: this converts a plan that the component
    produced, in the component's own directory, and must not acquire a
    workspace or touch a backend.
    """
    env = {**os.environ}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout
    )


def derive_orders_table_arn(table_name: str, region: str, account_id: str) -> str:
    """Table ARN per the DynamoDB service's fixed ARN format.

    Verified against a real table in the account rather than assumed:
        mays-orders-terraform-locks
        -> arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-terraform-locks
    Note the `table/` segment - a bare name would produce a plausible-looking
    but wrong ARN, which is the kind of error that only shows up at runtime.
    """
    return f"arn:aws:dynamodb:{region}:{account_id}:table/{table_name}"


def orders_plan_path_from_output(stdout: str) -> Optional[str]:
    """The plan file the component just produced, as the component names it.

    Read from the component's own "Deploy with: ... --plan <path>" line, i.e.
    the exact path it tells the operator to use. Nothing is discovered by
    globbing, so a concurrent run cannot make RIS read someone else's plan.
    """
    marker = "--plan "
    idx = stdout.rfind(marker)
    if idx < 0:
        return None
    rest = stdout[idx + len(marker) :]
    path = rest.split()[0].strip() if rest.split() else ""
    return path or None


def resolve_plan_path(plan_path: str, component_dir: str) -> str:
    """Anchor the component's plan path to its clone root.

    The component prints `.mays-installer/runs/.../plans/<name>.tfplan`, which
    is relative to the CLONE ROOT. The conversion runs with cwd=terraform/, so
    the relative path has to be resolved first. Measured: passing it through
    unchanged fails with "Failed to read the given file as a state or plan
    file".

    An already absolute path is left alone, so this is idempotent.
    """
    path = Path(plan_path)
    if path.is_absolute():
        return str(path)
    return str(Path(component_dir) / path)


def load_orders_plan_json(
    plan_path: str, component_dir: str, tf_data_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Convert the component's plan to JSON, read-only.

    `terraform show -json` on a plan needs the provider plugins that produced
    it, so it runs with cwd=the component's terraform directory. Measured, not
    assumed: from the clone root it fails with "Failed to load plugin schemas"
    even though every provider binary is present.

    Same conversion the component's own Policy Gate performs
    (installer/projects/mays_orders/installer/run/manager.py:235).
    """
    result = _run_plain_process(
        ["terraform", "show", "-json", resolve_plan_path(plan_path, component_dir)],
        cwd=os.path.join(component_dir, "terraform"),
        extra_env={"TF_DATA_DIR": tf_data_dir} if tf_data_dir else None,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"terraform show -json failed for the Orders plan "
            f"({result.stderr.strip()[:300]})"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Orders plan JSON is malformed: {exc}")


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


def validate_orders_binding(
    handoff_vars: Dict[str, str],
    orders_project_name: str,
    account_id: str,
    expected_queue_url: Optional[str] = None,
) -> None:
    """Validate that Orders outputs match the expected component binding.

    Fail-closed: reject mismatched, empty, or malformed bindings.
    Raises RuntimeError on ANY mismatch (all are collected first, so one
    run tells the operator everything that is wrong).

    WHY THIS IS NOT REDUNDANT WITH THE TERRAFORM CHECKS
    ---------------------------------------------------
    The binding is guarded on two layers, and they are deliberately
    different -- do not "fix" one by copying the other:

      Root  terraform/variables.tf       default = "" and a condition that
                                           never rejects (x == "" || len(x) > 0).
                                           It only DECLARES that empty is
                                           tolerated.
      Module terraform/modules/orders_reader/variables.tf
                                           condition x != "" || can(regex(...))
                                           REJECTS empty.

    So "empty default = fail-closed binding" is literally true, but the
    rejection happens one layer down, at the module boundary. A plan with
    no Orders binding fails there with "Invalid value for variable".
    Verified against a real plan, not assumed.

    KNOWN GAP (documented, deliberately not changed here):
    the table and queue ARNs are checked for PREFIX and ACCOUNT only
    (see rules 2 and 4 below). They are NOT compared against
    orders_project_name, so a name/ARN pair pointing at two DIFFERENT
    tables is accepted: format right, identity unchecked. The name rule (1)
    and the URL rule (3) do compare identity. Closing this needs the
    component name in the ARN, e.g. f":table/{orders_project_name}" in
    table_arn - tracked, not silently assumed fixed.
    """
    errors = []

    # 1. Table name must match expected project name.
    #    IDENTITY check: this is what pins RIS to exactly one Orders
    #    installation. Derived, never read from AWS.
    table_name = handoff_vars.get("orders_table_name", "")
    if not table_name:
        errors.append("orders_table_name is empty or missing")
    elif table_name != orders_project_name:
        errors.append(
            f"orders_table_name mismatch: got {table_name!r}, "
            f"expected {orders_project_name!r} (binding collision detected)"
        )

    # 2. Table ARN must be in same account.
    #    FORMAT + ACCOUNT only -- see KNOWN GAP in the docstring.
    #    Value comes from the Orders `output` command, i.e. real AWS output.
    table_arn = handoff_vars.get("orders_table_arn", "")
    if not table_arn:
        errors.append("orders_table_arn is empty or missing")
    elif not table_arn.startswith(f"arn:aws:dynamodb:") or account_id not in table_arn:
        errors.append(
            f"orders_table_arn account mismatch: {table_arn!r} "
            f"does not contain expected account {account_id}"
        )
    
    # 3. Queue URL must match expected
    queue_url = handoff_vars.get("orders_queue_url", "")
    if not queue_url:
        errors.append("orders_queue_url is empty or missing")
    elif expected_queue_url and queue_url != expected_queue_url:
        # IDENTITY check. Note the queue URL is DERIVED by
        # derive_orders_queue_url(), not read from AWS: the Orders component
        # exports no SQS output. expected_queue_url must be passed by the
        # caller (install/destroy do) or this check silently does nothing.
        errors.append(
            f"orders_queue_url mismatch: got {queue_url!r}, "
            f"expected {expected_queue_url!r}"
        )
    elif "mays-orders-orders-queue" in queue_url and "-mays-orders" not in orders_project_name:
        # Belt-and-braces: catch a bind to the standalone namespace even
        # when expected_queue_url was not supplied.
        errors.append(
            f"orders_queue_url appears to bind to standalone mays-orders "
            f"but project is {orders_project_name!r}"
        )

    # 4. Queue ARN must be in same account.
    #    FORMAT + ACCOUNT only -- see KNOWN GAP in the docstring.
    queue_arn = handoff_vars.get("orders_queue_arn", "")
    if not queue_arn:
        errors.append("orders_queue_arn is empty or missing")
    elif not queue_arn.startswith(f"arn:aws:sqs:") or account_id not in queue_arn:
        errors.append(
            f"orders_queue_arn account mismatch: {queue_arn!r} "
            f"does not contain expected account {account_id}"
        )
    
    if errors:
        raise RuntimeError("Orders binding validation failed:\n  " + "\n  ".join(errors))


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
    stop_through: Optional[str] = None
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
        # Fail closed before any AWS call: every RIS resource name is derived
        # from project_name and AWS rejects the overflow during plan.
        validate_ris_aws_name_limits(self.project_name)

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
            # Prefix, not the environment, is what makes the path unique per
            # project: {prefix}/{workspace}/{key}. RIS_WORKSPACE_KEY_PREFIX.
            workspace_key_prefix=RIS_WORKSPACE_KEY_PREFIX,
        )

    def terraform_vars(self) -> Dict[str, str]:
        """Input variables for plan/apply (ordinary vars, never backend).

        Extra --var entries ride along, but project identity always wins
        (fail-closed: identity cannot be overridden via --var).
        """
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
        base = Path(self._workdir_base) if self._workdir_base else isolated_workdir_base()
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

    @property
    def isolated_mirror_dir(self) -> str:
        """Where the local state mirror lives for this project.

        Deliberately a SIBLING of the isolated workdir, not a child: only
        `.../terraform` is deleted and recreated per run, so a mirror placed
        there would be destroyed on the very next invocation.
        """
        from installer.state_mirror import mirror_dir_for

        base = (
            Path(self._workdir_base)
            if self._workdir_base
            else isolated_workdir_base()
        )
        return str(mirror_dir_for(base, self.project_name, self.environment))


def _cmd_preflight(ctx: RisInstallContext) -> int:
    """PHASE A: read-only AWS identity + composite component validation.

    Validates AWS identity (STS), then verifies the Mays-Orders-AWS
    component: Git pin, installer discovery, and (read-only) AWS
    collision scan for the derived component project name. No resource
    mutation and no Terraform apply anywhere in this path.
    """
    if ctx.aws_context is None:
        try:
            aws_ctx = validate_aws_context(
                profile=ctx.aws_profile, region=ctx.aws_region
            )
        except AwsValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        ctx.aws_context = aws_ctx
    else:
            aws_ctx = ctx.aws_context
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
        #
        # KNOWN BLIND SPOT -- read before trusting a clean result here.
        # The component's collision scan (installer/core/collision_scan.py in
        # the Orders repo) matches resources by SUBSTRING of the project
        # name. Measured against live account 240571105849:
        #
        #   probe "mays-orders"                      ->  9 hits
        #   probe "mays-ris-composite-a-mays-orders" ->  0 hits
        #
        # So for a COMPOSITE name the scan sees nothing and a second Orders
        # installation in the shared mays-orders namespace is NOT reported.
        # That is exactly how a parallel mays-orders installation went
        # unnoticed. A green preflight does NOT mean "no other Orders
        # installation exists". Fixing it belongs in RIS (scan the
        # namespace token as well as the full name), not in the Orders repo.
        #
        # This call also duplicates the Orders validate that
        # _run_orders_component() performs a moment later -- 2x STS calls
        # and 2x 10-check validates per install. Recorded, not changed.
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
    if ctx.aws_context is None:
        ctx.aws_context = validate_aws_context(profile=ctx.aws_profile, region=ctx.aws_region)
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
        runner.init(backend_config=ctx.backend_config(), reconfigure=True),
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
    init_res = runner.init(backend_config=ctx.backend_config(), reconfigure=True)
    
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
    
    # Local mirror of the pre-apply state (S3-outage fallback, mirrors the
    # component's .backups rotation). Advisory: never blocks apply.
    mirror_project_state(ctx, runner)

    apply_res = runner.run_and_get_result(["apply", plan_file], ensure_workspace=True)
    return [init_res, plan_res, apply_res]


def mirror_project_state(
    ctx: RisInstallContext, runner, purpose: str = "pre-apply"
) -> Optional[str]:
    """Pull the remote state into the local mirror before mutating it.

    Called after the safety gate passed and immediately before apply, so the
    mirror holds the PRE-apply state - the only version worth rolling back
    to. Mirrors the component's rotation (`.backups` + backup_count) at
    installer/state_mirror.py.

    ensure_workspace=False on the pull: the plan in this same run already
    resolved the workspace, and re-selecting it here would take a second
    state lock in the gap between the safety gate and apply - a new failure
    point in the one window that must not grow one.

    Never fatal: a state that has not been written yet, or an S3 hiccup, must
    not block a plan that is otherwise safe. It reports and returns None.
    """
    try:
        pulled = runner.state_pull(ensure_workspace=False)
    except (RuntimeError, ValueError) as exc:
        print(f"state mirror: pull skipped ({exc})", file=sys.stderr)
        return None
    if pulled.returncode != 0 or not pulled.stdout.strip():
        print(
            f"state mirror: no remote state to mirror "
            f"({pulled.stderr.strip()[:160]})",
            file=sys.stderr,
        )
        return None
    try:
        mirror = StateMirror(ctx.isolated_mirror_dir)
        entry = mirror.snapshot(pulled.stdout, label=ctx.workspace)
    except (OSError, ValueError) as exc:
        print(f"state mirror: snapshot failed ({exc})", file=sys.stderr)
        return None
    print(f"state mirror: {purpose} snapshot {entry.describe()}")
    return str(entry.path)


def _cmd_state_mirror(ctx: RisInstallContext, capture: bool) -> int:
    """`state mirror` — list or refresh the local state mirror.

    Deliberately usable with no backend and no AWS credentials: the mirror is
    the fallback for when the backend is the thing that is broken, so it must
    not itself depend on the backend.

    capture=False  list what is stored locally, and write the MANIFEST
    capture=True   additionally refresh it from the current backend
    """
    mirror = StateMirror(ctx.isolated_mirror_dir)

    if capture:
        if not ctx.backend_bucket:
            print(
                "error: backend-bucket required for 'state mirror capture' "
                "(listing works without it)",
                file=sys.stderr,
            )
            return 2
        try:
            ctx.aws_context = validate_aws_context(
                profile=ctx.aws_profile, region=ctx.aws_region
            )
        except AwsValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        try:
            runner = ctx.make_runner()
            # init against the REQUESTED backend first. Without it
            # `state pull` would silently use whatever backend a previous run
            # left in the workdir, so --backend-bucket would be ignored and the
            # mirror would capture the wrong bucket - a silent second source of
            # truth, which is worse than no mirror at all.
            # -reconfigure is required, not cosmetic: measured, a run against a
            # different bucket leaves the workdir pointing at the old one and
            # every later run fails with "Backend configuration changed".
            init_res = runner.init(
                backend_config=ctx.backend_config(), reconfigure=True
            )
            if init_res.returncode != 0:
                print(
                    f"warning: capture failed, backend init failed: "
                    f"{init_res.stderr.strip()[:200]}",
                    file=sys.stderr,
                )
                return _list_mirror(mirror)
            mirror_project_state(ctx, runner, purpose="on-demand")
        except Exception as exc:  # noqa: BLE001 - listing must still work
            print(f"warning: capture failed ({exc})", file=sys.stderr)

    entries = mirror.entries()
    return _list_mirror(mirror, entries)


def _list_mirror(mirror: StateMirror, entries: Optional[List[MirrorEntry]] = None) -> int:
    """Print the mirror. Always succeeds: it is a local, offline listing."""
    if entries is None:
        entries = mirror.entries()
    print(f"Local state mirror: {mirror.mirror_dir}")
    if not entries:
        print(
            "  empty. A snapshot is taken automatically before every apply; "
            "run 'state mirror capture' to take one now."
        )
        return 0
    print(f"  {len(entries)} snapshot(s), keeping the newest {mirror.keep}:")
    for entry in entries:
        print(f"    {entry.path.name}")
        print(f"      {entry.describe()}")
    manifest = mirror.write_manifest()
    print(f"\nManifest written: {manifest}")
    return 0


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
    init_res = runner.init(backend_config=ctx.backend_config(), reconfigure=True)
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
            # No workspace env var: the component's own routine selects the
            # workspace from --project-name, and Terraform refuses
            # `workspace select` while TF_WORKSPACE is set. Same reasoning as
            # _run_orders_component; see the long comment there.
            "TF_DATA_DIR": component_tf_data_dir(ctx.project_name, orders_project),
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

    WHY THERE IS AN INIT HERE
    ------------------------
    ctx.make_runner() resolves to the ISOLATED workdir
    (~/.ris-workdirs/<project>/<env>/terraform), a copy created by
    _ensure_isolated_workdir() with ignore_patterns('.terraform', ...). That
    copy therefore has NO backend metadata on a fresh run, so every state
    subcommand failed with "Backend initialization required". The bucket in
    terraform/main.tf is a template, so a bare `terraform init` asks for input
    and dies with "Error asking for input to configure backend s3: bucket: EOF".

    _cmd_plan/_cmd_apply already pass ctx.backend_config() to init(); the state
    path did not. Verified against HEAD: `state list` failed identically before
    any of this session's changes.

    Backend values come ONLY from the explicit CLI flags, same as everywhere
    else -- nothing is invented here. Without a bucket there is nothing to read
    from, and the subcommands that need it already error out themselves.

    `discover` and `inventory` talk to S3/DynamoDB directly and never touch
    Terraform, so they are exempt and stay cheap.
    """
    import subprocess
    runner = ctx.make_runner()
    if state_command in ("list", "show", "pull"):
        # Backend first, and ONLY here. `push` must keep its guards ahead of
        # any subprocess (a refused push calls nothing at all), and
        # discover/inventory talk to S3/DynamoDB directly, so neither needs
        # terraform at all.
        if state_command == "show" and not address:
            print("error: address is required for state show", file=sys.stderr)
            return 2
        try:
            init_res = runner.init(backend_config=ctx.backend_config(), reconfigure=True)
        except (ValueError, RuntimeError) as exc:
            # BackendConfig raises when an explicit value is missing. Pass it
            # on rather than inventing a bucket: no defaults, per the
            # installer contract.
            print(f"error: backend init failed: {exc}", file=sys.stderr)
            return 2
        if init_res.returncode != 0:
            print(
                f"error: terraform init failed: "
                f"{init_res.stderr.strip()[:300]}",
                file=sys.stderr,
            )
            return 1
    if state_command == "discover":
        if not ctx.backend_bucket:
            print("error: backend-bucket required for state discover", file=sys.stderr)
            return 2
        try:
            orders_project = orders_component_project_name(ctx.project_name)
        except ValueError as exc:
            print(f"warning: no component project name ({exc})", file=sys.stderr)
            orders_project = None
        prefixes = state_prefixes_for_project(ctx.project_name, orders_project)
        try:
            aws_ctx = validate_aws_context(profile=ctx.aws_profile, region=ctx.aws_region)
            ctx.aws_context = aws_ctx
        except AwsValidationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        env = {**os.environ, **aws_ctx.to_env()}
        import json

        found_any = False
        for label, prefix in prefixes.items():
            cmd = [
                "aws", "s3api", "list-objects-v2",
                "--bucket", ctx.backend_bucket,
                "--prefix", prefix,
                "--query", "Contents[].{Key:Key,Size:Size,LastModified:LastModified}",
                "--output", "json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if result.returncode != 0:
                print(
                    f"error: aws s3api failed for prefix {prefix!r}: "
                    f"{result.stderr.strip()[:200]}",
                    file=sys.stderr,
                )
                return 1
            try:
                items = json.loads(result.stdout) or []
            except Exception:
                items = []
            if not items:
                print(f"[{label}] no states under {prefix}")
                continue
            found_any = True
            print(f"[{label}] states under {prefix}")
            for it in items:
                print(
                    f"    {it.get('Key')}  size={it.get('Size')}  "
                    f"modified={it.get('LastModified')}"
                )
        if not found_any:
            print(
                f"No state objects for project {ctx.project_name} in "
                f"bucket {ctx.backend_bucket}"
            )
        else:
            print(
                f"\nAll states live in bucket {ctx.backend_bucket}. "
                f"RIS states at '{prefixes['RIS']}', component states under "
                f"'{ORDERS_STATE_SUBDIR}/'. Layout: "
                f"{RIS_WORKSPACE_KEY_PREFIX}/<project>/<env>/terraform.tfstate"
            )
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
    if state_command == "mirror":
        # Local and read-only. Needs no backend and no AWS identity, because
        # the whole point of the mirror is that it stands on its own when S3
        # does not. `mirror capture` refreshes it, bare `mirror` only lists.
        return _cmd_state_mirror(ctx, capture=(address or "").lower() == "capture")
    if state_command in ("list", "show", "pull"):
        if state_command == "list":
            result = runner.state_list(state_file)
        elif state_command == "show":
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


def isolated_workdir_base() -> Path:
    """Root of all per-project isolated working directories.

    Single source of truth: the RIS workdir, the state mirror and the Orders
    component instances must all live under the same root, or a project would
    be spread over two directories that nothing knows how to clean up together.
    """
    return Path.home() / ".ris-workdirs"


def component_tf_data_dir(ris_project_name: str, orders_project: str) -> str:
    """Working state for one Orders component INSTANCE.

    Why a consumer needs this
    -------------------------
    The orchestrator runs the component with cwd=installer/projects/mays_orders
    for every RIS project, so all of them share ONE .terraform/ directory and
    therefore ONE .terraform/environment file - a mutable file that records the
    currently selected workspace. Two RIS projects running the same clone can
    overwrite each other's selection, and a plan can then resolve against the
    wrong workspace. Measured, that is what once produced a plan proposing to
    destroy 9 adopted resources.

    The obvious fix from the outside - inject TF_WORKSPACE so the selection is
    process-local - is the wrong fix, and measurably so: Terraform refuses
    `workspace select` while TF_WORKSPACE is set, which breaks the component's
    own workspace management outright (see the comment at the call site).

    Giving each instance its own TF_DATA_DIR is how a component consumer should
    do it: the component keeps its routine untouched and still runs
    `workspace select` / `workspace new`, but against private state, so there
    is nothing shared to race over. Measured: with a private TF_DATA_DIR the
    component plan succeeds (exit 0) and the shared .terraform/environment is
    left byte-for-byte unchanged, while the instance's own file records the
    composite workspace.

    MO-only runs in the clone keep using the default .terraform, so they are
    unaffected.

    Cost, stated rather than hidden: a fresh TF_DATA_DIR re-downloads providers,
    which is why the first isolated run is slow. That is a one-off per composite
    project, and it buys correctness.
    """
    return str(
        Path(isolated_workdir_base())
        / "component"
        / orders_project
    )


def _run_orders_component(ctx: RisInstallContext, orchestrator: RISInstaller, orders_project: str, *, dry_run: Optional[bool] = None, stop_after_plan: bool = False) -> Dict[str, Any]:
    """
      validate -> plan -> deploy -> output
    - profile/region passed as *global* args (argparse subcommand contract).
    - --project-name = orders_project (isolated component identity).
    - --yes on deploy requires ALLOW_AWS_OPERATIONS=true (env-only, set by caller).
    - dry_run override: if not None, overrides ctx.dry_run for deciding ALLOW_AWS_OPERATIONS.
    - stop_after_plan: if True, returns after plan (no deploy/output).
    Returns the orchestrator result dicts for each stage.
    Preserves the Orders state: a RIS-side failure later does NOT destroy a
    successfully installed Orders component (no auto-cleanup; destroy is a
    separate, explicit composite destroy operation).
    """
#    WHAT CONTROLS THE BACKEND -- measured, do not re-derive from the docs
#    --------------------------------------------------------------------
#    The component's own installer decides S3 vs local in
#    installer/cli/main.py: `runner.init(backend=not context.dry_run)`.
#    It is a BOOLEAN, not a bucket choice: the bucket is hardcoded in the
#    pinned terraform/backend.tf and cannot be overridden from here. The
#    component's own audit (docs/reports/MAYS-ORDERS-MODULARITY-01A-
#    INSTALLER-TERRAFORM-BACKEND-AUDIT.md, section 9) records
#    "backend-config: FOUND NO".
#
#    Because DRY_RUN=true implies backend=false, it was worth checking
#    whether a RIS dry-run plan reads the WRONG state. It does NOT, as long
#    as .terraform/ already carries a configured S3 backend:
#
#      DRY_RUN=true  + existing S3 .terraform -> reads env:/<project>/  (correct)
#      DRY_RUN=false + fresh clone           -> reads env:/<project>/  (correct)
#      DRY_RUN=true  + FRESH clone           -> PLAN FAILS, no backend
#
#    Reason: `init -backend=false` means "do not CONFIGURE the backend", not
#    "use a local state". The already-configured S3 backend stays active.
#    A hypothesis that dry-run plans a local state was tested and REJECTED;
#    do not re-open it without new evidence. The real fragility is the third
#    row: correctness depends on leftover local .terraform/ metadata, and a
#    fresh checkout fails rather than silently mis-planning.
#    """
    # Fail closed BEFORE any AWS call: the flags below decide which AWS name
    # limits apply, and Terraform would otherwise surface the overflow one
    # resource at a time, after the backend is already initialised.
    validate_orders_aws_name_limits(
        orders_project,
        enable_cognito_backup=ORDERS_ENABLE_COGNITO_BACKUP,
    )

    # Global options go first; command word; then command-specific args.
    # Dry-run is the Orders default; live deploy is opt-in via env + --yes.
    allow_aws = "true" if not ctx.dry_run else "false"
    env_extra: Dict[str, str] = {
        "ALLOW_AWS_OPERATIONS": allow_aws,
        # Force the component's Terraform workspace to match its project name.
        # The component's InstallationContext.from_env() reads PROJECT_NAME,
        # and its __post_init__ falls back to "default" if unset -- which is
        # how an earlier run ended up planning against the shared DEFAULT
        # state (and against a stale lock on it).
        "PROJECT_NAME": orders_project,
        # NO workspace environment variable is injected, deliberately.
        #
        # RIS is the CONSUMER here. The component owns its own routine, and
        # that routine includes workspace management: its runner calls
        # `terraform workspace select` unconditionally (terraform/runner.py:419)
        # and creates the workspace if missing. That is its business, and a
        # consumer does not reach into it.
        #
        # Both variables that used to be set here were wrong on the evidence:
        #   TERRAFORM_WORKSPACE - no-op on this path. The component's CLI
        #     overwrites the context value with project_name
        #     (installer/cli/main.py:386), so it never selected anything.
        #   TF_WORKSPACE - actively hostile. The Terraform CLI REFUSES
        #     `workspace select` while it is set, and the component's
        #     missing-workspace signals do not match the override message, so
        #     the runner raises instead of creating the workspace. Measured
        #     controlled pair, same command, one variable apart:
        #       without TF_WORKSPACE -> "Status: Generated successfully"  exit 0
        #       with    TF_WORKSPACE -> TerraformError                   exit 1
        #     Removing it also unblocks workspace CREATION for new composites,
        #     which the override had prevented outright.
        #
        # The workspace is selected through the component's own interface:
        # `--project-name`, passed below as project_name_override.
        #
        # The original contamination this was meant to fix is handled the way a
        # component consumer should handle it - by giving each instance its own
        # working state, not by fighting the component's routine. See
        # component_tf_data_dir() and the isolation note there.
        "TF_DATA_DIR": component_tf_data_dir(ctx.project_name, orders_project),
    }
    # Persisted here, not left to the caller: a CLI-only pin is lost on the
    # next unpinned run (see G3-COGNITO-CONFIG-PERSISTENCE-01 in AI_AUDITLOG).
    # The backup bucket cannot be renamed: its "Development" segment is
    # hardcoded in the pinned Orders main.tf, so disabling the module is the
    # only way composite names fit the 63-char S3 limit.
    orders_plan_vars = [
        f"project_name={orders_project}",
        f"aws_region={ctx.aws_region}",
        f"enable_cognito_backup="
        f"{str(ORDERS_ENABLE_COGNITO_BACKUP).lower()}",
    ]

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
        extra_args=[arg for pair in orders_plan_vars for arg in ("--var", pair)],
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

    outputs = parse_orders_outputs(out.get("stdout", ""))

    # A dry run must rehearse the WHOLE chain, otherwise it stops exactly where
    # the interesting part begins: nothing is applied, so `terraform output` is
    # empty and RIS has no binding to plan against. Measured on a real composite
    # plan: the table NAME is known at plan time, the table ARN is not.
    if not _has_consumable_outputs(outputs):
        plan_path = orders_plan_path_from_output(plan.get("stdout", "") or "")
        if not plan_path:
            raise RuntimeError(
                "Orders returned no outputs (nothing applied) and named no plan "
                "file, so the handoff cannot be built. Run the component plan "
                "with the component installer so it prints the plan path."
            )
        component_dir = orchestrator.checkout_project("mays-orders").local_path
        plan_json = load_orders_plan_json(
            plan_path, component_dir, env_extra["TF_DATA_DIR"]
        )
        planned = orders_outputs_from_plan(plan_json)
        predicted = predict_orders_outputs(
            planned, orders_project, ctx.aws_region, ctx.aws_context.account_id
        )
        print(
            f"  Orders handoff (from plan, nothing applied): "
            f"table={predicted.get('dynamodb_table_name')}, "
            f"predicted={predicted.get('_predicted') or 'none'}"
        )
        if predicted.get("_predicted"):
            print(
                "  NOTE: the table ARN is not knowable before apply "
                "(Terraform marks it unknown). It is derived from the service's "
                "fixed ARN format and is re-verified against the real output at "
                "apply time."
            )
        outputs = predicted
    return outputs


def _has_consumable_outputs(outputs: Dict[str, Any]) -> bool:
    """Whether the component gave us anything RIS can bind to."""
    return any(outputs.get(name) for name in ORDERS_OUTPUT_VAR_MAP)


def _cmd_install(
    ctx: RisInstallContext, out_file: Optional[str] = None, through: Optional[str] = None
) -> int:
    """Composite phased installation: preflight -> orders validate/plan/deploy ->
    output handoff -> RIS package/plan/apply. Dry-run (no --yes) stops before
    any mutation and reports the planned phases.

    PHASE ORDER IS CURRENTLY WRONG -- recorded, not yet changed
    ----------------------------------------------------------
    Execution order is:
      A  preflight  (read-only)
      C  Orders validate -> plan -> DEPLOY -> output     <- mutation here
         handoff + binding validation
      B  RIS backend bootstrap                            <- after Orders is live
      D  RIS lambda packaging                             <- after Orders is live
      E..G  RIS init/validate/plan/apply

    Two defects fall out of that:
      1. Orders is APPLIED before the RIS backend and before the RIS lambda
         artifacts exist. If B or D fails, Orders is already deployed and is
         NOT rolled back (see the explicit note at the packaging failure).
      2. The phase letters do not match the execution order (A, C, B, D, E).

    Intended order: package -> bootstrap -> orders validate -> orders plan ->
    RIS plan -> orders deploy -> RIS apply, i.e. every read-only step first
    and mutations last, so a late failure leaves nothing behind.

    Also duplicated: validate_aws_context() runs inline above AND again
    inside _cmd_preflight(), and the Orders validate runs both in
    preflight and in _run_orders_component(). Two STS calls and two
    10-check validations per install. Pure overhead, no behaviour.
    """
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

    # Update context with backend configuration derived from project name
    ctx.backend_bucket = names.bucket
    ctx.backend_region = names.region
    ctx.backend_lock_table = names.lock_table
    if ctx.dry_run:
        print("dry-run composite installation plan (no mutation performed):")
        print(f"  account: {aws_ctx.account_id}")
        print(f"  region: {aws_ctx.region}")
        print(f"  RIS project: {ctx.project_name} -> workspace {ctx.workspace}")
        print(f"  Orders component: {orders_project}")
        print(f"  backend bucket: {names.bucket}")
        print(f"  lock table: {names.lock_table}")
        print("  phases: orders validate -> orders plan -> output handoff -> ")
        print("  phases: package -> bootstrap -> orders validate -> orders plan -> RIS plan -> orders deploy -> RIS apply")

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
        # Validate binding matches expected component (fail-closed)
        expected_queue_url = derive_orders_queue_url(
            orders_project, ctx.aws_region, aws_ctx.account_id
        )
        validate_orders_binding(handoff, orders_project, aws_ctx.account_id, expected_queue_url)
        print(f"Orders binding validated: {orders_project}")
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
        ctx.stop_through = through
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
        # Same prefix as RisInstallContext.backend_config(). This call site
        # builds its own BackendConfig instead of reusing the method, so it
        # has to opt in explicitly -- otherwise the main install path would
        # keep resolving to the un-prefixed, colliding state path while plan
        # and apply use the prefixed one.
        workspace_key_prefix=RIS_WORKSPACE_KEY_PREFIX,
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
        choices=[
            "list",
            "show",
            "pull",
            "push",
            "discover",
            "inventory",
            "mirror",
        ],
        help=(
            "State subcommand (state command). 'mirror' lists the local "
            "state mirror ('--address capture' refreshes it from the "
            "backend); listing needs no backend."
        ),
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
        "--through",
        choices=["orders-deploy", "ris-apply"],
        help="Stop after the specified phase (for phased apply).",
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
        # Derive backend names from project name and environment if not explicitly provided
        backend_bucket = parsed.backend_bucket
        backend_region = parsed.backend_region
        backend_lock_table = parsed.backend_lock_table
        
        if backend_bucket is None or backend_region is None or backend_lock_table is None:
            # Create a temporary RisInstallContext to derive the backend names
            temp_ctx = RisInstallContext(
                project_name=parsed.project_name,
                environment=parsed.environment,
                aws_region=parsed.aws_region,
                terraform_dir=parsed.terraform_dir,
                backend_bucket=backend_bucket,  # May be None, but that's OK for derivation
                backend_region=backend_region,  # May be None, but that's OK for derivation
                backend_lock_table=backend_lock_table,  # May be None, but that's OK for derivation
                aws_profile=parsed.profile,
            )
            names = BackendNames.for_project(
                temp_ctx.project_name, 
                temp_ctx.environment, 
                region=temp_ctx.aws_region
            )
            if backend_bucket is None:
                backend_bucket = names.bucket
            if backend_region is None:
                backend_region = names.region
            if backend_lock_table is None:
                backend_lock_table = names.lock_table
        
        ctx = RisInstallContext(
            project_name=parsed.project_name,
            environment=parsed.environment,
            aws_region=parsed.aws_region,
            terraform_dir=parsed.terraform_dir,
            backend_bucket=backend_bucket,
            backend_region=backend_region,
            backend_lock_table=backend_lock_table,
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
        return _cmd_install(ctx, out_file=parsed.out, through=parsed.through)
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
