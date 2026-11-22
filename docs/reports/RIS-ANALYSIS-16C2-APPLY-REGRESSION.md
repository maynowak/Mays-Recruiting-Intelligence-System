# RIS-ANALYSIS-16C2 — Approved Apply A & Hardened Regression

**Date:** 2026-11-22
**Base:** `50ead67` on `feature/ris-analysis-integration-07`
**Approval:** Gate A, reference `RIS-ANALYSIS-16C2-A-2026-11-22`
**Approved plan:** `7393445789d92bdb15ebcc9ea3ae85a9e98cb068c27ad84bc6fd982d3ba0f64a`
**Result:** **APPLIED — INFRASTRUCTURE AWS VERIFIED.**
**Analysis live E2E is NOT verified; B and C remain separate gates.**

---

## 1. Installer hardening and apply

### 1.1 Saved-plan mode

`installer.ris._cmd_apply()` always created a new plan. A separate
`--apply-saved-plan` path now:

- applies the existing `--out` plan exactly once;
- **never calls `terraform plan`**;
- requires `--yes`, `--approval-ref`, `--approved-plan-sha256`,
  `--expected-account`, `--expected-region`, `--expected-workspace`,
  `--expected-state-serial`, `--expected-state-lineage` and
  `--expected-plan-shape`;
- verifies the plan SHA, AWS account/region/workspace, remote state
  serial/lineage, exact shape, Lambda `source_code_hash` against the current
  worker/analysis/parser/reader/health/Mays artifacts, `is_plan_safe`,
  `NO_SHARED_DESTROY`, plan TOCTOU hash and the existing state mirror;
- keeps the existing protected-resource gates; no direct unprotected
  Terraform invocation.

Commit: `9ad94ac` (`feat(installer): apply an approved saved plan without
re-planning`). New negative suite: **17 passed**.

### 1.2 First attempt — stopped before mutation

The first saved-plan attempt stopped at the existing `Safety gate`:

```
Protected resource action is forbidden:
module.cognito[0].aws_cognito_resource_server.ris_api[0]
(type: aws_cognito_resource_server, actions: ['no-op'])
```

`is_plan_safe` wrongly treated `no-op` inventory rows as actions. No
`terraform apply` ran; only `terraform init` executed. The gate was fixed to
ignore `no-op`/`read` while still rejecting any real protected action. Commit:
`a51700f` (`fix(installer): ignore no-op rows in protected plan gate`), with
regression tests (92 relevant tests green). The approved plan and bundles were
untouched.

### 1.3 Apply result

| Item | Value |
|---|---|
| Apply exit code | **0** |
| State serial | **67 → 69** |
| Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` (unchanged) |
| Resources | **283 → 287** |
| State last modified | `2026-11-22T11:52:56+00:00` |
| Created | 4 (analysis Lambda, data policy, 2 invoke permissions) |
| Updated | 3 (ingress IAM policy, ingress Lambda, worker Lambda) |
| Removed / replaced | 0 / 0 |
| Plan guard | `NO_SHARED_DESTROY` |

The apply log shows `state mirror: pre-apply snapshot serial=67`, then
`terraform apply … -> exit 0`.

## 2. AWS installation acceptance

### 2.1 Analysis Lambda

| Property | Value |
|---|---|
| Function | `ris-dev2-dev-analysis` |
| Runtime / handler | `python3.14` / `analysis_runner.handler` |
| Architecture | **`x86_64`** (plan did not pin an architecture; Terraform/provider default) |
| Timeout / memory | 60 s / 512 MB |
| State / update | `Active` / `Successful` |
| CodeSha256 / size | `Qgv4YQkg4Dho2vjlk6ccKp3nzGN8oAalGS3SgApKDJ4=` / 295,959 |
| Last modified | `2026-11-22T11:52:26.745+0000` |
| Public function URL | **absent** (`ResourceNotFoundException`) |
| Log retention | 14 days |

Deny-by-default environment:

```
ANALYSIS_SYNTHETIC_MODE=false
ANALYSIS_CONSENT=false
ANALYSIS_NOTICE_APPROVED=false
ANALYSIS_ENTITLEMENTS=""
RIS_PARSER_MODE=lambda
```

The code hash matches the analysis bundle exactly.

### 2.2 Parser Lambda

`ris-dev2-dev-analysis-parser`: `nodejs22.x`, **arm64**, handler
`lambda/ris_parser_handler.handler`, 15 s, 512 MB, `Active`/`Successful`,
CodeSha256 `+3Qfsl580pIypDpjE3puKoyg6UjMLv32dkuHeRGfMBo=` (18,937,176 bytes),
log retention 14 days.

### 2.3 IAM and invoke permissions

Analysis role policies:

- `ris-dev2-dev-analysis-invoke-parser` — `lambda:InvokeFunction` on the parser.
- `ris-dev2-dev-analysis-policy` — existing docs/logs policy.
- `ris-dev2-dev-analysis-runtime-data`:
  - PartnerProfiles `GetItem`, `Query`;
  - WorkItems `GetItem` (`SyntheticWorkItemReadback`);
  - no WorkItems write, no Entitlements read, no Order/Result SQS.

Analysis function resource policy:

- `AllowRisIngressInvokeAnalysis` → `ris-dev2-dev-agent-dispatch-ingress`
- `AllowRisWorkerInvokeAnalysis` → `ris-dev2-dev-agent`

Both match the approved plan.

### 2.4 Worker and dispatch ingress

| Function | Runtime | CodeSha256 | Last modified | Analysis env |
|---|---|---|---|---|
| `ris-dev2-dev-agent` | python3.14 | `hXdfaF7aV/vS9J5jUbQPWTAd4BUMY8tnKJ+1wySJcJY=` | `2026-11-22T11:52:45Z` | `ANALYSIS_FUNCTION_NAME=ris-dev2-dev-analysis`, timeout 45 |
| `ris-dev2-dev-agent-dispatch-ingress` | python3.14 | same worker hash | `2026-11-22T11:52:39Z` | same analysis binding, work queue URL |

Both are `Active` / `LastUpdateStatus=Successful`.

### 2.5 Unchanged services and deny-by-default

- State diff: **0 protected changes** for Cognito, CloudFront, API Gateway,
  SQS, DynamoDB tables and Secrets Manager.
- **0 `mays_orders` non-no-op actions**; the post-apply drift plan has 35 Mays
  resources, all no-op.
- Catalog scan for `analysis.*`: **no offers**.
- Entitlement scan for `agentId=analysis-agent`: **no grants**.
- No synthetic mode, consent, notice or entitlement activation.

### 2.6 Queues and health

| Queue | Messages | Not visible | Delayed |
|---|---:|---:|---:|
| `ris-dev2-dev-agent-dispatch` | 0 | 0 | 0 |
| `ris-dev2-dev-agent-dispatch-dlq` | 0 | 0 | 0 |
| `ris-dev2-dev-work-queue` | 0 | 0 | 0 |
| `ris-dev2-dev-dlq` | 0 | 0 | 0 |
| `ris-dev2-mays-orders-agent-results` | 0 | 0 | 0 |
| `ris-dev2-mays-orders-agent-results-dlq` | 0 | 0 | 0 |

CloudWatch `AWS/Lambda` Errors/Throttles for analysis, parser, worker and
ingress: **no datapoints** in the apply window (no invocations, no errors).
No queue messages were altered.

### 2.7 Drift finding / state freshness

The pre-apply S3 state serial 67 was behind the plan's refreshed `prior_state`
for several **no-op** resources (Mays handler inline policy set, documents
CORS, analysis jobs lifecycle, parser inline policy). The plan already saw the
refreshed values; it had **no `mays_orders` non-no-op action**. Apply persisted
the refresh (serial 68) and the planned 4/3 changes (serial 69). A subsequent
read-only plan shows **0 changes (272 no-op)**. This is a stale-state refresh,
not an apply-driven Mays mutation. No rollback or re-plan was performed.

## 3. Agent factory / installer tests

- All five packages `addition-agent`, `analysis-agent`, `ats-agent`,
  `cv-parser-agent`, `job-parser-agent`: **VALIDATED**.
- `analysis-agent` stages DISCOVER → HANDOFF: all **PASSED** on a local status
  file. `APPLY` explicitly records `executed: false` (local approval only);
  `E2E` records `executed: false`.
- Agent lifecycle/install-orchestrator: **34 passed** (INSTALL, UPDATE, ENABLE,
  DISABLE, DETACH_PARTNER, UNINSTALL, VERIFY, idempotent UNINSTALL,
  open-order/result blockers, shared-resource retention, PURGE blocked).
- Composite lifecycle: **40 passed**, **3 BLOCKED_ENV** because the local
  `installer/projects/mays_orders` checkout/installer script is absent
  (`Installer script not found`); unrelated to the apply.

## 4. Broad regression

| Suite | Result |
|---|---|
| Relevant RIS/agent/installer regression | **739 passed, 41 skipped, 13 subtests** |
| Addition/ATS local regression | **95 passed, 9 subtests** |
| Agent lifecycle/install | **34 passed** |
| Composite lifecycle | 40 passed, 3 blocked (environment) |
| Full `tests/` suite | **BLOCKED_ENV** — collection errors: missing `requests`, missing `moto`/`mock_aws`, unrelated `ConsentContext` NameError |

No relevant test failed. The 41 skips are existing optional/live-fixture gates.

## 5. E2E boundaries after apply

| Stage | Status | Evidence |
|---|---|---|
| Infrastructure smoke | **AWS VERIFIED** | Lambda configs, IAM, permissions, queues, logs, deny env |
| Local/isolated contract E2E | **PASSED** | 739-test regression incl. dispatch → work queue → worker contracts |
| Isolated Analysis Executor canary | **BLOCKED_B** | Synthetic profile is not active; not invoked |
| Authenticated RIS API/Worker canary | **BLOCKED_B** | No synthetic identity/consent activation |
| Full Mays-Orders transport | **BLOCKED_C** | `apiProfileRef` owner/partner binding remains open |
| Automatic agent resume | **BLOCKED** | Not implemented; not claimed |

**`INFRASTRUCTURE AWS VERIFIED` is not `ANALYSIS LIVE E2E VERIFIED`.**

## 6. Cleanup and evidence

- **No synthetic data, orders, entitlements, catalog offers or customer data**
  were created, so no synthetic cleanup was required.
- Infrastructure is intentionally retained and deny-by-default.
- AWS access after apply was read-only (Lambda/IAM/SQS/CloudWatch/DynamoDB
  reads and one read-only drift plan).
- No main merge, production deployment or further apply.

Machine-readable evidence:
`docs/reports/RIS-ANALYSIS-16C2-APPLY-MANIFEST.json`.

## 7. Verdict

**APPROVED PLAN APPLIED SUCCESSFULLY.** The analysis runtime exists, is
healthy, least-privilege and deny-by-default; protected services and Mays
resources were not changed by the plan. The 4/3/0/0 shape, guard, state,
bundles and resource allowlist were verified.

**B (synthetic profile) and C (Mays `apiProfileRef`) remain open and
separate.** No live analysis E2E or automatic resume is claimed.
