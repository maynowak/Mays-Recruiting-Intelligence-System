"""Verify the built RIS parser Lambda artifact without deploying it.

Checks the SHA-256, the module closure, forbidden entries and the IAM-facing
shape, then extracts the artifact and runs the real Node handler for job, CV,
ATS and error cases. ``@napi-rs/canvas`` is a native dependency: the deployment
artifact contains the Lambda ``linux-arm64`` package only. For local
verification on another OS, pass ``--host-canvas-dir`` with the matching
extracted package; it is added only to the extracted staging copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

FORBIDDEN_PARTS = ("web/", "__tests__", "/test/", "/tests/", "coverage/")
FORBIDDEN_SUFFIXES = (".map", ".test.mjs", ".spec.mjs")
REQUIRED = (
    "lambda/ris_parser_handler.mjs",
    "scripts/ris-parser-cli.mjs",
    "api/_lib/analysis/service.mjs",
    "api/_lib/ats.mjs",
    "node_modules/pdfjs-dist/legacy/build/pdf.mjs",
    "node_modules/@napi-rs/canvas/package.json",
    "node_modules/@napi-rs/canvas-linux-arm64-gnu/package.json",
)

SMOKE = r"""
import { handler } from 'file:///__HANDLER__';
import { readFileSync } from 'node:fs';
const job = await handler({ capability: 'parse.job', input: { job: {
  title: 'Synthetic Canary Engineer',
  company: 'Canary GmbH',
  descriptionPlain: 'Required: Python and AWS. Kubernetes is a nice to have.' } } });
const cv = await handler({ capability: 'parse.cv', input: {
  pdfBase64: readFileSync('__PDF__').toString('base64') } });
const ats = await handler({ capability: 'parse.ats', input: {
  job: { title: 'Synthetic Canary Engineer',
         descriptionPlain: 'Required: Python and AWS.' },
  profile: { skills: ['Python'] } } });
const bad = await handler({ capability: 'parse.job', input: { job: {} } });
const unknown = await handler({ capability: 'parse.other', input: {} });
console.log(JSON.stringify({
  jobStableId: job.data?.stableId?.length,
  jobTags: job.data?.jobTags?.length,
  cvStableId: cv.data?.stableId?.length,
  cvTags: cv.data?.cvTags,
  cvSkills: cv.data?.skills,
  atsTags: ats.data?.atsTags?.length,
  invalidInput: bad.error?.code,
  unknownCapability: unknown.error?.code,
}));
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(archive: zipfile.ZipFile, manifest: dict) -> list[str]:
    names = archive.namelist()
    problems = []
    for entry in REQUIRED:
        if entry not in names:
            problems.append(f"missing {entry}")
    for name in names:
        if any(part in name for part in FORBIDDEN_PARTS):
            problems.append(f"forbidden path {name}")
        if name.endswith(FORBIDDEN_SUFFIXES):
            problems.append(f"forbidden file {name}")
    natives = [name for name in names if name.endswith(".node")]
    if len(natives) != 1 or "canvas-linux-arm64-gnu" not in natives[0]:
        problems.append(f"unexpected native binaries: {natives}")
    if manifest.get("architecture") != "arm64":
        problems.append("manifest architecture is not arm64")
    if manifest.get("publicEndpoint") is not False:
        problems.append("manifest does not deny a public endpoint")
    if manifest.get("handler") != "lambda/ris_parser_handler.handler":
        problems.append("unexpected handler")
    return problems


def verify(artifact: Path, pdf: Path, host_canvas: Path | None,
           expected_sha: str = "") -> dict:
    manifest_path = artifact.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = sha256(artifact)
    if digest != manifest.get("sha256"):
        raise SystemExit("artifact SHA-256 does not match the manifest")
    if expected_sha and digest != expected_sha:
        raise SystemExit("artifact SHA-256 does not match the expected value")
    if not pdf.is_file():
        raise SystemExit(f"canary PDF fixture not found: {pdf}")

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "stage"
        with zipfile.ZipFile(artifact) as archive:
            problems = inspect(archive, manifest)
            if problems:
                raise SystemExit("; ".join(problems))
            archive.extractall(staging)
        if host_canvas is not None:
            target = staging / "node_modules" / "@napi-rs" / host_canvas.name
            shutil.copytree(host_canvas, target)
        handler = staging / "lambda" / "ris_parser_handler.mjs"
        script = staging / "smoke.mjs"
        body = (SMOKE
                .replace("__HANDLER__", handler.as_posix())
                .replace("__PDF__", pdf.as_posix()))
        script.write_text(body, encoding="utf-8")
        result = subprocess.run([shutil.which("node") or "node", str(script)],
                                capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            raise SystemExit(f"node smoke failed: {result.stderr[-2000:]}")
        smoke = json.loads(result.stdout.strip().splitlines()[-1])

    expected = {
        "jobStableId": 64,
        "cvStableId": 64,
        "invalidInput": "invalid_input",
        "unknownCapability": "unsupported_capability",
    }
    for key, value in expected.items():
        if smoke.get(key) != value:
            problems.append(f"{key}: {smoke.get(key)!r} != {value!r}")
    if not smoke.get("jobTags"):
        problems.append("jobTags is empty")
    if "Python" not in (smoke.get("cvSkills") or []):
        problems.append("synthetic CV did not yield the Python skill")
    if not smoke.get("atsTags"):
        problems.append("atsTags is empty")
    if problems:
        raise SystemExit("; ".join(problems))

    return {"sha256": digest, "size": artifact.stat().st_size,
            "fileCount": manifest.get("fileCount"),
            "manifest": manifest, "smoke": smoke}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--host-canvas-dir", type=Path)
    parser.add_argument("--expected-sha", default="")
    args = parser.parse_args(argv)
    print(json.dumps(verify(args.artifact.resolve(), args.pdf.resolve(),
                            args.host_canvas_dir,
                            args.expected_sha), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
