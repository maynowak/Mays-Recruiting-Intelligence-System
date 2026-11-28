"""Stage exact preserved RIS-DEV2 ZIP bytes at their historical Terraform paths.

This copies already-preserved archives byte-for-byte. It never rebuilds or edits
archive members; destination guards prevent replacing an unexpected local file.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "terraform" / "artifacts"

ARTIFACTS_TO_STAGE = (
    {
        "name": "analysis",
        "source": ARTIFACTS
        / "ris-dev2-analysis-276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10.zip",
        "destination": ROOT / "terraform" / "analysis-lambda.zip",
        "expected_source_sha256": "276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10",
        "expected_existing_destination_sha256": "370890d459488304481d99255cfa6a2891b5f19a8c5df2723556905195c7c621",
    },
    {
        "name": "orders-reader",
        "source": ARTIFACTS
        / "ris-dev2-orders-reader-610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b.zip",
        "destination": ROOT / "lambda" / "dist" / "orders-reader.zip",
        "expected_source_sha256": "610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b",
        "expected_existing_destination_sha256": "bea4c3e59666bed8ad071ad4e405bcdfd57dafdac68096ce648667f0effb1b41",
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage() -> list[dict[str, str]]:
    staged = []
    for artifact in ARTIFACTS_TO_STAGE:
        source = artifact["source"]
        destination = artifact["destination"]
        source_hash = _sha256(source)
        if source_hash != artifact["expected_source_sha256"]:
            raise RuntimeError(f"{artifact['name']} preserved source hash mismatch: {source_hash}")
        if not destination.is_file():
            raise RuntimeError(f"{artifact['name']} expected existing build output missing: {destination}")
        previous_hash = _sha256(destination)
        allowed_destination_hashes = {
            artifact["expected_existing_destination_sha256"],
            artifact["expected_source_sha256"],
        }
        if previous_hash not in allowed_destination_hashes:
            raise RuntimeError(f"{artifact['name']} destination changed unexpectedly: {previous_hash}")

    for artifact in ARTIFACTS_TO_STAGE:
        source = artifact["source"]
        destination = artifact["destination"]
        already_staged = _sha256(destination) == artifact["expected_source_sha256"]
        if not already_staged:
            shutil.copyfile(source, destination)
        copied_hash = _sha256(destination)
        if copied_hash != artifact["expected_source_sha256"]:
            raise RuntimeError(f"{artifact['name']} staged hash mismatch: {copied_hash}")
        staged.append(
            {
                "name": artifact["name"],
                "source": str(source),
                "destination": str(destination),
                "sha256": copied_hash,
                "action": "already-present" if already_staged else "copied-preserved-bytes",
            }
        )
    return staged


if __name__ == "__main__":
    for item in stage():
        print(item)
