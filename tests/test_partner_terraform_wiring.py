"""Terraform wiring tests for the Partner Application Registry.

These are static structural assertions over the Terraform sources. They do
not run `terraform plan` and never touch AWS. Their purpose is to catch the
exact failure mode that made both partner routes unusable: the table existed
but the runtime Lambda was never told which table to read, and no IAM policy
covered the lookup.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF = os.path.join(ROOT, "terraform")


def read(rel):
    with open(os.path.join(TF, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestDynamoModule(unittest.TestCase):
    def setUp(self):
        self.main = read("modules/dynamodb/main.tf")
        self.outputs = read("modules/dynamodb/outputs.tf")

    def test_table_exists_exactly_once(self):
        self.assertEqual(
            self.main.count(
                'resource "aws_dynamodb_table" "partner_applications"'),
            1)

    def test_table_primary_key_is_application_id(self):
        block = self.main.split(
            'resource "aws_dynamodb_table" "partner_applications"')[1]
        block = block.split("\nresource ")[0]
        self.assertIn('hash_key     = "applicationId"', block)
        self.assertIn('name = "applicationId"', block)
        self.assertIn('name = "cognitoClientId"', block)

    def test_gsi_client_exists(self):
        self.assertIn('name            = "gsi-client"', self.main)
        self.assertIn('hash_key        = "cognitoClientId"', self.main)

    def test_naming_follows_convention(self):
        self.assertIn(
            'name         = "${var.project_name}-${var.environment}'
            '-partner-applications"', self.main)

    def test_table_name_output_exists(self):
        self.assertIn('output "partner_applications_table_name"', self.outputs)
        self.assertIn("aws_dynamodb_table.partner_applications.name",
                      self.outputs)

    def test_table_arn_output_exists(self):
        self.assertIn('output "partner_applications_table_arn"', self.outputs)
        self.assertIn("aws_dynamodb_table.partner_applications.arn",
                      self.outputs)

    def test_gsi_arn_output_exists(self):
        self.assertIn('output "partner_applications_gsi_client_arn"',
                      self.outputs)
        self.assertIn("/index/gsi-client", self.outputs)

    def test_pay_per_request(self):
        block = self.main.split(
            'resource "aws_dynamodb_table" "partner_applications"')[1]
        block = block.split("\nresource ")[0]
        self.assertIn("PAY_PER_REQUEST", block)


class TestRootWiring(unittest.TestCase):
    def setUp(self):
        self.main = read("main.tf")

    def test_lambda_receives_partner_table_name(self):
        self.assertRegex(
            self.main,
            r"partner_applications_table_name\s*=\s*"
            r"module\.dynamodb\.partner_applications_table_name")

    def test_lambda_receives_partner_table_arn(self):
        self.assertRegex(
            self.main,
            r"partner_applications_table_arn\s*=\s*"
            r"module\.dynamodb\.partner_applications_table_arn")

    def test_lambda_receives_gsi_arn(self):
        self.assertRegex(
            self.main,
            r"partner_applications_gsi_client_arn\s*=\s*"
            r"module\.dynamodb\.partner_applications_gsi_client_arn")


class TestLambdaModule(unittest.TestCase):
    def setUp(self):
        self.main = read("modules/lambda/main.tf")
        self.vars = read("modules/lambda/variables.tf")

    def test_env_var_is_wired_to_the_table_name(self):
        self.assertIn("RIS_PARTNER_APPLICATIONS_TABLE", self.main)
        self.assertRegex(
            self.main,
            r"RIS_PARTNER_APPLICATIONS_TABLE\s*=\s*"
            r"var\.partner_applications_table_name")

    def test_env_var_matches_python_code(self):
        """The Lambda env var name must equal what partner_registry.py reads."""
        with open(os.path.join(ROOT, "agents", "ecosystem",
                               "partner_registry.py"), encoding="utf-8") as fh:
            py = fh.read()
        self.assertIn("os.getenv('RIS_PARTNER_APPLICATIONS_TABLE')", py)
        self.assertIn("RIS_PARTNER_APPLICATIONS_TABLE", self.main)

    def test_variables_declared(self):
        for name in ("partner_applications_table_name",
                     "partner_applications_table_arn",
                     "partner_applications_gsi_client_arn"):
            self.assertIn('variable "%s"' % name, self.vars)

    def test_runtime_policy_exists(self):
        self.assertIn(
            'resource "aws_iam_role_policy" "lambda_dynamodb_partner_registry"',
            self.main)

    def test_runtime_policy_is_scoped_to_the_gsi_arn(self):
        block = self.main.split(
            'resource "aws_iam_role_policy" '
            '"lambda_dynamodb_partner_registry"')[1]
        block = block.split("\nresource ")[0]
        self.assertIn("var.partner_applications_gsi_client_arn", block)
        # The runtime role must not receive a table-wide grant.
        self.assertNotIn("var.partner_applications_table_arn", block)

    def test_runtime_policy_grants_only_query(self):
        block = self.main.split(
            'resource "aws_iam_role_policy" '
            '"lambda_dynamodb_partner_registry"')[1]
        block = block.split("\nresource ")[0]
        actions = re.search(r"Action = \[(.*?)\]", block, re.S).group(1)
        granted = re.findall(r"dynamodb:\w+", actions)
        self.assertEqual(granted, ["dynamodb:Query"])

    def test_runtime_policy_has_no_wildcards(self):
        block = self.main.split(
            'resource "aws_iam_role_policy" '
            '"lambda_dynamodb_partner_registry"')[1]
        block = block.split("\nresource ")[0]
        self.assertNotIn('"*"', block)

    def test_policy_is_attached_before_the_function_exists(self):
        self.assertIn("aws_iam_role_policy.lambda_dynamodb_partner_registry",
                      self.main)

    def test_admin_operations_not_granted_to_runtime(self):
        """create/deactivate/list are CLI-only and must not reach the API."""
        block = self.main.split(
            'resource "aws_iam_role_policy" '
            '"lambda_dynamodb_partner_registry"')[1]
        block = block.split("\nresource ")[0]
        for forbidden in ("dynamodb:TransactWriteItems", "dynamodb:UpdateItem",
                          "dynamodb:Scan", "dynamodb:PutItem",
                          "dynamodb:DeleteItem"):
            self.assertNotIn(forbidden, block)


class TestNoDuplicateTable(unittest.TestCase):
    def test_no_other_module_defines_the_table(self):
        hits = []
        for dirpath, _dirs, files in os.walk(TF):
            if ".terraform" in dirpath:
                continue
            for fn in files:
                if not fn.endswith(".tf"):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8") as fh:
                    body = fh.read()
                if ('resource "aws_dynamodb_table" "partner_applications"'
                        in body):
                    hits.append(os.path.relpath(path, TF))
        self.assertEqual(hits, ["modules/dynamodb/main.tf"])


if __name__ == "__main__":
    unittest.main()