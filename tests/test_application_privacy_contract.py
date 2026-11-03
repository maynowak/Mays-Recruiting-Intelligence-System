import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLER = (ROOT / "lambda" / "handler.py").read_text(encoding="utf-8")
CONTRACT = (ROOT / "agents" / "ecosystem" / "privacy_erasure_contract.py").read_text(encoding="utf-8")


class ApplicationPrivacyContractTests(unittest.TestCase):
    def test_inspect_and_export_have_application_category(self):
        self.assertGreaterEqual(HANDLER.count("categories['applications']"), 2)
        self.assertIn("ApplicationV1", HANDLER)
        self.assertIn("RIS-APPLICATION-V1-RETENTION-DECISION#APPROVAL_REQUIRED", HANDLER)

    def test_erasure_category_is_durable_contract_member(self):
        self.assertIn('"applications"', CONTRACT)
        self.assertIn("save_checkpoint", (ROOT / "agents" / "ecosystem" / "privacy_profile_erasure.py").read_text(encoding="utf-8"))

    def test_sensitive_application_material_is_not_in_export_contract(self):
        # The implementation exports references and explicit cover-letter
        # versions, but never access credentials or raw CV bytes.
        self.assertNotIn("accessToken", HANDLER)
        self.assertNotIn("rawCv", HANDLER)


if __name__ == "__main__":
    unittest.main()
