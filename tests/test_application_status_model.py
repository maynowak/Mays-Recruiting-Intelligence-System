import unittest

from jobsearch.application_contract import (
    ApplicationContractError,
    JOBSEARCH_STAGES,
    STATUSES,
    legacy_status_stage,
    validate_stage_transition,
    validate_transition,
)


class ApplicationStatusModelTests(unittest.TestCase):
    def test_legacy_statuses_remain_valid(self):
        self.assertEqual(STATUSES, {"DRAFT", "READY", "SUBMITTED", "WITHDRAWN", "ARCHIVED"})
        for status in STATUSES:
            validate_transition(status, status, confirm=status == "SUBMITTED")

    def test_jobsearch_statuses_are_complete_and_roundtrip_as_stages(self):
        self.assertEqual(
            JOBSEARCH_STAGES,
            {"draft", "submitted", "feedback", "interview", "offer", "rejected", "withdrawn"},
        )
        for stage in JOBSEARCH_STAGES:
            validate_stage_transition(stage, stage, confirm=stage == "submitted")
        self.assertEqual("draft", legacy_status_stage("DRAFT"))
        self.assertEqual("submitted", legacy_status_stage("SUBMITTED"))
        self.assertIsNone(legacy_status_stage("READY"))
        self.assertIsNone(legacy_status_stage("ARCHIVED"))

    def test_stage_transitions_and_explicit_submission(self):
        validate_stage_transition("draft", "submitted", confirm=True)
        with self.assertRaisesRegex(ApplicationContractError, "confirmation"):
            validate_stage_transition("draft", "submitted")
        for current, target in (("submitted", "feedback"), ("feedback", "interview"),
                                ("interview", "offer"), ("offer", "withdrawn")):
            validate_stage_transition(current, target)
        with self.assertRaisesRegex(ApplicationContractError, "stage transition"):
            validate_stage_transition("rejected", "interview")

    def test_legacy_ready_and_archived_are_not_silently_mapped(self):
        with self.assertRaisesRegex(ApplicationContractError, "stage"):
            # A legacy READY row has no persisted Jobsearch stage. It remains
            # readable as READY until an explicit client transition is made.
            validate_stage_transition("ARCHIVED", "feedback")


if __name__ == "__main__":
    unittest.main()
