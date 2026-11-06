#!/usr/bin/env bash
set -euo pipefail

# Reproducible local QA for MAYS-XREPO-V1. No GitHub API, no dispatch, no writes.
cd "$(git rev-parse --show-toplevel)"

echo "== Python syntax =="
python3 -m py_compile \
  scripts/xrepo/validate_event.py \
  scripts/xrepo/apply_event.py \
  scripts/xrepo/build_event.py \
  scripts/xrepo/test_validate_event.py \
  scripts/xrepo/test_apply_event.py \
  scripts/xrepo/test_build_event.py

echo "== Contract/receiver/sender tests =="
python3 -m unittest discover -s scripts/xrepo -p 'test_*.py' -v

echo "== JSON fixtures/schema =="
python3 - <<'PY'
import json
from pathlib import Path

for path in sorted(Path("docs/xrepo").rglob("*.json")):
    json.loads(path.read_text(encoding="utf-8"))
    print(f"JSON OK {path}")
PY

echo "== Workflow YAML (optional; requires PyYAML) =="
python3 - <<'PY'
try:
    import yaml
except ImportError:
    print("SKIP PyYAML not installed")
else:
    from pathlib import Path

    for path in sorted(Path(".github/workflows").glob("xrepo-*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit(f"YAML is not a mapping: {path}")
        print(f"YAML OK {path}")
PY

echo "== Diff check =="
git diff --check

echo "LOCAL QA PASS"
