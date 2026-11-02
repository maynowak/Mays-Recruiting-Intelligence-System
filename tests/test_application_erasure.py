import unittest
from unittest.mock import Mock

from agents.ecosystem.privacy_application_erasure import ApplicationErasureExecutor
from jobsearch.application_contract import ApplicationContext


class ApplicationErasureTests(unittest.TestCase):
    def test_page_deletion_returns_resumable_checkpoint(self):
        repo = Mock()
        repo.list.return_value = ([{"applicationId": "a1", "version": 2}], {"applicationId": "a1", "entityKey": "META"})
        result = ApplicationErasureExecutor(repo).run(ApplicationContext("u", "t", "p", "i"))
        repo.delete.assert_called_once_with("a1", 2, ApplicationContext("u", "t", "p", "i"))
        self.assertTrue(result.pending)
        self.assertEqual(1, result.deleted)

    def test_failure_is_pending_not_success(self):
        repo = Mock()
        repo.list.return_value = ([{"applicationId": "a1", "version": 1}], None)
        repo.delete.side_effect = RuntimeError("transient")
        # Unexpected failures must remain visible to the existing orchestrator;
        # it must not convert an unknown failure into a successful deletion.
        with self.assertRaises(RuntimeError):
            ApplicationErasureExecutor(repo).run(ApplicationContext("u", "t", "p", "i"))


if __name__ == "__main__":
    unittest.main()
