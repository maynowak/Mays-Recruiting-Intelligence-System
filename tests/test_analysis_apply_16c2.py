"""RIS-ANALYSIS-16C2 apply/drift/test manifest invariants.

Static, no AWS call. Pins the exact approved apply and the post-apply
deny-by-default/drift state.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "reports" / "RIS-ANALYSIS-16C2-APPLY-MANIFEST.json"


class ApplyManifest16C2Test(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_approved_plan_and_apply(self):
        self.assertEqual("RIS-ANALYSIS-16C2", self.data["release"])
        self.assertEqual("A", self.data["approval"]["gate"])
        self.assertTrue(self.data["approval"]["applied"])
        self.assertEqual(
            "7393445789d92bdb15ebcc9ea3ae85a9e98cb068c27ad84bc6fd982d3ba0f64a",
            self.data["approval"]["approvedPlanSha256"])
        self.assertEqual("SUCCESS", self.data["apply"]["result"])
        self.assertEqual(0, self.data["apply"]["exitCode"])

    def test_state_and_change_set(self):
        apply = self.data["apply"]
        self.assertEqual(67, apply["stateSerialBefore"])
        self.assertEqual(69, apply["stateSerialAfter"])
        self.assertEqual("a0bd361d-5cd1-a207-a8c0-e6888f0be082",
                         apply["lineage"])
        self.assertEqual(283, apply["resourcesBefore"])
        self.assertEqual(287, apply["resourcesAfter"])
        self.assertEqual(4, len(apply["created"]))
        self.assertEqual(3, len(apply["updated"]))
        self.assertEqual([], apply["removed"])
        self.assertEqual(0, apply["protectedStateChanges"])
        self.assertEqual(0, apply["maysNonNoopActions"])

    def test_analysis_lambda_is_healthy_and_deny_by_default(self):
        fn = self.data["awsAcceptance"]["analysisLambda"]
        self.assertEqual("ris-dev2-dev-analysis", fn["functionName"])
        self.assertEqual("python3.14", fn["runtime"])
        self.assertEqual("analysis_runner.handler", fn["handler"])
        self.assertIn(fn["architecture"], ("x86_64", "arm64"))
        self.assertEqual("Active", fn["state"])
        self.assertEqual("Successful", fn["lastUpdateStatus"])
        self.assertFalse(fn["publicFunctionUrl"])
        deny = fn["denyByDefault"]
        self.assertEqual("false", deny["ANALYSIS_SYNTHETIC_MODE"])
        self.assertEqual("false", deny["ANALYSIS_CONSENT"])
        self.assertEqual("false", deny["ANALYSIS_NOTICE_APPROVED"])
        self.assertEqual("", deny["ANALYSIS_ENTITLEMENTS"])

    def test_parser_architecture_and_code(self):
        fn = self.data["awsAcceptance"]["parserLambda"]
        self.assertEqual("nodejs22.x", fn["runtime"])
        self.assertEqual("arm64", fn["architecture"])
        self.assertEqual("lambda/ris_parser_handler.handler", fn["handler"])
        self.assertRegex(fn["codeSha256"], r"^[A-Za-z0-9+/=]+$")

    def test_iam_is_least_privilege(self):
        iam = self.data["awsAcceptance"]["iam"]
        statements = " ".join(iam["runtimeDataPolicy"]["statements"])
        self.assertIn("PartnerProfiles", statements)
        self.assertIn("WorkItems GetItem", statements)
        self.assertEqual(
            {"AllowRisIngressInvokeAnalysis", "AllowRisWorkerInvokeAnalysis"},
            {item.split(" -> ")[0] for item in iam["invokePermissions"]})

    def test_queues_are_empty(self):
        for name, count in self.data["awsAcceptance"]["queues"].items():
            self.assertEqual(0, count, name)

    def test_drift_plan_is_clean(self):
        drift = self.data["drift"]["postApplyPlan"]
        self.assertEqual({"no-op": 272}, drift["actions"])
        self.assertFalse(drift["applyable"])
        self.assertEqual([], drift["nonNoop"])
        self.assertEqual(0, drift["maysNonNoop"])
        self.assertEqual(0, self.data["drift"]["protectedStateChanges"])

    def test_regression_and_stage_matrix(self):
        tests = self.data["tests"]
        self.assertEqual(5, tests["agentPackagesValidated"])
        for stage, status in tests["agentStages"].items():
            self.assertTrue(status.startswith("PASSED"), stage)
        self.assertEqual(739, tests["broadRegression"]["passed"])
        self.assertEqual(41, tests["broadRegression"]["skipped"])
        self.assertEqual(13, tests["broadRegression"]["subtests"])
        self.assertEqual(95, tests["additionAtsRegression"]["passed"])
        self.assertEqual(34, tests["agentLifecycle"]["passed"])
        self.assertEqual(40, tests["compositeLifecycle"]["passed"])
        self.assertEqual(3, tests["compositeLifecycle"]["blocked"])
        self.assertEqual("BLOCKED_ENV", tests["fullSuite"]["status"])

    def test_e2e_boundaries_remain_blocked(self):
        e2e = self.data["e2e"]
        for key in ("isolatedAnalysisExecutor", "authenticatedRisApiWorker"):
            self.assertEqual("BLOCKED_B", e2e[key]["status"])
            self.assertFalse(e2e[key]["awsVerified"])
        self.assertEqual("BLOCKED_C", e2e["maysTransport"]["status"])
        self.assertFalse(e2e["maysTransport"]["awsVerified"])
        self.assertEqual("BLOCKED", e2e["automaticResume"]["status"])
        self.assertFalse(e2e["automaticResume"]["implemented"])

    def test_cleanup_balance(self):
        cleanup = self.data["cleanup"]
        self.assertFalse(cleanup["syntheticDataCreated"])
        self.assertEqual(0, cleanup["ordersCreated"])
        self.assertEqual(0, cleanup["entitlementsCreated"])
        self.assertEqual(0, cleanup["catalogOffersCreated"])
        self.assertTrue(cleanup["infrastructureRetained"])
        self.assertFalse(cleanup["cleanupRequired"])

    def test_no_secret_shaped_values(self):
        text = json.dumps(self.data)
        self.assertNotRegex(text, r"\bris_[A-Za-z0-9]{24,}\b")
        self.assertNotIn("Bearer ", text)
        self.assertNotIn("eyJ", text)
        self.assertNotIn("Authorization:", text)
        self.assertIsNone(re.search(r"aws_secret_access_key", text, re.I))


if __name__ == "__main__":
    unittest.main()
