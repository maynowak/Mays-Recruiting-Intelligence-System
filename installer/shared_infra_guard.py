"""Shared-infrastructure guard for Terraform plan/apply.

Purpose: a missing or contradictory transport flag must never be read as a
teardown request. `enable_agent_transport`, `orders_agent_result_enabled` and
`orders_lifecycle` gate the shared dispatch and result transport. Their
Terraform defaults can destroy the transport when the live state still has it.

This module is pure: it inspects Terraform plan JSON and returns a decision.
It never calls AWS and never changes resources.

Contract:
- no shared delete/replace/forget -> safe;
- shared delete/replace/forget without an explicit ``teardown_intent`` ->
  refused, fail closed;
- intent present but malformed, or plan shape malformed/incomplete ->
  refused, fail closed;
- valid intent -> allowed, and the intent plus plan digest are recorded in
  the decision for the audit log.

The intent authorizes the plan it was reviewed with, not an arbitrary future
plan: callers pass the plan SHA-256 that was reviewed.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Flags that gate shared transport. False/absent must never mean "teardown".
TRANSPORT_FLAGS = (
    "enable_agent_transport",
    "orders_agent_result_enabled",
    "orders_lifecycle",
)

#: Value that counts as "transport available" per flag.
TRANSPORT_FLAG_EXPECTED = {
    "enable_agent_transport": "true",
    "orders_agent_result_enabled": "true",
    "orders_lifecycle": "managed",
}

#: Modules whose children are shared platform infrastructure.
SHARED_MODULE_PREFIXES = (
    "module.agent_transport",
    "module.mays_orders",
    "module.lambda",
    "module.dynamodb",
    "module.cognito",
    "module.orders_reader",
    "module.api",
    "module.sqs",
    "module.iam",
    "module.health_plane",
    "module.health_public",
    "module.health",
    "module.monitoring",
    "module.monitoring_orders",
    "module.documents",
    "module.cloudtrail",
    "module.jobsearch_edge",
    "module.partner_edge",
)

#: Top-level resource types that are shared even outside a known module.
SHARED_RESOURCE_TYPES = (
    "aws_sqs_queue",
    "aws_sqs_queue_policy",
    "aws_sqs_queue_redrive_policy",
    "aws_sqs_queue_redrive_allow_policy",
    "aws_lambda_function",
    "aws_lambda_event_source_mapping",
    "aws_lambda_permission",
    "aws_lambda_alias",
    "aws_lambda_event_invoke_config",
    "aws_dynamodb_table",
    "aws_secretsmanager_secret",
    "aws_secretsmanager_secret_version",
    "aws_secretsmanager_secret_policy",
    "aws_cognito_user_pool",
    "aws_cognito_user_pool_client",
    "aws_apigatewayv2_api",
    "aws_apigatewayv2_route",
    "aws_apigatewayv2_integration",
    "aws_apigatewayv2_stage",
    "aws_apigatewayv2_authorizer",
    "aws_cloudfront_distribution",
    "aws_iam_role",
    "aws_iam_role_policy",
    "aws_iam_policy",
    "aws_iam_role_policy_attachment",
    "aws_cloudwatch_event_rule",
    "aws_cloudwatch_event_target",
    "aws_cloudwatch_log_group",
    "aws_s3_bucket",
    "aws_s3_bucket_policy",
    "aws_cloudtrail",
    "aws_kms_key",
    "aws_sns_topic",
)

#: Address/name markers that identify shared agent infrastructure. Both the
#: AWS name (hyphen) and the Terraform label (underscore) are listed.
SHARED_NAME_MARKERS = (
    "agent-dispatch",
    "agent_dispatch",
    "agent-results",
    "agent_results",
    "work-items",
    "work_items",
    "mays-orders",
    "mays_orders",
    "agent-catalog",
    "agent_catalog",
    "entitlements",
    "api-profiles",
    "api_profiles",
    "lambda-role",
    "lambda_role",
)

DESTRUCTIVE_ACTIONS = ("delete", "forget")

INTENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/ ()-]*$")


@dataclass(frozen=True)
class Finding:
    address: str
    actions: Tuple[str, ...]
    protection: str
    resource_type: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "actions": list(self.actions),
            "protection": self.protection,
            "type": self.resource_type,
        }


@dataclass(frozen=True)
class GuardDecision:
    safe: bool
    code: str
    message: str
    findings: Tuple[Finding, ...] = ()
    transport_flags: Dict[str, str] = field(default_factory=dict)
    teardown_intent: Optional[str] = None
    plan_sha256: Optional[str] = None

    @property
    def authorized_teardown(self) -> bool:
        return bool(self.teardown_intent) and self.safe and bool(self.findings)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "safe": self.safe,
            "code": self.code,
            "message": self.message,
            "findings": [f.as_dict() for f in self.findings],
            "transportFlags": dict(self.transport_flags),
            "teardownIntent": self.teardown_intent,
            "planSha256": self.plan_sha256,
            "authorizedTeardown": self.authorized_teardown,
        }


def _safe(text: str) -> str:
    """Printable-only rendering for messages (no control-char log injection)."""
    return "".join(c if c.isprintable() else "?" for c in str(text))


def _protection_for(address: str, resource_type: str) -> Optional[str]:
    for prefix in SHARED_MODULE_PREFIXES:
        if address == prefix or address.startswith(prefix + ".") \
                or address.startswith(prefix + "["):
            return f"module:{prefix}"
    if resource_type in SHARED_RESOURCE_TYPES:
        return f"type:{resource_type}"
    for marker in SHARED_NAME_MARKERS:
        if marker in address:
            return f"name:{marker}"
    return None


def _validated_intent(intent: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return (intent, error). Empty/blank means 'no intent', not an error."""
    text = (intent or "").strip()
    if not text:
        return None, None
    if not 6 <= len(text) <= 128:
        return None, "teardown intent must be 6..128 characters"
    if any(unicodedata.category(c) in ("Cc", "Cf") for c in text):
        return None, "teardown intent contains control/format characters"
    if not INTENT_PATTERN.match(text):
        return None, "teardown intent contains unsupported characters"
    return text, None


def validate_plan_shape(plan_json: Any) -> Optional[str]:
    """Return a reason when the document is not a usable plan JSON."""
    if not isinstance(plan_json, dict):
        return "plan is not a JSON object"
    if "resource_changes" not in plan_json:
        return "plan has no resource_changes (state document or truncated output)"
    changes = plan_json.get("resource_changes")
    if not isinstance(changes, list):
        return "resource_changes is not a list"
    if plan_json.get("errored") is True:
        return "plan is marked errored"
    if plan_json.get("complete") is False:
        return "plan is marked incomplete"
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            return f"resource_changes[{index}] is not an object"
        payload = change.get("change")
        if not isinstance(payload, dict):
            return f"resource_changes[{index}].change is not an object"
        actions = payload.get("actions")
        if not isinstance(actions, list) \
                or not all(isinstance(a, str) for a in actions):
            return f"resource_changes[{index}].actions is not a list of strings"
    return None


def collect_findings(plan_json: Dict[str, Any]) -> List[Finding]:
    """Shared resources that the plan deletes, replaces or forgets."""
    findings: List[Finding] = []
    for change in plan_json.get("resource_changes") or []:
        payload = change.get("change") or {}
        actions = tuple(payload.get("actions") or [])
        if not any(a in actions for a in DESTRUCTIVE_ACTIONS):
            continue
        address = str(change.get("address") or "")
        resource_type = str(change.get("type") or "")
        protection = _protection_for(address, resource_type)
        if protection is None:
            continue
        findings.append(Finding(address=address, actions=actions,
                                protection=protection,
                                resource_type=resource_type))
    return findings


def transport_flag_state(plan_json: Dict[str, Any]) -> Dict[str, str]:
    """Flag values as planned; ``<absent>`` when the variable is not set."""
    variables = plan_json.get("variables") or {}
    if not isinstance(variables, dict):
        variables = {}
    state: Dict[str, str] = {}
    for name in TRANSPORT_FLAGS:
        entry = variables.get(name)
        if not isinstance(entry, dict) or "value" not in entry:
            state[name] = "<absent>"
            continue
        value = entry.get("value")
        if isinstance(value, bool):
            state[name] = "true" if value else "false"
        else:
            state[name] = str(value).lower()
    return state


def _flag_problems(flags: Dict[str, str]) -> List[str]:
    problems: List[str] = []
    for name, expected in TRANSPORT_FLAG_EXPECTED.items():
        if flags.get(name) != expected:
            problems.append(name)
    return problems


def evaluate_plan(
    plan_json: Dict[str, Any],
    teardown_intent: Optional[str] = None,
    *,
    protected_names: Optional[List[str]] = None,
    plan_sha256: Optional[str] = None,
) -> GuardDecision:
    """Decide whether a plan may proceed (fail closed on doubt)."""
    shape_error = validate_plan_shape(plan_json)
    if shape_error:
        return GuardDecision(
            safe=False, code="PLAN_SHAPE_INVALID",
            message=f"refusing to judge the plan: {shape_error}",
            plan_sha256=plan_sha256,
        )

    intent, intent_error = _validated_intent(teardown_intent)
    if intent_error:
        return GuardDecision(
            safe=False, code="TEARDOWN_INTENT_INVALID",
            message=f"invalid --shared-teardown-intent: {intent_error}",
            plan_sha256=plan_sha256,
        )

    findings = collect_findings(plan_json)
    if protected_names:
        lowered = {n.lower() for n in protected_names}
        for change in plan_json.get("resource_changes") or []:
            actions = tuple((change.get("change") or {}).get("actions") or [])
            if not any(a in actions for a in DESTRUCTIVE_ACTIONS):
                continue
            address = str(change.get("address") or "")
            if any(name in address.lower() for name in lowered):
                if not any(f.address == address for f in findings):
                    findings.append(Finding(
                        address=address, actions=actions,
                        protection="explicit:protected_name",
                        resource_type=str(change.get("type") or "")))

    flags = transport_flag_state(plan_json)
    if not findings:
        return GuardDecision(
            safe=True, code="NO_SHARED_DESTROY",
            message="plan deletes/replaces no shared infrastructure",
            transport_flags=flags, plan_sha256=plan_sha256,
        )

    addresses = ", ".join(sorted(_safe(f.address) for f in findings))
    problems = _flag_problems(flags)
    if intent is None:
        if problems:
            return GuardDecision(
                safe=False, code="MISSING_OR_FALSE_TRANSPORT_FLAG",
                message=(
                    "plan would destroy shared infrastructure while transport "
                    f"flag(s) are not set to their managed value: "
                    f"{', '.join(problems)}. A managed installation must set "
                    "them explicitly; a missing flag is not a teardown request. "
                    "Blocked: " + addresses),
                findings=tuple(findings), transport_flags=flags,
                plan_sha256=plan_sha256,
            )
        return GuardDecision(
            safe=False, code="SHARED_DESTROY_WITHOUT_INTENT",
            message=(
                "plan deletes/replaces shared infrastructure without an "
                "explicit teardown intent (--shared-teardown-intent <ref>). "
                "Blocked: " + addresses),
            findings=tuple(findings), transport_flags=flags,
            plan_sha256=plan_sha256,
        )

    return GuardDecision(
        safe=True, code="SHARED_TEARDOWN_AUTHORIZED",
        message=(
            f"shared teardown explicitly authorized by {intent!r}"
            + (f" for plan {plan_sha256}" if plan_sha256 else "")
            + ": " + addresses),
        findings=tuple(findings), transport_flags=flags,
        teardown_intent=intent, plan_sha256=plan_sha256,
    )
