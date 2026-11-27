"""RIS-ANALYSIS-READINESS-09 — static checks for the dedicated parser runtime.

No Terraform is applied. These tests pin the default-off gate, the internal
invoke path (no public endpoint) and the absence of shared-policy changes.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, "terraform", "modules", "analysis_runtime")


def read(name):
    with open(os.path.join(MODULE, name), encoding="utf-8") as handle:
        return handle.read()


def module_source():
    return "\n".join(read(name) for name in sorted(os.listdir(MODULE))
                     if name.endswith(".tf"))


def root_source():
    with open(os.path.join(ROOT, "terraform", "main.tf"), encoding="utf-8") as handle:
        return handle.read()


def root_variables():
    with open(os.path.join(ROOT, "terraform", "variables.tf"), encoding="utf-8") as handle:
        return handle.read()


class ParserRuntimeGateTest(unittest.TestCase):
    def setUp(self):
        self.module = module_source()
        self.variables = read("variables.tf")

    def test_runtime_flag_defaults_to_false(self):
        self.assertRegex(
            self.module,
            r'variable "enable_analysis_runtime"\s*\{[^}]*default\s*=\s*false',
        )

    def test_every_parser_resource_is_gated(self):
        gated_count = len(re.findall(
            r"count\s*=\s*var\.enable_analysis_runtime\s*\?\s*1\s*:\s*0",
            self.module))
        # role, logs policy, log group, function, invoke policy, permission
        self.assertGreaterEqual(gated_count, 6)

    def test_parser_is_the_shared_node_handler(self):
        self.assertIn('resource "aws_lambda_function" "parser"', self.module)
        self.assertIn('handler       = "lambda/ris_parser_handler.handler"',
                      self.module)
        self.assertIn('default = "nodejs22.x"', self.variables)
        self.assertIn("filebase64sha256(var.parser_artifact_path)", self.module)

    def test_no_public_endpoint_is_created(self):
        for forbidden in ("aws_apigatewayv2", "aws_api_gateway",
                          "aws_lambda_function_url", "aws_cloudfront"):
            self.assertNotIn(forbidden, self.module)

    def test_internal_invoke_only(self):
        self.assertIn('action        = "lambda:InvokeFunction"', self.module)
        self.assertIn("principal     = aws_iam_role.analysis.arn", self.module)
        self.assertIn('Action   = ["lambda:InvokeFunction"]', self.module)

    def test_parser_role_has_no_shared_transport_access(self):
        role_block = self.module.split('resource "aws_iam_role" "parser"', 1)[1]
        role_block = role_block.split('resource "', 1)[0]
        for forbidden in ("sqs:", "secretsmanager:", "dynamodb:", "s3:"):
            self.assertNotIn(forbidden, role_block)

    def test_timeout_limits(self):
        self.assertIn("var.parser_timeout_seconds >= 1", self.variables)
        self.assertIn("var.parser_timeout_seconds <= 60", self.variables)
        self.assertIn("default     = 15", self.variables)

    def test_dedicated_analysis_compute_is_gated_and_internal(self):
        self.assertIn('resource "aws_lambda_function" "analysis"', self.module)
        self.assertIn('handler       = "analysis_runner.handler"', self.module)
        self.assertIn('runtime       = "python3.14"', self.module)
        self.assertIn("role          = aws_iam_role.analysis.arn", self.module)
        self.assertIn("RIS_PARSER_MODE            = \"lambda\"", self.module)
        self.assertIn("RIS_PARSER_FUNCTION        = aws_lambda_function.parser[0].function_name",
                      self.module)
        for forbidden in ("aws_apigateway", "aws_lambda_function_url",
                          "aws_cloudfront", "aws_sqs", "aws_secretsmanager"):
            self.assertNotIn(forbidden, self.module)

    def test_analysis_configuration_defaults_deny(self):
        for name, value in ((("ANALYSIS_ENTITLEMENTS"), '""'),
                            (("ANALYSIS_CONSENT"), '"false"'),
                            (("ANALYSIS_NOTICE_APPROVED"), '"false"')):
            self.assertRegex(self.module, name + r"\s*=\s*" + value)
        self.assertNotRegex(self.module, r"ANALYSIS_CONSENT\s*=\s*\"true\"")
        # Synthetic mode is parameterized but defaults off.
        self.assertRegex(
            self.module,
            r'ANALYSIS_SYNTHETIC_MODE\s*=\s*var\.analysis_synthetic_mode\s*\?\s*"true"\s*:\s*"false"')
        self.assertRegex(
            self.variables,
            r'variable "analysis_synthetic_mode"\s*\{[^}]*default\s*=\s*false')
        self.assertRegex(
            self.variables,
            r'variable "analysis_synthetic_installation"\s*\{[^}]*default\s*=\s*"ris-dev2"')
        for name in ("analysis_synthetic_tenant_id",
                     "analysis_synthetic_user_id",
                     "analysis_synthetic_partner_application_id",
                     "analysis_synthetic_issuer",
                     "analysis_synthetic_entitlements",
                     "analysis_synthetic_expires_at"):
            self.assertRegex(
                self.variables,
                r'variable "' + name + r'"\s*\{[^}]*default\s*=\s*""')

    def test_synthetic_profile_env_is_wired_to_variables(self):
        expected = {
            "ANALYSIS_SYNTHETIC_INSTALLATION": "var.analysis_synthetic_installation",
            "ANALYSIS_SYNTHETIC_TENANT_ID": "var.analysis_synthetic_tenant_id",
            "ANALYSIS_SYNTHETIC_USER_ID": "var.analysis_synthetic_user_id",
            "ANALYSIS_SYNTHETIC_PARTNER_APPLICATION_ID":
                "var.analysis_synthetic_partner_application_id",
            "ANALYSIS_SYNTHETIC_ISSUER": "var.analysis_synthetic_issuer",
            "ANALYSIS_SYNTHETIC_ENTITLEMENTS": "var.analysis_synthetic_entitlements",
            "ANALYSIS_SYNTHETIC_EXPIRES_AT": "var.analysis_synthetic_expires_at",
        }
        for key, variable in expected.items():
            self.assertRegex(self.module, key + r"\s*=\s*" + re.escape(variable))
        # Consent/notice stay deny; the synthetic path must not relax them.
        self.assertNotRegex(self.module, r"ANALYSIS_CONSENT\s*=\s*\"true\"")
        self.assertNotRegex(self.module, r"ANALYSIS_NOTICE_APPROVED\s*=\s*\"true\"")

    def test_data_policy_is_dedicated_and_least_privilege(self):
        block = self.module.split('resource "aws_iam_role_policy" "analysis_runtime_data"', 1)[1]
        block = block.split('resource "', 1)[0]
        self.assertIn('name  = "${local.name}-runtime-data"', block)
        self.assertIn("role  = aws_iam_role.analysis.id", block)
        self.assertIn("var.partner_profiles_table_arn", block)
        # Synthetic verification only reads the persisted WorkItem.
        self.assertIn("var.work_items_table_arn", block)
        self.assertIn('Action   = ["dynamodb:GetItem"]', block)
        self.assertNotIn("dynamodb:PutItem", block)
        self.assertNotIn("dynamodb:UpdateItem", block)
        self.assertNotIn("var.entitlements_table_arn", block)
        for forbidden in ("s3:", "sqs:", "secretsmanager:", "lambda:"):
            self.assertNotIn(forbidden, block)
        granted = set(re.findall(r"dynamodb:[A-Za-z]+", block))
        self.assertEqual({"dynamodb:GetItem"}, granted)

    def test_partner_profiles_is_get_item_only(self):
        """RIS-DEV2-IAM-AUTHORIZATION-01: no unused Query/index grants."""
        block = self.module.split('resource "aws_iam_role_policy" "analysis_runtime_data"', 1)[1]
        block = block.split('resource "', 1)[0]
        partner = block.split('Sid = "OwnedPartnerProfiles"', 1)[1].split("},", 1)[0]
        self.assertIn("var.partner_profiles_table_arn", partner)
        self.assertIn('["dynamodb:GetItem"]', partner)
        self.assertNotIn("dynamodb:Query", partner)
        self.assertNotIn("index/*", partner)

    def test_analysis_runtime_has_no_order_table_access(self):
        """Orders are read through the RIS order API, never by this Lambda."""
        self.assertNotIn("mays-orders", self.module)
        self.assertNotIn("ORDERS_TABLE", self.module)
        source_root = os.path.join(ROOT, "lambda")
        sources = [os.path.join(source_root, "analysis_runner.py")]
        analysis_dir = os.path.join(ROOT, "agents", "analysis")
        sources += [os.path.join(analysis_dir, name)
                    for name in sorted(os.listdir(analysis_dir))
                    if name.endswith(".py")]
        for path in sources:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("ORDERS_TABLE", text, path)
            self.assertNotIn("mays-orders", text, path)
            self.assertNotIn("orders_table", text, path)

    def test_build_bundle_contains_the_analysis_runner(self):
        import importlib.util

        path = os.path.join(ROOT, "lambda", "build_zip.py")
        spec = importlib.util.spec_from_file_location("ris_build_zip", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        collected = module._collect(
            __import__("pathlib").Path(ROOT),
            ["lambda/analysis_runner.py"] + module.AGENT_DIRS)
        self.assertIn("lambda/analysis_runner.py", collected)
        self.assertNotIn("lambda/analysis_runner.py", module.AGENT_FILES)

    def test_limits_are_enforced_in_python_too(self):
        from agents.parsers import lambda_adapter, node_adapter

        self.assertEqual(15, lambda_adapter.DEFAULT_TIMEOUT_SECONDS)
        self.assertLessEqual(lambda_adapter.DEFAULT_TIMEOUT_SECONDS, 60)
        self.assertEqual(node_adapter.MAX_PAYLOAD_CHARS,
                         lambda_adapter.MAX_PAYLOAD_CHARS)


class ParserRuntimeRootWiringTest(unittest.TestCase):
    def test_root_gate_defaults_to_false(self):
        variables = root_variables()
        self.assertRegex(
            variables,
            r'variable "enable_analysis_runtime"\s*\{[^}]*default\s*=\s*false',
        )

    def test_root_passes_the_gate_to_the_module(self):
        main = root_source()
        block = main.split('module "analysis_runtime"', 1)[1].split("\n}", 1)[0]
        self.assertIn("enable_analysis_runtime = var.enable_analysis_runtime",
                      block)
        self.assertIn("parser_artifact_path    = var.analysis_parser_zip_path",
                      block)
        self.assertIn("analysis_zip_path       = local.analysis_artifact_filename",
                      block)
        for table in ("work_items_table", "entitlements_table",
                      "partner_profiles_table"):
            self.assertIn(f"module.dynamodb.{table}_name", block)
            self.assertIn(f"module.dynamodb.{table}_arn", block)

    def test_no_shared_policy_is_replaced(self):
        module = module_source()
        self.assertNotIn('resource "aws_iam_policy"', module)
        self.assertNotIn("aws_iam_role_policy_attachment", module)
        self.assertNotIn("order_result", module)


if __name__ == "__main__":
    unittest.main()
