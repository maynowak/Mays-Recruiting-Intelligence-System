"""Portability of the Mays-Orders module builder on Linux/macOS/Windows.

The wrapper previously resolved Terraform through the Windows-only ``where``
command and hardcoded ``C:\\Program Files\\Git\\bin\\git.exe`` for every Git
call. These tests pin the platform-independent discovery (PATH via
``shutil.which``, explicit ``TERRAFORM_EXE`` / ``GIT_EXE`` overrides, Windows
Git install fallback) and the actionable fail-closed errors.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import installer.build_mays_orders_module as builder


def _write_executable(directory: Path, name: str) -> Path:
    path = directory / name
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


class _IsolatedDiscovery(unittest.TestCase):
    """Keep PATH and the env overrides isolated for every discovery test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin_dir = Path(self.tmp.name) / "bin"
        self.bin_dir.mkdir()
        self.empty_path = patch.dict(
            os.environ, {"PATH": str(self.bin_dir)}, clear=False
        )
        self.empty_path.start()
        self.addCleanup(self.empty_path.stop)
        self.addCleanup(self.tmp.cleanup)
        for var in ("TERRAFORM_EXE", "GIT_EXE"):
            patcher = patch.dict(os.environ, {var: ""}, clear=False)
            patcher.start()
            self.addCleanup(patcher.stop)
        self._constant_patches = [
            patch.object(builder, "TERRAFORM_EXE", ""),
            patch.object(builder, "GIT_EXE", ""),
        ]
        for patcher in self._constant_patches:
            patcher.start()
            self.addCleanup(patcher.stop)


class TerraformDiscoveryTest(_IsolatedDiscovery):
    def test_terraform_is_found_on_path_without_windows_where(self):
        expected = _write_executable(self.bin_dir, "terraform")
        self.assertEqual(str(expected), builder._terraform_exe())

    def test_terraform_env_override_wins_over_path(self):
        _write_executable(self.bin_dir, "terraform")
        override = _write_executable(Path(self.tmp.name), "terraform-custom")
        with patch.dict(os.environ, {"TERRAFORM_EXE": str(override)}):
            self.assertEqual(str(override), builder._terraform_exe())

    def test_missing_terraform_env_override_fails_closed(self):
        missing = str(Path(self.tmp.name) / "does-not-exist-terraform")
        with patch.dict(os.environ, {"TERRAFORM_EXE": missing}):
            with self.assertRaisesRegex(
                RuntimeError, "TERRAFORM_EXE ist gesetzt"
            ):
                builder._terraform_exe()

    def test_missing_terraform_reports_actionable_error(self):
        with patch.object(builder, "_is_windows", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                builder._terraform_exe()
        message = str(ctx.exception)
        self.assertIn("'terraform' wurde nicht gefunden", message)
        self.assertIn("TERRAFORM_EXE", message)
        self.assertIn("Terraform installieren", message)


class GitDiscoveryTest(_IsolatedDiscovery):
    def test_git_is_found_on_path(self):
        expected = _write_executable(self.bin_dir, "git")
        self.assertEqual(str(expected), builder._git_exe())

    def test_git_env_override_wins_over_path(self):
        _write_executable(self.bin_dir, "git")
        override = _write_executable(Path(self.tmp.name), "git-custom")
        with patch.dict(os.environ, {"GIT_EXE": str(override)}):
            self.assertEqual(str(override), builder._git_exe())

    def test_missing_git_reports_actionable_error(self):
        with patch.object(builder, "_is_windows", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                builder._git_exe()
        message = str(ctx.exception)
        self.assertIn("'git' wurde nicht gefunden", message)
        self.assertIn("GIT_EXE", message)
        self.assertIn("Git installieren", message)

    def test_windows_git_install_fallback_is_used(self):
        candidate = _write_executable(self.bin_dir, "git.exe")
        with patch.object(builder, "_is_windows", return_value=True), patch.object(
            builder, "_WINDOWS_GIT_CANDIDATES", (str(candidate),)
        ):
            self.assertEqual(str(candidate), builder._git_exe())

    def test_windows_without_git_never_invents_exe_name(self):
        with patch.object(builder, "_is_windows", return_value=True), patch.object(
            builder,
            "_WINDOWS_GIT_CANDIDATES",
            (str(Path(self.tmp.name) / "missing" / "git.exe"),),
        ):
            with self.assertRaisesRegex(RuntimeError, "GIT_EXE"):
                builder._git_exe()


class RunCommandTest(_IsolatedDiscovery):
    def _run_captured(self, cmd, resolved_git="/resolved/git",
                      resolved_terraform="/resolved/terraform", cwd=None):
        completed = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(builder, "_git_exe",
                          return_value=resolved_git), patch.object(
                builder, "_terraform_exe", return_value=resolved_terraform), patch(
                "installer.build_mays_orders_module.subprocess.run",
                return_value=completed) as mock_run:
            builder.run(cmd, cwd=cwd)
        args, kwargs = mock_run.call_args
        return args[0], kwargs

    def test_run_resolves_git_and_terraform_commands(self):
        git_cmd, _ = self._run_captured(["git", "-C", "repo", "status"])
        self.assertEqual("/resolved/git", git_cmd[0])
        self.assertEqual("-C", git_cmd[1])

        tf_cmd, tf_kwargs = self._run_captured(["terraform", "fmt", "-recursive"])
        self.assertEqual("/resolved/terraform", tf_cmd[0])
        self.assertEqual("fmt", tf_cmd[1])
        self.assertTrue(
            Path(tf_kwargs["env"]["TF_DATA_DIR"]).is_absolute()
        )

    def test_run_keeps_non_tool_commands_untouched(self):
        cmd = [sys.executable, "-m", "module_builder", "build"]
        executed, _ = self._run_captured(cmd)
        self.assertEqual(cmd, executed)

    def test_run_passes_cwd_through(self):
        _, kwargs = self._run_captured(["git", "status"], cwd="/some/module")
        self.assertEqual("/some/module", kwargs["cwd"])


class EnsureRepoCommandTest(_IsolatedDiscovery):
    def test_ensure_repo_uses_portable_git_token(self):
        builder_dir = Path(self.tmp.name) / "builder"
        builder_dir.mkdir()
        with patch.object(builder, "MAYS_ORDERS_BUILDER_DIR", builder_dir), patch.object(
            builder, "INSTALLER_PROJECTS", builder_dir.parent
        ), patch.object(builder, "run", return_value=MagicMock(returncode=0)) as mock_run, patch(
            "installer.build_mays_orders_module.subprocess.run",
            return_value=MagicMock(stdout=""),
        ):
            builder.ensure_repo()
        for args, _ in mock_run.call_args_list:
            self.assertEqual("git", args[0][0])
            self.assertNotIn("git.exe", args[0][0])

    def test_missing_terraform_blocks_post_run_checks(self):
        module_dir = Path(self.tmp.name) / "module"
        module_dir.mkdir()
        with patch.object(
            builder, "_terraform_exe",
            side_effect=RuntimeError("'terraform' wurde nicht gefunden."),
        ):
            with self.assertRaisesRegex(RuntimeError, "nicht gefunden"):
                builder.post_run_checks(module_dir)


class CliContractTest(_IsolatedDiscovery):
    def test_cli_parameters_are_preserved(self):
        with patch.object(builder, "ensure_repo"), patch.object(
            builder, "build_module"
        ) as mock_build, patch.object(
            sys, "argv",
            ["build_mays_orders_module", "--project-name", "ris-dev", "--force"],
        ):
            builder.main()
        mock_build.assert_called_once_with("ris-dev", True)

    def test_cli_defaults_are_preserved(self):
        with patch.object(builder, "ensure_repo"), patch.object(
            builder, "build_module"
        ) as mock_build, patch.object(
            sys, "argv", ["build_mays_orders_module"]
        ):
            builder.main()
        mock_build.assert_called_once_with("ris-dev2", False)


if __name__ == "__main__":
    unittest.main()
