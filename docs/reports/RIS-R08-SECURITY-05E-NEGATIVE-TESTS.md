# RIS-R08-SECURITY-05E — Negative Tests

Evidence from the local suite:

- `tests/test_worker_pipeline.py`: production-shaped transactional admission,
  stale replay with missing WorkItem, and atomic create tests pass.
- `tests/test_subject_fence.py`: deterministic scope binding, active fence,
  corrupt row, and unavailable store fail-closed tests pass.
- `tests/test_privacy_erasure_security.py`: fence activation is idempotent and
  occurs before cancellation; terminal rows remain retained.

Focused result: **108 passed, 7 subtests passed** across the selected worker,
erasure, authorization, HTTP, machine-entrypoint, and M2M tests. No AWS tests
or live queue/redrive tests were run.
