"""Regression tests for the per-project Terraform overlay (Phase 2, ris-dev).

The permanent dev install ``ris-dev`` needs site-specific browser-login values
(OAuth callback/logout URLs, CORS origins, Cognito custom domain + ACM ARN).
Those must not be baked into the reusable Terraform module defaults, because
the same modules build ``ris-a``/``ris-b`` and future installations.

The committed overlay lives in ``installer/project-configs/<project>.json`` and
is loaded by ``installer.ris.load_project_config``. These tests pin:

  * only the named project receives the overlay,
  * the reusable module/root defaults stay OFF (backwards compatible),
  * the overlay is fail-closed on mismatch, secrets, wildcards, unknown keys,
  * the verifier reads the SAME overlay as the installer (no drift).

No AWS access is required.
"""

import json
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from installer.ris import (  # noqa: E402
    PROJECT_CONFIG_ALLOWED_KEYS,
    PROJECT_CONFIG_DIR,
    RisInstallContext,
    load_project_config,
)

CONFIG_DIR = os.path.join(REPO, "installer", PROJECT_CONFIG_DIR)
RIS_DEV_CONFIG = os.path.join(CONFIG_DIR, "ris-dev.json")
ROOT_VARS = os.path.join(REPO, "terraform", "variables.tf")
COGNITO_VARS = os.path.join(REPO, "terraform", "modules", "cognito", "variables.tf")
API_VARS = os.path.join(REPO, "terraform", "modules", "api", "variables.tf")
RUNNER = os.path.join(REPO, "scripts", "parallel_tests.sh")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _var_default(text, name):
    match = re.search(r'variable\s+"%s"\s*\{(.*?)\n\}' % re.escape(name), text, re.S)
    assert match, "variable %r not found" % name
    default = re.search(r"default\s*=\s*(\S+)", match.group(1))
    return default.group(1) if default else None


class TestOverlaySelection(unittest.TestCase):
    def test_ris_dev_overlay_exists_and_loads(self):
        cfg = load_project_config("ris-dev")
        self.assertTrue(cfg, "ris-dev overlay must be present and non-empty")

    def test_ris_dev_overlay_names_the_project(self):
        data = json.loads(_read(RIS_DEV_CONFIG))
        self.assertEqual("ris-dev", data["project_name"])

    def test_other_projects_have_no_overlay(self):
        for project in ("ris-a", "ris-b", "mays-ris", "mays-ris-e2e-test"):
            self.assertEqual({}, load_project_config(project),
                             "%s must NOT inherit the ris-dev overlay" % project)

    def test_only_allowed_keys_present(self):
        data = json.loads(_read(RIS_DEV_CONFIG))
        unknown = set(data["terraform_vars"]) - PROJECT_CONFIG_ALLOWED_KEYS
        self.assertEqual(set(), unknown)

    def test_overlay_activates_oauth_and_custom_domain(self):
        cfg = load_project_config("ris-dev")
        self.assertEqual("true", cfg["identity_oauth_enabled"])
        self.assertEqual("true", cfg["identity_custom_domain_enabled"])
        self.assertEqual("auth.mays-job-matcher.app", cfg["identity_custom_domain"])

    def test_overlay_references_existing_us_east_1_cert(self):
        cfg = load_project_config("ris-dev")
        arn = cfg["identity_custom_domain_certificate_arn"]
        self.assertIn(":acm:us-east-1:", arn,
                      "Cognito custom domains require a us-east-1 certificate")


class TestOverlaySafety(unittest.TestCase):
    def test_no_wildcard_cors_origin(self):
        cfg = load_project_config("ris-dev")
        self.assertNotIn("*", cfg["api_cors_origins"])
        self.assertNotIn('"*"', cfg["api_cors_origins"])

    def test_cors_origins_are_explicit_jobsearch_frontends(self):
        cfg = load_project_config("ris-dev")
        # JSON list literal -> parse back for a robust assertion.
        origins = json.loads(cfg["api_cors_origins"])
        self.assertEqual(
            sorted(["http://localhost:5173",
                    "https://mays-job-matcher.vercel.app",
                    "https://www.mays-job-matcher.app"]),
            sorted(origins),
        )

    def test_callback_and_logout_urls_are_explicit(self):
        cfg = load_project_config("ris-dev")
        callbacks = json.loads(cfg["identity_oauth_callback_urls"])
        logouts = json.loads(cfg["identity_oauth_logout_urls"])
        self.assertTrue(all(u.endswith("/auth/callback") for u in callbacks))
        self.assertTrue(all(o.startswith("http") for o in logouts))
        self.assertNotIn("*", cfg["identity_oauth_callback_urls"])

    def test_no_secret_like_values_in_config(self):
        data = json.loads(_read(RIS_DEV_CONFIG))
        blob = json.dumps(data).lower()
        for marker in ("secret", "password", "client_secret"):
            self.assertNotIn(
                '%s":' % marker, blob,
                "overlay must never carry a value keyed like a secret")

    def test_project_mismatch_is_rejected(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / PROJECT_CONFIG_DIR
            cfg_dir.mkdir()
            (cfg_dir / "ris-dev.json").write_text(json.dumps({
                "project_name": "some-other-project",
                "terraform_vars": {"identity_oauth_enabled": "true"},
            }))
            with self.assertRaises(ValueError):
                load_project_config("ris-dev", installer_dir=Path(tmp))

    def test_unknown_key_is_rejected(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / PROJECT_CONFIG_DIR
            cfg_dir.mkdir()
            (cfg_dir / "ris-dev.json").write_text(json.dumps({
                "project_name": "ris-dev",
                "terraform_vars": {"not_a_real_var": "1"},
            }))
            with self.assertRaises(ValueError):
                load_project_config("ris-dev", installer_dir=Path(tmp))

    def test_wildcard_cors_is_rejected(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / PROJECT_CONFIG_DIR
            cfg_dir.mkdir()
            (cfg_dir / "ris-dev.json").write_text(json.dumps({
                "project_name": "ris-dev",
                "terraform_vars": {"api_cors_origins": '["*"]'},
            }))
            with self.assertRaises(ValueError):
                load_project_config("ris-dev", installer_dir=Path(tmp))


class TestModuleDefaultsStayOff(unittest.TestCase):
    """Reusable module/root defaults must remain backwards compatible (OFF)."""

    def test_cognito_oauth_default_off(self):
        self.assertEqual("false", _var_default(_read(COGNITO_VARS), "oauth_enabled"))

    def test_cognito_custom_domain_default_off(self):
        self.assertEqual("false",
                         _var_default(_read(COGNITO_VARS), "custom_domain_enabled"))

    def test_root_oauth_default_off(self):
        self.assertEqual("false",
                         _var_default(_read(ROOT_VARS), "identity_oauth_enabled"))

    def test_root_cors_default_empty(self):
        self.assertEqual("[]", _var_default(_read(ROOT_VARS), "api_cors_origins"))

    def test_api_module_cors_default_empty(self):
        self.assertEqual("[]", _var_default(_read(API_VARS), "cors_origins"))


class TestInstallerWiring(unittest.TestCase):
    def test_overlay_reaches_terraform_vars(self):
        ctx = RisInstallContext(project_name="ris-dev", environment="dev")
        variables = ctx.terraform_vars()
        self.assertEqual("true", variables["identity_oauth_enabled"])
        self.assertEqual("auth.mays-job-matcher.app",
                         variables["identity_custom_domain"])

    def test_ris_a_gets_no_oauth_vars(self):
        ctx = RisInstallContext(project_name="ris-a", environment="dev")
        variables = ctx.terraform_vars()
        self.assertNotIn("identity_oauth_enabled", variables)
        self.assertNotIn("api_cors_origins", variables)

    def test_explicit_var_overrides_overlay_for_rollback(self):
        ctx = RisInstallContext(
            project_name="ris-dev", environment="dev",
            extra_vars={"identity_oauth_enabled": "false"})
        self.assertEqual("false", ctx.terraform_vars()["identity_oauth_enabled"])

    def test_identity_still_wins_over_overlay_and_var(self):
        ctx = RisInstallContext(
            project_name="ris-dev", environment="dev",
            extra_vars={"project_name": "evil", "environment": "prod"})
        variables = ctx.terraform_vars()
        self.assertEqual("ris-dev", variables["project_name"])
        self.assertEqual("dev", variables["environment"])

    def test_verifier_reads_the_same_overlay(self):
        runner = _read(RUNNER)
        self.assertIn("project_overlay_vars", runner,
                      "verifier must reuse the committed overlay, not duplicate it")
        self.assertIn("load_project_config", runner,
                      "verifier must call the same loader as the installer")


if __name__ == "__main__":
    unittest.main()
