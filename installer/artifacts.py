#!/usr/bin/env python3
"""
Run artifacts for RIS foundation installation (minimal).

Consolidated from the Mays-Orders-AWS installer routine (verified there):
- sanitized plan copies (no secrets in stored artifacts),
- per-run directories (context, plans, logs),
- retention cleanup (keep newest runs).

NOT transferred (no proven need / separate concerns):
- plan integrity gate engine, deployment identity guard,
  secret-filter logging framework.

All operations are LOCAL filesystem only (no AWS contact).
"""

import copy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SENSITIVE_KEY_PARTS = ("password", "secret", "key", "token", "credential")

DEFAULT_BASE_DIR = ".ris-installer/runs"
DEFAULT_KEEP_LAST = 10


def sanitize_plan_json(plan_json: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep-copied plan with sensitive values redacted.

    Scans resource change before/after maps for sensitive key names
    (password/secret/key/token/credential, case-insensitive) and replaces
    values with "***REDACTED***". Input is never mutated.
    """
    sanitized = copy.deepcopy(plan_json)
    changes = sanitized.get("resource_changes")
    if not isinstance(changes, list):
        return sanitized
    for change in changes:
        if not isinstance(change, dict):
            continue
        change_data = change.get("change", {})
        if not isinstance(change_data, dict):
            continue
        for section in ("after", "before"):
            values = change_data.get(section, {})
            if not isinstance(values, dict):
                continue
            for key in list(values.keys()):
                lowered = str(key).lower()
                if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                    values[key] = "***REDACTED***"
    return sanitized


class RunArtifacts:
    """Per-run artifact directory (local only, no AWS contact)."""

    def __init__(self, base_dir: str = DEFAULT_BASE_DIR) -> None:
        self.base_dir = Path(base_dir)

    def create_run_dir(self, run_id: Optional[str] = None) -> Path:
        """Create runs/<run_id>/ with logs/, plans/, artifacts/."""
        rid = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_dir = self.base_dir / rid
        for sub in ("", "logs", "plans", "artifacts"):
            (run_dir / sub).mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_context(self, run_dir: Path, context: Dict[str, Any]) -> Path:
        """Save installation context (identifiers only — never secrets)."""
        target = Path(run_dir) / "context.json"
        target.write_text(json.dumps(context, indent=2, default=str))
        return target

    def save_plan_copy(
        self, run_dir: Path, plan_json: Dict[str, Any], name: str = "plan"
    ) -> Path:
        """Save SANITIZED plan JSON copy (originals stay with Terraform)."""
        target = Path(run_dir) / "plans" / f"{name}.sanitized.json"
        target.write_text(json.dumps(sanitize_plan_json(plan_json), indent=2))
        return target

    def save_log(self, run_dir: Path, content: str, name: str = "run") -> Path:
        """Save execution log text."""
        target = Path(run_dir) / "logs" / f"{name}.log"
        target.write_text(content)
        return target

    def list_runs(self) -> List[Path]:
        """Newest-first run directories (empty if none)."""
        if not self.base_dir.is_dir():
            return []
        return sorted(
            (p for p in self.base_dir.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )

    def cleanup_old_runs(self, keep_last: int = DEFAULT_KEEP_LAST) -> int:
        """Delete runs beyond keep_last newest. Returns removed count."""
        runs = self.list_runs()
        removed = 0
        for old in runs[keep_last:]:
            shutil.rmtree(old, ignore_errors=True)
            removed += 1
        return removed
