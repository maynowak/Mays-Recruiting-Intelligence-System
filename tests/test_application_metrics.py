import unittest

from jobsearch.application_repository import ApplicationRepository


class ApplicationMetricsTests(unittest.TestCase):
    def test_metrics_consumes_all_pages_and_counts_open_overdue_followups(self):
        repo = object.__new__(ApplicationRepository)
        pages = iter([
            ([
                {"applicationId": "a", "stage": "draft"},
                {"applicationId": "b", "stage": "interview", "followUp": {"status": "open", "dueOn": "2000-01-01"}},
            ], {"cursor": "next"}),
            ([
                {"applicationId": "c", "stage": "feedback", "followUp": {"status": "open", "dueOn": "2999-01-01"}},
                {"applicationId": "d", "stage": "offer", "followUp": {"status": "completed", "dueOn": "2000-01-01", "completedAt": "2026-01-01T00:00:00Z"}},
                {"applicationId": "e", "stage": "submitted"},
            ], None),
        ])
        repo.list = lambda *args, **kwargs: next(pages)
        class Context:
            def validate(self):
                return self
        metrics = repo.metrics(Context())
        self.assertEqual({
            "total": 5,
            "drafts": 1,
            "submitted": 1,
            "interviews": 1,
            "openFollowUps": 2,
            "overdueFollowUps": 1,
        }, metrics)


if __name__ == "__main__":
    unittest.main()
