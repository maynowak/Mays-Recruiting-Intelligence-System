# RIS-ANALYSIS-CANARY-10B — Apply Approval Request (STEP A)

**Date:** 2026-11-20
**Status:** **AWAITING EXPLICIT OPERATOR APPROVAL — NO APPLY PERFORMED**
**Installation:** `ris-dev2` / `eu-central-1` / account `262370457690`
**Repository HEAD:** RIS `a75f59b` · Jobsearch `e77ee94` (parser code `c40bf78`)

---

## 1. Preflight verification

| Check | Result |
|---|---|
| Git (RIS / Jobsearch) | `a75f59b` / `e77ee94`, both clean |
| AWS caller | `arn:aws:iam::262370457690:user/devnemo`, account `262370457690` |
| Region | `eu-central-1` |
| Backend | `ris-dev2-tf-state-dev`, key `dev/terraform.tfstate`, lock `ris-dev2-tf-lock` |
| Workspace | `ris-dev2` |
| State serial | **64** (unchanged from 10A) |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Terraform | 1.17.0 |
| Artifact | 412 files, 17 937 176 bytes |
| Artifact SHA-256 | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` (matches manifest) |

A fresh plan was generated from the current configuration. Plan binaries are
not byte-stable across runs; this approval covers **this** plan only.

## 2. Plan under approval

| Item | Value |
|---|---|
| Plan file | `C:/Users/DCI-Student/AppData/Local/Temp/opencode/rc10b/plan.out` |
| **Plan SHA-256** | `e64a6272ac212dce54123c2b9533d42175f85ccc8d34ec2b6e26c3b39d15e676` |
| **Plan JSON SHA-256** | `66a954763dae6662974bdc7338a7d69f59b76102773fa4b8d75330976a8c9f31` |
| Adds / changes / destroys / replacements | **17 / 2 / 0 / 0** |
| Runtime flag | `enable_analysis_runtime=true` |
| Shared guard | **`NO_SHARED_DESTROY` — safe** |
| Machine-readable manifest | `docs/reports/analysis-canary-10b-plan-manifest.json` |

## 3. Resources to create (17)

Analysis runtime:

1. `module.analysis_runtime.aws_iam_role.analysis`
2. `module.analysis_runtime.aws_iam_role_policy.analysis`
3. `module.analysis_runtime.aws_s3_bucket.jobs`
4. `module.analysis_runtime.aws_s3_bucket_public_access_block.jobs`
5. `module.analysis_runtime.aws_s3_bucket_server_side_encryption_configuration.jobs`
6. `module.analysis_runtime.aws_s3_bucket_lifecycle_configuration.jobs`
7. `module.analysis_runtime.aws_cloudwatch_log_group.analysis`
8. `module.analysis_runtime.aws_iam_role.parser[0]`
9. `module.analysis_runtime.aws_iam_role_policy.parser_logs[0]`
10. `module.analysis_runtime.aws_cloudwatch_log_group.parser[0]`
11. `module.analysis_runtime.aws_lambda_function.parser[0]`
12. `module.analysis_runtime.aws_iam_role_policy.analysis_invoke_parser[0]`
13. `module.analysis_runtime.aws_lambda_permission.parser_invoke_analysis[0]`

Transport / documents (additive, no migration):

14. `aws_iam_role_policy.orders_agent_dispatch[0]`
15. `module.agent_transport[0].aws_iam_role_policy.order_result[0]`
16. `module.lambda.aws_iam_role_policy.order_result_transport[0]`
17. `module.documents.aws_s3_bucket_cors_configuration.documents`

## 4. The two in-place updates (no replacement)

### 4.1 `module.agent_transport[0].aws_iam_role_policy.dispatch_ingress`

**IAM policy update.** Adds the WorkItems GSI resource
`arn:aws:dynamodb:eu-central-1:262370457690:table/ris-dev2-dev-work-items/index/*`
to the existing `WorkItems` statement. The action list
(`GetItem`, `PutItem`, `UpdateItem`, `Query`) and all other statements
(logs, profiles, entitlements, dispatch queue) are unchanged. No permission is
removed, no resource is replaced. This is the only IAM broadening in the plan
and requires explicit approval.

### 4.2 `module.mays_orders[0].module.lambda.aws_lambda_function.handler`

**Environment update.** Adds `ORDER_DISPATCH_QUEUE_URL` =
`https://sqs.eu-central-1.amazonaws.com/262370457690/ris-dev2-dev-agent-dispatch`.
All existing variables are unchanged, including `ORDERS_COGNITO_ISSUER` and
`ORDERS_COGNITO_CLIENT_ID` (no Cognito configuration change).

## 5. Protected services and shared resources

| Area | Plan result |
|---|---|
| Cognito | 0 resources (issuer/client values unchanged) |
| CloudFront | 0 resources |
| Route53/DNS | 0 resources |
| ACM | 0 resources |
| Shared transport queues/policies/secrets/tables | no delete, no replacement |
| PURGE / erasure execution | none |
| Main merge / production deployment | none |

## 6. IAM, S3 and Lambda invoke readiness

| Item | Planned state |
|---|---|
| Analysis role | `${project}-${env}-analysis`; documents `tenant/*` read; jobs `jobs/*` Put/Get/Delete; logs |
| Parser role | logs only (`CreateLogStream`, `PutLogEvents`) |
| Parser Lambda | `ris-dev2-dev-analysis-parser`, nodejs22.x, arm64, 512 MB, 15 s, handler `lambda/ris_parser_handler.handler` |
| Invoke | analysis role may invoke the parser function only; Lambda permission principal = analysis role |
| Jobs bucket | `ris-dev2-dev-analysis-jobs`, Public Access Block all four flags, SSE AES256, lifecycle 1 day (backup), app enforces 2 h / 4 h |
| Logs | 14 days, no CV/job content |
| Public endpoint | none (no API Gateway, function URL or CloudFront) |

**Known runtime limitation (does not block apply):** the dedicated analysis
role is created but not yet attached to a deployed compute component; the
analysis agent currently runs inside the shared worker. A synthetic STEP C can
therefore exercise the deployed parser Lambda directly plus the local
orchestrator, but not a deployed analysis Lambda. Attaching the role to a
runtime is a separate change.

## 7. Rollback plan

| Point | Action |
|---|---|
| Before apply | none; state serial 64 unchanged |
| Apply fails midway | do **not** auto-destroy; inspect state/resources, then a reviewed reverse plan |
| After successful apply | reviewed reverse plan removes only the 17 additions (jobs bucket is empty/synthetic) |
| Parser runtime issue | set `enable_analysis_runtime=false` in a new plan → removes only the 6 parser resources; use `RIS_PARSER_MODE=cli` |
| Privacy/entitlement issue | keep notice DRAFT, grants empty, visibility ABSENT; withdrawal stops analysis |
| Shared resources | never touched by rollback |

## 8. Cost expectation

| Resource | Estimate |
|---|---|
| IAM roles/policies | $0 |
| Jobs bucket (synthetic, 1-day expiry) | < $0.05 / month |
| Log groups (14 days, little traffic) | < $0.05 / month |
| Parser Lambda (arm64, 512 MB) | $0 idle; ≈ $0.00002–0.0001 per invoke |
| Synthetic canary (≤ 1 000 runs) | ≈ $0.01–0.10 |
| New NAT / queue / secret / provisioned concurrency | none |

## 9. Stop conditions

Stop and do not apply if any of the following is true:

1. Plan SHA-256 differs from `e64a6272…d15e676` (or the JSON differs from
   `66a95476…8c9f31`).
2. State serial/lineage differs from 64 /
   `a0bd361d-5cd1-a207-a8c0-e6888f0be082`.
3. Any add/change/destroy/replacement outside the manifest.
4. Any Cognito, CloudFront, Route53/DNS or ACM change.
5. Any shared transport queue/policy/secret/table delete or replacement.
6. Artifact SHA-256 differs from
   `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a`.
7. Guard does not return `NO_SHARED_DESTROY`.

## 10. Requested approval

**Approve exactly this plan** (`e64a6272…`, 17/2/0) for a controlled
**synthetic** apply in `ris-dev2`, including the IAM index-resource update in
4.1 and the dispatch URL env update in 4.2.

- No real personal data.
- `analysis-processing` remains DRAFT; entitlements/catalog/activation remain
  unchanged.
- STEP B (apply) and STEP C (synthetic AWS canary) only run after this explicit
  approval.

**No Terraform apply has been executed.**
