# Analysis Agent — Handoff

## Current status (2026-11-22, QA2 baseline 550090e)

- **LOCAL / FIXTURE VERIFIED**: Python 3.14.10 and 3.15 both: 3,193 standard tests
  passed, 134 skipped, 0 failures; 3,259 fixture tests passed, 68 skipped,
  0 failures; 441 subtests. Five agent installation packages VALIDATED.
- **AWS INFRA VERIFIED (16C2 Apply A)**: approved plan
  `7393445789d92bdb15ebcc9ea3ae85a9e98cb068c27ad84bc6fd982d3ba0f64a`
  applied (4 add / 3 change / 0 destroy, state 67 -> 69). Analysis Lambda
  `ris-dev2-dev-analysis`, dedicated Node parser Lambda, worker/ingress invoke
  wiring and scoped IAM were verified. Infrastructure is deny-by-default.
- **NOT Analysis live E2E**: no synthetic-profile Gate B, no Mays Orders
  transport Gate C, no activated offers/catalog/grants, no real customer traffic.
- Evidence: `docs/reports/RIS-ANALYSIS-16C2-APPLY-REGRESSION.md` and manifest;
  `docs/reports/RIS-ANALYSIS-16C2-QA1-REGRESSION.md` and manifest;
  `docs/reports/RIS-ANALYSIS-16C2-QA2-MODULE-CONTRACT.md` and JSON (including
  Python 3.14 addendum). Earlier E1B report is historical.

## Source and pins

- RIS reviewed source: `feature/ris-analysis-integration-07` @
  `550090e435e24a873e64837abee52679f769a0d0` (pre-closeout baseline).
- Jobsearch parser: `feature/ris-analysis-parser-cli-04` @ `e77ee94`;
  parser artifact source commit `c40bf78`, artifact SHA-256 `fb741fb2...`.
- Mays Orders generated module source: `016cdfd6ac62565dcec9a2fee78cb898fb919e59`.
- Separate composite clone fixture pin: `5cf50a0` (v0.5.0-rc.2).
  RC4 `v0.6.0-rc.1` / `5bc154e` is NOT integrated in this branch.
- QA2 generator: 23 outputs (three additive references to result queue/ARN/HMAC
  secret inside the generated Mays module); **applied target intentionally 20**.
  Target builder `--check` FAIL_EXPECTED, not a new infrastructure blocker.
  No target regeneration or Terraform apply performed in QA2.

## Execution and product boundary

- Composite agent: `analysis-agent`, `analysis.run`, `agent_analysis_agent`;
  `analysis.cv`, `analysis.job`, `analysis.match` remain **DRAFT / activation:false / catalog ABSENT**.
- One outer order/WorkItem; internal CV/job/ATS parser calls are technical
  subfunctions. Shared Correction-14 worker/SQS/agent registry and existing
  Mays-Orders status/result route; no second queue or order state machine.
- CV bridge uses existing owner-scoped RIS documents; structured CV may skip
  parsing. Temporary job refs default to 2h (4h maximum), opaque, max 1 MiB.
- Results: `CVParserResultBody` 1.0, `JobParserResultBody` 1.0,
  optional `ATSAnalysisResultBody` 2.0, `ComparisonResultBody` 1.0.
- Mays-Orders owner-bound GET `/orders/{orderId}` projects
  `processing.status/result/error` in the integrated `016cdfd` contract;
  RIS Orders Reader provides its own owner-scoped facade.

## Separate gates before live use

1. **B**: approved synthetic profile, test identity, scoped entitlements and
   expiry, followed by an executed synthetic AWS canary.
2. **C**: server-side Mays-Orders direct-API binding of `apiProfileRef` to
   verified Owner/Partner before Mays transport E2E or real Order traffic.
3. `analysis-processing` notice/legal basis, consent, entitlement, catalog,
   pricing/billing and customer activation remain separately pending.
4. DLQ retry exhaustion lacks terminal `ORDER_FAILED`; no automatic parent
   Agent-A WAITING/wake-up/resume. These are separate platform tracks, not
   prerequisites for a disabled-code main merge or a single Analysis order.

## Main merge boundary

A documented, clean, validated feature branch can be proposed for controlled
main review **without** activating the product. Inspect the full branch diff,
CI triggers and deployment side effects first. Never infer live E2E or service
approval from infrastructure installation or successful local fixtures.
