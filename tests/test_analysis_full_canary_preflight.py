"""RIS-ANALYSIS-FULL-AWS-CANARY-12 STEP A — apply approval invariants."""

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "reports" / "analysis-full-canary-12-manifest.json"
BUNDLE = ROOT / "terraform" / "analysis-lambda.zip"
ADDRESSES = {
    "module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]",
    "module.analysis_runtime.aws_lambda_function.analysis[0]",
}


def load():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class FullCanaryManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = load()

    def test_state_identity(self):
        self.assertEqual("262370457690", self.manifest["aws"]["account"])
        self.assertEqual("eu-central-1", self.manifest["aws"]["region"])
        self.assertEqual(67, self.manifest["state"]["serialBefore"])
        self.assertEqual("a0bd361d-5cd1-a207-a8c0-e6888f0be082",
                         self.manifest["state"]["lineage"])
        self.assertEqual("ris-dev2", self.manifest["backend"]["workspace"])

    def test_exact_two_resource_plan(self):
        plan = self.manifest["plan"]
        self.assertEqual((2, 0, 0, 0), (plan["adds"], plan["changes"],
                                        plan["destroys"], plan["replacements"]))
        self.assertEqual("NO_SHARED_DESTROY", plan["guard"])
        self.assertEqual(ADDRESSES,
                         {item["address"] for item in self.manifest["resources"]})
        self.assertEqual(["create"],
                         list({item["action"] for item in self.manifest["resources"]}))

    def test_iam_is_least_privilege(self):
        iam = self.manifest["iam"]
        self.assertEqual("ris-dev2-dev-analysis", iam["role"])
        statements = {item["sid"]: item for item in iam["statements"]}
        self.assertEqual({"WorkItems", "EntitlementRecheck",
                          "OwnedPartnerProfiles"}, set(statements))
        self.assertEqual(
            {"dynamodb:GetItem", "dynamodb:PutItem",
             "dynamodb:UpdateItem", "dynamodb:Query"},
            set(statements["WorkItems"]["actions"]))
        self.assertEqual({"dynamodb:GetItem", "dynamodb:Query"},
                         set(statements["EntitlementRecheck"]["actions"]))
        for item in statements.values():
            for resource in item["resources"]:
                self.assertIn(":262370457690:table/ris-dev2-dev-", resource)
        joined = json.dumps(statements).lower()
        for forbidden in iam["forbidden"]:
            self.assertNotIn(forbidden, joined)

    def test_lambda_and_parser_contract(self):
        fn = self.manifest["lambda"]
        self.assertEqual("analysis_runner.handler", fn["handler"])
        self.assertEqual("python3.14", fn["runtime"])
        self.assertEqual(60, fn["timeoutSeconds"])
        self.assertEqual("ris-dev2-dev-analysis", fn["functionName"])
        self.assertFalse(fn["publicEndpoint"])
        self.assertEqual("lambda", fn["env"]["RIS_PARSER_MODE"])
        self.assertEqual("false", fn["env"]["ANALYSIS_CONSENT"])
        self.assertEqual("", fn["env"]["ANALYSIS_ENTITLEMENTS"])
        self.assertEqual("false", fn["env"]["ANALYSIS_NOTICE_APPROVED"])
        self.assertFalse(self.manifest["parser"]["changedByPlan"])
        self.assertEqual("nodejs22.x", self.manifest["parser"]["runtime"])

    def test_plan_and_bundle_pins(self):
        plan = self.manifest["plan"]
        self.assertRegex(plan["sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(plan["jsonSha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(
            "f3c2f1a20d4af4b3d6c818222ae0edb5d59c985e37c074c4e025e797700a2314",
            self.manifest["bundle"]["sha256"])
        if BUNDLE.is_file():
            digest = hashlib.sha256(BUNDLE.read_bytes()).hexdigest()
            self.assertEqual(self.manifest["bundle"]["sha256"], digest)
        else:
            self.skipTest("analysis bundle not built on this host")

    def test_saved_plan_matches_if_present(self):
        path = Path(self.manifest["plan"]["path"])
        if not path.is_file():
            self.skipTest("saved plan not present on this host")
        self.assertEqual(self.manifest["plan"]["sha256"],
                         hashlib.sha256(path.read_bytes()).hexdigest())

    def test_stop_conditions_cover_drift(self):
        conditions = " ".join(self.manifest["stopConditions"]).lower()
        for marker in ("sha-256", "state serial", "parser lambda",
                       "cognito", "guard"):
            self.assertIn(marker, conditions)


if __name__ == "__main__":
    unittest.main()
