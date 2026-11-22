# RIS-ANALYSIS-READINESS-09 — Runtime · CV Wiring · Entitlements · Release Gate

**Date:** 2026-11-20
**Base:** RIS `b344616` (`feature/ris-analysis-integration-07`) · Jobsearch
`aaa260c` (`feature/ris-analysis-parser-cli-04`)
**Verdict:** **READY FOR CONTROLLED APPLY REVIEW** — the additive plan is
unchanged (11/2/0) and locally verified. **Live analysis stays BLOCKED** until
the legal, entitlement and apply approvals below are recorded. No apply, no
merge, no production change.

> Follow-up: `docs/reports/RIS-ANALYSIS-CANARY-10A.md` prepares the controlled
> synthetic apply (baseline 11/2/0, runtime 17/2/0, pinned artifact, 15-case
> canary matrix).

---

## 1. Runtime status

The dedicated Node runtime is complete as code and reachable through two
transports with one parser:

| Mode | Selector | Implementation |
|---|---|---|
| CLI (default) | `RIS_PARSER_MODE=cli` | `agents/parsers/node_adapter.py` → jobsearch `scripts/ris-parser-cli.mjs` |
| Internal Lambda | `RIS_PARSER_MODE=lambda` | `agents/parsers/lambda_adapter.py` → `lambda/ris_parser_handler.mjs` |

- `NodeParser` selects the mode, fails closed on an unknown mode and shares the
  envelope, capability set, 100 000-char payload limit and 15 s timeout.
- The handler re-exports the same `runParser` as the CLI; there is **no second
  parser and no public HTTP endpoint** (no API Gateway, function URL or
  CloudFront route).
- Error mapping: `invalid_input`/`unsupported_capability`/`too_large` →
  `ParserInputError`; `FunctionError`, non-200, invalid JSON, wrong capability,
  client exception, missing `RIS_PARSER_FUNCTION` → `ParserUnavailable`.
- IAM: the parser Lambda has a dedicated logs-only role; the analysis role gets
  `lambda:InvokeFunction` on that function only. No shared transport policy is
  referenced, replaced or deleted.
- Artifact pinning: `lambda/ris_parser_handler.mjs` (jobsearch `c40bf78`) is
  packaged deterministically; `filebase64sha256(parser_artifact_path)` pins the
  zip. Build/sha contract: jobsearch `docs/RIS-PARSER-LAMBDA.md`.
- Terraform: parser role, log group, Lambda (nodejs22.x, arm64, 512 MB, 15 s),
  invoke policy and permission are all gated by `enable_analysis_runtime`
  (default `false`).

## 2. CV wiring status

`RequestCvResolver` is connected to the existing `PartnerProfileRepository` and
a documents loader (`build_cv_resolver(config)`); `AnalysisAgent` builds its
default orchestrator with it.

- Structured CVs are reused as-is (no repository read, no parser call).
- `cvId` resolves owner- and tenant-scoped; the record owner/tenant are
  re-checked against the verified identity (`cv_access_denied`).
- `processing_status != ready`, missing document, empty PDF → `cv_not_ready`;
  non-PDF → `cv_unsupported`; unknown/unreadable → `cv_not_found` /
  `cv_not_accessible`.
- Deleted, erased, purged or withdrawn CVs fail closed with `cv_not_available`;
  withdrawal/erasure therefore takes effect before any parsing.
- PDFs are forwarded to the parser as base64; CV bytes and extracted text never
  appear in WorkItems, result bodies, logs or error messages.

## 3. Entitlement / catalog status

`agent-installations/analysis-agent/entitlements.yaml`:

| Field | Value |
|---|---|
| Partner | `ris-internal` / `ris-internal-analysis` / `analysis-agent` |
| Status | `PENDING_APPROVAL` |
| Activation | `false` |
| Grant policy | `explicit-approval-only`, `autoGrant: false`, no grants |
| Existing consents | not inherited, not extended |
| Catalog | `visibility: ABSENT`, no seed |
| Capabilities | `parse.cv`, `parse.job`, `analyze.job`, `compare.tags` (all bound to analysis-processing 1.0) |

Manifest status moved from `active` to `pending-approval`; `lifecycle.yaml`
records `activation: PENDING_APPROVAL` with the four approvals. The installer
still discovers and validates the package.

## 4. Privacy approvals

`analysis-processing` v1.0 remains **DRAFT** in `jobsearch/consent_contract.py`
with an empty `legal_approval_ref`; existing purposes do not authorize analysis.

`docs/privacy/ANALYSIS-PROCESSING-APPROVAL-PACK.md` prepares the release
decision: roles, data categories, legal-basis checklist (Art. 6/9, **REVIEW
REQUIRED**), retention (temporary jobs 2 h/4 h hard max, 14-day logs, no agent
result storage), withdrawal, erasure, approval record (all **PENDING**),
activation gate and rollback. No consent is granted automatically.

## 5. Terraform plan and shared guard

- `terraform fmt -check -recursive` **PASS**.
- `terraform init -backend=false` + `validate` **PASS** (deprecation warnings
  only).
- Standard installer read-only plan (ris-dev2 overlay + result-secret ARN):
  exit 0, guard message `plan deletes/replaces no shared infrastructure`.
- Change set: **11 add / 2 change / 0 destroy** — identical to the
  INTERNAL-PARTNER-08 baseline.
  - adds: analysis role/policy/jobs bucket/PAB/SSE/lifecycle/log group,
    `orders_agent_dispatch`, `order_result` policies, documents CORS,
  - updates: two Lambda in-place environment updates,
  - **no** parser Lambda resources (gated off), no replacement, no delete.
- Guard on the plan JSON: **`NO_SHARED_DESTROY`, safe**.
- Deviation from 11/2/0: **none.** Enabling `enable_analysis_runtime` is a
  separate plan (+6 resources) that is not part of this review.

## 6. Tests and commits

| Check | Result |
|---|---|
| `test_analysis_pipeline.py` | 31 passed |
| `test_parser_runtime_modes.py` | 16 passed |
| `test_cv_service_wiring.py` | 15 passed |
| `test_analysis_entitlements.py` | 11 passed |
| `test_analysis_runtime_terraform.py` | 11 passed |
| `test_parser_agents.py` | 17 passed |
| Focused RIS regression (12 files) | **218 passed, 13 subtests** |
| Jobsearch parser CLI + handler | 4 passed |
| `terraform fmt -check` / `validate` | PASS |
| Synthetic E2E (real Node CLI) | cv/job/ats/comparison, 100/100/100, `atsTags 4`, idempotent replay |

Commits:

| Repo | Commit | Content |
|---|---|---|
| Jobsearch | `c40bf78` | `runParser` export + internal Lambda handler + docs |
| RIS | `716e8ac` | parser runtime modes, adapter, gated parser Lambda, tests |
| RIS | `454f678` | CV resolver wiring, erasure handling, tests |
| RIS | `175ff74` | entitlements, manifest/lifecycle gates, privacy pack, tests |

All pushed to the feature branches.

## 7. Security, cost and rollback boundaries

**Security**

- No public parser endpoint; invoke is IAM-scoped to the analysis role.
- Owner/tenant isolation is re-checked at the CV record; cross-tenant and
  cross-partner fail closed.
- Parser role has logs only; analysis role has documents `tenant/*` read and
  `jobs/*` RW; no SQS, Secrets Manager or DynamoDB access added.
- No shared IAM/transport policy is modified; 0 destroys.
- No Cognito, CloudFront, DNS or PURGE action.

**Cost (incremental, ris-dev2)**

| Resource | Estimate |
|---|---|
| Analysis IAM role/policy | $0 |
| Jobs bucket (1-day expiry, tiny synthetic objects) | < $0.10/month |
| Log group (14 days) | < $0.10/month |
| Parser Lambda (gated off) | $0 now; ≈ $0.0001 per 15 s / 512 MB invoke when enabled |
| Requests/data transfer | negligible |

**Rollback**

1. No apply ⇒ no rollback needed (state unchanged).
2. After the additive apply: re-plan with the module removed (11 destroys of
   only the new resources; jobs bucket is temporary), or keep the role/bucket
   idle — no shared resource is touched.
3. Parser runtime: set `enable_analysis_runtime=false`, `RIS_PARSER_MODE=cli`.
4. Analysis: withdraw entitlements, keep `visibility: ABSENT`, leave the notice
   DRAFT.

## 8. Controlled apply / canary plan (not executed)

1. **Preflight:** verify STS account `262370457690`, region `eu-central-1`,
   workspace `ris-dev2`, backend key/lock, plan SHA-256 and the guard result.
2. **Apply phase 1 (additive, parser flag false):** apply the reviewed 11/2/0
   plan; post-apply plan must be clean; verify no delete/replace.
3. **Verify:** analysis role/bucket exist, public access blocked, SSE on,
   lifecycle 1 day; shared policies/queues unchanged.
4. **Parser phase (only after approvals + artifact):** build the zip from the
   pinned jobsearch commit, record SHA-256, plan +6 resources, apply, invoke the
   synthetic job/cv payload.
5. **Canary:** synthetic tenant/user, structured CV + job text + `cvId` PDF,
   expect 100/100/100 and `atsTags 4`; confirm no CV bytes in logs.
6. **Stop conditions:** any delete/replace, any shared-policy change, any
   cross-tenant success, any PII in logs, any non-DRAFT consent grant.
7. **Rollback:** disable the runtime flag, revert to CLI mode, withdraw
   entitlements.

## 9. Remaining blockers

1. **Legal/operator approval** of the analysis-processing notice v1.0
   (basis, retention, withdrawal, `legal_approval_ref`).
2. **Entitlement approval** for `ris-internal-analysis` / `analysis-agent`
   (grants remain empty).
3. **Apply approval** for the additive plan; parser enablement is a separate
   approved plan.
4. **Catalog seed decision** (visibility stays `ABSENT`).
5. **Live canary identity/token** for an authenticated E2E after apply.

## 10. Verdict

**READY FOR CONTROLLED APPLY REVIEW.** Runtime, CV wiring, entitlements and
privacy gates are implemented and locally verified; the plan is unchanged
(11/2/0) and the shared guard passes. Live analysis remains **BLOCKED** by
approvals 1–3; nothing was applied, merged or deployed.
