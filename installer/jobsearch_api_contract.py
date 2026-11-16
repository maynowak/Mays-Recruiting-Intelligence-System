#!/usr/bin/env python3
"""Verify and refresh the mays-jobsearch API contract snapshot.

The contract is **interface metadata only** (endpoint, field names, types,
statuses). No AGPL source is copied into RIS: the source files are read from a
read-only checkout and hashed for provenance.

Usage:
    python installer/jobsearch_api_contract.py check
    python installer/jobsearch_api_contract.py check --fetch
    python installer/jobsearch_api_contract.py refresh --commit <sha>

Exit codes: 0 = up to date, 1 = drift/mismatch, 2 = usage/source error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "installer" / "projects" / "mays_jobsearch_ats_readonly"
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "contracts" / "mays-jobsearch-api.manifest.json"

# Markers that must still exist in the pinned source. They prove the fields the
# RIS client depends on are still part of the implementation.
MARKERS: Dict[str, Tuple[str, ...]] = {
    "api/ats-analysis.mjs": (
        "/api/ats-analysis",
        "validateRequest",
        "score:",
        "keywordCoverage",
        "requirementCoverage",
        "profileEvidenceCoverage",
        "roleMatch",
        "analysisStatus",
        "basis",
        "metadata",
        "criticalGaps",
        "requirements:",
        "matches:",
        "recommendations:",
        "ai: {",
    ),
    "api/_lib/ats.mjs": (
        "analyzeJobForAts",
        "extractRequirementsFromJob",
        "matchRequirement",
        "calculateRoleMatch",
        "extractJobMetadata",
        "generateCVRecommendations",
        "importanceWeight",
        "analysisStatus",
        "requirementMatch",
        "criticalGaps",
    ),
    "api/_lib/filter.mjs": (
        "tokenize",
        "stripHtml",
        "htmlToPlainText",
        "detectLanguage",
    ),
}


class ContractError(RuntimeError):
    """Source or contract error that must stop the command."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Source(Protocol):
    def head(self) -> str: ...

    def has_commit(self, commit: str) -> bool: ...

    def read(self, commit: str, path: str) -> bytes: ...


class GitSource:
    """Read-only access to a local Jobsearch clone via git plumbing."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.is_dir():
            raise ContractError(
                f"source checkout not found: {self.path}. "
                "Clone it read-only (see docs/contracts/JOBSEARCH-ATS-ANALYSIS-V1.md)."
            )

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.path), *args], capture_output=True
        )

    def head(self) -> str:
        result = self._run("rev-parse", "HEAD")
        if result.returncode != 0:
            raise ContractError(f"cannot read HEAD: {self.path}")
        return result.stdout.decode("utf-8", "replace").strip()

    def remote_head(self) -> str:
        result = self._run("rev-parse", "origin/main")
        if result.returncode != 0:
            return self.head()
        return result.stdout.decode("utf-8", "replace").strip()

    def fetch(self) -> None:
        result = self._run("fetch", "--quiet", "origin")
        if result.returncode != 0:
            raise ContractError("git fetch origin failed")

    def has_commit(self, commit: str) -> bool:
        return self._run("cat-file", "-e", f"{commit}^{{commit}}").returncode == 0

    def read(self, commit: str, path: str) -> bytes:
        result = self._run("show", f"{commit}:{path}")
        if result.returncode != 0:
            raise ContractError(f"cannot read {path} at {commit}")
        return result.stdout


def load_json(path: Path) -> Dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {path}: {exc}") from exc


def verify(source: Source, manifest: Mapping) -> List[str]:
    """Return a list of problems; empty means the pin is intact."""
    problems: List[str] = []
    commit = manifest.get("source", {}).get("commit", "")
    if not commit:
        return ["manifest has no source.commit"]
    if not source.has_commit(commit):
        return [f"pinned commit not present in source: {commit}"]

    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        return ["manifest has no files map"]
    if set(files) != set(MARKERS):
        return [
            "manifest file set does not match the known API files: "
            f"{sorted(files)} != {sorted(MARKERS)}"
        ]

    for path in sorted(files):
        expected = files[path]
        try:
            data = source.read(commit, path)
        except ContractError as exc:
            problems.append(str(exc))
            continue
        actual = sha256(data)
        if actual != expected:
            problems.append(f"{path}: sha256 {actual} != pinned {expected}")
        text = data.decode("utf-8", "replace")
        missing = [marker for marker in MARKERS[path] if marker not in text]
        if missing:
            problems.append(f"{path}: missing contract markers {missing}")
    return problems


def build_manifest(
    source: Source, commit: str, base: Mapping
) -> Dict:
    files: Dict[str, str] = {}
    for path in sorted(MARKERS):
        data = source.read(commit, path)
        text = data.decode("utf-8", "replace")
        missing = [marker for marker in MARKERS[path] if marker not in text]
        if missing:
            raise ContractError(
                f"refusing to pin {commit}: {path} misses {missing}"
            )
        files[path] = sha256(data)

    manifest = dict(base)
    manifest["source"] = dict(base.get("source", {}))
    manifest["source"]["commit"] = commit
    manifest["files"] = files
    return manifest


def write_manifest(path: Path, manifest: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def check(source: Source, manifest_path: Path, head: Optional[str] = None) -> Dict:
    manifest = load_json(manifest_path)
    problems = verify(source, manifest)
    pinned = manifest.get("source", {}).get("commit", "")
    current = head or source.head()
    if problems:
        status = "MISMATCH"
    elif current != pinned:
        status = "DRIFT"
    else:
        status = "UP_TO_DATE"
    return {
        "status": status,
        "repo": manifest.get("source", {}).get("repo", ""),
        "pinned": pinned,
        "head": current,
        "files": len(manifest.get("files", {})),
        "problems": problems,
    }


def refresh(
    source: Source, manifest_path: Path, commit: Optional[str] = None
) -> Dict:
    base = load_json(manifest_path)
    target = commit or source.head()
    if not source.has_commit(target):
        raise ContractError(f"commit not present in source: {target}")
    manifest = build_manifest(source, target, base)
    write_manifest(manifest_path, manifest)
    return {
        "status": "REFRESHED",
        "repo": manifest["source"]["repo"],
        "commit": target,
        "files": len(manifest["files"]),
    }


def _print_human(result: Mapping) -> None:
    if result["status"] == "REFRESHED":
        print("MAYS-JOBSEARCH-API-SNAPSHOT-V1")
        print(f"repo      : {result['repo']}")
        print(f"pinned    : {result['commit']}")
        print(f"files     : {result['files']} hashed")
        print("status    : REFRESHED")
        print("next      : review the contract JSON, then commit")
        return

    print("MAYS-JOBSEARCH-API-SNAPSHOT-V1")
    print(f"repo      : {result['repo']}")
    print(f"pinned    : {result['pinned']}")
    print(f"local HEAD: {result['head']}")
    print(f"files     : {result['files']} checked")
    print(f"status    : {result['status']}")
    for problem in result["problems"]:
        print(f"  - {problem}")
    if result["status"] == "DRIFT":
        print("next      : python installer/jobsearch_api_contract.py refresh --commit <sha>")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check_parser = sub.add_parser("check", help="verify the pinned contract")
    check_parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    check_parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    check_parser.add_argument("--fetch", action="store_true")
    check_parser.add_argument("--json", action="store_true")

    refresh_parser = sub.add_parser("refresh", help="pin a new source commit")
    refresh_parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    refresh_parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    refresh_parser.add_argument("--commit", default=None)
    refresh_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        source = GitSource(Path(args.source))
        if args.command == "check":
            head = None
            if args.fetch:
                source.fetch()
                head = source.remote_head()
            result = check(source, Path(args.manifest), head=head)
        else:
            result = refresh(source, Path(args.manifest), commit=args.commit)
    except ContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human(result)
    return 0 if result["status"] in ("UP_TO_DATE", "REFRESHED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
