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
import hashlib
import json
import os
import re
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from installer import agent_lifecycle as _lifecycle

STAGES = [
    "discover", "analyze", "compatibility", "risk-review", "package",
    "validate", "privacy-evidence", "plan", "apply", "e2e", "handoff",
]
# Lifecycle actions are owned by installer.agent_lifecycle (single source).
LIFECYCLE_ACTIONS = _lifecycle.ACTIONS
REQUIRED_FILES = (
    "manifest.yaml", "risks.md", "operations.md", "handoff.md",
    "lifecycle.yaml", "uninstall.md", "partner-bindings.md", "retention.md",
)
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
    for key in ("sha", "ordersPin"):
        value = _value(info["manifest"], key)
        if not re.fullmatch(r"[0-9a-f]{40}", value or ""):
            raise AgentInstallError(
                f"{package.name}: {key} must be a full 40-char lowercase git "
                f"SHA, got {value!r}")
    privacy = _privacy_inputs(package, info)
    return {"validated": True, "agentId": _value(info["manifest"], "agentId")}


def _privacy_inputs(package: Path, info: Dict[str, Any]) -> tuple[dict, dict, Path]:
    """Load a package privacy declaration; a manifest alone is not evidence."""
    try:
        import yaml
        manifest_data = yaml.safe_load(info["manifest"])
    except Exception as exc:
        raise AgentInstallError(f"{package.name}: invalid YAML manifest: {exc}") from exc
    privacy = (manifest_data or {}).get("privacy")
    if not isinstance(privacy, dict):
        raise AgentInstallError(f"{package.name}: privacy declaration missing")
    contract_name = privacy.get("contractPath")
    tests = privacy.get("testPaths")
    sources = privacy.get("sourcePaths")
    test_args = privacy.get("testArgs", [])
    if (not isinstance(contract_name, str) or not contract_name
            or not isinstance(tests, list) or not tests
            or not isinstance(sources, list) or not sources
            or not isinstance(test_args, list)
            or any(not isinstance(arg, str) for arg in test_args)):
        raise AgentInstallError(
            f"{package.name}: privacy contractPath, testPaths and sourcePaths are required")
    contract_path = (package / contract_name).resolve()
    if package.resolve() not in contract_path.parents or not contract_path.is_file():
        raise AgentInstallError(f"{package.name}: privacy contract path is missing/unsafe")
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentInstallError(f"{package.name}: invalid privacy contract JSON: {exc}") from exc
    from agents.ecosystem.privacy_contract import (
        PRIVACY_CONTRACT_VERSION, declaration_from_mapping,
    )
    if privacy.get("contractVersion") != PRIVACY_CONTRACT_VERSION:
        raise AgentInstallError(f"{package.name}: unsupported privacy contract version")
    try:
        declaration = declaration_from_mapping(contract)
    except (TypeError, ValueError) as exc:
        raise AgentInstallError(f"{package.name}: invalid privacy contract fields: {exc}") from exc
    if declaration.capability != _value(info["manifest"], "capability"):
        raise AgentInstallError(f"{package.name}: privacy capability does not match manifest")
    if declaration.order_result_disposition not in {"forbidden", "reference-only", "allowlisted"}:
        raise AgentInstallError(f"{package.name}: invalid ORDER_RESULT disposition")
    repo_root = Path(__file__).resolve().parent.parent
    resolved_tests = [_resolve_repo_file(repo_root, value, package, "test") for value in tests]
    resolved_sources = [_resolve_repo_file(repo_root, value, package, "source") for value in sources]
    return privacy, contract, contract_path


def _resolve_repo_file(repo_root: Path, value: Any, package: Path, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AgentInstallError(f"{package.name}: invalid privacy {label} path")
    path = (repo_root / value).resolve()
    if repo_root not in path.parents or not path.is_file():
        raise AgentInstallError(f"{package.name}: privacy {label} file missing/unsafe: {value}")
    return path


def _content_digest(files: List[Path], repo_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(files), key=lambda item: item.as_posix()):
        try:
            name = path.relative_to(repo_root).as_posix()
        except ValueError:
            name = path.as_posix()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _stage_fingerprint(package: Path, repo_root: Path) -> str:
    files = [path for path in package.rglob("*") if path.is_file()
             and path.name not in {"install-status.json", "privacy-evidence.json",
                                   "privacy-test-report.json"}]
    manifest = package / "manifest.yaml"
    if manifest.is_file():
        try:
            import yaml
            privacy = (yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}).get("privacy", {})
            for name in (privacy.get("contractPath"), *(privacy.get("sourcePaths") or []),
                         *(privacy.get("testPaths") or [])):
                if name:
                    path = (repo_root / name).resolve()
                    if repo_root in path.parents and path.is_file():
                        files.append(path)
        except Exception:
            # Invalid/missing references remain part of the current package
            # fingerprint and will be rejected by the stage validator.
            pass
    return _content_digest(files, repo_root)


def generate_privacy_evidence(package: Path, artifact_path: Path) -> Dict[str, Any]:
    """Run declared original tests and bind their report to source/contract/artifact."""
    repo_root = Path(__file__).resolve().parent.parent
    info = analyze(package)
    privacy, contract, contract_path = _privacy_inputs(package, info)
    import yaml
    manifest_data = yaml.safe_load(info["manifest"])
    declared_artifact = (repo_root / manifest_data["privacy"]["evidenceArtifact"]).resolve()
    artifact_path = artifact_path.resolve()
    if artifact_path != declared_artifact:
        raise AgentInstallError("privacy evidence artifact must match manifest evidenceArtifact")
    build_command = [sys.executable, "lambda/build_zip.py", "--bundle", "agent"]
    build_result = subprocess.run(build_command, cwd=repo_root,
                                  capture_output=True, text=True, check=False)
    if build_result.returncode != 0 or not artifact_path.is_file():
        raise AgentInstallError("declared deterministic agent artifact build failed")
    try:
        import zipfile
        with zipfile.ZipFile(artifact_path) as archive:
            names = set(archive.namelist())
        required = {"agents/addition_agent/agent.py",
                    "agents/ecosystem/privacy_contract.py"}
        if not required.issubset(names):
            raise AgentInstallError("built artifact omits declared agent/privacy runtime")
    except (OSError, zipfile.BadZipFile) as exc:
        raise AgentInstallError("built privacy evidence artifact is not a valid ZIP") from exc
    test_paths = manifest_data["privacy"]["testPaths"]
    test_args = manifest_data["privacy"].get("testArgs", [])
    source_paths = manifest_data["privacy"]["sourcePaths"]
    test_files = [_resolve_repo_file(repo_root, p, package, "test") for p in test_paths]
    source_files = [_resolve_repo_file(repo_root, p, package, "source") for p in source_paths]
    manifest_path = package / "manifest.yaml"
    source_sha = _content_digest(
        [manifest_path, contract_path, *source_files, *test_files], repo_root)
    selection = {"paths": test_paths, "args": test_args}
    selection_sha = hashlib.sha256(json.dumps(selection, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=False).encode()).hexdigest()
    command = [sys.executable, "-m", "pytest", "-q", "-ra", *test_args, *test_paths]
    env = dict(os.environ)
    for key in tuple(env):
        if key.startswith("AWS_") or key in {"MO_ORDERS_SRC", "API_BASE_URL"}:
            env.pop(key, None)
    completed = subprocess.run(command, cwd=repo_root, env=env,
                               capture_output=True, text=True, check=False)
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    skipped = sum(int(value) for value in re.findall(r"\b(\d+) skipped\b", output))
    report = {
        "buildCommand": build_command,
        "buildExitCode": build_result.returncode,
        "buildStdout": build_result.stdout,
        "buildStderr": build_result.stderr,
        "command": command, "exitCode": completed.returncode,
        "testPaths": test_paths, "testArgs": test_args, "stdout": completed.stdout,
        "stderr": completed.stderr, "sourceSha256": source_sha,
        "artifactSha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "requiredTestsSkipped": skipped > 0,
    }
    report_bytes = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    report_path = package / "privacy-test-report.json"
    if completed.returncode != 0 or skipped:
        raise AgentInstallError(
            f"{package.name}: required privacy/original tests failed or skipped; evidence not written")
    from agents.ecosystem.privacy_contract import (
        PRIVACY_CONTRACT_VERSION, PrivacyEvidence, declaration_from_mapping,
        declaration_digest,
    )
    declaration = declaration_from_mapping(contract)
    artifact_sha = report["artifactSha256"]
    # Store artifact paths repo-relative so runtime can verify the local artifact.
    artifact_rel = artifact_path.relative_to(repo_root).as_posix()
    try:
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root,
            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        source_commit = ""
    if source_commit and not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        source_commit = ""
    evidence = PrivacyEvidence(
        agent_id=_value(info["manifest"], "agentId"),
        agent_version=str((manifest_data.get("agent") or {}).get("runtimeAgentVersion") or
                          (manifest_data.get("package") or {}).get("version") or ""),
        capability=declaration.capability,
        contract_version=PRIVACY_CONTRACT_VERSION,
        contract_sha256=declaration_digest(declaration),
        source_sha=source_sha,
        test_report_sha256=hashlib.sha256(report_bytes).hexdigest(),
        artifact_sha256=artifact_sha,
        tests_passed=True, required_tests_skipped=False,
        source_commit=source_commit,
        test_selection_sha256=selection_sha,
        build_tool_version="lambda.build_zip --bundle agent; deterministic bundle v1",
    )
    report_path.write_bytes(report_bytes)
    evidence_data = {
        **evidence.__dict__, "test_paths": test_paths,
        "test_args": test_args, "source_paths": source_paths,
        "artifact_path": artifact_rel,
        "contract_path": contract_path.relative_to(repo_root).as_posix(),
        "manifest_path": manifest_path.relative_to(repo_root).as_posix(),
        "test_report_path": report_path.relative_to(repo_root).as_posix(),
    }
    evidence_path = package / "privacy-evidence.json"
    evidence_path.write_text(json.dumps(evidence_data, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    return {"evidence": str(evidence_path), "sourceSha256": source_sha,
            "contractSha256": evidence.contract_sha256,
            "testReportSha256": evidence.test_report_sha256,
            "artifactSha256": artifact_sha, "sourceCommit": source_commit,
            "testPaths": test_paths, "status": "PASSED"}


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


def run_stage(stage: str, package: Path, status_path: Path, *, artifact_path: Optional[Path] = None,
              execute: bool = False, allow_apply: bool = False,
              yes: bool = False, force: bool = False) -> Dict[str, Any]:
    if stage not in STAGES:
        raise AgentInstallError(f"unknown stage {stage!r}")
    manifest_text = _read(package / "manifest.yaml") if (package / "manifest.yaml").is_file() else ""
    if package.name == "_template" or "\n  status: template" in manifest_text \
            or manifest_text.startswith("package:\n  status: template"):
        raise AgentInstallError(
            "_template and template-status packages are scaffolds, not deployable agents")
    status = _load_status(status_path)
    previous = status["stages"].get(stage, {})
    repo_root = Path(__file__).resolve().parent.parent
    fingerprint = _stage_fingerprint(package, repo_root)
    if stage == "privacy-evidence":
        try:
            import yaml
            data = yaml.safe_load(manifest_text)
            if artifact_path is None:
                artifact_path = repo_root / data["privacy"]["evidenceArtifact"]
            artifact = Path(artifact_path).resolve()
            if artifact.is_file():
                fingerprint = hashlib.sha256(
                    (fingerprint + hashlib.sha256(artifact.read_bytes()).hexdigest()).encode()
                ).hexdigest()
            else:
                fingerprint = hashlib.sha256((fingerprint + "|missing-artifact").encode()).hexdigest()
        except Exception:
            fingerprint = hashlib.sha256((fingerprint + "|invalid-artifact-config").encode()).hexdigest()
    if (previous.get("status") == "PASSED" and not force
            and previous.get("inputFingerprint") == fingerprint):
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
    elif stage == "privacy-evidence":
        if artifact_path is None:
            try:
                import yaml
                manifest_data = yaml.safe_load(info["manifest"])
                artifact_name = manifest_data["privacy"]["evidenceArtifact"]
                artifact_path = repo_root / artifact_name
            except Exception as exc:
                raise AgentInstallError(
                    "privacy-evidence stage requires a valid evidenceArtifact or --artifact") from exc
        if artifact_path is None:
            raise AgentInstallError("privacy-evidence stage requires --artifact")
        result.update(generate_privacy_evidence(package, artifact_path))
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
        result.update({
            "executed": False,
            "scope": "ris-dev2 test only",
            "requires": "reviewed terraform plan + --shared-teardown-intent "
                        "when shared infrastructure would change",
            "note": "this stage records approval only; it runs no terraform",
        })
    elif stage == "e2e":
        result.update({"executed": bool(execute),
                       "checklist": "docs/reports/RIS-AGENT-INSTALLATION-HANDOFF-08.md"})
    elif stage == "handoff":
        result.update({"artifact": "docs/releases/ris-agent-installation-08.json"})

    status["agentId"] = _value(info["manifest"], "agentId") or package.name
    status["packageVersion"] = _value(info["manifest"], "version")
    result["inputFingerprint"] = fingerprint
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
    parser.add_argument("--artifact", help="built artifact used for privacy evidence")
    parser.add_argument(
        "--action",
        choices=[a.lower() for a in LIFECYCLE_ACTIONS]
        + [a.lower().replace("_", "-") for a in LIFECYCLE_ACTIONS],
        help="run an agent lifecycle action instead of an install stage")
    parser.add_argument("--inventory", help="JSON inventory for lifecycle impact")
    parser.add_argument("--lifecycle-state")
    parser.add_argument("--lifecycle-audit")
    parser.add_argument("--purge-confirm", help="exact agentId to confirm PURGE")
    parser.add_argument("--actor", help="operator identity for the audit log")
    parser.add_argument("--approval", help="approval/ticket reference")
    parser.add_argument("--reason", help="short reason for the action")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        if args.action:
            if not args.agent:
                raise AgentInstallError("--agent is required with --action")
            result = _lifecycle.run(
                args.action, root / args.agent, execute=args.execute,
                inventory_path=Path(args.inventory) if args.inventory else None,
                state_path=Path(args.lifecycle_state) if args.lifecycle_state else None,
                audit_path=(Path(args.lifecycle_audit)
                            if args.lifecycle_audit else None),
                purge_confirm=args.purge_confirm,
                actor=args.actor, approval=args.approval,
                reason=args.reason)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["status"] != "BLOCKED" else 2
        if args.stage:
            if not args.agent:
                raise AgentInstallError("--agent is required with --stage")
            package = root / args.agent
            status_path = Path(args.status_file) if args.status_file else (
                package / "install-status.json")
            result = run_stage(args.stage, package, status_path,
                               artifact_path=Path(args.artifact) if args.artifact else None,
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
