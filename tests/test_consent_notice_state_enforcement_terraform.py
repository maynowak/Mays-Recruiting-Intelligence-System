"""Terraform wiring for the consent notice-state enforcement gate.

Static structural assertions only. They never run `terraform plan` and never
touch AWS. The gate `CONSENT_NOTICE_STATE_ENFORCED` existed in the Python
runtime but was not wired into Terraform, so it could not be enabled through an
approved plan. These tests pin the wiring and keep the default fail-closed
(disabled) until a separate activation decision.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF = os.path.join(ROOT, "terraform")


def read(rel):
    with open(os.path.join(TF, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def variable_block(text, name):
    match = re.search(
        r'variable\s+"%s"\s*\{(.*?)\n\}' % re.escape(name), text, re.S)
    return match.group(1) if match else ""


class ConsentPilotAllowlistTests(unittest.TestCase):
    """Scoped pilot identity list: non-secret, empty by default, wired."""

    def setUp(self):
        self.root_variables = read("variables.tf")
        self.module_variables = read("modules/lambda/variables.tf")
        self.module_main = read("modules/lambda/main.tf")
        self.root_main = read("main.tf")

    def test_root_variable_is_string_default_empty(self):
        block = variable_block(self.root_variables, "consent_pilot_allowlist")
        self.assertTrue(block, "root variable is missing")
        self.assertRegex(block, r"type\s*=\s*string")
        self.assertRegex(block, r'default\s*=\s*""')

    def test_module_variable_is_string_default_empty(self):
        block = variable_block(
            self.module_variables, "consent_pilot_allowlist")
        self.assertTrue(block, "module variable is missing")
        self.assertRegex(block, r"type\s*=\s*string")
        self.assertRegex(block, r'default\s*=\s*""')

    def test_module_environment_wires_the_allowlist(self):
        self.assertRegex(
            self.module_main,
            r"CONSENT_PILOT_ALLOWLIST\s*=\s*"
            r"var\.consent_pilot_allowlist")

    def test_module_environment_has_no_hardcoded_identity(self):
        self.assertNotRegex(
            self.module_main,
            r'CONSENT_PILOT_ALLOWLIST\s*=\s*"[^"]+"')

    def test_root_passes_the_allowlist_to_the_lambda_module(self):
        self.assertRegex(
            self.root_main,
            r"consent_pilot_allowlist\s*=\s*"
            r"var\.consent_pilot_allowlist")

    def test_project_configs_do_not_set_the_pilot_allowlist(self):
        for name in ("ris-dev.json", "ris-dev2.json"):
            path = os.path.join(ROOT, "installer", "project-configs", name)
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("consent_pilot_allowlist", text, name)


class RootVariablesTests(unittest.TestCase):
    def setUp(self):
        self.variables = read("variables.tf")

    def test_consent_notice_state_variable_is_bool_default_false(self):
        block = variable_block(self.variables, "consent_notice_state_enforced")
        self.assertTrue(block, "root variable is missing")
        self.assertRegex(block, r"type\s*=\s*bool")
        self.assertRegex(block, r"default\s*=\s*false")

    def test_application_consent_gate_stays_default_false(self):
        block = variable_block(self.variables, "application_consent_enforced")
        self.assertTrue(block, "application_consent_enforced variable is missing")
        self.assertRegex(block, r"type\s*=\s*bool")
        self.assertRegex(block, r"default\s*=\s*false")


class LambdaModuleTests(unittest.TestCase):
    def setUp(self):
        self.variables = read("modules/lambda/variables.tf")
        self.main = read("modules/lambda/main.tf")

    def test_module_consent_notice_state_variable_is_bool_default_false(self):
        block = variable_block(self.variables, "consent_notice_state_enforced")
        self.assertTrue(block, "module variable is missing")
        self.assertRegex(block, r"type\s*=\s*bool")
        self.assertRegex(block, r"default\s*=\s*false")

    def test_module_environment_wires_the_variable(self):
        self.assertRegex(
            self.main,
            r"CONSENT_NOTICE_STATE_ENFORCED\s*=\s*"
            r"var\.consent_notice_state_enforced\s*\?\s*"
            r'"true"\s*:\s*"false"')

    def test_module_environment_has_no_hardcoded_notice_enforcement(self):
        self.assertNotRegex(
            self.main, r'CONSENT_NOTICE_STATE_ENFORCED\s*=\s*"true"')

    def test_application_consent_gate_stays_wired_and_default_false(self):
        self.assertRegex(
            self.main,
            r"APPLICATION_CONSENT_ENFORCED\s*=\s*"
            r"var\.application_consent_enforced\s*\?\s*"
            r'"true"\s*:\s*"false"')
        self.assertNotRegex(
            self.main, r'APPLICATION_CONSENT_ENFORCED\s*=\s*"true"')


class RootWiringTests(unittest.TestCase):
    def setUp(self):
        self.main = read("main.tf")

    def test_root_passes_notice_state_variable_to_lambda_module(self):
        self.assertRegex(
            self.main,
            r"consent_notice_state_enforced\s*=\s*"
            r"var\.consent_notice_state_enforced")

    def test_root_passes_application_consent_variable_to_lambda_module(self):
        self.assertRegex(
            self.main,
            r"application_consent_enforced\s*=\s*"
            r"var\.application_consent_enforced")

    def test_both_gates_are_passed_by_the_same_lambda_module(self):
        lambda_block = self.main.split('module "lambda"', 1)[1]
        lambda_block = lambda_block.split("\nmodule ", 1)[0]
        self.assertIn("consent_notice_state_enforced", lambda_block)
        self.assertIn("application_consent_enforced", lambda_block)


class ProjectConfigTests(unittest.TestCase):
    """No live workspace config may pre-enable either gate."""

    def test_ris_dev_config_does_not_set_consent_flags(self):
        for name in ("ris-dev.json", "ris-dev2.json"):
            path = os.path.join(ROOT, "installer", "project-configs", name)
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("consent_notice_state_enforced", text, name)
            self.assertNotIn("application_consent_enforced", text, name)


if __name__ == "__main__":
    unittest.main()
