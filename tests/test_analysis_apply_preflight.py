"""RIS-ANALYSIS-CANARY-10B STEP A — apply approval manifest invariants.

The saved plan itself is machine/backend/state-specific and not committed; this
test pins the approved manifest and, when the plan file is present locally,
re-checks its SHA-256 against the approval.
"""

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "reports" / "analysis-canary-10b-plan-manifest.json"
PARSER = {
    "module.analysis_runtime.aws_cloudwatch_log_group.parser[0]",
    "module.analysis_runtime.aws_iam_role.parser[0]",
    "module.analysis_runtime.aws_iam_role_policy.analysis_invoke_parser[0]",
    "module.analysis_runtime.aws_iam_role_policy.parser_logs[0]",
    "module.analysis_runtime.aws_lambda_function.parser[0]",
    "module.analysis_runtime.aws_lambda_permission.parser_invoke_analysis[0]",
}
UPDATES = {
    "module.agent_transport[0].aws_iam_role_policy.dispatch_ingress",
    "module.mays_orders[0].module.lambda.aws_lambda_function.handler",
}


def load():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class ApplyManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = load()

    def test_identity_matches_the_installation(self):
        self.assertEqual("262370457690", self.manifest["aws"]["account"])
        self.assertEqual("eu-central-1", self.manifest["aws"]["region"])
        backend = self.manifest["backend"]
        self.assertEqual("ris-dev2-tf-state-dev", backend["bucket"])
        self.assertEqual("dev/terraform.tfstate", backend["key"])
        self.assertEqual("ris-dev2-tf-lock", backend["lockTable"])
        self.assertEqual("ris-dev2", backend["workspace"])
        self.assertEqual(64, self.manifest["state"]["serialBefore"])
        self.assertEqual("a0bd361d-5cd1-a207-a8c0-e6888f0be082",
                         self.manifest["state"]["lineage"])

    def test_plan_counts_and_guard(self):
        plan = self.manifest["plan"]
        self.assertEqual((17, 2, 0, 0), (
            plan["adds"], plan["changes"], plan["destroys"],
            plan["replacements"]))
        self.assertEqual("NO_SHARED_DESTROY", plan["guard"])
        self.assertRegex(plan["sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(plan["jsonSha256"], r"^[a-f0-9]{64}$")

    def test_add_manifest_is_exact(self):
        adds = self.manifest["adds"]
        self.assertEqual(17, len(adds))
        self.assertEqual(17, len(set(adds)))
        self.assertTrue(PARSER.issubset(set(adds)))
        for forbidden in ("cognito", "cloudfront", "route53", "acm"):
            self.assertFalse([a for a in adds if forbidden in a.lower()])

    def test_updates_are_the_two_known_in_place_changes(self):
        updates = self.manifest["updates"]
        self.assertEqual(UPDATES, {item["address"] for item in updates})
        for item in updates:
            self.assertFalse(item["destructive"])
            self.assertIn("in-place", item["effect"])

    def test_artifact_pin(self):
        artifact = self.manifest["artifact"]
        self.assertEqual(
            "fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a",
            artifact["sha256"])
        self.assertEqual(412, artifact["fileCount"])
        self.assertEqual("nodejs22.x", artifact["runtime"])
        self.assertEqual("arm64", artifact["architecture"])

    def test_protected_services_and_stop_conditions(self):
        self.assertEqual(
            ["cognito", "cloudfront", "route53", "acm"],
            self.manifest["protectedServicesUnchanged"])
        self.assertGreaterEqual(len(self.manifest["stopConditions"]), 5)
        joined = " ".join(self.manifest["stopConditions"]).lower()
        self.assertIn("sha-256", joined)
        self.assertIn("state serial", joined)


class ApprovedPlanFileTest(unittest.TestCase):
    def test_saved_plan_matches_the_approved_sha_if_present(self):
        path = Path(load()["plan"]["path"])
        if not path.is_file():
            self.skipTest("saved plan is not present on this host")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(load()["plan"]["sha256"], digest)


if __name__ == "__main__":
    unittest.main()
