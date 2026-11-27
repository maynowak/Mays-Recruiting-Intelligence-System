"""Version-bound, process-isolated local RIS and Mays-Orders test profiles.

This runner never performs network/AWS operations. LIVE is a permanently locked
inventory profile; live verification remains a separately authorized workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAYS = ROOT / "installer" / "projects" / "mays_order_builder"
VERSIONS_FILE = ROOT / "installer" / "mays-orders-test-versions.json"
SUPPORT_RUNNER = ROOT / "scripts" / "unified_test_process.py"
DEFAULT_REPORT = ROOT / "docs" / "reports" / "RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json"
EXPECTED_WORKER_BUNDLE_SHA256 = "78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7"
AWS_ENV_KEYS = {
    "AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN", "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_ROLE_ARN", "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "AWS_ENDPOINT_URL",
    "AWS_ENDPOINT_URL_DYNAMODB", "AWS_ENDPOINT_URL_SQS", "AWS_ENDPOINT_URL_STS",
    "RIS_TEST_DYNAMODB_ENDPOINT", "API_BASE_URL", "COGNITO_CLIENT_ID",
    "TEST_USER_EMAIL", "TEST_USER_PASSWORD", "MO_E2E_LIVE",
}
PROFILES = (
    "RIS_NATIVE", "MAYS_MODULE", "XREPO_CONTRACT", "XREPO_E2E",
    "MODULE_BUILD", "UPGRADE_GATE", "FULL", "LIVE",
)


@dataclass
class Job:
    key: str
    repository: str
    cwd: str
    kind: str
    args: list[str]
    python_path: str = ""
    mays_source: bool = False
    module_artifact: bool = False


def load_versions() -> dict:
    return json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def child_environment(base: dict[str, str], job: Job, *, mays_source: Path,
                      module_dir: Path | None, module_sha: str, source_commit: str,
                      sandbox_dir: Path) -> dict[str, str]:
    env = dict(base)
    for key in AWS_ENV_KEYS:
        env.pop(key, None)
    # Never inherit an ambient cross-repository namespace.
    env.pop("PYTHONPATH", None)
    env.pop("MO_ORDERS_SRC", None)
    env.pop("MO_ORDERS_MODULE", None)
    env.pop("MO_ORDERS_MODULE_ZIP_SHA256", None)
    env.pop("MO_ORDERS_SOURCE_COMMIT", None)
    if job.python_path:
        env["PYTHONPATH"] = job.python_path
    if job.mays_source:
        env["MO_ORDERS_SRC"] = str(mays_source / "lambda" / "src")
    if job.module_artifact and module_dir is not None:
        env["MO_ORDERS_MODULE"] = str(module_dir)
        env["MO_ORDERS_MODULE_ZIP_SHA256"] = module_sha
        env["MO_ORDERS_SOURCE_COMMIT"] = source_commit
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    # AWS CLI/SDK children must not discover a real profile from the host.
    env["AWS_CONFIG_FILE"] = str(sandbox_dir / "empty-aws-config")
    env["AWS_SHARED_CREDENTIALS_FILE"] = str(sandbox_dir / "empty-aws-credentials")
    return env


def _pytest(key: str, cwd: Path, files: Sequence[str], *, mays_source=False,
            module_artifact=False, python_path="") -> Job:
    return Job(key, "RIS", str(cwd), "pytest", ["-q", "-ra", *files], python_path,
               mays_source, module_artifact)


def _mays_pytest(key: str, mays: Path, files: Sequence[str]) -> Job:
    return Job(key, "MAYS_ORDERS", str(mays), "pytest", ["-q", "-ra", *files],
               str(mays))


def _unittest(key: str, repo: str, cwd: Path, start: str, python_path="") -> Job:
    return Job(key, repo, str(cwd), "unittest", [start], python_path)


def profile_jobs(profile: str, mays: Path) -> list[Job]:
    ris_tests = ROOT / "tests"
    mays_root = mays
    lambda_src = mays / "lambda" / "src"
    jobs: dict[str, list[Job]] = {
        "RIS_NATIVE": [
            _pytest("ris_native", ROOT, ["tests/"]),
        ],
        "MAYS_MODULE": [
            _unittest("mays_lambda", "MAYS_ORDERS", mays / "lambda", "tests",
                      os.pathsep.join((str(mays / "lambda"), str(lambda_src)))),
            _mays_pytest("mays_module_builder", mays, ["module_builder/tests"]),
            Job("mays_installer", "MAYS_ORDERS", str(mays_root),
                "unittest_module", ["installer.tests.test_installer"], str(mays_root)),
            _unittest("mays_seed_tools", "MAYS_ORDERS", mays / "scripts", "tests",
                      str(mays / "scripts")),
            _mays_pytest("mays_cognito_backup", mays, ["cognito_backup/tests"]),
        ],
        "XREPO_CONTRACT": [
            _pytest("xrepo_contract", ROOT, [
                "tests/test_mo_contract_compat.py",
                "tests/test_cross_repo_mo_contract.py",
                "tests/test_order_transport_contract.py",
                "tests/test_agent_order_body.py",
                "tests/test_agent_order_order_description.py",
                "tests/test_dispatch_ingress_env.py",
            ], mays_source=True),
        ],
        "XREPO_E2E": [
            _pytest("xrepo_e2e", ROOT, [
                "tests/test_mo_dispatch_handoff.py",
                "tests/test_agent_order_dispatch_e2e.py",
                "tests/test_partner_e2e_real.py",
                "tests/test_lambda_bridge_e2e.py",
            ], mays_source=True),
        ],
        "MODULE_BUILD": [
            _mays_pytest("mays_module_builder", mays, ["module_builder/tests"]),
            Job("mays_installer", "MAYS_ORDERS", str(mays_root),
                "unittest_module", ["installer.tests.test_installer"], str(mays_root)),
            _pytest("ris_builder_contract", ROOT, [
                "tests/test_build_mays_orders_transport_outputs.py",
                "tests/test_orders_aws_name_limits.py",
            ]),
            _pytest("generated_module_artifact", ROOT, [
                "tests/test_generated_module_artifact.py",
            ], module_artifact=True),
        ],
    }
    if profile in jobs:
        return jobs[profile]
    if profile in ("FULL", "UPGRADE_GATE"):
        # Keep outputs as per-profile/per-group results; overlap is explicitly
        # reported and never summed as if each execution were an independent test.
        order = ("RIS_NATIVE", "MAYS_MODULE", "XREPO_CONTRACT", "XREPO_E2E", "MODULE_BUILD")
        selected = ("RIS_NATIVE", "MAYS_MODULE", "XREPO_CONTRACT", "XREPO_E2E", "MODULE_BUILD")
        result: list[Job] = []
        seen: set[str] = set()
        for name in order:
            if name not in selected:
                continue
            for job in jobs[name]:
                # Reuse identical job identity within a profile expansion.
                identity = json.dumps(asdict(job), sort_keys=True)
                if identity not in seen:
                    seen.add(identity)
                    result.append(job)
        return result
    return []


def verify_provenance(mays: Path, version_name: str, versions: dict) -> tuple[dict, list[str]]:
    entry = versions["versions"].get(version_name)
    if not entry:
        return {}, [f"unknown Mays-Orders test version: {version_name}"]
    problems: list[str] = []
    if not mays.is_dir():
        return entry, [f"Mays-Orders checkout not found: {mays}"]
    commands = [
        ["git", "-C", str(mays), "rev-parse", "HEAD"],
        ["git", "-C", str(mays), "status", "--porcelain"],
    ]
    results = [subprocess.run(cmd, capture_output=True, text=True, check=False) for cmd in commands]
    if any(r.returncode for r in results):
        return entry, ["Mays-Orders checkout is not a readable Git repository"]
    actual = results[0].stdout.strip()
    if actual != entry["commit"]:
        problems.append(f"Mays checkout HEAD {actual} != required {entry['commit']}")
    if results[1].stdout.strip():
        problems.append("Mays-Orders checkout is dirty; refusing a stale/modified source")
    if version_name == "integrated":
        pin_path = ROOT / "installer" / "mays-orders-builder.pinned.json"
        builder_path = ROOT / "installer" / "build_mays_orders_module.py"
        try:
            pin_commit = json.loads(pin_path.read_text(encoding="utf-8"))["commit"]
            builder_text = builder_path.read_text(encoding="utf-8")
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            problems.append(f"cannot verify active builder pin: {exc}")
        else:
            pin_constant = re.search(r'^PINNED_COMMIT\s*=\s*["\']([0-9a-f]{40})["\']',
                                     builder_text, re.MULTILINE)
            if pin_commit != entry["commit"]:
                problems.append("test version differs from mays-orders-builder.pinned.json")
            if not pin_constant or pin_constant.group(1) != entry["commit"]:
                problems.append("test version differs from builder PINNED_COMMIT")
    return entry, problems


def parse_result(job: Job, completed: subprocess.CompletedProcess[str], duration: float) -> dict:
    text = (completed.stdout or "") + "\n" + (completed.stderr or "")
    unittest_match = re.search(r"Ran (\d+) tests? in ([\d.]+)s", text)
    summary_lines = re.findall(
        r"(?m)^.*(?:passed|failed|skipped|xfailed|xpassed).+\bin\s+[\d.]+s"
        r"(?:\s+\([^\r\n]*\))?\s*$", text
    )
    pytest_summary = summary_lines[-1] if summary_lines else ""
    if unittest_match:
        outcome = re.search(r"(?m)^(OK|FAILED)(?: \(([^\n]+)\))?$", text)
        status_text = (outcome.group(2) or "") if outcome else ""
        numbers = {key: 0 for key in ("failures", "errors", "skipped")}
        for value, key in re.findall(r"(\d+) (failures?|errors?|skipped)", status_text):
            normalized = "failures" if key.startswith("failure") else key
            numbers[normalized] = int(value)
        for key in numbers:
            match = re.search(rf"\b{key}=(\d+)", status_text)
            if match:
                numbers[key] = int(match.group(1))
        total = int(unittest_match.group(1))
        counts = {
            "passed": max(0, total - numbers["failures"] - numbers["errors"] - numbers["skipped"]),
            "failed": numbers["failures"] + numbers["errors"],
            "skipped": numbers["skipped"], "subtests_passed": 0,
            "duration_seconds": float(unittest_match.group(2)), "tests_run": total,
        }
    elif pytest_summary:
        def count(label: str, *, negative_prefix: str | None = None) -> int:
            prefix = rf"(?<!{re.escape(negative_prefix)} )" if negative_prefix else ""
            match = re.search(prefix + rf"\b(\d+) {label}\b", pytest_summary)
            return int(match.group(1)) if match else 0

        duration_match = re.search(r"\bin\s+([\d.]+)s", pytest_summary)
        counts = {
            "passed": count("passed", negative_prefix="subtests"),
            "failed": count("failed"), "skipped": count("skipped"),
            "deselected": count("deselected"), "xfailed": count("xfailed"),
            "xpassed": count("xpassed"), "subtests_passed": count("subtests? passed"),
            "duration_seconds": float(duration_match.group(1)) if duration_match else duration,
        }
    else:
        counts = {"passed": 0, "failed": 0, "skipped": 0, "subtests_passed": 0,
                  "duration_seconds": duration, "summary_parse": "unrecognized"}
    status = "PASS" if completed.returncode == 0 else "FAIL"
    if unittest_match and int(unittest_match.group(1)) == 0:
        status = "BLOCKED"
    if counts.get("summary_parse") == "unrecognized":
        status = "BLOCKED" if completed.returncode else "PASS_WITH_UNPARSED_SUMMARY"
    return {
        "group": job.key, "repository": job.repository, "status": status,
        "return_code": completed.returncode, **counts,
        "collection_errors": len(re.findall(r"(?m)^ERROR collecting ", text)),
        "command": completed.args,
        "stdout_tail": (completed.stdout or "")[-5000:],
        "stderr_tail": (completed.stderr or "")[-3000:],
    }


def run_job(job: Job, *, python: str, base_env: dict[str, str], mays_source: Path,
            module_dir: Path | None, module_sha: str, source_commit: str) -> dict:
    if job.module_artifact and module_dir is None:
        return {"group": job.key, "repository": job.repository, "status": "BLOCKED",
                "reason": "Generated module artifact not present; no build/mutation attempted.",
                "passed": 0, "failed": 0, "skipped": 0, "collection_errors": 0,
                "subtests_passed": 0, "duration_seconds": 0.0}
    sandbox_context = tempfile.TemporaryDirectory(prefix="ris-qa-sandbox-")
    sandbox_dir = Path(sandbox_context.name)
    (sandbox_dir / "empty-aws-config").write_text("", encoding="utf-8")
    (sandbox_dir / "empty-aws-credentials").write_text("", encoding="utf-8")
    snapshot_context = sandbox_context if job.repository == "MAYS_ORDERS" else None
    try:
        if snapshot_context:
            snapshot_root = sandbox_dir / "source"
            clone = subprocess.run(
                ["git", "clone", "--no-hardlinks", "--local", "--no-checkout",
                 str(mays_source), str(snapshot_root)],
                capture_output=True, text=True, check=False,
            )
            if clone.returncode:
                return {"group": job.key, "repository": job.repository, "status": "BLOCKED",
                        "reason": "could not create isolated local Git clone",
                        "passed": 0, "failed": 0, "skipped": 0,
                        "collection_errors": 0, "subtests_passed": 0,
                        "duration_seconds": 0.0, "source_commit": source_commit,
                        "details": clone.stderr[-2000:]}
            checkout = subprocess.run(
                ["git", "-C", str(snapshot_root), "checkout", "--detach", source_commit],
                capture_output=True, text=True, check=False,
            )
            if checkout.returncode:
                return {"group": job.key, "repository": job.repository, "status": "BLOCKED",
                        "reason": "could not checkout exact verified source commit",
                        "passed": 0, "failed": 0, "skipped": 0,
                        "collection_errors": 0, "subtests_passed": 0,
                        "duration_seconds": 0.0, "source_commit": source_commit,
                        "details": checkout.stderr[-2000:]}
            old_root = str(mays_source)
            job = replace(
                job,
                cwd=job.cwd.replace(old_root, str(snapshot_root)),
                python_path=job.python_path.replace(old_root, str(snapshot_root)),
            )
    except OSError as exc:
        return {"group": job.key, "repository": job.repository, "status": "BLOCKED",
                "reason": f"failed to materialize read-only versioned test snapshot: {exc}",
                "passed": 0, "failed": 0, "skipped": 0,
                "collection_errors": 0, "subtests_passed": 0,
                "duration_seconds": 0.0, "source_commit": source_commit}

    command = [python, str(SUPPORT_RUNNER)]
    if job.kind == "pytest":
        command.extend(["--pytest", *job.args])
    if job.kind == "unittest":
        command.extend(["--unittest-start", job.args[0]])
        if job.args[0] == "installer/tests":
            command.extend(["--unittest-top-level", "."])
    if job.kind == "unittest_module":
        command.extend(["--unittest-module", job.args[0]])
    env = child_environment(base_env, job, mays_source=mays_source,
                            module_dir=module_dir, module_sha=module_sha,
                            source_commit=source_commit, sandbox_dir=sandbox_dir)
    preparation = None
    if job.repository == "MAYS_ORDERS" and job.key == "mays_module_builder":
        build_script = Path(job.cwd) / "lambda" / "build_zip.py"
        if build_script.is_file():
            prepared = subprocess.run(
                [python, "build_zip.py"], cwd=build_script.parent, env=env,
                capture_output=True, text=True, check=False,
            )
            preparation = {
                "action": "rebuild lambda/dist/lambda.zip in disposable exact-commit test clone",
                "return_code": prepared.returncode,
                "stdout_tail": prepared.stdout[-1500:],
                "stderr_tail": prepared.stderr[-1500:],
            }
            if prepared.returncode:
                sandbox_context.cleanup()
                return {
                    "group": job.key, "repository": job.repository,
                    "status": "BLOCKED", "reason": "candidate source artifact preparation failed",
                    "source_commit": source_commit,
                    "source_mode": "temporary_detached_git_clone",
                    "preparation": preparation,
                    "passed": 0, "failed": 0, "skipped": 0,
                    "collection_errors": 0, "subtests_passed": 0,
                    "duration_seconds": 0.0,
                }
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=job.cwd, env=env, capture_output=True,
                                   text=True, check=False)
    except OSError as exc:
        completed = subprocess.CompletedProcess(command, 127, "", str(exc))
    elapsed = time.monotonic() - started
    result = parse_result(job, completed, elapsed)
    if job.repository == "MAYS_ORDERS":
        result["source_commit"] = source_commit
        result["source_mode"] = (
            "temporary_detached_git_clone_with_rebuilt_lambda_artifact"
            if preparation else "temporary_detached_git_clone"
        )
        if preparation:
            result["preparation"] = preparation
    sandbox_context.cleanup()
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES)
    parser.add_argument("--mays-version", default="integrated",
                        choices=("integrated", "upgrade_candidate"))
    parser.add_argument("--mays-source", type=Path, default=DEFAULT_MAYS)
    parser.add_argument(
        "--module-artifact-dir", type=Path,
        help="Read-only generated module artifact to contract-test (e.g. isolated candidate build).",
    )
    parser.add_argument("--ris-python", default=sys.executable)
    parser.add_argument("--mays-python", default=sys.executable)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    versions = load_versions()
    version_key = args.mays_version
    profile = args.profile
    if profile == "LIVE":
        mays_entry, provenance_errors = versions["versions"][version_key], []
    else:
        mays_entry, provenance_errors = verify_provenance(
            args.mays_source, version_key, versions
        )
    created = datetime.now(timezone.utc).isoformat()
    ris_commit = ""
    if profile != "LIVE":
        ris_commit = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
    result = {
        "schema_version": 1,
        "created_at": created,
        "profile": profile,
        "ris_commit": ris_commit,
        "mays_orders": {
            "version_key": version_key,
            "expected_commit": mays_entry.get("commit"),
            "release": mays_entry.get("release"),
            "checkout": str(args.mays_source),
            "provenance_status": "VERIFIED" if not provenance_errors else "BLOCKED",
            "errors": provenance_errors,
        },
        "platform": sys.platform,
        "python": sys.version,
        "artifact_hashes": {
            "worker_bundle_terraform/lambda.zip": (
                sha256(ROOT / "terraform" / "lambda.zip")
                if (ROOT / "terraform" / "lambda.zip").is_file() else None
            ),
            "worker_bundle_expected": EXPECTED_WORKER_BUNDLE_SHA256,
            "worker_bundle_matches_baseline": (
                sha256(ROOT / "terraform" / "lambda.zip") == EXPECTED_WORKER_BUNDLE_SHA256
                if (ROOT / "terraform" / "lambda.zip").is_file() else False
            ),
            "mays_test_version_map": sha256(VERSIONS_FILE),
        },
        "live_profile": "LOCKED_NOT_EXECUTED",
        "aggregate_counts": "Per-group only; overlapping profile executions are not summed.",
        "groups": [],
        "profile_status": "PENDING",
    }

    if profile == "LIVE":
        result["profile_status"] = "BLOCKED"
        result["groups"].append({"group": "live_inventory", "status": "BLOCKED",
                                 "reason": "LIVE is intentionally locked; use a separate approved live-test task."})
    elif provenance_errors:
        result["profile_status"] = "BLOCKED"
        result["groups"].append({"group": "provenance", "status": "BLOCKED",
                                 "reason": "; ".join(provenance_errors)})
    else:
        module_dir = args.module_artifact_dir or (ROOT / "terraform" / "modules" / "mays_orders")
        manifest_path = module_dir / "module-builder.manifest.json"
        artifact_path = module_dir / "lambda" / "dist" / "lambda.zip"
        module_manifest = None
        module_sha = ""
        artifact_errors: list[str] = []
        if manifest_path.is_file() and artifact_path.is_file():
            module_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            module_sha = sha256(artifact_path)
            expected_sha = module_manifest.get("artifacts_sha256", {}).get("lambda/dist/lambda.zip")
            if expected_sha != module_sha:
                artifact_errors.append("generated-module ZIP hash differs from its manifest")
            elif module_manifest.get("source", {}).get("commit") != mays_entry["commit"]:
                artifact_errors.append(
                    "generated module source commit differs from selected Mays test version"
                )
        else:
            module_dir = None
        result["module_artifact"] = {
            "path": str(module_dir or (ROOT / "terraform" / "modules" / "mays_orders")),
            "source_commit": module_manifest.get("source", {}).get("commit") if module_manifest else None,
            "zip_sha256": module_sha or None,
            "manifest_sha256": sha256(manifest_path) if manifest_path.is_file() else None,
            "status": "VERIFIED" if module_dir and not artifact_errors else "BLOCKED",
            "errors": artifact_errors,
        }
        if profile in ("FULL", "UPGRADE_GATE") and args.mays_version == "upgrade_candidate":
            result["upgrade_candidate_status"] = "CANDIDATE_TESTS_ONLY_NOT_UPGRADE_AUTHORIZATION"
        if profile == "UPGRADE_GATE" and args.mays_version == "integrated":
            result["upgrade_candidate_status"] = "BLOCKED: UPGRADE_GATE requires --mays-version upgrade_candidate"
        selected = profile_jobs(profile, args.mays_source)
        for job in selected:
            python = args.mays_python if job.repository == "MAYS_ORDERS" else args.ris_python
            row = run_job(job, python=python, base_env=os.environ,
                          mays_source=args.mays_source, module_dir=module_dir,
                          module_sha=module_sha,
                          source_commit=mays_entry["commit"])
            result["groups"].append(row)
        required = [row for row in result["groups"] if row.get("group") not in ("provenance",)]
        result["profile_status"] = "PASS" if required and all(
            row.get("status") == "PASS" and row.get("collection_errors", 0) == 0
            for row in required
        ) else "BLOCKED"
        if profile in ("MODULE_BUILD", "FULL", "UPGRADE_GATE") and result[
            "module_artifact"]["status"] != "VERIFIED":
            result["profile_status"] = "BLOCKED"
        if profile == "UPGRADE_GATE" and args.mays_version != "upgrade_candidate":
            result["profile_status"] = "BLOCKED"

    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
    print(json.dumps({
        "profile": result["profile"], "status": result["profile_status"],
        "mays_provenance": result["mays_orders"]["provenance_status"],
        "groups": [{"group": row.get("group"), "status": row.get("status"),
                    "passed": row.get("passed"), "failed": row.get("failed"),
                    "skipped": row.get("skipped"), "subtests_passed": row.get("subtests_passed"),
                    "collection_errors": row.get("collection_errors")}
                   for row in result["groups"]],
        "report": str(args.json_report),
    }, indent=2))
    return 0 if result["profile_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
