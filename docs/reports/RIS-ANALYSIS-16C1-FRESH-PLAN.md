# RIS-ANALYSIS-16C1 — Fresh Plan & Canary Approval Gate

**Date:** 2026-11-22
**Base:** `50ead67` on `feature/ris-analysis-integration-07`
**Plan timestamp:** `2026-11-22T10:08:44Z`
**Mode:** fresh Terraform plan + local bundle builds + read-only AWS checks.
**No apply, no deployment, no synthetic activation, no real data.**
**Verdict:** **READY FOR A APPROVAL** for the exact plan
`73934457…`. **B** is a separate proposal and **not active**. **C** remains
**BLOCKED**.

---

## 1. Baseline

| Item | Value |
|---|---|
| RIS HEAD | `50ead677bb606ff6224e2f03bdfaf86654163f5c` |
| Branch | `feature/ris-analysis-integration-07` |
| Account / region | `262370457690` / `eu-central-1` |
| Workspace | `ris-dev2` |
| Backend | `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate` / lock `ris-dev2-tf-lock` |
| Remote state | serial **67**, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, **283** resources |
| State last modified | `2026-11-20T17:02:21+00:00` |
| Mays pin file | `5cf50a0` (v0.5.0-rc.2) |
| Generated Mays module | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| Local Mays checkout | `9627eb2` (review reference; not the generated module) |
| Jobsearch | `e77ee94`; runtime files identical to artifact commit `c40bf78` |
| Parser artifact | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` (412 files, nodejs22.x, arm64) |

The historical plan `9a0324a0…` is now **STALE / SUPERSEDED**. It pins the
pre-16B/16C0 worker and analysis bundles. It must not be applied.

## 2. Bundles and fresh plan

### 2.1 Deterministic bundles

Built with `python lambda/build_zip.py --bundle all` and
`tools/build_analysis_parser_artifact.py` (fixed timestamps, sorted entries):

| Bundle | SHA-256 | Files |
|---|---|---|
| Worker | `85775f685eda57fbd2f49e6351b40f59301de0150c63cb67289fb5c324897096` | 115 |
| Analysis | `420bf8610920e03868daf8e593a71c2a9de7cc637ca006a5192dd2800a4a0c9e` | 113 |
| Parser | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` | 412 |
| Reader | `464b991f784f0ea14da761fca355e676490f9a399209d4d3c2149165c25b1c4d` | 4 |
| Health writer | `2260581dedf4e08b6fbc4bbb10496fa0fd5a2d67737bdd3cf81cb75e8a7cd52c` | — |
| Health publisher | `b0a189b8ae1862b05b3d19bbf3b2dc4f8db3298789e4fc5483f6eeaeaab29a81` | — |

The parser runtime files (`lambda/ris_parser_handler.mjs`, `api/_lib`,
`scripts/ris-parser-cli.mjs`) are unchanged between `c40bf78` and `e77ee94`;
only tests/docs changed. The artifact hash therefore still matches the
historical `fb741fb2…`.

### 2.2 Plan result

| Item | Value |
|---|---|
| Plan file | `…/rc19/plan-final.out` |
| Plan SHA-256 | `7393445789d92bdb15ebcc9ea3ae85a9e98cb068c27ad84bc6fd982d3ba0f64a` |
| Plan JSON | `…/rc19/plan-final.json` |
| Plan JSON SHA-256 | `12527f565b263b377381145a646700df76363866590fb2c61155357063305e75` |
| Shape | **4 add / 3 change / 0 destroy / 0 replace** |
| Guard | **`NO_SHARED_DESTROY`** |
| Apply approved | **false** |
| `ANALYSIS_SYNTHETIC_MODE` | **`false`** |

**Creates (4):**

- `aws_lambda_permission.analysis_invoke_ingress[0]`
- `aws_lambda_permission.analysis_invoke_worker[0]`
- `module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]`
- `module.analysis_runtime.aws_lambda_function.analysis[0]`

**In-place updates (3):**

- `module.agent_transport[0].aws_iam_role_policy.dispatch_ingress`
- `module.agent_transport[0].aws_lambda_function.dispatch_ingress`
- `module.lambda.aws_lambda_function.agent`

**No change (0 non-no-op):**

- Cognito (15 resources, all no-op)
- CloudFront (2, all no-op)
- Route53 / ACM (none)
- Mays-Orders resources (35, all no-op)
- No SQS queue, DynamoDB table, secret, API Gateway or DNS change.

Analysis environment remains deny-by-default: `ANALYSIS_CONSENT=false`,
`ANALYSIS_ENTITLEMENTS=""`, `ANALYSIS_NOTICE_APPROVED=false`,
`ANALYSIS_SYNTHETIC_MODE=false`, parser mode `lambda`.

IAM for the analysis runtime: PartnerProfiles read (`GetItem`,`Query`) and
WorkItems `GetItem` only. No WorkItems write, no Entitlements read, no
Order/Result SQS permission.

### 2.3 Path-only drift, rejected and normalized

The first fresh attempt (`…/rc19/plan.out`, SHA
`82aa49428d0c7d3bb2e3c1692bb3702a834c8d4b51e4db4642517f0e8809eb5f`) produced
**4 add / 4 change**. The extra change was
`module.analysis_runtime.aws_lambda_function.parser[0]`: only the `filename`
string used Windows backslashes instead of the prior forward-slash form; the
`source_code_hash` was identical.

That attempt was rejected as non-canonical. The two analysis artifact paths
were normalized to forward slashes, the parser artifact was **not** rebuilt
differently, and the final plan is **4/3/0/0**. The rejected plan is recorded,
not used.

## 3. Approval gates

### A — technical plan approval

**Status: READY FOR APPROVAL; NOT APPLIED.**

- Exact plan `73934457…` (JSON `12527f56…`), 4/3/0/0,
  `NO_SHARED_DESTROY`, state serial 67 / lineage `a0bd361d…`.
- Approval must re-check the plan SHA, state serial/lineage, and bundle hashes
  immediately before apply.
- A does **not** authorize B, C, a catalog seed, consent activation, real user
  traffic or a second plan.

### B — synthetic profile (separate proposal, not active)

**Status: PROPOSED_NOT_ACTIVE. The current plan does not contain B.**

Proposal to be confirmed by the operator before a **new** plan:

| Field | Proposed value |
|---|---|
| `tenantId` | `tenant-ris-canary-16c1` |
| `userId` | `user-ris-canary-16c1` |
| `partnerApplicationId` | `ris-internal-analysis-canary-16c1` |
| `issuer` | `https://issuer.invalid/synthetic-ris-16c1` |
| Entitlements | `parse.cv`, `parse.job`, `compare.tags`, `analyze.job` |
| Expiry | `2026-11-24T18:00:00Z` |
| Activation window | `2026-11-24T09:00:00Z`–`2026-11-24T13:00:00Z` |
| Installation | `ris-dev2` |
| Default mode | `false` |

Rules:

- No activation in 16C1; the values are a proposal only.
- If the window moves, generate a new plan with the new expiry.
- Synthetic mode must remain false outside the approved window.
- The exact synthetic profile is **not** in plan A; plan A alone cannot run
  the canary.
- No real consent, no catalog seed, no public offer.

### C — Mays `apiProfileRef` binding

**Status: BLOCKED, Mays-owned.**

Mays generated module `016cdfd`:

- `_create_agent_order` stores the client-supplied
  `agentOrder.metadata.apiProfileRef`;
- `prepare_dispatch` checks `identity.can_read(item)` (order ownership) only;
- `dispatch.py` copies `apiProfileRef` to `identity.contextRef`.

RIS `dispatch_ingress.resolve_context` accepts any `ACTIVE` profile and cannot
prove it belongs to the order owner/partner. RIS `orders_reader` **does** bind
owner/profile/tenant/entitlement, but that is not the Mays direct path.

Required: server-side binding/validation in Mays, or a signed server binding.
**No bypass via synthetic identity fields.** The Mays transport canary remains
blocked.

## 4. Canary definition

### 4.1 Stages

| Stage | Status | AWS verified | Scope |
|---|---|---|---|
| **Isolated Analysis Executor** | `BLOCKED_PENDING_A_B` | **false** | Direct analysis Lambda invoke with a seeded synthetic `RUNNING` WorkItem; no API, worker or order |
| **Authenticated RIS API/Worker** | `BLOCKED_PENDING_A_B` | **false** | Cognito JWT + APIProfile + entitlement + consent; work queue + shared worker; no Mays order |
| **Full Mays-Orders Transport** | `BLOCKED_C` | **false** | Mays agent order → dispatch ingress → work queue → worker → result consumer → order GET |

Only a stage actually executed and evidenced may be marked `AWS VERIFIED`.
Nothing is AWS-verified in 16C1.

### 4.2 Cases

| Offer | Success | Error | Replay | Result | Denial | Cleanup |
|---|---|---|---|---|---|---|
| `analysis.cv` | synthetic structured CV or owner PDF -> `CVParserResultBody 1.0` | `missing_cv`, `cv_access_denied` | same key -> `idempotent=true`, one parse | WorkItem result or Mays `processing.result.bodyType=CVParserResultBody` | no `parse.cv` -> `entitlement_denied`; consent false -> `consent_required`; foreign partner -> `partner_mismatch` | delete synthetic CV/job objects, WorkItem, entitlement; restore deny env |
| `analysis.job` | synthetic job text -> `JobParserResultBody 1.0` | `missing_job`, `job_text_too_large`, `job_ref_expired` | same key -> `idempotent=true`, one parse | WorkItem result or Mays `JobParserResultBody` | no `parse.job` -> `entitlement_denied`; consent/partner as above | delete synthetic job object, WorkItem, entitlement; restore deny env |
| `analysis.match` | structured CV + job -> `ComparisonResultBody 1.0`; optional `ats.tags` -> `ATSAnalysisResultBody 2.0` | `missing_cv`, `missing_job`, `missing_comparison_inputs` | same key -> identical comparison, one CV + one job parse | WorkItem result or Mays `ComparisonResultBody` | no `compare.tags` -> `entitlement_denied`; `ats.tags` without `analyze.job` -> `entitlement_denied`; consent false -> `consent_required` | delete synthetic CV/job objects, WorkItem, entitlement; restore deny env |

Common: one outer order/WorkItem; no RIS key/JWT/Authorization in transport;
duplicate dispatch/result does not execute or bill twice; foreign owner 404;
invalid identity 401; DLQ exhaustion still cannot emit `ORDER_FAILED`.

## 5. Evidence and tests

- Manifest: `docs/reports/RIS-ANALYSIS-16C1-PLAN-MANIFEST.json`
- Static plan/gate test: `tests/test_analysis_fresh_plan_16c1.py` — **10 passed**
- Focused suite including 16C0/16B and plan evidence: **570 passed, 30 skipped,
  13 subtests passed**
- `installer.agent_install --agent analysis-agent --stage validate`: **PASSED**
- Plan guard: `Shared infrastructure gate: plan deletes/replaces no shared
  infrastructure`
- Bundle hashes were re-checked after the docs/test additions and are
  unchanged; the plan remains tied to the current source.

### 5.1 16C0 count reconciliation

The 16C0 report quoted **533** broad tests in one place and **560** in the
auditlog. Resolution: **533** was the pre-16C0 16B baseline; the actual 16C0
broad run including the new static preflight and the `DELIVERED` edge-case
tests was **560 passed, 30 skipped, 13 subtests**. 16C1 uses the actual **560**
figure as its baseline and adds its own **10** tests (570 total).

## 6. Hard stops / next actions

1. Apply only the exact plan `73934457…` after a separate A approval; re-check
   SHA, state serial 67/lineage and bundle hashes.
2. Do not apply the stale `9a0324a0…` plan.
3. B requires a **new plan** with the approved synthetic profile; no activation
   in 16C1.
4. C remains blocked; no Mays transport canary and no real order traffic.
5. Run the isolated executor first, then the authenticated API/worker path,
   then Mays only after C.
6. Mark `AWS VERIFIED` only for a stage actually executed with captured
   evidence. No stage has that status now.
