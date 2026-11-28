# DSGVO Master Orchestration Status

**Version:** 2.4
**Updated:** 2026-11-28
**Implementation baseline:** `feature/ris-dsgvo-compliance-01` @ `db2e09419931fc64e9377aed8fdd35c720023045`
**Orders pin constraint:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` — immutable for this orchestration.
**Current review base:** RIS `d8a7fffb112fc39ad839aef4a87e5722b521db1f`; Orders pin `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; provider Main reviewed `716a16590673cdb649df414c08fc0bf7814caac7`.
**Overall:** `PARTIAL — A CONTRACT/GATE IMPLEMENTED; B–F PENDING/BLOCKED`; DSGVO-02C remains `PARTIAL`.

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
| A / DSGVO-03 | RIS Ecosystem | Typed capability contract, descriptor, Eligibility and direct-execution gate | 02C | IMPLEMENTED; synthetic tests green; shipped capabilities blocked pending evidence |
| B / DSGVO-05 | Agent owners / Factory | Manifest + original-test/build evidence binding and invalidation | A | COMPLETE FOR ADDITION SYNTHETIC REFERENCE at `ee6055a`; exact post-C evidence recorded; other manifests blocked pending owner-reviewed contracts |
| C / DSGVO-04 | RIS domain/runtime/privacy owners | Capability input/result policy and resolver integration | A + owner-approved policy | PARTIAL; typed input/result/ORDER_RESULT runtime gates tested for Addition; generic retention and unclassified capabilities remain open |
| D | RIS runtime/privacy owners | Existing fence, erasure and lifecycle integration | C policy stable | NOT STARTED |
| E | RIS/Orders contract owners | Synthetic JWT identity proof, provider originals and CR disposition | A/C + identity decision | PARTIAL; RIS-side synthetic JWT priority/claims tested; provider verification/originals BLOCKED because pinned checkout absent; provider/pin unchanged |
| F / DSGVO-06 | RIS QA | `RIS_PRIVACY`, ten groups, exact SHA/artifact provenance | A–E selectors/evidence | PARTIAL; local groups PASS, unavailable Provider groups explicitly BLOCKED, profile BLOCKED overall |
| DSGVO-07 | RIS/provider/security/privacy reviewers | Review exact-SHA implementation evidence; separately gate live/legal acceptance | A–F complete | NOT STARTED / NOT AUTHORIZED |

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
| 2.4 | A implemented with fail-closed Eligibility/direct execution; existing capability regression fixtures expose missing declarations/evidence; B–F remain pending and DSGVO-02C remains PARTIAL | [`RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01-EXECUTION.md`](RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01-EXECUTION.md) |
| 2.5 | B installer/build evidence pipeline complete for Addition synthetic math capability; exact source/contract/test-report/artifact provenance recorded; all other agent capabilities remain fail-closed | [`RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01-EXECUTION.md`](RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01-EXECUTION.md) |
| 2.6 | C typed runtime boundaries added; Addition evidence refreshed; RIS_PRIVACY local groups pass and unavailable Provider groups explicitly block; synthetic Orders JWT tests do not claim Provider verification | [`RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01-EXECUTION.md`](RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01-EXECUTION.md) |

## Stop gate

Implementation is active under explicit authorization. A is implemented; B is complete for Addition with fresh post-C evidence. C has typed runtime input/result and ORDER_RESULT gates, but generic Order/WorkItem retention and unclassified capabilities remain open. RIS_PRIVACY is implemented with local PASS groups and explicit blocked Provider groups; synthetic Orders JWT claim/priority tests do not substitute for Provider verification. D remains pending. Other capabilities lack owner-reviewed declarations/evidence and fail closed. DSGVO-02C remains `PARTIAL`. Regression failures caused by missing privacy evidence are classified, not bypassed. No pin upgrade, Provider change, AWS/Terraform action, deployment, installation, merge, real-data processing, legal retention decision, or operational/legal approval has occurred.
