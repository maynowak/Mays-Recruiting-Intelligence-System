"""Cross-platform guards for the pinned Mays-Orders module builder.

The builder previously hardcoded a Windows Git path and a Windows Terraform
lookup, so a Linux G4 replan could not reproduce the generated module. These
checks protect the portability fix without invoking Git, Terraform or AWS.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "installer" / "build_mays_orders_module.py"
PIN = ROOT / "installer" / "mays-orders-builder.pinned.json"


def test_builder_has_no_windows_only_executable_paths():
    source = BUILDER.read_text(encoding="utf-8")
    assert r"C:\Program Files" not in source
    assert 'GIT_EXE = os.environ.get("GIT_EXE", "git")' in source
    assert "shutil.which(\"terraform\")" in source
    assert 'cmd = [GIT_EXE] + cmd[1:]' in source


def test_builder_pin_is_explicit():
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    assert pin["commit"] == "1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d"
    source = BUILDER.read_text(encoding="utf-8")
    assert 'PINNED_COMMIT = "1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d"' in source
