import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDLER = (ROOT / "lambda" / "handler.py").read_text(encoding="utf-8")
API_TF = (ROOT / "terraform" / "modules" / "api" / "main.tf").read_text(encoding="utf-8")


class ApplicationApiSecurityTests(unittest.TestCase):
    def test_all_application_routes_use_jwt_authorizer(self):
        blocks = re.findall(r'resource "aws_apigatewayv2_route" "applications_[^"]+" \{(.*?)\n\}', API_TF, re.S)
        self.assertEqual(9, len(blocks))
        for block in blocks:
            self.assertIn('authorization_type = "JWT"', block)
            self.assertIn('authorizer_id', block)

    def test_handler_reuses_existing_partner_boundary_and_no_agent_call(self):
        start = HANDLER.index("def _application_ctx")
        section = HANDLER[start:HANDLER.index("def _handle_health", start)]
        self.assertIn("_partner_profile_context", section)
        self.assertNotIn("AgentBody", section)
        self.assertNotIn("boto3.client('cognito", section.lower())

    def test_application_erasure_activation_flag_defaults_off(self):
        from pathlib import Path
        lambda_tf = (Path(__file__).resolve().parents[1] / "terraform" / "modules"
                     / "lambda" / "main.tf").read_text(encoding="utf-8")
        self.assertRegex(lambda_tf, r'ERASURE_APPLICATIONS_ENABLED\s+= "false"')
        self.assertIn('ERASURE_APPLICATIONS_ENABLED", "false"', HANDLER)
        self.assertIn("application_deleter=(", HANDLER)

    def test_identity_is_derived_not_read_from_request(self):
        start = HANDLER.index("def _application_ctx")
        section = HANDLER[start:HANDLER.index("def _application_body", start)]
        self.assertIn("ctx['userId']", section)
        self.assertIn("ctx['tenantId']", section)
        self.assertIn("ctx['partnerApplicationId']", section)
        self.assertIn("ctx['issuer']", section)


if __name__ == "__main__":
    unittest.main()
