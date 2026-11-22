# RIS-ANALYSIS-CANARY-10A — Controlled Deployment Preparation

**Date:** 2026-11-20
**Base:** RIS `3d6970a` (`feature/ris-analysis-integration-07`) · Jobsearch
`e77ee94` (`feature/ris-analysis-parser-cli-04`)
**Scope:** prepare a reproducible, tightly bounded deployment and synthetic
canary candidate. No architecture change, no parser rewrite.
**Verdict:** **READY FOR CONTROLLED SYNTHETIC APPLY REVIEW**
(no real personal data, no agent activation, no consent/entitlement grant).

---

## 1. Terraform baseline and runtime plans

Both plans are read-only, produced with the standard installer workflow
(`ris-dev2` overlay + result-secret ARN, runtime plan additionally
`enable_analysis_runtime=true` + artifact path). Plans are not committed: a
saved plan is tied to its exact configuration, backend, workspace and state.

**Backend / state (read-only pull):**

| Item | Value |
|---|---|
| Bucket / region | `ris-dev2-tf-state-dev` / `eu-central-1` |
| Key / lock table | `dev/terraform.tfstate` / `ris-dev2-tf-lock` |
| Workspace | `ris-dev2` |
| State serial | **64** |
| Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Terraform | 1.17.0 |

### Baseline plan (runtime flag `false`)

| Metric | Value |
|---|---|
| Adds / changes / destroys | **11 / 2 / 0** |
| Plan SHA-256 | `02c9d1c023d2ae90f43167b4e1f6312eeb8cc4607bf26cadac1c8908c0740d2f` |
| Plan JSON SHA-256 | `b59d8ef50033c6932f46af568ea2f6f26438bb2b4fe53fef2c6795f8c4fd918c` |
| Shared guard | **`NO_SHARED_DESTROY`, safe** |

Adds: analysis role/policy, jobs bucket, Public Access Block, SSE, lifecycle,
analysis log group, `orders_agent_dispatch`, `order_result` policies, documents
CORS. Changes: two existing Lambda in-place environment updates.

### Runtime plan (`enable_analysis_runtime=true`)

| Metric | Value |
|---|---|
| Adds / changes / destroys | **17 / 2 / 0** |
| Plan SHA-256 | `ea0e3298c3cb73bd32c5883e896bbd219ce2f587b79248ff11a56bfa720236f7` |
| Plan JSON SHA-256 | `0b7e45624b2c704112c0a9b1d3e6df8e1f158b3edc55087e627036fd63242832` |
| Shared guard | **`NO_SHARED_DESTROY`, safe** |

### Plan diff (baseline → runtime)

Exactly **+6 creates**, no additional update or destroy:

| Resource | Purpose |
|---|---|
| `aws_iam_role.parser[0]` | parser Lambda execution role (logs only) |
| `aws_iam_role_policy.parser_logs[0]` | log stream/put only |
| `aws_cloudwatch_log_group.parser[0]` | `/aws/lambda/ris-dev2-dev-analysis-parser`, 14 d |
| `aws_lambda_function.parser[0]` | nodejs22.x, arm64, 512 MB, 15 s |
| `aws_iam_role_policy.analysis_invoke_parser[0]` | `lambda:InvokeFunction` for the analysis role |
| `aws_lambda_permission.parser_invoke_analysis[0]` | invoke permission principal = analysis role |

Both plans keep the two existing Lambda in-place updates (`dispatch_ingress`
policy, mays-orders handler env). No replacement and no delete in either plan.

## 2. Parser artifact

| Item | Value |
|---|---|
| Source commit (code) | jobsearch `c40bf78` |
| Artifact | `lambda/dist/analysis-parser.zip` (not committed) |
| Size / files | 17 937 176 bytes / 412 |
| SHA-256 | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` |
| Runtime / arch | `nodejs22.x` / `arm64` |
| Handler | `lambda/ris_parser_handler.handler` |
| Public endpoint | none (no API Gateway, function URL or CloudFront) |

- Built by `tools/build_analysis_parser_artifact.py` with fixed timestamps,
  sorted entries and a required-closure check; a second build is byte-identical.
- Closure: handler, `scripts/ris-parser-cli.mjs`, `api/_lib/**`,
  `node_modules/pdfjs-dist/**`, `@napi-rs/canvas` + `canvas-linux-arm64-gnu`.
  No `web/`, no maps, no tests. `pdfjs-dist` requires the native canvas package
  (otherwise `DOMMatrix is not defined`); only the Lambda platform package ships.
- Verified by `tools/verify_analysis_parser_artifact.py` (SHA, closure, single
  linux-arm64 native, forbidden entries) and a real Node handler run: job
  stableId/tags, CV stableId with `Python, AWS, Terraform, Docker, Linux, SQL`,
  ATS tags, `invalid_input`, `unsupported_capability`.
- Jobsearch `e77ee94` only changes tests/docs; the packaged code is still
  `c40bf78`.

## 3. IAM and security review

| Check | Result |
|---|---|
| Parser role | logs only (`CreateLogStream`, `PutLogEvents`) |
| Analysis role | documents `tenant/*` read, jobs bucket `jobs/*` RW, logs, parser invoke |
| Invoke scope | `lambda:InvokeFunction` on the parser function only |
| Shared IAM | no policy replaced, attached, migrated or deleted (0 destroys) |
| Queues/secrets/tables | untouched; no SQS/Secrets/DynamoDB permission in the module |
| Public surface | no parser HTTP endpoint |
| Tenant/user isolation | CV record owner+tenant re-checked; WorkItem identity only |
| CV data handling | no CV bytes/text in WorkItems, results, logs or errors |
| Temporary jobs | private S3, SSE AES256, 2 h default / 4 h hard max, 1 MiB |
| Consent | `analysis-processing` 1.0 **DRAFT**; no automatic grant |
| Agent/catalog | entitlements PENDING, activation false, visibility ABSENT |
| Cognito/CloudFront/DNS | no change |
| PURGE | not performed |

## 4. Synthetic canary matrix

Fixtures (no real data): `synthetic-canary-cv.pdf` (SHA-256 `70e4076f…`,
`CANARY APPLICANT` only) and `synthetic-job.json` (SHA-256 `26c320d7…`).
Harness: `tests/test_analysis_canary_matrix.py`, real Node CLI.

| Case | Expected |
|---|---|
| CV-only | `cv.tags` with Python/AWS from the PDF |
| Job-only | `job.tags` ≥ 3 |
| ATS-only | `ats.tags` non-empty with explicit profile |
| Comparison | coverage values 0–100 |
| Full | all four result bodies |
| Full with PDF | same shape, PDF resolved once |
| Idempotent replay | `idempotent=true`, identical bodies |
| Missing entitlement | `entitlement_denied` |
| Cross-tenant CV | `cv_access_denied`, no loader call |
| Consent absent / notice DRAFT | `consent_required` / `consent_notice_not_approved` |
| Foreign partner | `partner_mismatch` |
| Oversize job / unknown ref | `job_text_too_large` / `job_not_found` |

Local result: **15/15 passed** (service level, synthetic `Identity`).
Temporary store: fake-S3 tests confirm 2 h/4 h access refusal, extend cap,
cleanup, cross-tenant key isolation, SSE/metadata and the 1 MiB limit.
Intended live claims are documented in
`docs/operations/RIS-ANALYSIS-CANARY-MATRIX.md`; no live token exists.

## 5. Rollback

| Stage | Rollback |
|---|---|
| Before apply | nothing to undo (state unchanged, serial 64) |
| After baseline apply | reviewed reverse plan removes only the 11 added resources; jobs bucket is empty/synthetic |
| After runtime apply | set `enable_analysis_runtime=false` → destroys the 6 parser resources only; analysis base stays |
| Parser failure | `RIS_PARSER_MODE=cli` (same envelope) or disable the Lambda invoke policy |
| Privacy/entitlement issue | keep notice DRAFT, keep grants empty, visibility ABSENT; withdrawal stops analysis |
| Shared resources | never touched by rollback |

State is never hand-edited; every rollback is a new reviewed plan.

## 6. Expected AWS cost (incremental, eu-central-1)

| Resource | Estimate |
|---|---|
| Analysis IAM role/policy | $0 |
| Jobs bucket (synthetic objects, 1-day expiry) | < $0.05 / month |
| Analysis + parser log groups (14 d) | < $0.05 / month (near zero without traffic) |
| Parser Lambda (arm64, 512 MB) | $0 idle; ≈ $0.00002–0.0001 per invoke depending on duration |
| Monthly synthetic canary (≈ 1 000 runs) | ≈ $0.01–0.10 |
| At 30 000 runs / month, ~1 s each | ≈ $0.20 + requests (< $0.01) |
| NAT / provisioned concurrency / new queue / secret | none |

No data transfer or paid AI provider is involved.

## 7. Required approvals — separated

### 7.1 Technical infrastructure approval — **PENDING**

- Accept the two plan SHAs and the artifact SHA.
- Approve the additive baseline and the +6 runtime plan for `ris-dev2` only.
- Confirm the canary window, operator and stop conditions.
- Not required for: no apply has happened.

### 7.2 Privacy / operator approval — **PENDING** (before any real data)

- Legal basis and `legal_approval_ref` for `analysis-processing` 1.0.
- Retention/withdrawal/erasure sign-off.
- Operator consent flag `consent_notice_approved=true`.
- Synthetic canary does **not** require this approval; real data does.

### 7.3 Entitlement / catalog approval — **PENDING** (before activation)

- Grants for `ris-internal-analysis` / `analysis-agent` (currently empty).
- Catalog seed decision (currently `ABSENT`).
- Agent activation (currently `false`).

### 7.4 Real personal data approval — **NOT GRANTED**

- No real CV/job data may enter the canary.
- Requires 7.1–7.3 plus a live canary identity/token.
- Until then all runs use the synthetic fixtures only.

## 8. Test and commit evidence

| Check | Result |
|---|---|
| Focused RIS regression (15 files) | **246 passed + 13 subtests** |
| Canary matrix (real Node CLI) | 15 passed |
| Artifact verifier invariants | 5 passed |
| Deployment preparation | 8 passed |
| Jobsearch parser CLI + handler | 4 passed |
| `terraform fmt -check` / `validate` | PASS |
| Baseline / runtime guard | `NO_SHARED_DESTROY` |

| Repo | Commit | Content |
|---|---|---|
| RIS | `4206a3d` | STEP A plans, artifact builder, synthetic PDF generator, prep tests |
| RIS | `de99c5c` | STEP B artifact verifier, operations doc, tests |
| RIS | `3d6970a` | STEP C canary fixtures, matrix, TTL negatives, docs |
| Jobsearch | `e77ee94` | handler CV test, deterministic build/SHA docs |

## 9. Verdict

**READY FOR CONTROLLED SYNTHETIC APPLY REVIEW.**

The baseline plan (11/2/0) and the runtime plan (17/2/0) are reproducible and
guarded, the artifact is pinned and verified, and the synthetic matrix passes
without real data. Real-data processing and agent activation remain **BLOCKED**
by approvals 7.1–7.4; nothing was applied, merged or deployed, and CANARY-10B
has not started.
