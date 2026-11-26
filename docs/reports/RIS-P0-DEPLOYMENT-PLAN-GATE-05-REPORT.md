# RIS-P0-DEPLOYMENT-PLAN-GATE-05 — MULTI-AGENT SECURITY & TERRAFORM PLAN ORCHESTRATION

**Status: BLOCKED — P0 SECURITY / PRIVACY / DEPLOYMENT GATE**

- Repository: `maynowak/Mays-Recruiting-Intelligence-System`
- Integration branch: `integration/ris-p0-deployment-plan-gate-05`
- Integration HEAD: `6aaa6c0`
- Base: `76c5785` (Deployment Decision 04)
- AWS mode: read-only only
- No Terraform plan/apply, no AWS mutation, no state write, no deployment,
  no main merge and no real erasure.

## 1. Ergebnisübersicht

| Bereich | Ergebnis |
| --- | --- |
| Agent A — Integration | NOTHING MISSING; two security fixes added (`a745d3d`, `6aaa6c0`) |
| Agent B — Consent / Privacy | cv-storage Art. 9 technically green; application-storage asymmetry + consent retention remain privacy decisions |
| Agent C — Terraform / State | Live state confirmed; material plan blockers found (Orders module/pin, plan inputs, IAM drift, live code behind branch) |
| Agent D — API / Erasure / IAM | Authorization/isolation sound; document-purge fail-open fixed locally; application-erasure scope remains open |
| Agent E — Rollback | Recovery concept complete; `$LATEST`-only, no version/alias; live artifact captured and hashed |
| Integration | `6aaa6c0` pushed; no main merge |
| Tests | 3393 PASS / 129 skipped / 18 baseline environment failures; no new failures |
| Blocker | No reviewable Terraform plan; privacy decisions and rollback/Orders prerequisites open |
| Empfehlung | Do not plan/apply yet; reconcile Orders module/pin and privacy decisions first |

## 2. Agent A — Integration

All required P0 changes were already ancestors of `76c5785`:

- erasure partner route (`db5ba54`);
- search-profile erasure (`1c8a4ed`, equivalent to `30668ff`);
- CVDocument metadata erasure (`f848c17`, equivalent to `2c7c200`);
- partner context (`9bfa554`, equivalent to `8a14b0b`);
- consent enforcement (`68f9074`, `2dd89be`);
- Art. 9 cv-storage validation (`e370567`);
- protected installer `--var-file` (`e370567`).

No reimplementation or main merge. Two additional security defects found by
Agents C/D were fixed on the integration branch:

| Commit | Change |
| --- | --- |
| `a745d3d` | document-purge wrapper now returns `(0, True)` on failure; CVDocument metadata is not deleted after a failed S3 purge |
| `6aaa6c0` | restore `dynamodb:ConditionCheckItem` on the partner-profile IAM policy to match live/state |

Final integration branch: `integration/ris-p0-deployment-plan-gate-05` at
**`6aaa6c0`**, pushed.

## 3. Agent B — Consent / Privacy

### Technically green

- `cv-storage` Art. 9 contract requires explicit special-category consent,
  a valid non-empty category subset, the approved
  `cv-storage-consent-2026-11-08-v1` text and pinned SHA-256.
- Missing/invalid proof fails closed (`422`); existing rows are not migrated or
  inferred; reads and withdrawal remain available.
- Re-grant with different proof returns `409 RECONSENT_REQUIRED` rather than
  silently reusing the old proof.
- Browser sends only the boolean; version/hash/categories are server-owned.
- No silent access widening found in configuration.

### Privacy decisions still open

| ID | Decision |
| --- | --- |
| D1 | Legal basis for Art. 9 data in durable CV/application documents |
| D2 | RIS vs Jobsearch controller/processor allocation |
| D3 | `application-storage`: partner-attested proof vs RIS-enforced proof |
| D4 | Disposition of historical application grants/events without proof |
| D5 | Consent retention after account erasure; PITR/backups disabled |
| D6 | Confirm global application gate and preserve current enforcement |

Important correction from Agent C: the consent table contains **9 current
`PURPOSE#` rows and 41 historical `EVENT#` rows**, not 50 active consents.
Current rows: application 1 GRANTED, cv 4 GRANTED, search 4 GRANTED. All 9
current rows carry the approved external text/hash; application and cv current
rows carry explicit Art. 9 proof. The previously reported “2 active
application grants without proof” were **historical events**, not active rows.
The remaining asymmetry is that RIS does not enforce Art. 9 proof for new
`application-storage` grants; only the Jobsearch BFF does.

Consent retention remains open:

- no erasure step deletes consent rows/events;
- IAM grants no `DeleteItem` on the consents table;
- the consents table has **PITR disabled and no backups**;
- consent events retain subject/identity references and category lists;
- privacy inventory/retention docs do not yet contain a consent-table row.

## 4. Agent C — Terraform & AWS State

Confirmed live on 2026-11-26 (read-only, `mayaws`, account `240571105849`,
region `eu-central-1`):

| Item | Value |
| --- | --- |
| State | `mays-ris-tf-state-dev`, key `env:/ris-dev/dev/terraform.tfstate` |
| Workspace | `ris-dev` |
| Serial / lineage | **83** / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Resources | 271 blocks / 312 instances |
| State last modified | `2026-11-18T14:07:45Z` |
| Lambda | `ris-dev-dev-agent`, `$LATEST`, Active, last modified `2026-11-17T18:16:03Z` |
| Live code SHA | `UCdPXzMRdBFnnPQyIj6C53YMfqg5qAm8PW8Gy3sk/Cs=` |
| State code hash | identical |
| Published versions / aliases | none |
| Consent flags | APPLICATION, CV, SEARCH, NOTICE all `true` |
| Allowlist | present, non-empty, 2 entries (values withheld) |
| Partner surface | `true` |
| Erasure flags | `ERASURE_APPLICATIONS_ENABLED=false`, `ERASURE_S3_EXECUTION_ENABLED=false` |
| APIs | partner `c7e9pdwe78`, kernel `g6901and25`; erasure/consent routes JWT |

### Material plan risks / blockers

1. **Generated Orders module incomplete and pin mismatch.** Local
   `terraform/modules/mays_orders/` contains only `variables.tf`; root
   validate/plan is impossible. The local builder pin is `016cdfd…`, while the
   reviewed live baseline is `1dbb0cb`. A rebuild risks the known DELETE of the
   legacy wildcard SQS queue policy.
2. **Consent inputs are not in the committed overlay.** A defaults/overlay-only
   run would set APPLICATION/CV/SEARCH/NOTICE to `false` and clear the
   allowlist. A plan must supply all four booleans plus the protected
   `--var-file` for the two allowlist entries.
3. **CORS.** Live/state values include the Jobsearch origins; Terraform defaults
   are empty. The `ris-dev.json` overlay contains the correct values and must be
   loaded; otherwise a plan would strip CORS.
4. **Live code is behind this branch.** Live has no
   `erase-partner-search-profiles`, no CVDocument metadata deletion, no
   `SPECIAL_CATEGORY_REQUIRED_PURPOSES` Art. 9 enforcement, and no
   report-based document deletion. A plan is **restorative/behavioral**, not a
   no-op; it must be explicitly approved and E2E-tested.
5. **IAM residual.** Partner-profile `ConditionCheckItem` is now restored in
   the branch and should be a plan no-op. The local work-table policy still adds
   `ConditionCheckItem` versus live; this is additive and needs plan review.
   Orders result-transport policies are conditional on overlay ARNs and must be
   verified not to delete live transport.
6. **PITR/backups.** Consent table PITR is disabled with zero backups. This is a
   rollout/privacy blocker, not a plan blocker.
7. **No plan executed.** 0 delete / 0 replace and full drift are unproven.

Terraform: `fmt -check` PASS; modules `lambda`, `api`, `partner_edge` validate
PASS; root validate fails only on pre-existing
`module.mays_orders[0].iam_handler_role_name`.

## 5. Agent D — API, Erasure & IAM

Verified:

- partner erasure route and kernel erasure route are JWT-protected;
- one deletion engine, verified identity only, tenant/partner isolation;
- consent withdrawal returns `409 NOT_GRANTED` when no active consent;
- search-profile/Ats erasure is identity-scoped, paginated and versioned;
- no IAM expansion by the erasure route itself;
- Jobsearch BFF path and auth boundary are consistent.

Fixed in integration:

- **F1 (High/Medium):** document purge wrapper returned bare `0` when the
  deletion helper raised; the erasure engine treated that as a successful empty
  purge and deleted CVDocument metadata. Fixed at `a745d3d`; live code still
  contains the old behavior until deployed.
- **F4 (Medium):** partner-profile `ConditionCheckItem` was missing locally but
  present live; restored at `6aaa6c0`.

Open findings:

- **F2 (Medium):** `ApplicationErasureExecutor` uses the partner-scoped
  `gsi-owner`; applications from another partner/issuer for the same user can
  remain. Kernel users without partner context fail the application step
  (`APPLICATION_AUTHORIZATION_CONTEXT_UNAVAILABLE`) and receive 207.
- **F3 (Medium):** the legacy `ERASURE_APPLICATIONS_ENABLED=true` path uses
  `gsi-user`, but IAM currently grants only `gsi-owner` for applications. Do
  not enable that flag without an explicit `gsi-user` grant and plan review.
- **F5 (Low/Medium):** raw exception strings can reach 207 responses/logs.
- **F6 (Low):** Jobsearch consent BFF requires the test allowlist even for
  withdrawal; identities with legacy rows may need an exception path.
- **F7/F8 (Low):** OpenAPI/API-STANDARD erasure steps and audit route label are
  incomplete.

Explicit statements:

- consent rows/events are **not** physically deleted by current erasure;
- `ERASURE_S3_EXECUTION_ENABLED=false`; object versions/backups can survive;
- no complete physical-purge claim is made;
- `ERASURE_APPLICATIONS_ENABLED=false` is the legacy flag only; the dedicated
  ApplicationErasureExecutor is wired and active;
- no real deletion was performed.

## 6. Agent E — Lambda Rollback & Recovery

- Deployment path is `package → plan → saved-plan apply` with strong
  plan-SHA/state-serial/lineage/shape gates.
- Lambda `ris-dev-dev-agent` is `$LATEST` with **no published version or
  alias**; both APIs share the same unqualified integration. Per-surface
  rollback is impossible.
- A deterministic commit → bundle → `CodeSha256` mapping exists. The current
  live artifact was captured read-only:
  - `/tmp/opencode/ris-dev-dev-agent-pre-gate05.zip`
  - size 305,767 bytes
  - `CodeSha256 = UCdPXzMRdBFnnPQyIj6C53YMfqg5qAm8PW8Gy3sk/Cs=`
- The expected new branch bundle is
  `HgRXwZoAtxIbvxme0soNRO8RIVUWQJwBdzDbuNP99go=` (115 files). A plan should
  update the agent code; it must not remove routes/env/IAM.
- Agent E’s earlier historical mapping (`cQFma…` / `0a6eb76`) is superseded by
  the current read-only capture (`UCdP…`). The current live artifact includes
  the partner erasure route and CV gate marker, but not the Art. 9/lifecycle
  fixes.
- Rollback must use the captured artifact or a regenerated bundle from the
  recorded commit, with a new plan and approval; never restore by state
  version, `-target`, `-replace`, or route deletion.

## 7. Tests / verification

| Check | Result |
| --- | --- |
| New privacy regression (`test_public_application_erasure`, search-profile) | 23 PASS |
| Partner-profile IAM harness | 37 PASS |
| Full suite | **3393 PASS / 129 skipped / 18 baseline failures** |
| Baseline | same 18 documented environment failures; no new failure |
| `terraform fmt -check -recursive` | PASS |
| Module `lambda`, `api`, `partner_edge` validate | PASS |
| Root validate | pre-existing `mays_orders` failure |
| `git diff --check` | PASS |
| Secret scan | PASS; no real allowlist value or secret |

## 8. Gate assessment

| Gate | Status |
| --- | --- |
| A — Repository | PASS; all P0 changes consolidated at `6aaa6c0` |
| B — Security | **BLOCKED**: application-erasure scope/IAM gap; live code still has F1; plan IAM/work-table review pending |
| C — Privacy | **BLOCKED**: Art. 9 legal basis, application-storage proof asymmetry, consent retention/PITR |
| D — Terraform | **BLOCKED**: no reviewable plan; Orders module/pin, consent inputs, CORS/overlay and drift unresolved |
| E — Recovery | **CONDITIONAL**: artifact captured, but no immutable Lambda version/alias; plan/rollback approval needed |
| F — Deployment | NOT IN SCOPE; no apply/deploy |

## 9. Offene Blocker

1. Reconcile the generated `mays_orders` module and pin (`016cdfd…` vs reviewed
   `1dbb0cb`) without the legacy wildcard SQS-policy DELETE; root plan is
   otherwise impossible.
2. Obtain written G4/G5 authorization for a fresh `ris-dev` plan with the four
   consent booleans, protected allowlist var-file and correct CORS/Orders
   overlay. Plan must show 0 delete/0 replace, no enforcement/CORS/allowlist
   weakening, no Cognito/CloudFront changes.
3. Approve or fix the work-table `ConditionCheckItem` IAM addition and verify
   the Orders transport policies are preserved.
4. Privacy/Legal: D1–D6, especially application-storage Art. 9 enforcement,
   consent retention/PITR and the global application gate.
5. Decide F2 application-erasure scope and F3 `gsi-user` IAM before enabling
   the legacy application flag or claiming tenant-wide erasure.
6. Capture/verify the rollback artifact and decide whether a published Lambda
   version is required; no alias is recommended for this pilot.
7. After plan approval: separate apply approval, synthetic E2E, rollback
   decision point.

## 10. Empfohlener nächster Schritt

**Do not plan or apply yet.** First reconcile the Orders module/pin and the
plan inputs, then produce an authorized plan for review. The technical
integration is ready at `6aaa6c0`, but the deployment package is not yet
reviewable as a safe Terraform plan.

**BLOCKED — P0 SECURITY / PRIVACY / DEPLOYMENT GATE**

No apply, no deployment, no main merge.
