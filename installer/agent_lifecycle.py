"""Agent lifecycle orchestration (local, safe by default).

Actions operate on a lifecycle state file and an optional JSON inventory. They
never call AWS: the module produces plans/impact/audit evidence and, with
``--execute``, updates only the local lifecycle state. AWS/Terraform changes
remain a separate, reviewed operation.

No action implicitly runs PURGE. PURGE requires the exact agent id and
``--execute``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "agent-installations"
ACTIONS = (
    "INSTALL", "UPDATE", "DISABLE", "ENABLE", "DETACH_PARTNER",
    "UNINSTALL", "PURGE", "STATUS", "VERIFY",
)
REQUIRED_LIFECYCLE_MARKERS = (
    "agentId:", "sharedResources:", "exclusiveResources:",
    "partnerBindings:", "uninstall:", "retention:",
)


class LifecycleError(RuntimeError):
    """Invalid package, state or action."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path) -> str:
    # utf-8-sig tolerates a BOM (e.g. PowerShell Set-Content -Encoding utf8).
    return path.read_text(encoding="utf-8-sig")


def load_lifecycle(package: Path) -> str:
    if package.name == "_template":
        raise LifecycleError(
            "_template is a scaffold, not a deployable agent")
    path = package / "lifecycle.yaml"
    if not path.is_file():
        raise LifecycleError(f"lifecycle.yaml missing in {package}")
    text = _read(path)
    missing = [m for m in REQUIRED_LIFECYCLE_MARKERS if m not in text]
    if missing:
        raise LifecycleError(
            f"lifecycle.yaml misses required sections: {missing}")
    return text


def _manifest_agent(package: Path) -> str:
    manifest = package / "manifest.yaml"
    if not manifest.is_file():
        raise LifecycleError(f"manifest.yaml missing in {package}")
    for line in _read(manifest).splitlines():
        if line.strip().startswith("agentId:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise LifecycleError("manifest.yaml has no agentId")


def _shared_resources(package: Path) -> List[str]:
    lines = _read(package / "lifecycle.yaml").splitlines()
    resources: List[str] = []
    in_shared = False
    for line in lines:
        stripped = line.strip()
        if stripped == "sharedResources:":
            in_shared = True
            continue
        if in_shared:
            if stripped.endswith(":") and not stripped.startswith("-"):
                break
            if stripped.startswith("- "):
                resources.append(stripped[2:].strip())
    return resources


def _detach_types(package: Path) -> List[str]:
    """Binding types with deleteOnDetach: true (simple block scan)."""
    lines = _read(package / "lifecycle.yaml").splitlines()
    result: List[str] = []
    current: Optional[str] = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- type:"):
            current = stripped.split(":", 1)[1].strip()
        elif current and stripped.startswith("deleteOnDetach: true"):
            result.append(current)
    return result


def _load_state(path: Path, agent: str) -> Dict[str, Any]:
    if path.is_file():
        try:
            state = json.loads(_read(path))
        except ValueError as exc:
            raise LifecycleError(f"invalid lifecycle state {path}: {exc}") from exc
    else:
        state = {}
    state.setdefault("agentId", agent)
    state.setdefault("status", "installed")
    state.setdefault("catalog", True)
    state.setdefault("version", "1.0.0")
    state.setdefault("history", [])
    return state


def _load_inventory(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {"_provided": False, "agents": {}, "partnerBindings": [],
                "openOrders": [], "sharedResources": [], "retailOrders": 0}
    try:
        value = json.loads(_read(path))
    except (OSError, ValueError) as exc:
        raise LifecycleError(f"invalid inventory {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleError("inventory must be a JSON object")
    # An inventory without an explicit openOrders list is not evidence of
    # "nothing is open" — it is missing evidence. Treat it as not provided.
    value["_provided"] = "openOrders" in value
    return value


def _bindings(inventory: Dict[str, Any], agent: str) -> List[Dict[str, Any]]:
    return [dict(b) for b in inventory.get("partnerBindings", [])
            if str(b.get("agentId")) == agent]


def _field(text: str, key: str) -> Optional[str]:
    """First ``key: value`` scalar in a simple YAML block."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(key + ":"):
            return stripped.split(":", 1)[1].strip().strip('"')
    return None


def _catalog_row_present(inventory: Dict[str, Any], agent: str) -> bool:
    record = (inventory.get("agents") or {}).get(agent) or {}
    status = str(record.get("catalog") or "").strip().upper()
    return status in ("ACTIVE", "INACTIVE", "BLOCKED")


def _warnings(action: str, package: Path, inventory: Dict[str, Any],
              agent: str) -> List[str]:
    lifecycle = _read(package / "lifecycle.yaml")
    warnings: List[str] = []
    # Truthful contract: the worker never reads the catalog.
    if action in ("DISABLE", "ENABLE", "UNINSTALL", "INSTALL", "VERIFY"):
        warnings.append("catalog_is_not_a_worker_execution_gate")
    if action in ("DISABLE", "UNINSTALL"):
        warnings.append("entitlement_withdraw_required_to_stop_dispatch")
    if action == "DISABLE":
        warnings.append("catalog_status_change_requires_terraform_plan_apply")
    visibility = (_field(lifecycle, "visibility") or "").upper()
    if action == "INSTALL" and not _catalog_row_present(inventory, agent):
        warnings.append("catalog_row_absent_dispatch_only")
    if visibility == "ABSENT":
        warnings.append("package_declares_no_catalog_visibility")
    if action in ("DISABLE", "UNINSTALL") and \
            "blockNewOrdersPending" in lifecycle:
        warnings.append("block_new_orders_not_enforced_in_reader")
    if action == "UNINSTALL":
        warnings.append("inventory_must_come_from_read_only_order_scan")
    return warnings


def _retention_retains(lifecycle: str) -> bool:
    """True only when orders, work items and results are all ``retain``."""
    in_block = False
    seen: Dict[str, str] = {}
    for line in lifecycle.splitlines():
        stripped = line.strip()
        if stripped == "retention:":
            in_block = True
            continue
        if in_block:
            if stripped and not line.startswith((" ", "\t")):
                break
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                seen[key.strip()] = value.strip().lower()
    return all(seen.get(k) == "retain" for k in
               ("orders", "workItems", "results"))


def _impact(action: str, package: Path, state: Dict[str, Any],
            inventory: Dict[str, Any], agent: str) -> Dict[str, Any]:
    lifecycle = _read(package / "lifecycle.yaml")
    shared = _shared_resources(package)
    detach_types = _detach_types(package)
    bindings = _bindings(inventory, agent)
    removing_actions = ("DETACH_PARTNER", "UNINSTALL", "PURGE")
    removable = [b for b in bindings
                 if b.get("managedBy") == "ris"
                 and b.get("type") in detach_types] \
        if action in removing_actions else []
    entitlements = [b for b in bindings
                    if b.get("managedBy") == "ris"
                    and b.get("type") == "entitlement"]
    withdraw_actions = ("DISABLE", "DETACH_PARTNER", "UNINSTALL", "PURGE")
    pending = [b for b in bindings if b.get("managedBy") == "external"]
    open_orders = [o for o in inventory.get("openOrders", [])
                   if str(o.get("agentId")) == agent]
    catalog_before = state.get("catalog", True)
    catalog_after = {
        "DISABLE": False, "UNINSTALL": False, "DETACH_PARTNER": False,
        "ENABLE": True, "INSTALL": True, "PURGE": False,
    }.get(action, catalog_before)
    partner_apps = [b for b in bindings
                    if b.get("type") == "partner-application"]
    open_results = [r for r in inventory.get("openResults", [])
                    if str(r.get("agentId")) == agent]
    agent_record = (inventory.get("agents") or {}).get(agent) or {}
    allowlist = agent_record.get("allowlist") or []
    entitlement_state = agent_record.get("entitlement") or (
        "present" if any(b.get("type") == "entitlement" for b in bindings)
        else "absent")
    return {
        "agentId": agent,
        "action": action,
        "catalogBefore": catalog_before,
        "catalogAfter": catalog_after,
        "bindingsToRemove": [{"type": b.get("type"), "id": b.get("id")}
                             for b in removable],
        "entitlementsToWithdraw": [
            {"id": b.get("id")} for b in entitlements
        ] if action in withdraw_actions else [],
        "entitlementWithdrawRequired": bool(entitlements)
        and action in withdraw_actions,
        "partnerApplicationsAffected": [
            {"id": b.get("id"), "action": "retained"} for b in partner_apps],
        "externalPartnerPending": [
            {"type": b.get("type"), "id": b.get("id")} for b in pending],
        "agentAllowlist": {"entries": list(allowlist),
                           "source": "inventory"},
        "entitlementStatus": entitlement_state,
        "openOrders": [{"orderId": o.get("orderId"),
                        "status": o.get("status")} for o in open_orders],
        "openResults": [{"orderId": r.get("orderId"),
                         "status": r.get("status")} for r in open_results],
        "sharedResourcesRetained": shared,
        "historyRetained": _retention_retains(lifecycle),
        "retailOrdersAffected": False,
        "secretValueRead": False,
        "irreversible": action == "PURGE",
        "executionGates": {
            "worker": "entitlement+registry",
            "apiIngress": "catalog+entitlement",
            "orderDispatch": "entitlement+registry",
            "catalogSource": "terraform",
            "catalogAloneBlocksExecution": False,
        },
    }


def _notifications(action: str, impact: Dict[str, Any]) -> List[str]:
    """Target only components with a real impact (no broadcast)."""
    targets: List[str] = []
    if action in ("INSTALL", "UPDATE", "DISABLE", "ENABLE", "UNINSTALL",
                  "DETACH_PARTNER"):
        targets.append("ris-runtime-team")
    if action in ("DISABLE", "UNINSTALL") or impact["openOrders"] \
            or impact["openResults"]:
        targets.append("operations")
    if impact["externalPartnerPending"] \
            or impact["partnerApplicationsAffected"]:
        targets.append("partner-team")
    if action in ("DETACH_PARTNER", "UNINSTALL", "PURGE"):
        targets.append("security-privacy")
    return targets


def removal_impact(action: str, package: Path, state: Dict[str, Any],
                   inventory: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone removal-impact report (Phase 3 of LIFECYCLE-12)."""
    agent = _manifest_agent(package)
    impact = _impact(action, package, state, inventory, agent)
    return {
        "schemaVersion": "1.0",
        "agentId": agent,
        "action": action,
        "generatedAt": _now(),
        "partnerApplications": impact["partnerApplicationsAffected"],
        "remainingExternalReferences": impact["externalPartnerPending"],
        "agentAllowlist": impact["agentAllowlist"],
        "entitlementStatus": impact["entitlementStatus"],
        "entitlementsToWithdraw": impact["entitlementsToWithdraw"],
        "entitlementWithdrawRequired": impact["entitlementWithdrawRequired"],
        "openOrders": impact["openOrders"],
        "openResults": impact["openResults"],
        "notifications": _notifications(action, impact),
        "pendingExternalChanges": [
            {"id": p.get("id"), "type": p.get("type"),
             "status": "PENDING"} for p in impact["externalPartnerPending"]],
        "retained": {
            "sharedResources": impact["sharedResourcesRetained"],
            "history": impact["historyRetained"],
        },
        "retailOrdersAffected": False,
        "secretValueRead": False,
    }


def _blockers(action: str, state: Dict[str, Any], impact: Dict[str, Any],
              purge_confirm: Optional[str], agent: str,
              inventory: Dict[str, Any],
              purge_grace_days: int = 0) -> List[str]:
    blockers: List[str] = []
    if action in ("DISABLE", "DETACH_PARTNER", "UNINSTALL") \
            and not inventory.get("_provided"):
        blockers.append("inventory_required_for_impact")
    if action == "UNINSTALL" and impact["openOrders"]:
        blockers.append("open_orders_must_drain_or_cancel")
    if action == "PURGE":
        if purge_confirm != agent:
            blockers.append("purge_confirmation_required")
        if state.get("status") not in ("uninstalled", "purged"):
            blockers.append("uninstall_required_before_purge")
        if not inventory.get("_provided"):
            blockers.append("inventory_required_for_impact")
        if impact["openOrders"]:
            blockers.append("open_orders_must_drain_or_cancel")
        uninstalled_at = state.get("uninstalledAt")
        if purge_grace_days > 0:
            if not uninstalled_at:
                blockers.append("purge_grace_window_not_started")
            else:
                from datetime import timedelta
                started = datetime.fromisoformat(uninstalled_at)
                if datetime.now(timezone.utc) < started + timedelta(
                        days=purge_grace_days):
                    blockers.append("purge_grace_window_not_elapsed")
        if state.get("catalog"):
            blockers.append("catalog_must_be_inactive_before_purge")
    return blockers


def _steps(action: str) -> List[str]:
    return {
        "INSTALL": ["validate package", "enable catalog visibility",
                    "attach RIS-managed agent bindings", "verify discovery"],
        "UPDATE": ["validate package/version", "keep catalog state",
                   "record source SHA"],
        "DISABLE": ["withdraw agent-scoped entitlements (stops reader and dispatch)",
                    "reader rejects new orders with 403 before persist",
                    "set catalog status INACTIVE via Terraform plan/apply",
                    "keep in-flight work and history"],
        "ENABLE": ["re-grant agent-scoped entitlements",
                   "set catalog status ACTIVE via Terraform plan/apply",
                   "verify discovery"],
        "DETACH_PARTNER": ["remove agent-specific RIS bindings",
                           "keep shared profile/credential/application",
                           "mark external partner references PENDING"],
        "UNINSTALL": ["withdraw agent-scoped entitlements (reader + worker block)",
                      "set catalog INACTIVE via Terraform",
                      "drain in-flight work",
                      "retain history",
                      "verify no stranded order"],
        "PURGE": ["require explicit confirmation", "delete lifecycle-local state",
                  "never delete orders/work/results/shared resources"],
        "STATUS": ["read state and inventory"],
        "VERIFY": ["compare catalog/state", "check open orders",
                   "check shared resources and pending partner confirmations"],
    }.get(action, [])


def _identity_ok(package: Path, agent: str) -> None:
    declared = _field(_read(package / "lifecycle.yaml"), "agentId")
    if declared and declared != agent:
        raise LifecycleError(
            f"lifecycle.yaml agentId {declared!r} does not match manifest {agent!r}")


def _digest(data: Dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def plan(action: str, package: Path, state: Dict[str, Any],
         inventory: Dict[str, Any], purge_confirm: Optional[str] = None,
         purge_grace_days: int = 0) -> Dict[str, Any]:
    if action not in ACTIONS:
        raise LifecycleError(f"unsupported action {action!r}")
    agent = _manifest_agent(package)
    load_lifecycle(package)
    _identity_ok(package, agent)
    impact = _impact(action, package, state, inventory, agent)
    blockers = _blockers(action, state, impact, purge_confirm, agent, inventory,
                         purge_grace_days)
    return {
        "schemaVersion": "1.0",
        "agentId": agent,
        "action": action,
        "plannedAt": _now(),
        "steps": _steps(action),
        "impact": impact,
        "blockers": blockers,
        "warnings": _warnings(action, package, inventory, agent),
        "removalImpact": removal_impact(action, package, state, inventory),
        "sharedInfrastructureTouched": False,
        "secretsIncluded": False,
    }


def _audit(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _apply(action: str, state: Dict[str, Any], plan_doc: Dict[str, Any]) -> None:
    impact = plan_doc["impact"]
    state["catalog"] = impact["catalogAfter"]
    state["updatedAt"] = _now()
    state.setdefault("history", []).append({
        "action": action, "at": _now(),
        "openOrders": len(impact["openOrders"]),
        "removedBindings": len(impact["bindingsToRemove"]),
    })
    if action == "INSTALL":
        state["status"] = "installed"
    elif action == "UPDATE":
        state["status"] = "installed"
    elif action == "DISABLE":
        state["status"] = "disabled"
    elif action == "ENABLE":
        state["status"] = "installed"
    elif action == "DETACH_PARTNER":
        state["status"] = "detached"
    elif action == "UNINSTALL":
        state["status"] = "uninstalled"
        state["uninstalledAt"] = _now()
    elif action == "PURGE":
        state["status"] = "purged"
        state["purgedAt"] = _now()
    elif action == "VERIFY":
        state["lastVerifiedAt"] = _now()


def run(action: str, package: Path, *, execute: bool = False,
        inventory_path: Optional[Path] = None,
        state_path: Optional[Path] = None,
        audit_path: Optional[Path] = None,
        purge_confirm: Optional[str] = None,
        purge_grace_days: int = 0,
        actor: Optional[str] = None,
        approval: Optional[str] = None,
        reason: Optional[str] = None) -> Dict[str, Any]:
    action = action.upper().replace("-", "_")
    state_file = state_path or (package / ".lifecycle-state.json")
    state = _load_state(state_file, _manifest_agent(package))
    inventory = _load_inventory(inventory_path)
    plan_doc = plan(action, package, state, inventory, purge_confirm,
                    purge_grace_days)
    plan_doc["dryRun"] = not execute
    plan_doc["status"] = "PLANNED"
    plan_doc["evidence"] = {
        "inventoryDigest": _digest(
            {k: v for k, v in inventory.items() if k != "_provided"}),
        "inventoryProvided": bool(inventory.get("_provided")),
        "packageVersion": state.get("version"),
    }

    already = (action == "UNINSTALL"
               and state.get("status") in ("uninstalled", "purged"))
    if already:
        plan_doc["idempotent"] = True
        plan_doc["result"] = "already_uninstalled"

    if action in ("STATUS", "VERIFY"):
        plan_doc["status"] = "REPORTED"
    elif execute:
        if plan_doc["blockers"]:
            plan_doc["status"] = "BLOCKED"
        elif already:
            # Idempotent: no second state write, no reset grace window.
            plan_doc["status"] = "APPLIED"
        else:
            _apply(action, state, plan_doc)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            plan_doc["status"] = "APPLIED"
    else:
        plan_doc["status"] = "DRY_RUN"

    audit = audit_path or (package / ".lifecycle-audit.jsonl")
    _audit(audit, {
        "at": _now(), "agentId": plan_doc["agentId"], "action": action,
        "status": plan_doc["status"], "dryRun": plan_doc["dryRun"],
        "actor": actor, "approval": approval, "reason": reason,
        "catalogAfter": plan_doc["impact"]["catalogAfter"],
        "removedBindings": len(plan_doc["impact"]["bindingsToRemove"]),
        "openOrders": len(plan_doc["impact"]["openOrders"]),
        "pendingPartner": len(plan_doc["impact"]["externalPartnerPending"]),
        "inventoryDigest": plan_doc["evidence"]["inventoryDigest"],
        "inventoryProvided": plan_doc["evidence"]["inventoryProvided"],
        "idempotent": plan_doc.get("idempotent", False),
        "blockers": plan_doc["blockers"],
    })

    result_path = state_file.with_suffix(".result.json")
    result_path.write_text(
        json.dumps({"plan": plan_doc, "state": state}, indent=2, sort_keys=True)
        + "\n", encoding="utf-8")
    plan_doc["resultManifest"] = str(result_path)
    return plan_doc


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Agent lifecycle (local, safe)")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--agent", required=True)
    parser.add_argument("--action", required=True,
                        choices=[a.lower() for a in ACTIONS]
                        + [a.lower().replace("_", "-") for a in ACTIONS])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--inventory")
    parser.add_argument("--state-file")
    parser.add_argument("--audit-log")
    parser.add_argument("--purge-confirm")
    parser.add_argument("--purge-grace-days", type=int, default=0,
                        help="minimum days between UNINSTALL and PURGE")
    parser.add_argument("--actor", help="operator identity for the audit log")
    parser.add_argument("--approval", help="approval/ticket reference")
    parser.add_argument("--reason", help="short reason for the action")
    parser.add_argument("--impact-report",
                        help="write the removal-impact report as JSON here")
    args = parser.parse_args(argv)
    package = Path(args.root).resolve() / args.agent
    try:
        result = run(args.action, package, execute=args.execute,
                     inventory_path=Path(args.inventory) if args.inventory else None,
                     state_path=Path(args.state_file) if args.state_file else None,
                     audit_path=Path(args.audit_log) if args.audit_log else None,
                     purge_confirm=args.purge_confirm,
                     purge_grace_days=args.purge_grace_days,
                     actor=args.actor, approval=args.approval,
                     reason=args.reason)
        if args.impact_report:
            path = Path(args.impact_report)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(result["removalImpact"], indent=2, sort_keys=True)
                + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] != "BLOCKED" else 2
    except LifecycleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
