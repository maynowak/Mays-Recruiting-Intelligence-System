"""RIS-ANALYSIS-16C1 fresh-plan and approval-gate evidence.

Static validation only. The saved plan is host-specific and not committed; when
it is present, its SHA-256 is re-checked. No AWS call is made.
"""

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "reports" / "RIS-ANALYSIS-16C1-PLAN-MANIFEST.json"


def load():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FreshPlan16C1Test(unittest.TestCase):
    def setUp(self):
        self.data = load()
        self.plan = self.data["plan"]

    def test_release_and_superseded_old_plan(self):
        self.assertEqual("RIS-ANALYSIS-16C1", self.data["release"])
        self.assertEqual("50ead67", self.data["base"])
        self.assertEqual("STALE_SUPERSEDED", self.data["oldPlan"]["status"])
        self.assertEqual(
            "9a0324a0523486b9d4850c9215030a084c35b8807508a6a55bd2e26596a4c7a6",
            self.data["oldPlan"]["sha256"])

    def test_new_plan_shape_and_guard(self):
        self.assertEqual((4, 3, 0, 0), (
            self.plan["adds"], self.plan["changes"],
            self.plan["destroys"], self.plan["replacements"]))
        self.assertEqual("NO_SHARED_DESTROY", self.plan["guard"])
        self.assertFalse(self.plan["applyApproved"])
        self.assertEqual("false", self.plan["analysisSyntheticMode"])
        self.assertEqual(0, self.plan["protectedChanges"])
        self.assertEqual(0, self.plan["ordersChanges"])
        self.assertRegex(self.plan["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(self.plan["jsonSha256"], r"^[0-9a-f]{64}$")

    def test_saved_plan_hashes_if_present(self):
        for key, path_key in (("sha256", "path"), ("jsonSha256", "jsonPath")):
            path = Path(self.plan[path_key])
            if not path.is_file():
                continue
            self.assertEqual(self.plan[key], sha256(path), str(path))

    def test_state_pin(self):
        state = self.data["state"]
        self.assertEqual("262370457690", state["account"])
        self.assertEqual("eu-central-1", state["region"])
        self.assertEqual("ris-dev2", state["workspace"])
        self.assertEqual(67, state["serial"])
        self.assertEqual("a0bd361d-5cd1-a207-a8c0-e6888f0be082",
                         state["lineage"])
        self.assertEqual(283, state["resources"])

    def test_historical_bundle_hashes_are_preserved(self):
        # This 16C1 manifest records artifacts from the historical 16C1 plan.
        # The old plan was explicitly superseded after later source changes;
        # comparing its hashes with today's local bundles would conflate two
        # different artifact versions. Current artifact hashes are guarded by
        # test_analysis_ecosystem_wiring.ManifestPinTest.
        historical_hashes = {
            "worker": "85775f685eda57fbd2f49e6351b40f59301de0150c63cb67289fb5c324897096",
            "analysis": "420bf8610920e03868daf8e593a71c2a9de7cc637ca006a5192dd2800a4a0c9e",
            "parser": "fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a",
            "reader": "464b991f784f0ea14da761fca355e676490f9a399209d4d3c2149165c25b1c4d",
        }
        for key, expected in historical_hashes.items():
            with self.subTest(bundle=key):
                self.assertEqual(expected, self.data["bundles"][key]["sha256"])
        parser = self.data["bundles"]["parser"]
        self.assertEqual("e77ee94", parser["sourceCommit"])
        self.assertEqual("c40bf78", parser["artifactSourceCommit"])
        self.assertTrue(parser["runtimeFilesIdenticalToArtifactCommit"])

    def test_approval_gates_are_separate(self):
        approvals = self.data["approvals"]
        self.assertEqual("READY_FOR_APPROVAL", approvals["A"]["status"])
        self.assertFalse(approvals["A"]["applyApproved"])
        self.assertEqual("PROPOSED_NOT_ACTIVE", approvals["B"]["status"])
        self.assertTrue(approvals["B"]["requiresNewPlan"])
        self.assertFalse(approvals["B"]["proposal"]["modeDefault"])
        self.assertEqual("BLOCKED", approvals["C"]["status"])
        self.assertEqual("mays-orders", approvals["C"]["owner"])
        self.assertIn("apiProfileRef", approvals["C"]["finding"])
        self.assertIn("noBypass", approvals["C"])

    def test_canary_stages_are_not_aws_verified(self):
        stages = {stage["id"]: stage for stage in self.data["canaryStages"]}
        self.assertEqual({
            "isolated-analysis-executor",
            "authenticated-ris-api-worker",
            "mays-orders-transport",
        }, set(stages))
        for stage in stages.values():
            self.assertFalse(stage["awsVerified"])
            self.assertTrue(stage["status"].startswith("BLOCKED"))
        self.assertIn("C", stages["mays-orders-transport"]["requires"])
        self.assertNotIn("C", stages["isolated-analysis-executor"]["requires"])

    def test_three_canary_cases_have_all_required_fields(self):
        cases = {case["offerId"]: case for case in self.data["canaryCases"]}
        self.assertEqual({"analysis.cv", "analysis.job", "analysis.match"},
                         set(cases))
        required = {"success", "error", "replay", "result", "denial",
                    "cleanup"}
        for case in cases.values():
            self.assertTrue(required.issubset(case))

    def test_regression_count_reconciliation(self):
        rec = self.data["regressionReconciliation"]
        self.assertEqual(533, rec["16C0ReportBroad"])
        self.assertEqual(560, rec["16C0ActualBroad"])
        self.assertIn("560", rec["explanation"])

    def test_no_secret_shaped_values(self):
        text = json.dumps(self.data)
        self.assertNotRegex(text, r"\bris_[A-Za-z0-9]")
        self.assertNotIn("Bearer ", text)
        self.assertNotIn("eyJ", text)
        self.assertNotIn("Authorization:", text)
        self.assertIsNone(re.search(r"aws_secret_access_key", text, re.I))


if __name__ == "__main__":
    unittest.main()
