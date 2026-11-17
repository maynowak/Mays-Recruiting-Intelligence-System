"""Static contract checks for the RIS consent deployment unblock.

These tests do not contact AWS and do not apply Terraform. They pin the
configuration values that preserve the existing transport/CORS resources while
allowing the consent Lambda bundle to be updated.
"""

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(relative: str) -> str:
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


class TestRisDevOverlay(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(
            read("installer/project-configs/ris-dev.json")
        )["terraform_vars"]

    def test_existing_agent_transport_is_enabled(self):
        self.assertEqual("true", self.config["enable_agent_transport"])

    def test_existing_transport_roles_are_preserved(self):
        self.assertEqual(
            ["arn:aws:iam::240571105849:role/ris-dev-mays-orders-handler-role"],
            json.loads(self.config["orders_producer_role_arns"]),
        )
        self.assertEqual(
            [
                "arn:aws:iam::240571105849:role/ris-dev-dev-agent",
                "arn:aws:iam::240571105849:role/ris-dev-dev-agent-dispatch-ingress",
            ],
            json.loads(self.config["ris_result_producer_role_arns"]),
        )

    def test_existing_result_transport_values_are_preserved(self):
        self.assertEqual(
            "https://sqs.eu-central-1.amazonaws.com/240571105849/"
            "ris-dev-mays-orders-agent-results",
            self.config["order_result_queue_url"],
        )
        self.assertEqual(
            "arn:aws:sqs:eu-central-1:240571105849:"
            "ris-dev-mays-orders-agent-results",
            self.config["order_result_queue_arn"],
        )
        self.assertEqual(
            "arn:aws:secretsmanager:eu-central-1:240571105849:secret:"
            "ris-dev-mays-orders-agent-result-hmac-8J5T6n",
            self.config["order_result_secret_arn"],
        )


class TestTerraformWiring(unittest.TestCase):
    def test_orders_module_receives_transport_inputs(self):
        source = read("terraform/main.tf")
        self.assertIn(
            "enable_agent_transport        = var.enable_agent_transport",
            source,
        )
        self.assertIn(
            "ris_result_producer_role_arns = var.ris_result_producer_role_arns",
            source,
        )

    def test_agent_lambda_receives_existing_result_env(self):
        source = read("terraform/modules/lambda/main.tf")
        self.assertIn("ORDER_RESULT_QUEUE_URL", source)
        self.assertIn("ORDER_RESULT_SECRET_ARN", source)
        transport = read("terraform/modules/agent_transport/lambda.tf")
        self.assertIn("ORDER_RESULT_QUEUE_URL", transport)
        self.assertIn("ORDER_RESULT_SECRET_ARN", transport)

    def test_legacy_orders_dispatch_policy_is_moved_not_recreated(self):
        source = read("terraform/main.tf")
        self.assertIn(
            "module.mays_orders[0].module.iam.aws_iam_role_policy.agent_dispatch[0]",
            source,
        )
        self.assertIn(
            'resource "aws_iam_role_policy" "orders_agent_dispatch"',
            source,
        )

    def test_documents_cors_is_declared(self):
        source = read("terraform/modules/documents/main.tf")
        variables = read("terraform/modules/documents/variables.tf")
        self.assertIn('resource "aws_s3_bucket_cors_configuration" "documents"', source)
        self.assertIn("var.browser_allowed_origins", source)
        self.assertIn('variable "browser_allowed_origins"', variables)


if __name__ == "__main__":
    unittest.main()
