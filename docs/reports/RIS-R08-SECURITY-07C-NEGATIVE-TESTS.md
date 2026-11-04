# RIS-R08-SECURITY-07C — Negative Tests

`tests/test_public_application_erasure.py` exercises the real Lambda routing
boundary and verifies:

- Application executor construction from verified claims;
- no-store headers on success and missing-store error responses;
- empty ApplicationV1 result;
- multi-page cursor/resume processing;
- application-store failure cannot report completion.

Existing ApplicationV1, R08-C, privacy, fence, worker, and API tests remain in
the regression selection. Latest focused result: **70 passed**.
