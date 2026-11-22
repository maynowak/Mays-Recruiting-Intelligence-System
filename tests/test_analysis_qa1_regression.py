"""RIS-ANALYSIS-16C2-QA1 regression manifest invariants."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "reports" / "RIS-ANALYSIS-16C2-QA1-REGRESSION.json"


class QA1RegressionManifestTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_release_and_environment(self):
        self.assertEqual("RIS-ANALYSIS-16C2-QA1", self.data["release"])
        self.assertEqual("95b7c4f", self.data["base"])
        installed = self.data["environment"]["installed"]
        self.assertIn("requests", installed)
        self.assertIn("moto", installed)
        self.assertIn("pytest-subtests", installed)

    def test_consent_fix_is_scoped(self):
        consent = self.data["consentContext"]
        self.assertIn("NameError", consent["rootCause"])
        self.assertIn("skip", consent["fix"].lower())
        self.assertFalse(consent["logicWeakened"])

    def test_mays_version_boundary_is_explicit(self):
        mays = self.data["maysOrders"]
        self.assertEqual("5cf50a0a8e4221348c264c59432ff4c8dc580c8b",
                         mays["risPin"])
        self.assertEqual("016cdfd6ac62565dcec9a2fee78cb898fb919e59",
                         mays["generatedModule"])
        self.assertEqual("9627eb2", mays["localReviewCheckout"])
        self.assertIn("5cf50a0", mays["compositeFixture"])
        self.assertIn("016cdfd", mays["contractFixture"])

    def test_full_suite_numbers(self):
        default = self.data["results"]["defaultFullSuite"]
        self.assertEqual((3185, 134, 0, 441), (
            default["passed"], default["skipped"], default["failed"],
            default["subtests"]))
        fixtures = self.data["results"]["fixtureFullSuite"]
        self.assertEqual((3250, 68, 1, 441), (
            fixtures["passed"], fixtures["skipped"], fixtures["failed"],
            fixtures["subtests"]))
        self.assertEqual(376, self.data["results"]["focusedEvidence"]["passed"])
        self.assertEqual(5, self.data["results"]["agentPackagesValidated"])
        self.assertEqual(34, self.data["results"]["agentLifecycle"])
        self.assertEqual(43, self.data["results"]["compositeLifecycle"])
        self.assertEqual(15, self.data["results"]["parserMatrix"])

    def test_known_failure_is_precise(self):
        failure = self.data["knownFailure"]
        self.assertIn("test_ris_transport_outputs_are_exposed_additively",
                      failure["test"])
        self.assertEqual("KNOWN_CONTRACT_DRIFT", failure["status"])
        self.assertIn("results_queue_url", failure["finding"])
        self.assertIn("Do not hand-edit", failure["action"])

    def test_skip_categories_sum_to_total(self):
        skips = self.data["skips"]
        self.assertEqual(68, skips["total"])
        self.assertEqual(68, sum(skips["categories"].values()))

    def test_comparison_and_boundaries(self):
        comparison = self.data["comparison16C2"]["broadRelevant"]
        self.assertEqual((739, 41, 13), (
            comparison["passed"], comparison["skipped"],
            comparison["subtests"]))
        boundaries = self.data["boundaries"]
        for key, value in boundaries.items():
            self.assertFalse(value, key)

    def test_no_secret_shaped_values(self):
        text = json.dumps(self.data)
        self.assertNotRegex(text, r"\bris_[A-Za-z0-9]{24,}\b")
        self.assertNotIn("Bearer ", text)
        self.assertNotIn("eyJ", text)
        self.assertNotIn("Authorization:", text)
        self.assertIsNone(re.search(r"aws_secret_access_key", text, re.I))


if __name__ == "__main__":
    unittest.main()
