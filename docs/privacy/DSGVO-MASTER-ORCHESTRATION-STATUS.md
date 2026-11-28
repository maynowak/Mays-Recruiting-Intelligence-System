# DSGVO Master Orchestration Status

**Version:** 2.3
**Updated:** 2026-11-28
**Branch baseline:** `feature/ris-dsgvo-compliance-01` @ `e25e900667a18f9123a89a2ea7fdc0ca96e7b553`
**Orders pin constraint:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` — immutable for this orchestration.
**Current review base:** RIS `d8a7fffb112fc39ad839aef4a87e5722b521db1f`; Orders pin `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; provider Main reviewed `716a16590673cdb649df414c08fc0bf7814caac7`.
**Overall:** `RIS ECOSYSTEM PRIVACY CONTRACT & UNIFIED QA READY FOR IMPLEMENTATION REVIEW` — design only; DSGVO-02C remains `PARTIAL`; STOP before implementation.

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
           |
           v
RIS Ecosystem privacy contract & Unified QA design (CURRENT; REVIEW GATE)
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

Interpretation (v2.3): A–E are ecosystem-centered workstreams; F depends on stable contracts/selectors from them. Provider privacy stays provider-owned, RIS reuses existing privacy orchestration/resolvers, and the existing Unified Test runner is extended rather than duplicated. DSGVO-07 reviews exact-SHA implementation evidence, not live acceptance/deployment. Separate legal and operational approvals remain outside this technical design.

## Ownership and work-package ledger

| Package | Repository / accountable owner | Scope | Depends on | Current state |
|---|---|---|---|---|
| DSGVO-01 | RIS / Privacy coordinator | Discovery, evidence index and plan | — | COMPLETE, documentation |
| DSGVO-02 | RIS docs / Privacy coordinator; decisions by named service and legal owners | Decision register, proposed subject identity contract, follow-up tickets, contract/migration/test plans | DSGVO-01 | DOCUMENTATION COMPLETE; technical recommendation ready; owner/legal decisions OPEN |
| DSGVO-02A | RIS coordinator; parallel read-only reviews A–D | Identity architecture, Orders paths, RIS capabilities, QA inventory | DSGVO-02 | COMPLETE AS REVIEW; recommendation unapproved |
| DSGVO-02B | RIS coordinator; Mays-Orders provider reviewed read-only | Pin/Main capability and evidence matrix, adapter gaps, provider CR drafts | 02A | READY FOR REVIEW; no implementation |
| DSGVO-02C | RIS coordinator | Actual AgentOrder/result producers, storage/lifecycle, existing privacy flow and provider-CR need | 02B | PARTIAL; content boundary and terminal/provider data coverage remain unresolved |
| DSGVO-03 | RIS Ecosystem + Orders contract owners | Capability privacy schema/eligibility; verify Orders JWT principal; provider CR disposition | DSGVO-02C + owner identity decision | DESIGN READY FOR IMPLEMENTATION REVIEW; no provider feature presumed |
| DSGVO-04 | RIS domain/runtime/privacy owners | Capability input/result policy, existing resolver/erasure/fence integration, lifecycle outcomes | DSGVO-03 contract | DESIGN READY; no runtime changes |
| DSGVO-05 | Agent owners / Factory | Manifest + original-test/build evidence binding and invalidation | DSGVO-03 schema | DESIGN READY; no package/build change |
| DSGVO-06 | RIS QA | Add `RIS_PRIVACY` to existing isolated Unified Test runner, ten groups, exact SHA/artifact provenance | DSGVO-03…05 test selectors | DESIGN READY; no runner/CI change |
| DSGVO-07 | RIS/provider/security/privacy reviewers | Review exact-SHA implementation evidence; separately gate live/legal acceptance | 03…06 implemented and approved | NOT STARTED / NOT AUTHORIZED |

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
| 2.3 | Ecosystem capability privacy contract, agent evidence/build binding, payload/result boundary, lifecycle and `RIS_PRIVACY` profile prepared for implementation review; no implementation authorization | [`RIS-DSGVO-ECOSYSTEM-ORCHESTRATION-01.md`](RIS-DSGVO-ECOSYSTEM-ORCHESTRATION-01.md) |

## Stop gate

Current stop point is **RIS Ecosystem Privacy Contract & Unified QA Implementation Review**. DSGVO-02C remains `PARTIAL`: generic input/results and terminal WorkItems do not yet prove the required boundary. A–F design, file map, dependencies and RED/GREEN criteria are documented; missing/stale evidence is proposed as an Eligibility blocker. Reuse existing resolvers, privacy routes, lifecycle fences and provider capabilities. No pin upgrade, provider/RIS runtime/build/test-runner/CI change, AWS/Terraform action, deployment, or real-data processing is in scope. This status authorizes review only, not implementation, legal approval or live deployment.
