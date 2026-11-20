# RIS-ANALYSIS-AGENT-RUNTIME-11 — Dedicated Analysis Compute

**Date:** 2026-11-20
**Base:** RIS `87a8e5e` (`feature/ris-analysis-integration-07`), Jobsearch
`e77ee94` (parser code `c40bf78`)
**Status:** **READY FOR CONTROLLED SYNTHETIC DEPLOYMENT REVIEW**
**No apply was performed.** The 2/0/0 plan below needs a new explicit operator
approval.

---

## 1. Compute architecture

| Item | Value |
|---|---|
| Function | `ris-dev2-dev-analysis` |
| Handler | `analysis_runner.handler` |
| Bundle | `terraform/analysis-lambda.zip` (dedicated) |
| Runtime / memory / timeout | `python3.14` / 512 MB / 60 s |
| Role | `ris-dev2-dev-analysis` (dedicated) |
| Parser | `RIS_PARSER_MODE=lambda` → `ris-dev2-dev-analysis-parser` |
| Invocation | internal `lambda:InvokeFunction` (direct WorkItem, wrapper or SQS shape) |
| Public endpoint | none |

The function reuses `agents.runtime.pipeline.process_record`:
WorkItem validation → registry/eligibility → entitlement re-check → analysis
agent → WorkItems result persistence/idempotency. No new queue, no second
routing system, no order result transport.

The bundle is built separately so the shared agent bundle and the shared worker
function code hash stay untouched:

```
python lambda/build_zip.py --bundle analysis
→ terraform/analysis-lambda.zip
  111 files, 287 919 bytes
  SHA-256 f3c2f1a20d4af4b3d6c818222ae0edb5d59c985e37c074c4e025e797700a2314
```

## 2. Agent factory integration

- `analysis_runner.build_runtime()` creates `AgentRegistry` + `AgentBody`,
  an `AnalysisAgent` with an explicit config, and registers it with
  `register_analysis_agent(..., agent=agent)`.
- `process_record(..., analysis_agent=agent)` and
  `ensure_reference_agent(..., analysis_agent=agent)` now accept that instance,
  so the pipeline cannot replace it with a default analysis agent.
- `AnalysisAgent` unwraps the runtime-nested WorkItem and reads
  tenant/user/partner application/issuer from the original item; direct calls
  keep the previous request shape.

## 3. Internal partner isolation

| Role | Identity |
|---|---|
| Caller | `ris-internal` (config, never from the body) |
| Executor | `ris-internal-analysis` / `analysis-agent` |
| CV owner | authenticated user + tenant (record re-check) |

Two independent gates must pass: the existing DynamoDB entitlement re-check
(`agentId=analysis-agent`) and the agent's capability/consent checks.
Cross-tenant CV, foreign caller, missing entitlement and missing/again
unapproved consent fail closed (`cv_access_denied`, `partner_mismatch`,
`entitlement_denied`, `consent_required`, `consent_notice_not_approved`).

## 4. Runtime / IAM / security tests

| Check | Result |
|---|---|
| Authorized WorkItem | COMPLETED, result persisted in WorkItems |
| Idempotent replay | duplicate, no second parser call |
| CV PDF | parsed, no base64/body persisted |
| Entitlement missing | DEAD_LETTER, no execution |
| Consent missing | DEAD_LETTER, `consent_required` |
| Cross-tenant CV | DEAD_LETTER, loader not called |
| SQS/Records shape | same pipeline |
| Permanent vs transient errors | rejected vs raised for retry |
| Node CLI timeout | controlled `ParserUnavailable` |
| SDK read timeout | controlled `ParserUnavailable` |
| Adapter timeout | 15 s, zero SDK retries |
| Budgets | analysis 60 s, parser 15 s, payload 100 000 chars, inline job 32 000 |
| Logging | runner logs only the failure type; no body/CV/job content |
| `terraform fmt -check` / `validate` | PASS |
| Focused regression | **296 passed + 13 subtests** |

**Limit:** the deployed parser Lambda's own 15 s timeout is configuration-pinned
and was not exercised (no controllable slow path); client and CLI timeouts were.

## 5. Terraform plan (read-only, not applied)

| Item | Value |
|---|---|
| Adds / changes / destroys / replacements | **2 / 0 / 0 / 0** |
| Plan SHA-256 | `b892d17a0168cac8df0278890323d1a1b10bbc7cc38dd14536239e776d4f700d` |
| Plan JSON SHA-256 | `0a1bb40cff4aee5fed9c3d6bdcc5a0167a4bb77c399fc65ad2fecf316a068861` |
| State serial / lineage | **67** / `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Backend | `ris-dev2-tf-state-dev`, `dev/terraform.tfstate`, lock `ris-dev2-tf-lock`, workspace `ris-dev2` |
| Shared guard | **`NO_SHARED_DESTROY`** |

Adds:

1. `module.analysis_runtime.aws_lambda_function.analysis[0]`
2. `module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]`

No change to the shared agent bundle/function, parser function, queues,
secrets, tables, or the previously applied analysis role policy.

IAM for the data policy: WorkItems `Get/Put/Update/Query` (table + index),
Entitlements `Get/Query` (table + index), PartnerProfiles `Get/Query`
(table + index). No SQS, Secrets Manager or Orders access.

## 6. Security and privacy gates

| Gate | State |
|---|---|
| `analysis-processing` v1.0 | **DRAFT** |
| `ANALYSIS_ENTITLEMENTS` | **empty** (no capability) |
| `ANALYSIS_CONSENT` / `ANALYSIS_NOTICE_APPROVED` | **false** |
| Entitlements (`ris-internal-analysis`, `analysis-agent`) | **PENDING_APPROVAL** |
| Catalog | **ABSENT** |
| Agent activation | **false** |
| Real personal data | none |
| Cognito/CloudFront/DNS/PURGE/shared IAM | no change |

**Consequence:** the deployed function denies every WorkItem until an operator
explicitly configures the synthetic analysis profile. That configuration change
is **not** part of the 2/0/0 plan and requires its own approval.

## 7. Synthetic AWS E2E matrix (prepared, not executed)

| Case | Expectation |
|---|---|
| Direct WorkItem, authorized synthetic profile | COMPLETED, WorkItems result |
| CV-only / job-only / ATS-only / comparison / full | four body versions (1.0/1.0/2.0/1.0) |
| CV PDF via parser Lambda | document SHA = fixture SHA |
| Idempotent replay | duplicate, no re-execution |
| Cross-tenant CV | `cv_access_denied` / DEAD_LETTER |
| Missing entitlement | `entitlement_denied` / DEAD_LETTER |
| Missing/unapproved consent | `consent_required` / `consent_notice_not_approved` |
| Expired jobRef | `job_ref_expired` |
| Oversize job/parser payload | `job_text_too_large` / `ParserInputError` |
| No payload in logs | only START/END/REPORT + failure type |

Prerequisites: apply approval for 2/0/0 **and** a separately approved synthetic
env configuration (entitlements/consent values); otherwise every case is
denied by design.

## 8. Rollback

| Stage | Action |
|---|---|
| Before apply | none (state serial 67) |
| Apply fails | no auto-destroy; inspect, then reviewed plan |
| After apply | reviewed reverse plan removes only the 2 additions |
| Runtime issue | set `enable_analysis_runtime=false` via reviewed plan (removes the analysis Lambda and data policy; parser/base runtime stay from 10B) |
| Privacy/entitlement issue | keep env deny defaults, notice DRAFT, grants empty |

## 9. Commits

| Commit | Content |
|---|---|
| `89929c5` | analysis runner, dedicated bundle, gated Lambda + data policy, wiring, tests |
| `af55b67` | pipeline accepts the configured agent; nested identity; integration tests |
| `87a8e5e` | timeout/limit tests, operations doc, audit log |

Both feature branches are pushed; working trees clean.

## 10. Open approvals

1. **Apply approval** for exactly the 2/0/0 plan (analysis Lambda + data
   policy), state serial 67.
2. **Synthetic test configuration approval** for the analysis env
   (entitlements/consent/notice flags); without it the function denies.
3. Legal/operator approval of the `analysis-processing` notice (real data).
4. Entitlement grant, catalog decision and agent activation (separate).
5. Live authenticated canary identity/token.

## 11. Verdict

**READY FOR CONTROLLED SYNTHETIC DEPLOYMENT REVIEW.**

The dedicated compute, factory integration, internal-partner isolation and
timeout/error boundaries are implemented and locally verified; the read-only
plan is additive (2/0/0), leaves shared resources untouched and passes the
guard. No apply was performed and no real data is in scope.
