# Analysis Agent — Handoff

## Status

- **LOCAL VERIFIED** through the Correction-14 chain; **NOT DEPLOYED**, no AWS
  canary, no offer/catalog activation, no real user data.
- Latest evidence: `docs/reports/RIS-ANALYSIS-OFFER-E2E-15-FINAL-CANARY-GATE.md`
  (RIS `c245512`) and `docs/reports/RIS-ANALYSIS-ECOSYSTEM-CORRECTION-14.md`.
- Final focused regression at E1B: **414 passed + 6 subtests**. The analysis
  package itself has 31 pipeline tests and 14 offer tests; synthetic identity
  coverage has 17 tests.
- Technical apply is ready for an exact-plan approval but was **not applied**.
  Plan `9a0324a0…` (4 add / 3 change / 0 destroy, guard
  `NO_SHARED_DESTROY`, state serial 67) is superseded by any later bundle or
  Terraform change.

## Pins

- RIS: `feature/ris-analysis-integration-07` @
  `c245512a99f3a9122e38a408747e04f6ca45c6c1`.
- Jobsearch: `feature/ris-analysis-parser-cli-04` @ `e77ee94`; parser artifact
  source commit `c40bf78`, artifact SHA-256 `fb741fb2…`.
- Mays-Orders generated module: source `016cdfd6…` (module-builder manifest).
- RIS pin file: `5cf50a0` (v0.5.0-rc.2). Local Mays checkout `9627eb2` is a
  review reference, **not** the generated module source; its `lambda/src` does
  not contain `dispatch.py`, `identity.py`, `result_consumer.py` or
  `result_envelope.py`.

## Runtime and data

- One outer order/WorkItem; internal CV/job/ATS parser calls are technical
  subfunctions, not additional orders.
- CV bridge: existing RIS documents S3; structured CV skips parsing.
- Temporary job store: 2 h default, 4 h maximum, 1 MiB, opaque refs.
- Results: `CVParserResultBody` 1.0, `JobParserResultBody` 1.0,
  `ATSAnalysisResultBody` 2.0 (optional), `ComparisonResultBody` 1.0.
- Result retrieval remains Mays-Orders `GET /orders/{orderId}`
  (`processing.status/result/error`); the RIS orders-reader exposes the same
  owner-scoped view. No new result API was added.

## Open approvals and blockers

1. **A — exact technical apply** `9a0324a0…`; not approved.
2. **B — synthetic profile** (tenant/user/partner/issuer/entitlements/expiry/
   installation); not approved.
3. **C — Mays-Orders `apiProfileRef` ownership binding**; cross-repo blocker,
   owned by Mays-Orders.
4. Legal notice `analysis-processing` 1.0, entitlement grants and catalog seed
   remain PENDING/ABSENT.
5. DLQ exhaustion cannot emit `ORDER_FAILED`; separate redrive decision.
6. Automatic agent resume after `ORDER_RESULT`/`ORDER_FAILED` is **not
   implemented**. Do not present it as part of this package.

## Next

Obtain A and B separately, run a synthetic canary against the existing
dispatch -> work queue -> worker -> result path, retrieve the result through
Mays-Orders, and clean up the synthetic profile. No main merge, production
deployment or real-user activation.
