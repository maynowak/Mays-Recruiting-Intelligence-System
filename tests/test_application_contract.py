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

    def test_details_and_follow_up_round_trip_with_nullable_patch_fields(self):
        value = validate_create({
            "job": {"jobId": "j1"},
            "applicationDate": "2026-11-03T00:00:00Z",
            "applicationChannel": "email",
            "contact": {"name": "Hiring Contact", "email": "hiring@example.test", "phone": "+49 30 1"},
            "notes": "Synthetic note",
            "salary": {"expectation": {"amount": 80000, "currency": "EUR", "period": "year"}},
            "followUp": {"dueOn": "2026-11-10", "note": "Send reminder", "status": "open"},
        })
        self.assertEqual("email", value["applicationChannel"])
        self.assertEqual("2026-11-10", value["followUp"]["dueOn"])
        patch = validate_patch({
            "expectedVersion": 1,
            "applicationDate": None,
            "contact": None,
            "salary": None,
            "followUp": None,
        })
        self.assertIsNone(patch["followUp"])

    def test_follow_up_calendar_and_completion_invariants(self):
        with self.assertRaises(ApplicationContractError):
            validate_create({"job": {"jobId": "j1"}, "followUp": {"dueOn": "2026-02-30", "status": "open"}})
        with self.assertRaises(ApplicationContractError):
            validate_create({"job": {"jobId": "j1"}, "followUp": {"dueOn": "2026-11-10", "status": "completed"}})
        with self.assertRaises(ApplicationContractError):
            validate_create({"job": {"jobId": "j1"}, "followUp": {"dueOn": "2026-11-10", "status": "open", "completedAt": "2026-11-03T00:00:00Z"}})


if __name__ == "__main__":
    unittest.main()
