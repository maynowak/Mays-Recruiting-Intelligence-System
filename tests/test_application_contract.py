import unittest

from jobsearch.application_contract import (
    ApplicationContractError, validate_create, validate_patch,
    validate_transition,
)


class ApplicationContractTests(unittest.TestCase):
    def test_identity_is_server_owned(self):
        with self.assertRaisesRegex(ApplicationContractError, "identity"):
            validate_create({"applicationId": "attacker", "job": {"jobId": "j1"}})
        with self.assertRaisesRegex(ApplicationContractError, "identity"):
            validate_create({"ownerId": "attacker", "job": {"jobId": "j1"}})

    def test_email_cannot_replace_verified_identity(self):
        with self.assertRaises(ApplicationContractError):
            validate_create({"email": "candidate@example.invalid", "job": {"jobId": "j1"}})

    def test_create_requires_job_id_and_preserves_references(self):
        value = validate_create({"job": {"jobId": "j1", "title": "Engineer"}, "cvRef": {"id": "cv1", "version": 2}})
        self.assertEqual(value["cvRef"]["version"], 2)
        with self.assertRaises(ApplicationContractError):
            validate_create({"job": {"title": "missing"}})

    def test_submit_requires_explicit_confirmation(self):
        with self.assertRaisesRegex(ApplicationContractError, "confirmation"):
            validate_transition("READY", "SUBMITTED")
        validate_transition("READY", "SUBMITTED", confirm=True)

    def test_stale_patch_is_rejected_by_contract(self):
        with self.assertRaises(ApplicationContractError):
            validate_patch({"job": {"jobId": "j1"}})


if __name__ == "__main__":
    unittest.main()
