"""Reproduce the deployed RIS-DEV2 Orders Reader ZIP from its legacy build contract.

This is an artifact-preservation tool, not the current cross-platform bundle
builder. It deliberately preserves the historical per-member line endings and
DEFLATE archive format so the output remains byte-identical to the deployed
reader artifact. New/canonical bundles must continue using lambda/build_zip.py.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "terraform" / "artifacts" / (
    "ris-dev2-orders-reader-610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b.zip"
)
EXPECTED_SHA256 = (
    "610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b"
)
FIXED_DATE = (1980, 1, 1, 0, 0, 0)

# Sorted by source path, matching build_zip.py at the deployed reader source
# revision. CRLF members are reconstructed from the exact digest-matching
# historical archive recipe; the other member remains LF.
MEMBERS = (
    ("agents/ecosystem/worker_authorization.py", "worker_authorization.py", "CRLF"),
    ("agents/orders/agent_order.py", "agent_order.py", "LF"),
    ("agents/transport/order_transport.py", "order_transport.py", "CRLF"),
    ("lambda/orders_reader.py", "orders_reader.py", "CRLF"),
)


def build() -> dict[str, object]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, name, newline in MEMBERS:
            data = (ROOT / source).read_bytes().replace(b"\r\n", b"\n")
            if newline == "CRLF":
                data = data.replace(b"\n", b"\r\n")
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.create_system = 0
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)

    payload = buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            f"preserved reader digest mismatch: expected {EXPECTED_SHA256}, got {digest}"
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(payload)
    with zipfile.ZipFile(OUTPUT) as archive:
        bad_member = archive.testzip()
        if bad_member is not None or len(archive.infolist()) != len(MEMBERS):
            raise RuntimeError(f"invalid preserved reader ZIP: {bad_member!r}")
    return {
        "path": str(OUTPUT),
        "sha256": digest,
        "entries": len(MEMBERS),
        "source_revision": "f08dfff36b8d4727ebdbbe92b641fb60a4da88fd",
        "compression": "DEFLATE",
        "create_system": 0,
    }


if __name__ == "__main__":
    print(build())
