# DSGVO Master Orchestration Status

**Version:** 2.2
**Updated:** 2026-11-28
**Branch baseline:** `feature/ris-dsgvo-compliance-01` @ `e25e900667a18f9123a89a2ea7fdc0ca96e7b553`
**Orders pin constraint:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` — immutable for this orchestration.
**Current review base:** RIS `d8a7fffb112fc39ad839aef4a87e5722b521db1f`; Orders pin `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; provider Main reviewed `716a16590673cdb649df414c08fc0bf7814caac7`.
**Overall:** `PARTIAL — ORDER PRIVACY BOUNDARY NOT VERIFIED` — AgentOrder/result paths can persist and transport domain payloads; STOP before implementation.

## Package graph

```text
DSGVO-01 Discovery (COMPLETE)
          |
          v
DSGVO-02 / 02A decisions and technical review (COMPLETE AS PROPOSAL)
           |
           v
DSGVO-02B Provider integration alignment (historical review)
           |
           v
DSGVO-02C Order data boundary (CURRENT; PARTIAL)
   |             |                 |                  |
   v             v                 v                  v
DSGVO-03       DSGVO-04          DSGVO-05           DSGVO-06
Provider       RIS privacy       XRepo integration   Unified privacy
contract       adapter           tests               QA
compliance     (depends on 03)   (depends on 03/04)  (depends on 03-05;
   \             |                 /                implementation awaits 03-05)
    \____________|________________/________________/
                         |
                         v
                  DSGVO-07 synthetic XRepo acceptance
                  (only after 03–06 implementation and approvals)
```

Interpretation: DSGVO-03 verifies and obtains provider contract dispositions; it does not reimplement Mays-Orders capabilities in RIS. DSGVO-04 is only the RIS consumer adapter. DSGVO-05/06 reuse provider originals and existing RIS QA; no redundant provider suite/report. DSGVO-07 is review of evidence at exact SHAs, not a live acceptance/deployment. Separate legal and operational approvals remain outside these technical packages.

## Ownership and work-package ledger

| Package | Repository / accountable owner | Scope | Depends on | Current state |
|---|---|---|---|---|
| DSGVO-01 | RIS / Privacy coordinator | Discovery, evidence index and plan | — | COMPLETE, documentation |
| DSGVO-02 | RIS docs / Privacy coordinator; decisions by named service and legal owners | Decision register, proposed subject identity contract, follow-up tickets, contract/migration/test plans | DSGVO-01 | DOCUMENTATION COMPLETE; technical recommendation ready; owner/legal decisions OPEN |
| DSGVO-02A | RIS coordinator; parallel read-only reviews A–D | Identity architecture, Orders paths, RIS capabilities, QA inventory | DSGVO-02 | COMPLETE AS REVIEW; recommendation unapproved |
| DSGVO-02B | RIS coordinator; Mays-Orders provider reviewed read-only | Pin/Main capability and evidence matrix, adapter gaps, provider CR drafts | 02A | READY FOR REVIEW; no implementation |
| DSGVO-02C | RIS coordinator | Actual AgentOrder/result producers, storage/lifecycle, existing privacy flow and provider-CR need | 02B | PARTIAL; content boundary and terminal/provider data coverage remain unresolved |
| DSGVO-03 | Mays-Orders provider owner + RIS contract owner | Provider contract compliance, trusted subject binding and CR disposition | 02 decisions + provider owner response | PREPARED ONLY; no RIS reimplementation |
| DSGVO-04 | RIS privacy/runtime owner | RIS Privacy Adapter, auth/secret, status and timeout mapping | 03 supported contract + separate authorization | PREPARED ONLY |
| DSGVO-05 | RIS QA + Mays-Orders test owners | Synthetic XRepo integration tests reusing provider originals | 03/04 exact contract and SHAs | PREPARED ONLY |
| DSGVO-06 | RIS CI + provider CI owners | Unified isolated synthetic QA and provenance | Stable 03–05 suites; CI owner approval | DESIGN ONLY |
| DSGVO-07 | RIS coordinator + provider/security/privacy reviewers | Evidence review and unresolved-status review | 03–06 separately authorized/completed | NOT STARTED / NOT AUTHORIZED |

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
| 2.0 | A–D consolidated; persistent opaque mapping recommended over default HMAC; DSGVO-03…07 work orders updated; decision stop gate active | [`DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md`](DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md), consolidated recommendation |
| 2.1 | Provider pin/Main aligned; provider functions/evidence distinguished from RIS adapter gaps; 03–07 recentered on contract compliance and reuse; stop before implementation | [`DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md`](DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md) |
| 2.2 | AgentOrder/result source paths inspected; input/result payloads can be stored and transported; existing RIS privacy flows reused; provider CR scope corrected; boundary remains PARTIAL | [`DSGVO-02C-ORDER-DATA-BOUNDARY-AND-LIFECYCLE.md`](DSGVO-02C-ORDER-DATA-BOUNDARY-AND-LIFECYCLE.md) |

## Stop gate

Current stop point is **DSGVO-02C Order Data Boundary Review**. The source review found that `input.data` and result bodies can contain domain/personal data and cross the Orders boundary; exclusive RIS storage is not verified. Reuse existing RIS inspect/export/erasure routes; never create AgentOrders for privacy requests. Narrow provider CRs to demonstrated identity/result/anonymization needs after contract-owner decisions. No pin upgrade, provider edit, RIS runtime work, AWS/Terraform action, deployment, or real-data processing is in scope. This is `PARTIAL`, not implementation authorization or live deployment proof.
