"""Collection isolation for the generated Mays-Orders test tree.

The Builder is a separate Python project embedded below ``installer/projects``.
Its tests intentionally use top-level imports (``installer``, ``index``,
``module_builder`` and script modules), while RIS has its own top-level
``installer`` package.  Keep the Builder paths local to collection of each
Builder test file so a full RIS collection cannot cross-import either project.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


# The existing Git installation is not visible to subprocesses launched from
# the isolated R07A Python environment.  Expose that executable for offline
# tests without installing or emulating Git.
if os.name == "nt":
    _GIT_CMD_DIR = Path(r"C:\Program Files\Git\cmd")
    if (_GIT_CMD_DIR / "git.exe").exists():
        _path_parts = os.environ.get("PATH", "").split(os.pathsep)
        if str(_GIT_CMD_DIR) not in _path_parts:
            os.environ["PATH"] = str(_GIT_CMD_DIR) + os.pathsep + os.environ.get(
                "PATH", "")


REPO_ROOT = Path(__file__).resolve().parent
BUILDER_ROOT = REPO_ROOT / "installer" / "projects" / "mays_order_builder"


def _path_is_below(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _paths_for_builder_directory(path: Path) -> tuple[Path, ...]:
    if not _path_is_below(path, BUILDER_ROOT):
        return ()
    relative = path.relative_to(BUILDER_ROOT)
    if not relative.parts:
        return (BUILDER_ROOT,)
    first = relative.parts[0]
    if first in {"cognito_backup", "installer", "module_builder"}:
        return (BUILDER_ROOT,)
    if first == "lambda":
        return (BUILDER_ROOT / "lambda" / "src",)
    if first == "scripts":
        return (BUILDER_ROOT / "scripts",)
    return ()


def _forget_modules_loaded_from(paths: tuple[Path, ...]) -> None:
    normalized = tuple(path.resolve() for path in paths)
    for name, module in list(sys.modules.items()):
        module_path = getattr(module, "__file__", None)
        if not module_path:
            continue
        try:
            resolved = Path(module_path).resolve()
        except OSError:
            continue
        if any(_path_is_below(resolved, path) for path in normalized):
            sys.modules.pop(name, None)


_ACTIVE_PATHS: dict[str, tuple[Path, tuple[Path, ...]]] = {}
_INSERTED_PATHS: list[Path] = []
_RUNTIME_PATHS: dict[str, tuple[Path, ...]] = {}


def _collector_path(collector) -> Path | None:
    value = getattr(collector, "path", None)
    if value is None:
        return None
    return Path(value).resolve()


def pytest_collectstart(collector) -> None:
    path = _collector_path(collector)
    if path is None:
        return
    if path == REPO_ROOT / "tests" or path.parent == REPO_ROOT:
        _end_builder_isolation()
    paths = _paths_for_builder_directory(path)
    if not paths:
        return

    # A root-level collection may have imported RIS's package with the same
    # top-level name already.  Remove only that cached package before loading
    # the isolated Builder test tree.
    if path == BUILDER_ROOT:
        _forget_modules_loaded_from((BUILDER_ROOT,))

    inserted: list[Path] = []
    for candidate in reversed(paths):
        value = str(candidate)
        if value not in sys.path:
            sys.path.insert(0, value)
            inserted.append(candidate)
    _ACTIVE_PATHS[getattr(collector, "nodeid", str(path))] = (
        path,
        tuple(inserted),
    )
    _INSERTED_PATHS.extend(inserted)


def pytest_collectreport(report) -> None:
    entry = _ACTIVE_PATHS.pop(report.nodeid, ())
    if not entry:
        return
    path, inserted = entry
    if path != BUILDER_ROOT:
        return
    _end_builder_isolation()


def _end_builder_isolation() -> None:
    """Restore RIS imports before the repository's own tests are collected."""
    for candidate in reversed(_INSERTED_PATHS):
        try:
            sys.path.remove(str(candidate))
        except ValueError:
            pass
    _INSERTED_PATHS.clear()
    _forget_modules_loaded_from((BUILDER_ROOT,))
    # ``installer`` can be a namespace package after pytest's import-mode
    # handling, so path-based cleanup alone is insufficient.
    for name in list(sys.modules):
        if name == "installer" or name.startswith("installer."):
            sys.modules.pop(name, None)


def pytest_runtest_setup(item) -> None:
    """Activate Builder import roots for runtime-only test imports.

    Some Builder tests resolve top-level Lambda modules from mock patch targets
    during test execution rather than during collection.  Collection cleanup
    must still happen before RIS tests, so the path is scoped to the individual
    Builder test instead of being left globally active.
    """
    path = _collector_path(item)
    if path is None:
        return
    try:
        is_builder_lambda = path.is_relative_to(BUILDER_ROOT / "lambda")
    except AttributeError:  # pragma: no cover - Python 3.8 compatibility
        is_builder_lambda = _path_is_below(path, BUILDER_ROOT / "lambda")
    if not is_builder_lambda:
        return
    paths = _paths_for_builder_directory(path)
    if not paths:
        return
    inserted: list[Path] = []
    for candidate in reversed(paths):
        value = str(candidate)
        if value not in sys.path:
            sys.path.insert(0, value)
            inserted.append(candidate)
    _RUNTIME_PATHS[item.nodeid] = tuple(inserted)


def pytest_runtest_teardown(item, nextitem) -> None:
    path = _collector_path(item)
    inserted = _RUNTIME_PATHS.pop(item.nodeid, ())
    for candidate in inserted:
        try:
            sys.path.remove(str(candidate))
        except ValueError:
            pass
    if inserted:
        _forget_modules_loaded_from(inserted)
    if path is not None and _path_is_below(path, BUILDER_ROOT):
        # Builder and RIS both expose a top-level ``installer`` package.  A
        # Builder test can import it at runtime without a __file__ on the
        # namespace package, so path-based cleanup alone is insufficient.
        for name in list(sys.modules):
            if name == "installer" or name.startswith("installer."):
                sys.modules.pop(name, None)
