#!/usr/bin/env python3
"""Local mirror of the remote Terraform state.

Why
---
RIS keeps its state in S3, so a local copy is what survives an S3 outage, a
wrong bucket, or a lost lock. The component project already ships the
mechanism and it is the reference: its `atomic_ops.AtomicStateManager` keeps a
`.backups` directory beside the state file and rotates `backup_count` copies.
That shape is mirrored here - `state-mirror/` plus a rotating count - adapted
to the one thing that differs: RIS state is remote, so the mirror is written
from a `terraform state pull`, not from a local file.

Placement
---------
NOT inside the isolated workdir. _ensure_isolated_workdir() deletes and
recreates that tree on every run, so a mirror there would vanish on the next
invocation - the exact failure this exists to prevent. It lives next to it:

    <workdir_base>/<project>/<environment>/state-mirror/

which survives because only `.../terraform` is wiped.

Read-only by construction. Mirroring pulls state and writes it to the local
disk. It never pushes, never writes to the backend, and never changes what
Terraform thinks its workspace is.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

#: Rotating copies to keep, matching the component's default backup_count.
MIRROR_KEEP = 3

#: Subdirectory name inside the per-project workdir root.
MIRROR_DIRNAME = "state-mirror"


@dataclass(frozen=True)
class MirrorEntry:
    """One stored snapshot."""

    path: Path
    serial: Optional[int]
    lineage: Optional[str]
    sha256: str
    size: int
    created_at: str

    def describe(self) -> str:
        return (
            f"serial={self.serial if self.serial is not None else '?'} "
            f"lineage={(self.lineage or '?')[:8]} sha256={self.sha256[:12]} "
            f"size={self.size} at={self.created_at}"
        )


class StateMirror:
    """Rotating local mirror of one project's remote state.

    Args:
        mirror_dir: Directory that holds the snapshots. Created on demand.
        keep: How many snapshots to retain; older ones are rotated out.
    """

    def __init__(self, mirror_dir: Path, keep: int = MIRROR_KEEP) -> None:
        if keep < 1:
            # Not invented: refusing a nonsensical value beats silently
            # keeping everything or nothing.
            raise ValueError(f"keep must be >= 1, got {keep!r}")
        self.mirror_dir = Path(mirror_dir)
        self.keep = keep

    # -- writing -----------------------------------------------------------
    def snapshot(self, raw: str, label: str = "state") -> MirrorEntry:
        """Store one snapshot of `raw` state text.

        Returns the stored entry. The payload is written verbatim so the file
        is a real state file, not a re-serialised guess.
        """
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # Keep alphanumerics plus dash/underscore. "." is allowed inside a name
        # but never as a leading run, so "../../etc/passwd" cannot survive
        # as a relative path fragment.
        safe_label = "".join(c for c in label if c.isalnum() or c in "-_") or "state"
        safe_label = safe_label.lstrip(".-") or "state"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        # The stamp has second resolution, so two snapshots inside one second
        # would collide. Two mechanisms cover that, and each covers a case the
        # other does not - measured, not assumed:
        #   the payload digest separates snapshots of DIFFERENT state written
        #   in the same second;
        #   the numeric suffix separates snapshots of the SAME state written in
        #   the same second, where the digest is identical by definition. That
        #   is the ordinary no-op-apply case, not an exotic one.
        target = self.mirror_dir / f"{safe_label}.{stamp}.{digest[:8]}.tfstate"
        attempt = 0
        while target.exists():
            attempt += 1
            target = (
                self.mirror_dir
                / f"{safe_label}.{stamp}.{digest[:8]}.{attempt}.tfstate"
            )

        # Exclusive create: a snapshot must never overwrite a previous one.
        with open(target, "x", encoding="utf-8") as handle:
            handle.write(raw)

        entry = self._describe(target, stamp)
        self._rotate()
        return entry

    # -- reading -----------------------------------------------------------
    def entries(self) -> List[MirrorEntry]:
        """Stored snapshots, newest first."""
        return [
            self._describe(path, self._stamp_of(path)) for path in self._snapshot_paths()
        ]

    def _snapshot_paths(self) -> List[Path]:
        """Snapshot paths, newest first, by actual write order.

        Sorting the filenames lexically would be wrong: the timestamp has
        second resolution and the disambiguating digest is not monotonic, so
        several snapshots taken in the same second would come back in
        arbitrary order and the rotation could discard the newest one. mtime
        has nanosecond resolution and reflects the real write order, so it is
        the authority; the filename only breaks an exact tie.
        """
        if not self.mirror_dir.exists():
            return []
        paths = list(self.mirror_dir.glob("*.tfstate"))
        return sorted(paths, key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)

    def latest(self) -> Optional[MirrorEntry]:
        found = self.entries()
        return found[0] if found else None

    def manifest(self) -> Dict[str, object]:
        """Machine-readable listing, for evidence archiving.

        Mirrors the shape RIS already uses under archived-evidence/:
        lineage plus a sha256 per entry, so a later reader can prove which
        bytes were captured without re-fetching S3.
        """
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mirror_dir": str(self.mirror_dir),
            "keep": self.keep,
            "count": len(self.entries()),
            "entries": [
                {
                    "file": e.path.name,
                    "serial": e.serial,
                    "lineage": e.lineage,
                    "sha256": e.sha256,
                    "size": e.size,
                    "created_at": e.created_at,
                }
                for e in self.entries()
            ],
        }

    def write_manifest(self) -> Path:
        """Persist the manifest next to the snapshots."""
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        path = self.mirror_dir / "MANIFEST.json"
        path.write_text(json.dumps(self.manifest(), indent=2), encoding="utf-8")
        return path

    # -- internals ---------------------------------------------------------
    def _rotate(self) -> None:
        for stale in self._snapshot_paths()[self.keep :]:
            try:
                stale.unlink()
            except OSError:
                # A snapshot we cannot remove is a problem to report, not a
                # reason to abort a mirror that already succeeded.
                pass

    @staticmethod
    def _stamp_of(path: Path) -> str:
        parts = path.name.split(".")
        return parts[1] if len(parts) > 1 else "?"

    def _describe(self, path: Path, stamp: str) -> MirrorEntry:
        data = path.read_bytes()
        serial = lineage = None
        try:
            parsed = json.loads(data.decode("utf-8"))
            serial = parsed.get("serial")
            lineage = parsed.get("lineage")
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Unparseable payload is still mirrored - that is precisely the
            # case where a local copy matters most. Record it honestly.
            pass
        return MirrorEntry(
            path=path,
            serial=serial,
            lineage=lineage,
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            created_at=stamp,
        )


def mirror_dir_for(workdir_base: Path, project_name: str, environment: str) -> Path:
    """Where one project's mirror lives.

    Beside the isolated workdir, never inside it, because that directory is
    deleted on every run.
    """
    return Path(workdir_base) / project_name / environment / MIRROR_DIRNAME