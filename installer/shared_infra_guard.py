"""Shared-infrastructure guard for Terraform plan/apply.

Purpose: a missing or contradictory transport flag must never be read as a
teardown request. `enable_agent_transport` and `orders_agent_result_enabled`
gate the shared dispatch and result transport. Their Terraform defaults are
`false`, so a plan without those variables destroys the whole transport when
the live state still contains it.

This module is pure: it inspects Terraform plan JSON and returns a decision.
It never calls AWS and never changes resources. The installer wires it into
`plan` and `apply`; a teardown is allowed only with an explicit
``shared_teardown_intent`` (a ticket/approval reference).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Flags that gate shared transport. False/absent must never mean "teardown".
TRANSPORT_FLAGS = (
    "enable_agent_transport",
    "orders_agent_result_enabled",
)

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
)

#: Top-level resource types that are shared even outside a known module.
SHARED_RESOURCE_TYPES = (
    "aws_sqs_queue",
    "aws_sqs_queue_policy",
    "aws_lambda_function",
    "aws_lambda_event_source_mapping",
    "aws_dynamodb_table",
    "aws_secretsmanager_secret",
    "aws_secretsmanager_secret_version",
    "aws_cognito_user_pool",
    "aws_cognito_user_pool_client",
    "aws_apigatewayv2_api",
    "aws_cloudfront_distribution",
)

#: Address/name markers that identify shared agent infrastructure.
SHARED_NAME_MARKERS = (
    "-agent-dispatch",
    "-agent-results",
    "work-items",
    "mays-orders",
    "-agent-catalog",
    "entitlements",
    "api-profiles",
)

DESTRUCTIVE_ACTIONS = ("delete",)


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
            "authorizedTeardown": self.authorized_teardown,
        }


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


def collect_findings(plan_json: Dict[str, Any]) -> List[Finding]:
    """Shared resources that the plan deletes or replaces."""
    findings: List[Finding] = []
    for change in plan_json.get("resource_changes") or []:
        actions = tuple(change.get("change", {}).get("actions") or [])
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
    state: Dict[str, str] = {}
    for name in TRANSPORT_FLAGS:
        entry = variables.get(name)
        if not isinstance(entry, dict) or "value" not in entry:
            state[name] = "<absent>"
        else:
            state[name] = "true" if entry.get("value") is True else (
                "false" if entry.get("value") is False else str(entry.get("value")))
    return state


def _flags_imply_teardown(flags: Dict[str, str]) -> List[str]:
    return [name for name, value in flags.items() if value != "true"]


def evaluate_plan(
    plan_json: Dict[str, Any],
    teardown_intent: Optional[str] = None,
    *,
    protected_names: Optional[List[str]] = None,
) -> GuardDecision:
    """Decide whether a plan may proceed.

    - no shared delete/replace -> safe
    - shared delete/replace without an intent -> unsafe (fail closed)
    - shared delete/replace with an explicit intent -> safe, but recorded
    """
    findings = collect_findings(plan_json)
    if protected_names:
        lowered = {n.lower() for n in protected_names}
        for change in plan_json.get("resource_changes") or []:
            actions = tuple(change.get("change", {}).get("actions") or [])
            if not any(a in actions for a in DESTRUCTIVE_ACTIONS):
                continue
            address = str(change.get("address") or "")
            if any(name in address.lower() for name in lowered):
                if not any(f.address == address for f in findings):
                    findings.append(Finding(address=address, actions=actions,
                                            protection="explicit:protected_name",
                                            resource_type=str(change.get("type") or "")))

    flags = transport_flag_state(plan_json)
    intent = (teardown_intent or "").strip() or None

    if not findings:
        return GuardDecision(
            safe=True, code="NO_SHARED_DESTROY",
            message="plan deletes/replaces no shared infrastructure",
            transport_flags=flags,
        )

    addresses = ", ".join(sorted(f.address for f in findings))
    bad_flags = _flags_imply_teardown(flags)
    if intent is None:
        if bad_flags:
            return GuardDecision(
                safe=False, code="MISSING_OR_FALSE_TRANSPORT_FLAG",
                message=(
                    "plan would destroy shared infrastructure while transport "
                    f"flag(s) are false/absent: {', '.join(bad_flags)}. "
                    "A managed installation must set them to true; a missing "
                    "flag is not a teardown request. Blocked: " + addresses),
                findings=tuple(findings), transport_flags=flags,
            )
        return GuardDecision(
            safe=False, code="SHARED_DESTROY_WITHOUT_INTENT",
            message=(
                "plan deletes/replaces shared infrastructure without an "
                "explicit teardown intent (--shared-teardown-intent <ref>). "
                "Blocked: " + addresses),
            findings=tuple(findings), transport_flags=flags,
        )

    return GuardDecision(
        safe=True, code="SHARED_TEARDOWN_AUTHORIZED",
        message=(
            f"shared teardown explicitly authorized by {intent!r}: "
            + addresses),
        findings=tuple(findings), transport_flags=flags,
        teardown_intent=intent,
    )
