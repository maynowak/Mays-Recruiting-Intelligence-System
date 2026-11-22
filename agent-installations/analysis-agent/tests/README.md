# Analysis Agent Package Tests

## Local evidence (not AWS-verified)

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

Latest focused regression at E1B: **414 passed + 6 subtests** (analysis,
synthetic, offers, ecosystem, credentials, machine entrypoint, partner
boundary, Mays dispatch/result handoff). Report:
`docs/reports/RIS-ANALYSIS-OFFER-E2E-15-FINAL-CANARY-GATE.md`.

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

- No AWS live canary and no analysis Lambda deployment.
- No `ORDER_FAILED` proof for SQS DLQ exhaustion.
- No automatic agent resume after `ORDER_RESULT`/`ORDER_FAILED`.
- No cross-repo proof that Mays-Orders binds `apiProfileRef` to the order
  owner/partner.
