"""
Tests for the persistent Cognito email-verification contract (G3).

Defect history: `identity_email_verification_enabled` defaulted to `false`
(the pre-Gate-11 behaviour) while no tfvars existed, so every *unpinned*
`terraform plan` proposed switching email verification OFF. That was
masked with `-var=identity_email_verification_enabled=true` in at least
8 gates, each time documented as a known "variable default artifact" and
never fixed.

The contract pinned here: repository configuration must resolve to the
delivered state (email verification ON) without any CLI flag, so that

  * an ordinary `terraform plan` proposes no Cognito change, and
  * a fresh installer run agrees with a later ordinary apply.

These tests read the Terraform sources and the installer directly — they do
not require AWS.
"""

import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

ROOT_VARS = os.path.join(REPO, "terraform", "variables.tf")
COGNITO_MAIN = os.path.join(REPO, "terraform", "modules", "cognito", "main.tf")
ROOT_MAIN = os.path.join(REPO, "terraform", "main.tf")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _variable_default(text, name):
    """Extract the `default` literal of a root variable block."""
    match = re.search(
        r'variable\s+"%s"\s*\{(.*?)\n\}' % re.escape(name), text, re.S)
    assert match, "variable %r not found" % name
    body = match.group(1)
    default = re.search(r"default\s*=\s*(\S+)", body)
    return default.group(1) if default else None


class TestRootVariableDefault(unittest.TestCase):
    def test_email_verification_default_is_enabled(self):
        """The delivered state is email verification ON. Config must say so."""
        self.assertEqual(
            "true", _variable_default(_read(ROOT_VARS),
                                      "identity_email_verification_enabled"),
            "identity_email_verification_enabled must default to true so an "
            "unpinned plan does not propose disabling email verification")

    def test_default_is_not_reintroduced_as_false(self):
        """Explicit guard against the historical defect returning."""
        text = _read(ROOT_VARS)
        self.assertNotIn("default     = false", text.split(
            'variable "identity_email_verification_enabled"')[1].split("\n}")[0],
            "email verification default must never silently revert to false")

    def test_no_tfvars_file_is_required(self):
        """The fix must not depend on an untracked local tfvars."""
        tfvars = [f for f in os.listdir(os.path.join(REPO, "terraform"))
                  if f.endswith(".tfvars") or f.endswith(".tfvars.json")]
        self.assertEqual([], tfvars,
                         "a committed tfvars would re-create the "
                         "flag-or-nothing problem; the root default is the "
                         "source of truth")


class TestModuleWiring(unittest.TestCase):
    def test_root_passes_variable_to_cognito_module(self):
        main = _read(ROOT_MAIN)
        self.assertRegex(
            main, r"email_verification_enabled\s*=\s*var\.identity_email_verification_enabled",
            "root module must forward identity_email_verification_enabled "
            "to the cognito module")

    def test_cognito_derives_auto_verified_attributes_from_the_flag(self):
        cognito = _read(COGNITO_MAIN)
        self.assertIn(
            'auto_verified_attributes = var.email_verification_enabled '
            '? ["email"] : []',
            cognito,
            "cognito module must derive auto_verified_attributes from the "
            "flag, so the resolved default fully determines behaviour")

    def test_cognito_receives_enabled_flag_from_root(self):
        """End-to-end resolution without evaluating Terraform.

        With no -var flags, Terraform substitutes the root default. The two
        links below plus the default assertion above are sufficient to
        conclude auto_verified_attributes == ["email"].
        """
        self.assertEqual(
            "true",
            _variable_default(_read(ROOT_VARS),
                              "identity_email_verification_enabled"))
        self.assertIn("email_verification_enabled = var.identity_email_verification_enabled",
                      _read(ROOT_MAIN))
        self.assertIn(
            'auto_verified_attributes = var.email_verification_enabled ? ["email"] : []',
            _read(COGNITO_MAIN))


class TestInstallerAgreesWithConfig(unittest.TestCase):
    """A fresh install must not diverge from a later ordinary apply."""

    def test_fresh_dev_install_relies_on_the_configured_default(self):
        from installer.ris import RisInstallContext
        ctx = RisInstallContext(project_name="mays-ris", environment="dev")
        variables = ctx.terraform_vars()
        # The installer supplies identity, not behaviour flags. That is
        # correct -- behaviour must come from committed configuration.
        self.assertEqual({"project_name": "mays-ris", "environment": "dev"},
                         variables)
        self.assertNotIn("identity_email_verification_enabled", variables,
                         "installer must not need to pass this flag; the root "
                         "default is the single source of truth")

    def test_identity_cannot_be_overridden_by_var(self):
        """Existing fail-closed guarantee must survive this change."""
        from installer.ris import RisInstallContext
        ctx = RisInstallContext(
            project_name="mays-ris", environment="dev",
            extra_vars={"project_name": "evil", "environment": "prod"})
        variables = ctx.terraform_vars()
        self.assertEqual("mays-ris", variables["project_name"])
        self.assertEqual("dev", variables["environment"])

    def test_explicit_var_still_overrides_for_rollback(self):
        """Changing the default must remain reversible at apply time."""
        from installer.ris import RisInstallContext
        ctx = RisInstallContext(
            project_name="mays-ris", environment="dev",
            extra_vars={"identity_email_verification_enabled": "false"})
        self.assertEqual(
            "false",
            ctx.terraform_vars()["identity_email_verification_enabled"])


if __name__ == "__main__":
    unittest.main()