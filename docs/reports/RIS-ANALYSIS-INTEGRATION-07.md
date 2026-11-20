# RIS-ANALYSIS-INTEGRATION-07 — Release Candidate

**Date:** 2026-11-20
**Verdict:** **SUPERSEDED by RIS-ANALYSIS-INTERNAL-PARTNER-08** (transport policies retained additively; 0 destroys). Original RC verdict: BLOCKED — controlled transport migration approval required.
All application-level checks are green; the only blocker is the upstream
Mays-Orders transport refactor, which replaces four shared IAM policies.

---

## 1. Repositories and git state

| Repo | Branch | HEAD | Divergence vs `origin/main` |
|---|---|---|---|
| RIS | `feature/ris-analysis-integration-07` | merge commit (this RC) | integration merge of `b05d78a` + `origin/main` `e95fe48` |
| Jobsearch | `feature/ris-analysis-parser-cli-04` | **`aaa260c`** | 3 ahead / 0 behind `origin/main` `81db09a` |

- RIS integration was done as a **merge** (no rebase/force), preserving all
  foreign changes from `origin/main` (consent/unblock work) and all local
  agent-factory commits.
- Jobsearch branch is based directly on `origin/main`; no rebase needed.
- The older `feature/ris-parser-library-01` and
  `feature/ris-jm-agent-standardization-01` branches remain untouched and are
  superseded.

### Merge conflicts resolved (7 files)

| File | Resolution |
|---|---|
| `installer/build_mays_orders_module.py` | adopted `origin/main`'s `apply_ris_order_dispatch_env_patch` |
| `installer/ris.py` | adopted main's transport allowlist; added `ats_api_base_url`/`agent_execution_timeout_seconds` |
| `terraform/main.tf` | adopted main's `order_result_*` model; kept ATS/orders/timeout wiring; removed old result locals |
| `terraform/variables.tf` | adopted main's `order_result_*`/producer vars; kept ATS/timeout vars |
| `terraform/modules/lambda/main.tf` | adopted `order_result_*` env merge + `order_result_transport` policy; kept `ORDERS_BASE_URL`/`ATS_API_BASE_URL` |
| `terraform/modules/agent_transport/lambda.tf` | adopted main's result env merge; kept ATS env; de-duplicated module variables |
| `docs/AI_AUDITLOG.md` | union of both append-only histories (no entries lost) |

Removed as superseded: `tests/test_orders_result_transport.py` (tested the
retired `agent_result_*` model; main's `tests/test_terraform_agent_transport.py`
covers the new one). `installer/project-configs/ris-dev2.json` keeps the live
ris-dev2 identity (`managed`, m2m=true) and drops the removed
`orders_agent_result_enabled` key.

## 2. Parser artifact and pins

- ARTIFACT: the Node CLI wraps the existing `api/_lib/analysis/service.mjs`
  (`parseCvBuffer`, `extractAtsRequirements`, `analyzeAts`). No second parser.
- Pins: `cv-parser-agent`, `job-parser-agent`, `analysis-agent` manifests now
  point to `feature/ris-analysis-parser-cli-04` @ **`aaa260c`**; RIS source
  branch `feature/ris-analysis-integration-07`.
- `npm run test:parsers` → 3 passed (job tags/stableId, CV PDF fixture, errors).

## 3. Five agent packages

`ats-agent`, `addition-agent`, `cv-parser-agent`, `job-parser-agent`,
`analysis-agent`: installer discovery + validate **PASS** (orchestrator test
asserts all five and their required lifecycle artifacts).

## 4. Synthetic E2E pipeline (real Node CLI, no AWS)

Request: `cv.tags, job.tags, ats.tags, comparison` with structured CV
(Python/AWS/Kubernetes, German, MSc) and synthetic job text.

| Result | Evidence |
|---|---|
| `cv.tags` | `CVParserResultBody 1.0`, 5 tags |
| `job.tags` | `JobParserResultBody 1.0`, 5 tags |
| `ats.tags` | `ATSAnalysisResultBody 2.0`, 2 tags, score 100, status complete |
| `comparison` | `ComparisonResultBody 1.0`, required/preferred/overall 100 %, weightedScore 100.0 |
| Idempotency | second delivery returns `idempotent: true` with identical results |

A separate run used the real CV PDF fixture through the CLI:
`parse.cv` returned AWS/Terraform/TypeScript tags, a 64-hex document SHA-256 and
`confidence: confirmed`.

## 5. Entitlements, consent, idempotency, cost/order boundaries

- Per-result capability check: `parse.cv`, `parse.job`, `analyze.job`,
  `compare.tags` (+ `parse.cv`/`parse.job` for comparison).
- Missing consent → `consent_required`; missing entitlement →
  `entitlement_denied`; the agent fails closed without configured entitlements.
- Cross-tenant `jobRef` → `job_access_denied`; expired ref →
  `job_ref_expired`; 2 h default, 4 h hard maximum, 1 MiB limit.
- Only requested parsers run (ATS-only does not run the job parser).
- Idempotency key is scoped by tenant+user; repeated delivery is cached.
- Internal parser steps are not separate billable orders; no payment activation;
  no AI provider call in the comparison.
- No document content in results or WorkItems (tested).

## 6. Tests, CI, Terraform

| Check | Result |
|---|---|
| `tests/test_analysis_pipeline.py` | 25 passed (incl. agent/registration tests) |
| `tests/test_parser_agents.py` | 17 passed (incl. real CLI PDF/job) |
| Focused RIS regression (analysis, parser, orchestrator, guard, transport, reader gate, partner, lifecycle) | **180 passed, 13 subtests** |
| Jobsearch parser tests | 3 passed |
| `terraform init -backend=false` + `validate` | **PASS** (deprecation warnings only) |
| `terraform fmt -check -recursive` | **PASS** |
| Read-only ris-dev2 plan | **4 add / 2 change / 4 destroy** |

### Plan detail (the blocker)

The four destroys are **IAM policies**, replaced one-for-one by equivalent new
policies; no queue, Lambda, table, secret or data resource is destroyed:

| Destroy | Replace with |
|---|---|
| `module.agent_transport[0].aws_iam_role_policy.dispatch_result_secret[0]` | `module.agent_transport[0].aws_iam_role_policy.order_result[0]` |
| `module.agent_transport[0].aws_iam_role_policy.dispatch_result_send[0]` | same |
| `module.lambda.aws_iam_role_policy.lambda_order_result_secret[0]` | `module.lambda.aws_iam_role_policy.order_result_transport[0]` |
| `module.lambda.aws_iam_role_policy.lambda_order_result_send[0]` | same |

Adds: `aws_iam_role_policy.orders_agent_dispatch[0]`,
`module.documents.aws_s3_bucket_cors_configuration.documents`.
The shared-infrastructure guard treats any delete under `agent_transport`/
`lambda` as protected and refuses without
`--shared-teardown-intent`; that is why this RC is **BLOCKED** rather than
READY.

## 7. Deployment and rollback runbook (draft, not executed)

**Preconditions**
- Approved migration decision for the four IAM policy replacements.
- `RIS_PARSER_CLI` + `node` execution path available (Python Lambda has none).
- Job bucket Terraform (private, SSE, lifecycle 4 h) and IAM plan reviewed.
- Live transport refs passed explicitly:
  `enable_agent_transport=true`,
  `orders_producer_role_arns`, `ris_result_producer_role_arns`,
  `order_dispatch_queue_url`, `order_result_queue_url`,
  `order_result_queue_arn`, `order_result_secret_arn`.

**Steps**
1. `terraform init` + `plan` in an isolated workdir; confirm exactly the
   4-policy replacement, 2 in-place updates and the listed creates.
2. Review and supply `--shared-teardown-intent <approved-ref>` only for the
   IAM policy migration; the guard must print the authorized decision with the
   plan SHA.
3. Apply the reviewed plan; verify CloudTrail and the four policies exist.
4. Deploy the parser CLI artifact and set `RIS_PARSER_CLI`/`RIS_PARSER_NODE`.
5. Canary: CV-only, job-only, ATS-only, comparison, full request; verify result
   bodies, idempotency, tenant/consent denials and no document content.
6. Post-apply plan: no changes.

**Rollback**
- Restore the previous Lambda bundles and IAM policies from the pre-apply plan;
  the old policies are recreated by reverting the transport refactor.
- Disable the agent entitlement; do not delete the parser or bucket.
- Delete temporary job objects; no CV bytes are stored by the agents.
- Keep orders/work/results/audit; PURGE stays blocked.

## 8. Blockers and recommendations

1. **Transport migration approval (blocker):** four shared IAM policies are
   replaced. Options: (a) approve the replacement with a reviewed intent
   (recommended; equivalent grants, no data loss), or (b) keep the old policy
   addresses and add the new model additively (no destroys, redundant grants).
2. **Node runtime (blocker for live):** Python Lambda has no `node`; approve a
   Node execution path before LIVE VERIFIED.
3. **Job bucket/IAM:** Terraform plan only; no apply.
4. **CV repository wiring:** inject `RequestCvResolver(repository=…,
   document_loader=…)` in the service layer.
5. **Branch hygiene:** RIS integration branch is a merge; jobsearch branch is
   main-based. No main merge in this RC.

## 9. Verdict

**BLOCKED** — not because of application code, contracts, tests or the parser
pipeline (all green), but because the upstream transport refactor requires a
reviewed replacement of four shared IAM policies. After that approval and the
Node runtime decision, the package is ready for **controlled deployment
review**.
