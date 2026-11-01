# RIS-R08-C1B-1 — COMPLETE LOCAL ERASURE ACCEPTANCE

**Status:** LOCAL SYNTHETIC E2E GO / REAL AWS E2E BLOCKED

## Baseline and scope

- Baseline: `9827e09ca5a100f959b56bce80c0e34eba8e9f84`
- C1A and C1B-0 orchestration reused; no parallel erasure architecture
- Synthetic profile, operation, phase-ledger and versioned Fake-S3 stores only
- No AWS calls, real S3 mutation, deployment, Terraform change or receipt
  journal activation
- 39 pre-existing untracked files preserved

## Local E2E scenarios

The acceptance suite exercises a complete synthetic USER fixture containing
UserProfile authorization, CVDocuments, CVSearchProfile, ATSSearchProfile and
ManualSearchProfile records. It verifies:

- authorized operation/context and foreign-context rejection;
- profile hierarchy ordering and scope isolation;
- multiple document references, S3 versions and delete markers;
- C0F inventory, explicit-version deletion and final re-inventory;
- metadata deletion only after verified empty Fake-S3 inventory;
- durable operation progress and local completion conditions;
- retry/resume after an unknown S3 result;
- replay/idempotent absence handling;
- unmapped S3 objects, missing references and blocked quiescence;
- selected-CV deletion without touching a foreign CV; and
- empty post-erasure inspection/export inventories.

An explicitly local operation may become `COMPLETED` only when every category
present in that operation is `COMPLETED` or `SKIPPED`, including
`cvDocuments`. A standard operation created with additional open G5 categories
remains `PARTIAL`, even after profile and document work succeeds. Thus local
completion cannot accidentally claim completion of credentials, external
systems, receipts or other unresolved phases.

Unknown legacy tickets, absent quiescence evidence, stale execution context,
missing document references, unmapped objects, S3 unknown results and open
phases remain `PARTIAL`/`RETRY`.

## Acceptance results

| Check | Result |
|---|---|
| C1B-1 acceptance tests | **12 passed** |
| C1A/C1B/C0F focused suite | **44 passed** |
| Available RIS regression subset | **324 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| AWS/S3 calls | **None** |

The repository-wide pytest command is not a clean dependency baseline in this
environment: DynamoDB Local is unavailable, and collection also lacks
`boto3`, `requests`, `urllib3` and generated Builder package imports. These
are reported as environment blockers, not converted into passing results.

## Prioritized production release checklist

1. **P0 — Distributed S3 fencing:** design and independently verify a
   service-mediated or S3-enforced stale-worker fence; DynamoDB CAS alone is
   insufficient.
2. **P0 — Upload cutover:** prove all historical issuers, unknown legacy-ticket
   population and final inventory; no assumed TTL or automatic release date.
3. **P0 — Quiescence:** verify freeze, blocked ticket creation, zero active
   actions and complete version/delete-marker re-inventory in the target
   environment.
4. **P0 — IAM/Object Lock:** verify versioned list/delete permissions, bucket
   Deny behavior, legal holds and Object Lock state.
5. **P1 — Durable stores:** enable and test operation/checkpoint persistence,
   crash recovery and receipt policy under approved retention controls.
6. **P1 — Production canary:** run authorized, audited canaries with real
   evidence only after all prior gates pass; retain rollback/retry procedures.

## Gate decisions

- **LOCAL E2E:** **GO** — complete synthetic USER/CV lifecycle verified.
- **REAL AWS E2E:** **BLOCKED** — no AWS execution was performed and C0F-2D/
  C0F-2E production evidence is unresolved.
- **PRODUCTION:** **BLOCKED** — fencing, legacy tickets, quiescence,
  IAM/Object-Lock and persistence activation remain open.
