import unittest
from unittest.mock import Mock
from dataclasses import replace

from agents.ecosystem.privacy_application_erasure import ApplicationErasureExecutor
from jobsearch.application_contract import ApplicationContext
from agents.ecosystem.privacy_profile_erasure import ProfileOnlyErasureExecutor
from agents.ecosystem.privacy_erasure_contract import OPERATION_SCOPE_USER
from tests.test_r08_c1a_profile_only_erasure import OperationFake, Profiles, make


class ApplicationErasureTests(unittest.TestCase):
    def test_application_phase_is_registered_in_durable_operation(self):
        class Apps:
            def __init__(self):
                self.items = [{"applicationId": "a1", "version": 1}]

            def list(self, context, *, limit, cursor=None, include_deleting=False):
                self.include_deleting = include_deleting
                return list(self.items), None

            def delete(self, application_id, expected_version, context):
                self.items = [x for x in self.items if x["applicationId"] != application_id]

        operation, context = make(OPERATION_SCOPE_USER)
        store = OperationFake(operation)
        result = ProfileOnlyErasureExecutor(
            profile_repository=Profiles({}), operation_repository=store,
            application_repository=Apps(),
            delete_user_profile=lambda *args, **kwargs: None).run(operation, context)
        self.assertEqual("COMPLETED", result.progress["applications"].status)

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


class PrivacyErasureApplicationStepTests(unittest.TestCase):
    def test_application_step_runs_and_counts(self):
        from agents.ecosystem.privacy_erasure import PrivacyErasure
        calls = []

        def deleter(user_id, tenant_id):
            calls.append((user_id, tenant_id))
            return 2, False

        result = PrivacyErasure(application_deleter=deleter).erase("u1", tenant_id="t1")
        step = next(s for s in result.steps if s.step == "delete-applications")
        self.assertTrue(step.ok)
        self.assertEqual(2, step.affected)
        self.assertTrue(result.complete)
        self.assertEqual([("u1", "t1")], calls)

    def test_pending_application_page_keeps_run_incomplete(self):
        from agents.ecosystem.privacy_erasure import PrivacyErasure
        result = PrivacyErasure(application_deleter=lambda u, t: (1, True)).erase("u1", tenant_id="t1")
        step = next(s for s in result.steps if s.step == "delete-applications")
        self.assertFalse(step.ok)
        self.assertFalse(result.complete)

    def test_absent_deleter_is_a_no_op(self):
        from agents.ecosystem.privacy_erasure import PrivacyErasure
        result = PrivacyErasure().erase("u1", tenant_id="t1")
        step = next(s for s in result.steps if s.step == "delete-applications")
        self.assertTrue(step.ok)
        self.assertEqual(0, step.affected)
