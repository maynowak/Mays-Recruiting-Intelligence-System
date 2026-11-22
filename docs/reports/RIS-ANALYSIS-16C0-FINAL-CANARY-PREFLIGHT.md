# RIS-ANALYSIS-16C0 — Final Canary Preflight

**Date:** 2026-11-22
**Base:** `7dc7c74` on `feature/ris-analysis-integration-07`
**Edge fix:** `0a2388a`
**Mode:** read-only preflight + local bundle rebuild + static contract tests.
**No AWS mutation, no Terraform apply, no deployment, no approval, no real
data.**
**Verdict:** **NOT READY TO APPLY.** Both synthetic paths are prepared but
**BLOCKED**; the saved plan is stale and does not contain approval B.

---

## 1. Edge case: `agent.execution` + `DELIVERED` without `processing.result`

The 16B contract treated top-level `DELIVERED` as `APPROVED`. That is correct
for retail, but wrong for an agent execution: an `agent.execution` order can
only be proven complete by `processing.status=COMPLETED` plus a result body.

Minimal correction in `agents/orders/real.py`:

| Order type / state | Result |
|---|---|
| `agent.execution`, `DELIVERED`, no `processing.result` | **ERROR** + `contract_error=missing_processing_result` |
| `agent.execution`, `DELIVERED`, `processing.status=COMPLETED` + result | **APPROVED** |
| `agent.execution`, `DELIVERED`, `processing.status=FAILED` | **REJECTED** |
| `retail`, `DELIVERED` | **APPROVED** (unchanged) |

`orders_function` now also forwards `order_type`. Tests:
`tests/test_real_orders_adapter.py::TestOrderStatusSemantics`.
No other adapter, Mays or transport behavior changed.

## 2. Mays `apiProfileRef` binding C — final proof

### 2.1 Version boundary

| State | Value | Meaning |
|---|---|---|
| RIS pin file | `5cf50a0` | v0.5.0-rc.2 pin metadata |
| Generated module | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` | behavior inspected here |
| Local Mays checkout | `9627eb2` | review reference; not the generated module |

### 2.2 Actual code path

| Step | File / function | Check |
|---|---|---|
| Mays agent order create | `order_service.py::create_order` -> `_create_agent_order` | Stores `agentOrder.metadata.apiProfileRef`; validates shape/fingerprint, **not profile ownership** |
| Mays dispatch bind | `order_service.py::prepare_dispatch` | Calls `identity.can_read(item)` only (order owner); **no profile lookup/binding** |
| Mays envelope | `dispatch.py::build_dispatch_envelope` | Copies `metadata.apiProfileRef` to `identity.contextRef` |
| RIS ingress | `lambda/dispatch_ingress.py::resolve_context` | Resolves any profile with `status=ACTIVE` and a user/tenant; **no comparison to the Mays order owner** |
| RIS agent-order reader | `lambda/orders_reader.py::_create_agent_order` / `_load_profile` | **Does** require ACTIVE profile, `ownerUserId == verified subject`, tenant and entitlement |
| RIS OrdersPort | `agents/orders/real.py::submit_order` | `orders.create` is retail-only; no agent-order create |

**Conclusion:** C is **confirmed open, Mays-owned**. A Mays user who can create
an agent order can reference another ACTIVE `apiProfileRef`; Mays stores and
dispatches it, and RIS executes under that profile's tenant/owner. The RIS
reader path is safe, but it is not the Mays direct path. No Mays code was
changed and no workaround was invented.

## 3. Plan, state, bundles and approvals — freshness check

### 3.1 Saved plan

| Item | Value | Result |
|---|---|---|
| Plan file | `…/rc18/plan.out` | present |
| Plan SHA-256 | `9a0324a0523486b9d4850c9215030a084c35b8807508a6a55bd2e26596a4c7a6` | matches gate 15B manifest |
| Plan JSON SHA-256 | `c1360c511e53f6cadcf48b26f49c94d90d551578e83fc97be8b758ae7f5cb391` | matches |
| Timestamp | `2026-11-21T17:09:52Z` | — |
| Shape | 4 create / 3 update / 0 delete / 0 replace | matches |
| Guard | `NO_SHARED_DESTROY` | matches |
| Apply approved | `false` | **A not granted** |

Plan changes:

- **Create:** analysis Lambda, analysis data policy, two analysis invoke
  permissions.
- **Update:** dispatch-ingress IAM/role policy, dispatch-ingress Lambda, shared
  worker Lambda.
- **No change:** Cognito (15 no-op), CloudFront (2 no-op), Route53/ACM absent.
- Analysis env: `ANALYSIS_SYNTHETIC_MODE=false`, no synthetic profile values;
  parser mode `lambda`, worker analysis timeout 45 s.

### 3.2 Remote state (read-only)

| Item | Value |
|---|---|
| Bucket / key | `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate` |
| Serial | **67** |
| Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Resources | 283 |
| Last modified | `2026-11-20T17:02:21+00:00` |

The state is unchanged since the plan. The plan's state basis is current.

### 3.3 Bundle freshness — **plan is stale**

The 16B and 16C0 changes touched `agents/orders`, so the worker and analysis
bundles must be rebuilt. A local rebuild (`python lambda/build_zip.py --bundle
all`, no AWS) produced:

| Bundle | Saved plan | Current source | Verdict |
|---|---|---|---|
| Worker | `28125fe1…` | `85775f68…` | **CHANGED** |
| Analysis | `fcc2a008…` | `420bf861…` | **CHANGED** |
| Parser | `fb741fb2…` | `fb741fb2…` | unchanged |

**Consequence:** plan `9a0324a0…` is **STALE / RE-PLAN REQUIRED**. It would
either deploy the pre-16B worker code or fail the final-plan consistency check.
**Approval A cannot be exercised against the current feature branch.**

### 3.4 Approval B

Plan `9a0324a0…` contains only `ANALYSIS_SYNTHETIC_MODE=false`. The synthetic
tenant/user/partner/issuer/entitlement/expiry values are not in the plan or
repository. **Approval B is not verifiable from the saved plan** and requires
a new reviewed plan or an approved environment update.

## 4. Prepared synthetic paths

Machine-readable specification:
`docs/reports/RIS-ANALYSIS-16C0-PREFLIGHT.json`.
Static validation: `tests/test_analysis_canary_16c0.py` (10 passed).

### 4.1 Direct RIS path

**Status: BLOCKED (prepared).**

Blockers:

1. `A_STALE_PLAN` — new plan required.
2. `B_SYNTHETIC_ENV_NOT_IN_PLAN` — synthetic profile must be in the new plan.
3. `SYNTHETIC_RUNNING_WORKITEM_SEED_REQUIRED` — the verifier requires a
   persisted `RUNNING` WorkItem with the exact identity.
4. `NO_APPLY_OR_EXECUTION_APPROVAL`.

Execution sequence after remediation:

1. Build the 16C0 bundles and generate a new exact plan.
2. Approve and apply that plan (separate gate) with synthetic mode false.
3. Seed one synthetic `RUNNING` WorkItem.
4. Enable the approved synthetic env only for the canary window.
5. Invoke the analysis Lambda through the approved IAM path.
6. Verify WorkItem `COMPLETED` and the result body.
7. Delete synthetic WorkItem/job/CV artifacts and restore deny-by-default env.

### 4.2 Full Mays-Orders transport

**Status: BLOCKED (prepared).**

Blockers: all direct-RIS blockers **plus** `C_APIPROFILEREF_OWNER_BINDING`.

Execution sequence after remediation:

1. Dedicated synthetic Cognito user and an APIProfile owned by that user; only
   the required analysis entitlement.
2. Create one Mays agent order (`target=analysis-agent`,
   `metadata.apiProfileRef`, `requestId`).
3. `prepare_dispatch` binds one `workId`.
4. `ORDER_DISPATCH` -> dispatch ingress -> work queue -> shared worker ->
   analysis Lambda.
5. `ORDER_RESULT`/`ORDER_FAILED` -> Mays result consumer.
6. Retrieve `processing.status/result/error` via `GET /orders/{orderId}`.
7. Replay the same dispatch/result; prove one execution and deduplicated
   result.
8. Cleanup synthetic order/work/objects and revoke the profile/entitlement.

Even with a correctly owned synthetic profile, this path **does not prove C**
until Mays validates the profile ownership server-side.

## 5. CV / Job / Match test specification

| Offer | Success | Error | Idempotency | Result retrieval | Permission denial |
|---|---|---|---|---|---|
| `analysis.cv` | synthetic structured CV or owner PDF -> `CVParserResultBody 1.0`, `cvTags` | `missing_cv`, `cv_access_denied` | same key -> `idempotent=true`, identical result, one parse | WorkItem result; Mays order `processing.result.bodyType=CVParserResultBody` | no `parse.cv` -> `entitlement_denied`; consent false -> `consent_required`; foreign partner -> `partner_mismatch` |
| `analysis.job` | synthetic job text -> `JobParserResultBody 1.0`, `jobTags` >= 3 | `missing_job`, `job_text_too_large`, `job_ref_expired` | same key -> identical result, one parse | WorkItem result; Mays order `processing.result.bodyType=JobParserResultBody` | no `parse.job` -> `entitlement_denied`; consent/partner as above |
| `analysis.match` | structured CV + job -> `ComparisonResultBody 1.0`; optional `ats.tags` -> `ATSAnalysisResultBody 2.0` | `missing_cv`, `missing_job`, `missing_comparison_inputs` | same key -> identical comparison, one CV + one job parse | WorkItem result; Mays order `processing.result.bodyType=ComparisonResultBody` | no `compare.tags` -> `entitlement_denied`; `ats.tags` without `analyze.job` -> `entitlement_denied` |

Common assertions:

- One outer order/WorkItem; internal parser calls create no order.
- No RIS key/JWT/Authorization value in SQS, WorkItems, results or logs.
- Duplicate `ORDER_DISPATCH`/result -> no second execution or charge.
- Foreign owner 404; invalid identity 401; entitlement/consent fail closed.
- DLQ exhaustion still does **not** emit `ORDER_FAILED` (open ecosystem item).

## 6. Evidence matrix

| Area | Status |
|---|---|
| `agent.execution` + `DELIVERED` edge case | **IMPLEMENTED / LOCAL TESTED** (`0a2388a`) |
| 16B status/result contract | **IMPLEMENTED / LOCAL TESTED** |
| Mays `apiProfileRef` binding C | **BLOCKED** (Mays-owned, proven in code) |
| Plan `9a0324a0…` | **BLOCKED / STALE** (worker + analysis bundles changed) |
| Plan shape / guard / state | **VERIFIED READ-ONLY** (4/3/0, `NO_SHARED_DESTROY`, serial 67, lineage match) |
| Approval A | **NOT GRANTED / NOT EXERCISABLE** |
| Approval B | **UNVERIFIED / NOT IN PLAN** |
| Direct RIS path | **BLOCKED (prepared)** |
| Mays transport path | **BLOCKED (prepared + C)** |
| AWS live canary | **NOT RUN** |

## 7. Local tests run

- `tests/test_real_orders_adapter.py`, `tests/test_orders_reader.py`,
  `tests/test_orders_reader_agent_gate.py`: **79 passed + 7 subtests**.
- `tests/test_analysis_canary_16c0.py`: **10 passed**.
- Broader factory/analysis/auth regression (16B baseline): **533 passed,
  30 skipped, 13 subtests**.

No network and no AWS calls were used by these tests. The only AWS access in
this task was a read-only `sts get-caller-identity` and a read-only S3
`get-object` of the Terraform state; no object was written.

## 8. Verdict and required next actions

1. **Re-plan** after the 16C0 bundle rebuild; the old plan is invalid.
2. Keep **A** as a new exact-plan approval; do not reuse `9a0324a0…`.
3. Fold the approved **B** synthetic profile into the new plan or an approved
   environment change; keep `ANALYSIS_SYNTHETIC_MODE=false` by default.
4. Keep **C** blocked for the Mays transport path until Mays binds
   `apiProfileRef` to the order owner/partner.
5. Run the direct RIS path first; run the Mays path only after C is closed or
   explicitly accepted as a synthetic-only, non-security-proof test.
6. Do not claim AWS verification, offer activation or automatic agent resume.
