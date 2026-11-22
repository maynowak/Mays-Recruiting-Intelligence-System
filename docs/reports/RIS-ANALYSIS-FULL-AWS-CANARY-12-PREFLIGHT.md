# RIS-ANALYSIS-FULL-AWS-CANARY-12 — Final Preflight (STEP A)

**Date:** 2026-11-21
**Status:** **AWAITING NEW EXPLICIT OPERATOR APPROVAL — NO APPLY PERFORMED**
**Installation:** `ris-dev2` / `eu-central-1` / account `262370457690`
**Repository HEAD:** RIS `90810f7` · Jobsearch `e77ee94` (parser code `c40bf78`)

The CANARY-10B approval is **not** reused. This report asks for a new approval
for exactly the plan below.

---

## 1. Verification

| Check | Result |
|---|---|
| Working trees | RIS clean, Jobsearch clean |
| Caller | `arn:aws:iam::262370457690:user/devnemo` |
| Account / region | `262370457690` / `eu-central-1` |
| Backend | `ris-dev2-tf-state-dev`, key `dev/terraform.tfstate`, lock `ris-dev2-tf-lock` |
| Workspace | `ris-dev2` |
| State serial / lineage | **67** / `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| State resources | 283 |
| Terraform | 1.17.0 |
| Analysis Lambda | not deployed (`ResourceNotFoundException`) |
| Parser Lambda | unchanged: nodejs22.x, arm64, 512 MB, 15 s, code SHA `+3Qfsl58…` |

## 2. Plan under approval

| Item | Value |
|---|---|
| Plan file | `C:/Users/DCI-Student/AppData/Local/Temp/opencode/rc11/plan.out` |
| **Plan SHA-256** | `b892d17a0168cac8df0278890323d1a1b10bbc7cc38dd14536239e776d4f700d` |
| **Plan JSON SHA-256** | `0a1bb40cff4aee5fed9c3d6bdcc5a0167a4bb77c399fc65ad2fecf316a068861` |
| Adds / changes / destroys / replacements | **2 / 0 / 0 / 0** |
| Guard | **`NO_SHARED_DESTROY`** |
| Manifest | `docs/reports/analysis-full-canary-12-manifest.json` |

The saved plan was re-rendered to JSON from the exact file; both hashes match
the approval values. No new plan was generated.

## 3. The two resources

1. `module.analysis_runtime.aws_lambda_function.analysis[0]`
   → `ris-dev2-dev-analysis`, `python3.14`, 512 MB, 60 s,
   handler `analysis_runner.handler`, role `ris-dev2-dev-analysis`,
   no public endpoint.
2. `module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]`
   → `ris-dev2-dev-analysis-runtime-data` on the dedicated analysis role.

No other resource is created, changed, replaced or destroyed. The parser
Lambda is untouched.

## 4. IAM actions and resources (least privilege)

| Statement | Actions | Resources |
|---|---|---|
| `WorkItems` | `dynamodb:GetItem`, `PutItem`, `UpdateItem`, `Query` | `ris-dev2-dev-work-items`, `…/index/*` |
| `EntitlementRecheck` | `dynamodb:GetItem`, `Query` | `ris-dev2-dev-entitlements`, `…/index/*` |
| `OwnedPartnerProfiles` | `dynamodb:GetItem`, `Query` | `ris-dev2-dev-partner-profiles`, `…/index/*` |

No SQS, Secrets Manager, Lambda, S3, Orders or shared policy permission is
added. Parser invoke remains the existing policy on the same role.

## 5. Analysis bundle

| Item | Value |
|---|---|
| Path | `terraform/analysis-lambda.zip` |
| Size / files | 287 919 bytes / 111 |
| SHA-256 | `f3c2f1a20d4af4b3d6c818222ae0edb5d59c985e37c074c4e025e797700a2314` |
| Contents | `analysis_runner.py` + `agents/` + `jobsearch/` |
| Separation | distinct from the shared agent bundle; worker code hash unchanged |

## 6. WorkItem reject / DEAD_LETTER semantics

Verified in `tests/test_analysis_runner_pipeline.py` against the real
`process_record`:

- authorized → `COMPLETED`, result persisted in WorkItems;
- idempotent replay → duplicate, no re-execution;
- missing entitlement → `DEAD_LETTER`, `denied=true`, no agent run;
- missing consent → `DEAD_LETTER`, `ValidationError consent_required`;
- cross-tenant CV → `DEAD_LETTER`, loader not called;
- invalid WorkItem → `REJECTED` without logging the body;
- unexpected failure → raise for the existing retry/attempt semantics.

## 7. Environment and synthetic-test prerequisite

The plan deploys with **deny defaults**:

```
ANALYSIS_ENTITLEMENTS=""  ANALYSIS_CONSENT=false  ANALYSIS_NOTICE_APPROVED=false
```

Consequently, after this apply every analysis WorkItem is denied until a
**separately approved synthetic environment configuration** is applied
(entitlements, consent, notice flag for the synthetic tenant). That update is
**not** part of this 2/0/0 plan. STEP C cannot produce a green pipeline without
it; it can only prove the deny paths.

## 8. Synthetic AWS test procedure (after approval)

1. Apply only the approved plan; verify both resources and the analysis role.
2. Confirm the parser Lambda is unchanged.
3. For the deny baseline: invoke the analysis Lambda with a synthetic WorkItem
   (no entitlements/consent) → `DEAD_LETTER` for entitlement/consent, and a
   cross-tenant CV → `cv_access_denied`.
4. After the separate env approval: set the synthetic entitlements/consent,
   invoke with the synthetic CV PDF and job ad; expect
   `CVParserResultBody 1.0`, `JobParserResultBody 1.0`,
   `ATSAnalysisResultBody 2.0`, `ComparisonResultBody 1.0`.
5. Idempotent replay: same `workId` → duplicate, no second parser call.
6. Verify the analysis→parser call under the analysis role (CloudWatch +
   parser logs), WorkItems status transitions, job S3 cleanup, and that logs
   contain no payload/CV content.
7. Remove synthetic WorkItems/job objects; keep privacy gates unchanged.
8. Revert the synthetic env configuration (deny defaults) after the canary.

## 9. Stop conditions

1. Plan SHA-256 ≠ `b892d17a…f700d` or JSON ≠ `0a1bb40c…68861`.
2. State serial/lineage ≠ 67 / `a0bd361d…e082`.
3. Any change outside the two manifest resources.
4. Parser Lambda modified.
5. Any Cognito/CloudFront/Route53/ACM change.
6. Any shared queue/policy/secret/table delete or replacement.
7. Bundle SHA ≠ `f3c2f1a2…a2314`.
8. Guard ≠ `NO_SHARED_DESTROY`.

## 10. Rollback

| Point | Action |
|---|---|
| Before apply | none; state serial 67 |
| Apply fails | no auto-destroy; inspect, then a reviewed plan |
| After success | reviewed reverse plan removes only the 2 additions |
| Runtime issue | `enable_analysis_runtime=false` via reviewed plan (analysis function + data policy only; parser/base stay) |
| Privacy issue | keep deny defaults; notice DRAFT; no grants |

## 11. Tests

- 7 new preflight invariants (exact resources, IAM least privilege, bundle and
  saved-plan hashes, stop conditions).
- Focused runtime/security set: 56 passed (runner, pipeline, timeouts, worker
  pipeline, Terraform invariants).

## 12. Requested approval

**Approve exactly plan `b892d17a…f700d` (2/0/0)** for a controlled **synthetic**
apply in `ris-dev2`, and state whether the separate synthetic environment
configuration (section 7) is approved for STEP C.

No Terraform apply has been executed. STEP B/C will not start without this new
approval.
