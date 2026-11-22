# Analysis Agent Package Tests

## Local test evidence (distinct from AWS infrastructure verification)

| Area | Test file | Count |
|---|---|---|
| Orchestration pipeline (CV/job/ATS/comparison, consent, entitlement, TTL, owner) | `tests/test_analysis_pipeline.py` | 31 |
| Three offer contracts and DRAFT catalog | `tests/test_analysis_offers.py` | 14 |
| Synthetic identity/verifier, negatives, no global consent | `tests/test_analysis_synthetic_profile.py` | 17 |
| Entitlements, lifecycle and installer gate | `tests/test_analysis_entitlements.py` | 12 |
| Ecosystem/registry/AgentBody wiring | `tests/test_analysis_ecosystem_wiring.py` | 9 |
| Parser adapters and runtime modes | `tests/test_parser_runtime_modes.py` | 17 |
| Parser agent packages | `tests/test_parser_agents.py` | 17 |
| Parser timeouts | `tests/test_parser_timeouts.py` | 5 |

Historical focused E1B regression: **414 passed + 6 subtests**;
`docs/reports/RIS-ANALYSIS-OFFER-E2E-15-FINAL-CANARY-GATE.md`.

Latest QA2 local regression, identically on **Python 3.14.10 and 3.15**:
**3193 passed / 134 skipped / 0 failed / 441 subtests** standard;
**3259 passed / 68 skipped / 0 failed / 441 subtests** full fixtures.
Five agent installation packages VALIDATED.
Evidence: `docs/reports/RIS-ANALYSIS-16C2-QA2-MODULE-CONTRACT.md`
and `.json`. AWS infrastructure acceptance is separately recorded in
`docs/reports/RIS-ANALYSIS-16C2-APPLY-REGRESSION.md`.

## Commands

```bash
python -m pytest tests/test_analysis_pipeline.py -q
python -m pytest tests/test_analysis_offers.py -q
python -m pytest tests/test_analysis_synthetic_profile.py -q
python -m pytest tests/test_analysis_entitlements.py -q
python -m pytest tests/test_analysis_ecosystem_wiring.py -q
python -m installer.agent_install --agent analysis-agent --stage validate --status-file <path>
```

## Not covered by local tests

- **No executed Analysis live E2E**: B synthetic profile/consent not approved.
  The Analysis and Node parser Lambdas are **AWS infrastructure verified**
  (16C2 Apply A, 4/3/0, state 69); not a claim of executed business work.
- No `ORDER_FAILED` proof for SQS DLQ exhaustion.
- No automatic agent resume after `ORDER_RESULT`/`ORDER_FAILED`.
- No cross-repo proof that Mays-Orders binds `apiProfileRef` to the order
  owner/partner.
