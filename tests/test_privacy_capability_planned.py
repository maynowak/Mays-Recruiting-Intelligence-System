"""R08-G0 planned capability tests.

These are deliberately skipped: R08-G0 implements only the receipt/context
contract. The tests document the acceptance requirements for R08-A/B/C so
they cannot be mistaken for implemented behavior.
"""

import unittest


class TestPlannedPrivacyCapability(unittest.TestCase):
    @unittest.skip("R08-A1 internal repository exists; public privacy.receipts read model is R08-B")
    def test_receipts_are_identity_isolated(self):
        raise AssertionError("planned")

    @unittest.skip("R08-A1 internal repository exists; CRUD emission is R08-A2")
    def test_receipt_journal_is_append_only(self):
        raise AssertionError("planned")

    @unittest.skip("R08-B planned: RIS inspect/export not implemented")
    def test_export_is_machine_readable_and_minimal(self):
        raise AssertionError("planned")

    @unittest.skip("R08-C planned: erasure lifecycle not implemented")
    def test_erasure_preview_does_not_mutate(self):
        raise AssertionError("planned")

    @unittest.skip("R08-C planned: erasure lifecycle not implemented")
    def test_erasure_execute_is_idempotent_and_resumable(self):
        raise AssertionError("planned")

    @unittest.skip("R08-C planned: partner-profile/S3-version erasure not implemented")
    def test_erasure_completeness_across_partner_profiles_and_versions(self):
        raise AssertionError("planned")
