# Analysis Agent Package Tests

Covered in `tests/test_analysis_pipeline.py` (25 tests): CV-only, job-only,
ATS-only, comparison-only, full analysis, invalid result choice, missing
inputs, cross-tenant access, consent, entitlement, idempotency, jobRef expiry,
2h/4h TTL, 1 MiB limit, no document content in results, parser failure,
cleanup, ATS 2.0 compatibility, deterministic comparison and agent registration.

Run: `python -m pytest tests/test_analysis_pipeline.py -q`.
