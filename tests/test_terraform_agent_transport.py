"""W03/W04 — static contract checks for the RIS agent transport Terraform.

Terraform is not applied here; these tests pin the wiring so a refactor cannot
silently drop a permission, a handler or the default-off gate.
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, "terraform", "modules", "agent_transport")


def module_source() -> str:
    parts = []
    for name in sorted(os.listdir(MODULE)):
        if name.endswith(".tf"):
            with open(os.path.join(MODULE, name), encoding="utf-8") as handle:
                parts.append(handle.read())
    return "\n".join(parts)


def root_source() -> str:
    with open(os.path.join(ROOT, "terraform", "main.tf"), encoding="utf-8") as f:
        return f.read()


def variables_source() -> str:
    with open(os.path.join(ROOT, "terraform", "variables.tf"), encoding="utf-8") as f:
        return f.read()


class TestDispatchIngressWiring(unittest.TestCase):
    def setUp(self):
        self.source = module_source()

    def test_expected_resources_exist(self):
        expected = {
            ("aws_sqs_queue", "dispatch"),
            ("aws_sqs_queue", "dispatch_dlq"),
            ("aws_sqs_queue_policy", "dispatch"),
            ("aws_cloudwatch_log_group", "dispatch_ingress"),
            ("aws_iam_role", "dispatch_ingress"),
            ("aws_iam_role_policy", "dispatch_ingress"),
            ("aws_lambda_function", "dispatch_ingress"),
            ("aws_lambda_event_source_mapping", "dispatch"),
        }
        found = set(re.findall(r'resource "([a-z0-9_]+)" "([a-z0-9_]+)"', self.source))
        self.assertTrue(expected.issubset(found), expected - found)

    def test_handler_is_the_ingress_entrypoint(self):
        self.assertIn('handler       = "dispatch_ingress.handler"', self.source)

    def test_event_source_mapping_reports_batch_failures(self):
        self.assertIn('function_response_types            = ["ReportBatchItemFailures"]',
                      self.source)

    def test_required_environment_variables(self):
        for name in ("WORK_ITEMS_TABLE", "API_PROFILES_TABLE",
                     "ENTITLEMENTS_TABLE", "DISPATCH_QUEUE_ARN"):
            self.assertIn(name, self.source)

    def test_queue_policy_has_no_public_principal(self):
        self.assertIn("var.orders_producer_role_arns", self.source)
        self.assertNotIn('Principal    = "*"', self.source)

    def test_no_wildcard_dynamodb_or_sqs_resource(self):
        for action in ("dynamodb:", "sqs:"):
            for match in re.finditer(
                    r'Action\s*=\s*\[[^\]]*' + action + r'[^\]]*\]', self.source):
                block = self.source[match.start():match.start() + 400]
                resource = re.search(r'Resource\s*=\s*(\S+)', block)
                if resource:
                    self.assertNotEqual('"*"', resource.group(1),
                                        f"wildcard resource for {action}")

    def test_no_api_route_is_added(self):
        self.assertNotIn('"aws_apigatewayv2_route"', self.source)

    def test_secret_is_not_in_the_ris_module(self):
        # The HMAC secret lives on the consumer (Orders) side.
        self.assertNotIn("aws_secretsmanager_secret", self.source)


class TestDefaultOff(unittest.TestCase):
    def test_flag_defaults_to_false(self):
        variables = variables_source()
        block = variables[variables.index('variable "enable_agent_transport"'):
                          variables.index('variable "enable_agent_transport"') + 300]
        self.assertIn("default     = false", block)

    def test_module_is_gated_by_the_flag(self):
        root = root_source()
        self.assertIn('module "agent_transport"', root)
        self.assertIn("count  = var.enable_agent_transport ? 1 : 0", root)

    def test_module_is_wired_to_existing_tables(self):
        root = root_source()
        for reference in ("module.dynamodb.work_items_table_name",
                          "module.dynamodb.api_profiles_table_name",
                          "module.dynamodb.entitlements_table_name"):
            self.assertIn(reference, root)


if __name__ == "__main__":
    unittest.main()
