"""Static IaC contract for the consent enforcement switches.

Regression guard for RIS-CONSENT-IAC-ALIGNMENT-01.

Before this gate, ``lambda/handler.py`` and ``jobsearch/consent_contract.py``
read five consent variables that ``terraform/modules/lambda`` never declared.

* ``CV_STORAGE_CONSENT_ENFORCED``
* ``SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED``
* ``CONSENT_NOTICE_STATE_ENFORCED``
* ``CONSENT_PILOT_ALLOWLIST``

(``APPLICATION_CONSENT_ENFORCED`` was already wired.) A routine apply from a
checkout without the wiring therefore removed keys from the live Lambda and
weakened enforcement.

These tests are static: they read Terraform, the installer overlay and the
Python sources. They never run ``terraform plan``, never contact AWS and never
apply anything.
"""

import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from installer.ris import (  # noqa: E402
    PROJECT_CONFIG_ALLOWED_KEYS,
    load_project_config,
)

TF = ROOT / "terraform"
LAMBDA_MAIN = TF / "modules" / "lambda" / "main.tf"
LAMBDA_VARS = TF / "modules" / "lambda" / "variables.tf"
ROOT_MAIN = TF / "main.tf"
ROOT_VARS = TF / "variables.tf"
HANDLER = ROOT / "lambda" / "handler.py"
CONTRACT = ROOT / "jobsearch" / "consent_contract.py"
OVERLAY = ROOT / "installer" / "project-configs" / "ris-dev.json"

#: Lambda env name -> Terraform variable (root + lambda module).
ENV_TO_VAR = {
    "APPLICATION_CONSENT_ENFORCED": "application_consent_enforced",
    "CV_STORAGE_CONSENT_ENFORCED": "cv_storage_consent_enforced",
    "SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED":
        "search_profile_storage_consent_enforced",
    "CONSENT_NOTICE_STATE_ENFORCED": "consent_notice_state_enforced",
    "CONSENT_PILOT_ALLOWLIST": "consent_pilot_allowlist",
}


def _read(path):
    return path.read_text(encoding="utf-8")


def _variable_block(text, name):
    match = re.search(
        r'variable\s+"%s"\s*\{(.*?)\n\}' % re.escape(name), text, re.S)
    assert match, "variable %r missing" % name
    return match.group(1)


class TestHandlerVariablesAreWired(unittest.TestCase):
    def setUp(self):
        self.lambda_main = _read(LAMBDA_MAIN)
        self.lambda_vars = _read(LAMBDA_VARS)
        self.root_main = _read(ROOT_MAIN)
        self.root_vars = _read(ROOT_VARS)
        self.python = _read(HANDLER) + _read(CONTRACT)

    def test_every_runtime_consent_env_var_is_covered(self):
        """Guard against future drift: a new read must appear in ENV_TO_VAR."""
        for name in ENV_TO_VAR:
            self.assertIn(name, self.python,
                          "%s is no longer read; update ENV_TO_VAR" % name)
        runtime_reads = set(re.findall(
            r'(?:os\.environ\.get|enforcement_flag)\(\s*"([A-Z0-9_]*(?:'
            r'CONSENT|PILOT)[A-Z0-9_]*)"', self.python))
        self.assertEqual(
            {"APPLICATION_CONSENT_ENFORCED",
             "CV_STORAGE_CONSENT_ENFORCED",
             "SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED",
             "CONSENT_NOTICE_STATE_ENFORCED",
             "CONSENT_PILOT_ALLOWLIST"},
            runtime_reads)

    def test_lambda_env_reads_a_declared_module_variable(self):
        for env_name, var_name in ENV_TO_VAR.items():
            with self.subTest(env=env_name):
                self.assertIn(env_name, self.lambda_main)
                self.assertRegex(
                    self.lambda_main,
                    r"%s\s*=\s*(?:\(\s*)?var\.%s\b" % (
                        re.escape(env_name), re.escape(var_name)),
                    "%s is not wired to var.%s" % (env_name, var_name))
                self.assertIn('variable "%s"' % var_name, self.lambda_vars)

    def test_root_module_call_passes_every_variable(self):
        for var_name in ENV_TO_VAR.values():
            with self.subTest(var=var_name):
                self.assertRegex(
                    self.root_main,
                    r"\b%s\s*=\s*var\.%s\b" % (
                        re.escape(var_name), re.escape(var_name)))
                self.assertIn('variable "%s"' % var_name, self.root_vars)

    def test_defaults_are_safe_and_never_enable_enforcement(self):
        for var_name in ENV_TO_VAR.values():
            for label, text in (("root", self.root_vars),
                                ("module", self.lambda_vars)):
                block = _variable_block(text, var_name)
                with self.subTest(var=var_name, scope=label):
                    self.assertNotRegex(
                        block, r"default\s*=\s*true",
                        "%s must never default to enforcement" % var_name)
                    if var_name == "consent_pilot_allowlist":
                        self.assertRegex(block, r'default\s*=\s*""')
                    else:
                        self.assertRegex(block, r"default\s*=\s*false")

    def test_env_map_contains_no_hard_coded_true(self):
        """Enforcement must come from variables, never from a literal."""
        env_block = self.lambda_main.split("environment {", 1)[1]
        env_block = env_block.split("depends_on", 1)[0]
        for env_name, var_name in ENV_TO_VAR.items():
            match = re.search(
                r"%s\s*=\s*(?:\(\s*)?(var\.\w+)" % re.escape(env_name),
                env_block, re.S)
            self.assertIsNotNone(match)
            self.assertEqual("var.%s" % var_name, match.group(1))
            tail = env_block[match.end():match.end() + 80]
            self.assertNotRegex(tail, r'^\s*"(?:true|false)"')


class TestFailClosedPlanGuards(unittest.TestCase):
    def setUp(self):
        self.lambda_main = _read(LAMBDA_MAIN)
        self.root_vars = _read(ROOT_VARS)
        self.lambda_vars = _read(LAMBDA_VARS)

    def test_enforcement_requires_notice_state_enforcement(self):
        self.assertIn("lifecycle {", self.lambda_main)
        self.assertIn("precondition {", self.lambda_main)
        self.assertIn("consent_notice_state_enforced must be true", 
                      self.lambda_main)

    def test_pilot_gates_require_an_allowlist(self):
        self.assertIn(
            "require a non-empty consent_pilot_allowlist", self.lambda_main)

    def test_allowlist_is_sensitive_and_validated(self):
        for text in (self.root_vars, self.lambda_vars):
            block = _variable_block(text, "consent_pilot_allowlist")
            self.assertIn("sensitive   = true", block)
            self.assertIn("validation {", block)
            self.assertIn('<issuer>|<sub>', block)


class TestInstallerOverlaySafety(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(_read(OVERLAY))["terraform_vars"]

    def test_consent_switches_are_allowed_overlay_keys(self):
        for key in ("cv_storage_consent_enforced",
                    "search_profile_storage_consent_enforced",
                    "consent_notice_state_enforced"):
            self.assertIn(key, PROJECT_CONFIG_ALLOWED_KEYS)

    def test_allowlist_is_never_an_overlay_key(self):
        self.assertNotIn("consent_pilot_allowlist", PROJECT_CONFIG_ALLOWED_KEYS)

    def test_committed_overlay_does_not_enable_enforcement(self):
        for key in ("application_consent_enforced",
                    "cv_storage_consent_enforced",
                    "search_profile_storage_consent_enforced",
                    "consent_notice_state_enforced"):
            with self.subTest(key=key):
                self.assertNotEqual("true", self.config.get(key))
        self.assertNotIn("consent_pilot_allowlist", self.config)
        blob = json.dumps(self.config)
        self.assertNotIn("|", blob)

    def test_overlay_cannot_carry_the_allowlist(self):
        import tempfile
        from pathlib import Path as _Path

        from installer.ris import PROJECT_CONFIG_DIR
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = _Path(tmp) / PROJECT_CONFIG_DIR
            cfg_dir.mkdir()
            (cfg_dir / "ris-dev.json").write_text(json.dumps({
                "project_name": "ris-dev",
                "terraform_vars": {
                    "consent_pilot_allowlist": "https://issuer|sub",
                },
            }))
            with self.assertRaises(ValueError):
                load_project_config("ris-dev", installer_dir=_Path(tmp))


if __name__ == "__main__":
    unittest.main()
