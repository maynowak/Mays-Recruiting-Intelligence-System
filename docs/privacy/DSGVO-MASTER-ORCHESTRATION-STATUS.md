# DSGVO Master Orchestration Status

**Version:** 1.5
**Updated:** 2026-11-28
**Branch baseline:** `feature/ris-dsgvo-compliance-01` @ `e25e900667a18f9123a89a2ea7fdc0ca96e7b553`
**Orders pin constraint:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` — immutable for this orchestration.
**Overall:** `DSGVO MASTER ORCHESTRATION READY` — DSGVO-02 package complete; STOP at Contract and Decision Gate. No technical remediation authorized.

## Package graph

```text
DSGVO-01 Discovery (COMPLETE)
          |
          v
DSGVO-02 Decision package + XRepo subject identity contract (CURRENT)
   |             |                 |                  |
   v             v                 v                  v
DSGVO-03       DSGVO-04          DSGVO-05           DSGVO-06
Orders         RIS privacy       retention/backup/   unified CI/CD
linkage +      orchestration     queue/security      gate design
DSAR           (depends on 03)   (policy from 02)   (design can parallel;
   \             |                 /                implementation awaits 03-05)
    \____________|________________/________________/
                         |
                         v
                  DSGVO-07 synthetic XRepo acceptance
                  (only after 03–06 implementation and approvals)
```

Interpretation: DSGVO-03, the policy/design portion of DSGVO-05, and the CI-gate design in DSGVO-06 can be prepared independently after DSGVO-02 decisions/contract are reviewed. Their technical execution is not authorized by this plan. DSGVO-04 depends on the subject-linkage and DSAR interface from DSGVO-03. DSGVO-07 depends on integrated implementations from 03–06 plus a test-ready approved contract. Legal/operational approvals are cross-cutting prerequisites, not tasks that CI can satisfy.

## Ownership and work-package ledger

| Package | Repository / accountable owner | Scope | Depends on | Current state |
|---|---|---|---|---|
| DSGVO-01 | RIS / Privacy coordinator | Discovery, evidence index and plan | — | COMPLETE, documentation |
| DSGVO-02 | RIS docs / Privacy coordinator; decisions by named service and legal owners | Decision register, proposed subject identity contract, follow-up tickets, contract/migration/test plans | DSGVO-01 | DOCUMENTATION COMPLETE; owner/legal decisions OPEN; stop at approval gate |
| DSGVO-03 | Mays-Orders / Orders owner; RIS adapter owner | Subject linkage on every write path, legacy strategy, inspect/export/erase coverage, anonymization, original tests | 02 approved contract + data/legal decisions | PREPARED ONLY |
| DSGVO-04 | RIS / Privacy runtime + data owners | Cross-domain operation orchestration, freeze, per-domain progress, partial/resume and receipts | 03 interface/linkage + 02 policy | PREPARED ONLY |
| DSGVO-05 | RIS platform/operations + Orders/Jobsearch owners + Security | Retention, S3 versions, PITR/restore, WorkItems/results/SQS/DLQ, logs and secret lifecycle | 02 policy decisions; affected implementation dependencies noted in plan | PREPARED ONLY |
| DSGVO-06 | RIS CI owner + Orders and Jobsearch CI owners | Unified, isolated, synthetic-only blocking gate and provenance report | 02 contract/test vectors; execution tests from 03–05 | DESIGN PREPARABLE; no gate implemented |
| DSGVO-07 | Cross-repository release coordinator + all owners | Synthetic integrated acceptance, reconciled evidence and unresolved-status report | 03–06 complete; human/security approvals | NOT STARTED / NOT AUTHORIZED |

## Shared quality constraints

- Preserve existing RIS/Orders/Jobsearch public and internal integration contracts unless separately versioned and approved.
- Reuse native implementations and original test suites; new tests supplement rather than replace them.
- Any historical-data migration requires separately approved, dry-run/read-only discovery first, then an explicit migration/backfill plan, idempotency, rollback and audit evidence. No migration executes in this orchestration.
- Do not hand-edit generated Terraform modules. Do not change the Orders source pin or silently upgrade any clone.
- Keep privacy status per work package: a blocker in Orders subject linkage blocks DSAR completeness claims and DSGVO-04/07, but does not prevent independent policy/CI design documentation.
- Tests prove technical properties only. No legal basis, consent validity, DPIA conclusion, retention approval, deployment or live-data approval is inferred from green tests.

## Checkpoint history

| Version | State | Evidence |
|---|---|---|
| 1.0 | Orchestration graph/ownership ledger established; DSGVO-02 active | This file; commit recorded in Git history |
| 1.1 | DSGVO-02 decision package and draft XRepo identity contract complete; 03–07 work orders prepared; stop gate active | [`DSGVO-02-DECISIONS-AND-CONTRACT.md`](DSGVO-02-DECISIONS-AND-CONTRACT.md); commit recorded in Git history |
| 1.2 | Identity architecture investigation complete; persistent opaque mapping recommended for decision; no contract approved | [`DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md`](DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md), section A |
| 1.3 | Orders write paths, GSI2 coverage, anonymization gap and native test changes reviewed; no implementation | [`DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md`](DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md), section B |
| 1.4 | RIS erasure components, missing XRepo adapters, coverage and minimal extension plan reviewed | [`DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md`](DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md), section C |
| 1.5 | Native suites/CI, synthetic catalog, isolated runners and SHA provenance reviewed | [`DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md`](DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md), section D |

## Stop gate

Current stop point is **DSGVO-02 Contract and Decision Gate**. No implementation work may begin until the contract is reviewed and the decisions listed in `DSGVO-02-DECISIONS-AND-CONTRACT.md` have named owners and explicit outcomes. Real personal data remains prohibited; no AWS/Terraform mutation, deployment, redrive, or Main merge is in scope.
