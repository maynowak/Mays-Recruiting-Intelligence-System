# PXX Phase 2 — Skipped Test Audit

**Baseline**
- 1046 passed
- 0 failed
- 8 skipped

**Audit Date**
2026-10-07

## Skipped Tests Overview

| # | Test Node ID | File | Line | Skip mechanism | Exact reason | Classification | Legitimate for baseline? | Re-enable condition | Status |
|---|--------------|------|------|----------------|--------------|----------------|--------------------------|---------------------|--------|
| 1 | tests/test_observability_foundation.py::TestObservabilityFoundation::test_dashboard_exists_with_real_widgets | tests/test_observability_foundation.py | 50 | unittest.SkipTest in setUpClass | keine AWS-Credentials (Contract-Tests brauchen Live) | C) INTEGRATION-CONDITIONAL | Yes | Valid AWS credentials for account 240571105849 and profile with access to CloudWatch | GREEN |
| 2 | tests/test_observability_foundation.py::TestObservabilityFoundation::test_alarms_present | tests/test_observability_foundation.py | 61 | unittest.SkipTest in setUpClass | keine AWS-Credentials (Contract-Tests brauchen Live) | C) INTEGRATION-CONDITIONAL | Yes | Valid AWS credentials for account 240571105849 | GREEN |
| 3 | tests/test_observability_foundation.py::TestObservabilityFoundation::test_trail_active | tests/test_observability_foundation.py | 71 | unittest.SkipTest in setUpClass | keine AWS-Credentials (Contract-Tests brauchen Live) | C) INTEGRATION-CONDITIONAL | Yes | Valid AWS credentials for account 240571105849 | GREEN |
| 4 | tests/test_observability_foundation.py::TestObservabilityFoundation::test_trail_bucket_protected_and_separate | tests/test_observability_foundation.py | 79 | unittest.SkipTest in setUpClass | keine AWS-Credentials (Contract-Tests brauchen Live) | C) INTEGRATION-CONDITIONAL | Yes | Valid AWS credentials for account 240571105849 | GREEN |
| 5 | tests/test_observability_foundation.py::TestObservabilityFoundation::test_project_isolation_no_mo_overlap | tests/test_observability_foundation.py | 91 | unittest.SkipTest in setUpClass | keine AWS-Credentials (Contract-Tests brauchen Live) | C) INTEGRATION-CONDITIONAL | Yes | Valid AWS credentials for account 240571105849 | GREEN |
| 6 | tests/test_observability_foundation.py::TestObservabilityFoundation::test_log_groups_exist | tests/test_observability_foundation.py | 100 | unittest.SkipTest in setUpClass | keine AWS-Credentials (Contract-Tests brauchen Live) | C) INTEGRATION-CONDITIONAL | Yes | Valid AWS credentials for account 240571105849 | GREEN |
| 7 | tests/test_lambda_packaging.py::TestLiveContract::test_e_noop_live_hash_matches | tests/test_lambda_packaging.py | 123 | unittest.SkipTest | keine mayaws-Credentials | C) INTEGRATION-CONDITIONAL | Yes | Valid mayaws AWS credentials / live Lambda access | GREEN |
| 8 | tests/test_lambda_packaging.py::TestLiveContract::test_h_reader_hash_matches | tests/test_lambda_packaging.py | 145 | unittest.SkipTest | keine mayaws-Credentials | C) INTEGRATION-CONDITIONAL | Yes | Valid mayaws AWS credentials / live Lambda access | GREEN |

## Classification Summary

- INTENTIONAL: 0
- ENVIRONMENT-CONDITIONAL: 0
- INTEGRATION-CONDITIONAL: 8
- TEMPORARY / TECHNICAL DEBT: 0
- OBSOLETE / SUSPICIOUS: 0

UNEXPLAINED SKIPS: 0
SKIPS HIDING KNOWN DEFECTS: 0

## Audit Notes

All 8 skips are integration-conditional live contract tests requiring real AWS credentials.
The skip mechanism is explicit `unittest.SkipTest` with clear reason messages.
Skip reasons are documented in code and test docstrings.
No skip hides a known defect; tests are designed to be CI-safe.

## Baseline Semantics

1046 passed / 0 failed / 8 skipped

- 0 failed = all executed tests in baseline are successful.
- 8 skipped = live integration contract tests deliberately skipped without credentials.
- The GREEN status of PXX gate is not compromised by skips; skips are intentional integration guards.

## Reviewer Status
GREEN

## Skip Audit Status
GREEN
