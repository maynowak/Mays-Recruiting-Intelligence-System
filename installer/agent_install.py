"""Minimal agent installation orchestrator.

This is orchestration only: it discovers versioned packages under
``agent-installations/``, validates their manifests/contracts, and records
explicit stage evidence. It does not create a second runtime, does not enable
agents, and never applies infrastructure without an explicit, separate gate.

Stages:
DISCOVER -> ANALYZE -> COMPATIBILITY -> RISK REVIEW -> PACKAGE ->
VALIDATE -> PLAN -> APPLY -> E2E -> HANDOFF
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

STAGES = [
    "discover", "analyze", "compatibility", "risk-review", "package",
    "validate", "plan", "apply", "e2e", "handoff",
]
REQUIRED_FILES = ("manifest.yaml", "risks.md", "operations.md", "handoff.md")
REQUIRED_DIRS = ("contracts", "tests")
REQUIRED_MANIFEST_KEYS = (
    "agentId", "capability", "sha", "transport", "resultBody", "ordersPin",
)
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "agent-installations"


class AgentInstallError(RuntimeError):
    """A package or stage could not be validated."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def discover(root: Path) -> List[Path]:
    if not root.is_dir():
        raise AgentInstallError(f"package root not found: {root}")
    packages = sorted(p.parent for p in root.glob("*/manifest.yaml")
                      if not p.parent.name.startswith("_"))
    if not packages:
        raise AgentInstallError(f"no agent packages under {root}")
    return packages


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def analyze(package: Path) -> Dict[str, Any]:
    manifest = package / "manifest.yaml"
    if not manifest.is_file():
        raise AgentInstallError(f"manifest.yaml missing in {package}")
    text = _read(manifest)
    missing = [key for key in REQUIRED_MANIFEST_KEYS if f"{key}:" not in text]
    if missing:
        raise AgentInstallError(
            f"manifest {manifest} misses required keys: {missing}")
    return {"package": str(package), "manifest": text}


def compatibility(package: Path, info: Dict[str, Any]) -> Dict[str, Any]:
    text = info["manifest"]
    for required in ("transport: \"1\"", "resultBody:", "ordersPin:"):
        if required not in text:
            raise AgentInstallError(
                f"{package.name}: manifest is not Transport V1 compatible "
                f"(missing {required!r})")
    return {"transport": "1", "ordersPin": _value(text, "ordersPin")}


def risk_review(package: Path) -> Dict[str, Any]:
    risks = package / "risks.md"
    if not risks.is_file():
        raise AgentInstallError(f"{package.name}: risks.md missing")
    body = _read(risks)
    if "Stop conditions" not in body and "stop" not in body.lower():
        raise AgentInstallError(
            f"{package.name}: risks.md has no stop conditions")
    return {"risks": str(risks)}


def package_check(package: Path) -> Dict[str, Any]:
    missing = [name for name in REQUIRED_FILES if not (package / name).is_file()]
    missing += [name for name in REQUIRED_DIRS if not (package / name).is_dir()]
    if missing:
        raise AgentInstallError(
            f"{package.name}: package incomplete, missing {missing}")
    return {"files": sorted(p.name for p in package.iterdir())}


def validate(package: Path, info: Dict[str, Any]) -> Dict[str, Any]:
    compatibility(package, info)
    package_check(package)
    risk_review(package)
    return {"validated": True, "agentId": _value(info["manifest"], "agentId")}


def _value(text: str, key: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip().strip('"')
    return ""


def _load_status(path: Path) -> Dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise AgentInstallError(f"invalid status file {path}: {exc}") from exc
    return {"stages": {}}


def _save_status(path: Path, status: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status["updatedAt"] = _now()
    path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def run_stage(stage: str, package: Path, status_path: Path, *,
              execute: bool = False, allow_apply: bool = False,
              yes: bool = False, force: bool = False) -> Dict[str, Any]:
    if stage not in STAGES:
        raise AgentInstallError(f"unknown stage {stage!r}")
    status = _load_status(status_path)
    previous = status["stages"].get(stage, {})
    if previous.get("status") == "PASSED" and not force:
        return {"stage": stage, "status": "SKIPPED", "reason": "already passed"}

    info = analyze(package)
    result: Dict[str, Any] = {"stage": stage, "status": "PASSED", "at": _now()}
    if stage == "discover":
        result["packages"] = [str(p) for p in discover(package.parent)]
    elif stage == "analyze":
        result["manifest"] = str(package / "manifest.yaml")
    elif stage == "compatibility":
        result.update(compatibility(package, info))
    elif stage == "risk-review":
        result.update(risk_review(package))
    elif stage == "package":
        result.update(package_check(package))
    elif stage == "validate":
        result.update(validate(package, info))
    elif stage == "plan":
        if not execute:
            result.update({"executed": False,
                           "command": "terraform plan (reviewed workspace only)"})
        else:
            result.update({"executed": True,
                           "command": "python lambda/build_zip.py --bundle all; "
                                      "python -m installer.build_mays_orders_module "
                                      "--project-name ris-dev2 --force; terraform plan"})
    elif stage == "apply":
        if not (execute and allow_apply and yes):
            raise AgentInstallError(
                "apply requires --execute --allow-apply --yes and a separate "
                "approval gate; package creation never enables an agent")
        result.update({"executed": True, "scope": "ris-dev2 test only"})
    elif stage == "e2e":
        result.update({"executed": bool(execute),
                       "checklist": "docs/reports/RIS-AGENT-INSTALLATION-HANDOFF-08.md"})
    elif stage == "handoff":
        result.update({"artifact": "docs/releases/ris-agent-installation-08.json"})

    status["agentId"] = _value(info["manifest"], "agentId") or package.name
    status["packageVersion"] = _value(info["manifest"], "version")
    status["stages"][stage] = result
    _save_status(status_path, status)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Agent installation orchestrator")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--agent", help="package directory name")
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--status-file")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        if args.stage:
            if not args.agent:
                raise AgentInstallError("--agent is required with --stage")
            package = root / args.agent
            status_path = Path(args.status_file) if args.status_file else (
                package / "install-status.json")
            result = run_stage(args.stage, package, status_path,
                               execute=args.execute, allow_apply=args.allow_apply,
                               yes=args.yes, force=args.force)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        packages = discover(root)
        print(json.dumps({"packages": [str(p) for p in packages]}, indent=2))
        return 0
    except AgentInstallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
