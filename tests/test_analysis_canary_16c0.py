"""RIS-ANALYSIS-16C0 static canary preflight.

Pins the two synthetic paths and the CV/job/match cases without calling AWS.
The plan freshness assertion is deliberately historical: it records that the
16B/16C0 source changes invalidated the 9a0324a0 bundle hashes.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "docs" / "reports" / "RIS-ANALYSIS-16C0-PREFLIGHT.json"
GATE_15B = ROOT / "docs" / "reports" / "analysis-final-canary-gate-15b-manifest.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class CanaryPreflight16C0Test(unittest.TestCase):
    def setUp(self):
        self.data = load(PREFLIGHT)
        self.gate = load(GATE_15B)

    def test_release_and_commits(self):
        self.assertEqual("RIS-ANALYSIS-16C0", self.data["release"])
        self.assertEqual("7dc7c74", self.data["base"])
        self.assertEqual("0a2388a", self.data["edgeFixCommit"])

    def test_plan_pin_matches_the_15b_gate(self):
        plan = self.data["planFreshness"]["plan"]
        self.assertEqual(self.gate["plan"]["sha256"], plan["sha256"])
        self.assertEqual(self.gate["plan"]["jsonSha256"], plan["jsonSha256"])
        self.assertEqual((4, 3, 0, 0), (
            plan["adds"], plan["changes"], plan["destroys"],
            plan["replacements"]))
        self.assertEqual("NO_SHARED_DESTROY", plan["guard"])
        self.assertFalse(plan["applyApproved"])

    def test_state_is_pinned_and_guard_is_recorded(self):
        state = self.data["planFreshness"]["state"]
        self.assertEqual(67, state["serial"])
        self.assertEqual("a0bd361d-5cd1-a207-a8c0-e6888f0be082",
                         state["lineage"])
        self.assertEqual(283, state["resources"])

    def test_plan_is_stale_for_the_current_source(self):
        freshness = self.data["planFreshness"]
        self.assertEqual("STALE_RE_PLAN_REQUIRED", freshness["verdict"])
        bundles = freshness["bundles"]
        planned = bundles["planned"]
        current = bundles["currentAfter16BAnd16C0"]
        self.assertNotEqual(planned["worker"], current["worker"])
        self.assertNotEqual(planned["analysis"], current["analysis"])
        self.assertEqual(planned["parser"], current["parser"])
        for value in (*planned.values(), *current.values()):
            self.assertRegex(value, r"^[0-9a-f]{64}$")

    def test_synthetic_profile_is_not_in_the_saved_plan(self):
        synthetic = self.data["planFreshness"]["syntheticProfile"]
        self.assertFalse(synthetic["inPlan"])
        self.assertEqual("false", synthetic["planEnv"]["ANALYSIS_SYNTHETIC_MODE"])
        self.assertEqual("UNVERIFIED_SEPARATE",
                         synthetic["approvalStatus"])

    def test_both_paths_are_prepared_but_blocked(self):
        paths = {path["id"]: path for path in self.data["paths"]}
        self.assertEqual({"direct-ris", "mays-transport"}, set(paths))
        for path in paths.values():
            self.assertEqual("BLOCKED", path["status"])
            self.assertTrue(path["prepared"])
            self.assertTrue(path["blockers"])
            self.assertTrue(path["afterRemediation"])
        self.assertIn("C_APIPROFILEREF_OWNER_BINDING",
                      paths["mays-transport"]["blockers"])
        self.assertNotIn("C_APIPROFILEREF_OWNER_BINDING",
                         paths["direct-ris"]["blockers"])

    def test_three_offers_cover_all_required_cases(self):
        offers = {offer["offerId"]: offer for offer in self.data["offers"]}
        self.assertEqual({"analysis.cv", "analysis.job", "analysis.match"},
                         set(offers))
        required = {"success", "error", "idempotency", "resultRetrieval",
                    "permissionDenial"}
        for offer in offers.values():
            self.assertEqual("analysis.run", offer["capability"])
            self.assertTrue(required.issubset(offer))
            self.assertTrue(offer["error"]["cases"])
            self.assertTrue(offer["permissionDenial"]["cases"])

    def test_result_bodies_match_the_analysis_contracts(self):
        offers = {offer["offerId"]: offer for offer in self.data["offers"]}
        self.assertEqual("CVParserResultBody",
                         offers["analysis.cv"]["resultBody"]["bodyType"])
        self.assertEqual("JobParserResultBody",
                         offers["analysis.job"]["resultBody"]["bodyType"])
        match = offers["analysis.match"]
        self.assertEqual("ComparisonResultBody",
                         match["resultBody"]["bodyType"])
        self.assertEqual("ATSAnalysisResultBody",
                         match["optionalResultBody"]["bodyType"])
        self.assertEqual(["ats.tags"], match["optionalResults"])

    def test_common_assertions_cover_security_and_dlq(self):
        joined = " ".join(self.data["commonAssertions"])
        for marker in ("RIS key", "JWT", "404", "401", "DLQ",
                       "ORDER_FAILED", "Duplicate ORDER_DISPATCH"):
            self.assertIn(marker, joined)

    def test_no_secret_shaped_values_in_the_preflight(self):
        serialized = json.dumps(self.data)
        self.assertNotRegex(serialized, r"\bris_[A-Za-z0-9]")
        self.assertNotIn("Bearer ", serialized)
        self.assertNotIn("eyJ", serialized)
        self.assertNotIn("Authorization:", serialized)
        self.assertRegex(self.data["planFreshness"]["plan"]["sha256"],
                         r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
