"""Build the deterministic RIS parser Lambda artifact.

The parser lives in the pinned Jobsearch repository. This script packages only
the modules the internal handler needs (no tests, no site code) with fixed
timestamps and sorted entries, so the same inputs always produce the same
SHA-256.

The Node Lambda runs on ``linux-arm64``. ``@napi-rs/canvas`` is an optional
pdfjs-dist dependency and is a native binary, so the target platform package is
passed explicitly:

    npm pack @napi-rs/canvas-linux-arm64-gnu@1.0.6 --pack-destination <tmp>
    tar -xzf <tmp>/napi-rs-canvas-linux-arm64-gnu-1.0.6.tgz -C <tmp>

Usage:
    python tools/build_analysis_parser_artifact.py \
        --jobsearch-root C:/.../mays-jobsearch \
        --expected-commit c40bf78 \
        --canvas-platform-dir @napi-rs/canvas-linux-arm64-gnu=C:/.../package \
        --out lambda/dist/analysis-parser.zip

Local verification builds may add the host package (``@napi-rs/canvas-win32-x64-msvc``)
as a second ``--canvas-platform-dir``; that produces a different artifact and is
never the deployment artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
INCLUDE_FILES = (
    "lambda/ris_parser_handler.mjs",
    "scripts/ris-parser-cli.mjs",
)
INCLUDE_DIRS = (
    "api/_lib",
    "node_modules/pdfjs-dist",
)
CANVAS_WRAPPER = "node_modules/@napi-rs/canvas"
EXCLUDE_DIR_NAMES = {
    "__pycache__", "__tests__", "test", "tests", "coverage", ".git",
    "web",  # pdfjs-dist browser bundle; the legacy Node build is included
}
EXCLUDE_SUFFIXES = (".map", ".test.mjs", ".spec.mjs")
REQUIRED_ENTRIES = (
    "lambda/ris_parser_handler.mjs",
    "scripts/ris-parser-cli.mjs",
    "api/_lib/analysis/service.mjs",
    "api/_lib/ats.mjs",
    "node_modules/pdfjs-dist/legacy/build/pdf.mjs",
    "node_modules/pdfjs-dist/package.json",
    f"{CANVAS_WRAPPER}/package.json",
    f"{CANVAS_WRAPPER}/index.js",
)


def _git_commit(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short=7", "HEAD"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.stdout.strip()


def _walk(target: str, source: Path, entries: dict) -> None:
    if not source.is_dir():
        raise SystemExit(f"missing required directory: {source}")
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if any(part in EXCLUDE_DIR_NAMES for part in relative.parts):
            continue
        if relative.name.endswith(EXCLUDE_SUFFIXES):
            continue
        entries[f"{target}/{relative.as_posix()}"] = path


def collect_entries(root: Path,
                    canvas_platforms: dict[str, Path]) -> dict[str, Path]:
    entries: dict[str, Path] = {}
    for name in INCLUDE_FILES:
        path = root / name
        if not path.is_file():
            raise SystemExit(f"missing required file: {name}")
        entries[name] = path
    for directory in INCLUDE_DIRS:
        _walk(directory, root / directory, entries)
    _walk(CANVAS_WRAPPER, root / CANVAS_WRAPPER, entries)
    for package, source in canvas_platforms.items():
        target = f"node_modules/@napi-rs/{package}"
        _walk(target, source, entries)
        if not any(entry.endswith(".node") for entry in entries
                   if entry.startswith(target + "/")):
            raise SystemExit(
                f"canvas platform package {package} has no native binary")

    missing = [entry for entry in REQUIRED_ENTRIES if entry not in entries]
    if missing:
        raise SystemExit(f"artifact misses required modules: {missing}")
    return entries


def build(root: Path, out: Path,
          canvas_platforms: dict[str, Path]) -> dict:
    entries = collect_entries(root, canvas_platforms)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name].read_bytes())

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    manifest = {
        "artifact": out.name,
        "size": out.stat().st_size,
        "sha256": digest,
        "fileCount": len(entries),
        "sourceCommit": _git_commit(root),
        "sourceRepository": "maynowak/mays-jobsearch",
        "includes": list(INCLUDE_DIRS),
        "canvasPlatforms": sorted(canvas_platforms),
        "handler": "lambda/ris_parser_handler.handler",
        "runtime": "nodejs22.x",
        "architecture": "arm64",
        "publicEndpoint": False,
    }
    out.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest


def _parse_platform(value: str) -> tuple[str, Path]:
    name, _, directory = value.partition("=")
    if not name.startswith("@napi-rs/") or not directory:
        raise argparse.ArgumentTypeError(
            "expected @napi-rs/<package>=<extracted-dir>")
    return name.split("/", 1)[1], Path(directory)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobsearch-root", required=True, type=Path)
    parser.add_argument("--out", type=Path,
                        default=Path("lambda/dist/analysis-parser.zip"))
    parser.add_argument("--expected-commit", default="")
    parser.add_argument("--canvas-platform-dir", action="append", default=[],
                        type=_parse_platform,
                        metavar="@napi-rs/canvas-linux-arm64-gnu=DIR")
    args = parser.parse_args(argv)

    root = args.jobsearch_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"jobsearch root not found: {root}")
    commit = _git_commit(root)
    if args.expected_commit and not commit.startswith(args.expected_commit):
        raise SystemExit(
            f"jobsearch HEAD {commit or '<unknown>'} does not match the pinned "
            f"commit {args.expected_commit}")
    platforms = {name: path.resolve()
                 for name, path in args.canvas_platform_dir}
    if not platforms:
        raise SystemExit(
            "at least one --canvas-platform-dir is required for pdfjs-dist")

    manifest = build(root, args.out, platforms)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
