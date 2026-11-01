# RIS-R08-C-G0 — RIS USER DATA ERASURE READINESS

**Status:** ANALYSIS COMPLETE / IMPLEMENTATION BLOCKED

## 1. Baseline and evidence

| Check | Result |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD | `2d672a614333f1b2d0b80adc9a8f5749b9b7323a` |
| Tracked working tree at start | clean |
| Original untracked files | 39, preserved |
| Scope | RIS only; no data deletion, AWS, deployment, Jobsearch or Orders changes |

Reviewed: R08-G0, R08-POLICY-01, R08-B1 inspection, R08-B2A export,
`agents/ecosystem/privacy_erasure.py`, the partner profile contract and
repository, cursor store, document storage helpers, Terraform table/bucket
definitions and the existing G5 handler.

## 2. Current G5 behavior

`POST /me/erasure` uses `PrivacyErasure` and currently performs this order:

1. revoke owned credentials;
2. revoke owned API profiles;
3. query `WORK_ITEMS_TABLE` by `gsi-user` and transition
   `CREATED`/`QUEUED`/`RUNNING`/`RETRY` to `CANCELLED`;
4. call `documents.delete_all_for_user`;
5. delete the `USER_PROFILE_TABLE` row.

The result is per-step and `complete` is false if any step fails. The workflow
does not persist an operation record, checkpoint, retry token or durable resume
state. Work cancellation is currently a single query and is not a complete,
durably resumed pagination proof. Terminal work is retained by design; Orders
are outside RIS ownership.

The document helper lists objects and calls `delete_object` for the current
object. It does not enumerate/delete all S3 versions and delete markers, does
not verify bucket emptiness, and returns a count that cannot prove physical
purge. The bucket is versioned and has no observed lifecycle rule.

## 3. Erasure coverage matrix

| Data/domain | Current G5 | Required C design | Decision |
|---|---|---|---|
| UserProfile | Deletes row last | Delete only after all required RIS scopes complete; tenant condition | C1/C2 |
| CVDocument metadata | **Not deleted** | Enumerate scoped `CVDocument` parents; guarded delete after children/PDF outcome | C1/C2 |
| CV PDF current object | Best-effort current-object delete | Verify ownership, list all object versions/delete markers, delete and verify | C1/C2 |
| S3 versions/delete markers | **Not covered** | Version-aware paginated purge with evidence and retry checkpoint | C2 |
| ManualSearchProfile | **Not deleted** | Scoped full enumeration and idempotent deletion | C1 |
| CVSearchProfile | **Not deleted** | Delete after ATS children, with parent/counter guards | C1 |
| ATSSearchProfile | **Not deleted** | Delete before CVSearchProfile parent | C1 |
| Capacity counters | **Not deleted** | Reconcile/decrement atomically or remove only when ownership is proven | C1 |
| Lifecycle guards | **Not deleted** | Mark subject/resource deleting; release/finalize safely on resume | C1/C3 |
| Cursor records | **Not deleted** | Delete subject-bound `CursorToken` records after enumeration or expire safely | C1/C3 |
| Idempotency records | **Not deleted** | Remove subject-owned records according to approved retention; preserve operation idempotency until finalization | C1/C3 |
| Non-terminal WorkItems | Cancels, not deletes | Keep cancellation as separate policy step; fully paginate and condition on version/state | Later decision |
| Terminal/FAILED/CANCELLED WorkItems | Retained | Explicit retention decision; do not alter agent lifecycle here | Later decision |
| Privacy Receipts | No G5 treatment | Preserve/minimize/delete only under approved receipt retention and evidence policy | Blocked |
| Cognito/session state | Not deleted | Separate authorized Cognito/session-revocation operation | External/explicit |
| PITR/backups/restore | Not affected | Restore reconciliation must prevent resurrection | External/explicit |

## 4. Single CV deletion versus user erasure

The existing single-CV path is a three-phase operation:

- reserve a `LifecycleGuard` and prove child freedom;
- delete the current S3 object;
- atomically delete the CV metadata, counter and guard.

It is ownership- and tenant-checked and refuses a parent with children. This is
appropriate for an individual CRUD delete, but it is not sufficient for user
erasure: user erasure must first remove every ATS child, then every
CVSearchProfile, then the CV PDF/object history and finally the CVDocument
parent. User erasure needs an internal guarded cascade, not a loop over public
parent deletes that can leave a race window or stop at the normal child `409`.

The manual profile is independent. Its deletion can be performed as a scoped
leaf operation. All operations must use stored item identity, not client
payload identity, and must condition on user, tenant, partner application,
issuer and current version where applicable.

## 5. Required ordering and safety contract

The proposed user-erasure contract is:

1. **Authorize and freeze:** build identity only from verified context; create
   an operation record; mark the subject/operation as `DELETING`; reject or
   quarantine new profile writes and new processing for that subject.
2. **Revoke capability:** revoke credentials/API profiles before data deletion;
   retain the G5 ordering invariant.
3. **Stop processing:** cancel non-terminal work with paginated GSI reads and
   conditional status transitions. Agent lifecycle changes are not part of
   this gate.
4. **Enumerate children:** repeatedly query scoped partner-profile pages and
   persist the last completed cursor/checkpoint. Delete
   `ATSSearchProfile` first, then `CVSearchProfile`, then `ManualSearchProfile`.
5. **Purge CV storage:** for each owned CV, verify the document key from the
   server-side tenant/user/document mapping, paginate object versions and
   delete markers, and verify no matching versions remain. Missing or
   indeterminate S3 results are `PARTIAL`, never success.
6. **Finalize metadata:** delete CVDocument rows and associated counters/
   lifecycle guards atomically where possible; remove or reconcile cursor and
   idempotency records only after their resume role is no longer needed.
7. **Delete UserProfile last:** require tenant/version conditions and only mark
   the operation complete after all required RIS categories report success.
8. **Record evidence:** emit an approved minimal receipt/operation result with
   `REQUESTED`, `PARTIALLY_COMPLETED` or `COMPLETED`; never claim physical,
   backup or provider deletion without independent evidence.

The ordering is deliberately resumable. A retry must recognize already
deleted/revoked rows, retain the operation checkpoint, and never recreate a
counter or treat a missing store as an empty successful store.

## 6. Concurrency, pagination and partial failure

- Use the existing opaque cursor store for bounded page traversal, but extend
  the operation with a durable checkpoint/operation ID so a 15-minute cursor
  expiry cannot make an erase unrecoverable.
- Re-check the verified identity and tenant/partner/issuer scope on every
  query and delete; never use a user-only scan for partner profiles.
- Acquire the subject deleting guard before enumeration. New writes must be
  rejected or conditionally fail once the guard is active.
- Use conditional writes on resource version, lifecycle state and ownership.
  A concurrent update causes a safe retry/conflict, not an unverified delete.
- DynamoDB `LastEvaluatedKey`, S3 continuation tokens and version IDs must be
  checkpointed. A page is acknowledged only after all intended mutations in
  that page have an unambiguous result.
- Unknown transaction/S3 outcomes are `INDETERMINATE` and require resume or
  operator review. They must not be counted as deleted.
- A partial result identifies affected categories and the next resumable step;
  `COMPLETE` is forbidden while any required category, version purge,
  authorization revocation or checkpoint finalization is unresolved.

## 7. Retention, receipts, Cognito and restore boundaries

R08-POLICY-01 records cursors at 15 minutes, idempotency records at 24 hours,
no general TTL for profiles/counters/guards, no receipt TTL, versioned S3 with
no observed lifecycle rule, and unproven backup/PITR/log periods. These are
technical observations, not approved legal retention durations.

Privacy Receipts require a separate decision: retain the minimum evidence
needed for accountability, anonymize or delete only under an approved policy,
and never use a receipt as proof that S3 versions, backups or external data are
gone. The journal is disabled and no receipt-writing or receipt-deletion
behavior is introduced in G0.

Cognito user deletion and refresh/session revocation are separate explicitly
authorized operations. G5 does not establish their completion. DynamoDB PITR,
backups, S3 historical versions and logs are not synchronously erased by the
application; restore reconciliation is required before a restored environment
can be promoted, otherwise erased data could be resurrected.

Terminal, FAILED and CANCELLED WorkItems, plus agent lifecycle semantics, are
kept as a later policy/implementation decision. This gate changes no agent
routine and makes no claim that those records are erased.

## 8. Committable implementation plan

### R08-C1 — operation and authorization foundation

**Goal:** create a durable, scoped, resumable erasure contract without
deleting data.

- Define `PrivacyErasureOperationV1` states, step IDs, evidence level,
  checkpoint and retry semantics.
- Add a subject deleting guard and write-gate checks for partner profiles.
- Add operation-status/read authorization using the same verified context.
- Specify receipt behavior and retention reference; keep journal disabled until
  policy approval.
- Add unit tests for identity/tenant/partner/issuer isolation, replay,
  concurrent write rejection and partial status.

**Exit:** no delete implementation yet; operation can be created/resumed and
  is fail-closed. Requires policy approval for retention and receipt handling.

### R08-C2 — scoped cascade and version-aware storage purge

**Goal:** implement the ordered, idempotent RIS data cascade.

- Add repository methods for paginated subject enumeration and guarded bulk
  deletion of ATS → CV search → manual → CV metadata and system records.
- Add S3 version/delete-marker pagination, ownership checks, checkpointing and
  empty-prefix verification; distinguish current-object deletion from physical
  purge.
- Integrate UserProfile-last finalization and G5 capability/work steps without
  changing public CRUD semantics.
- Test races, stale versions, child relationships, capacity/cursor/guard
  cleanup, S3 failures, retries and resume after every step.

**Exit:** synthetic persistence and S3 integration prove no scoped records or
  versions remain before a complete result; no AWS deployment is implied.

### R08-C3 — evidence, restore and production gate

**Goal:** prove operational correctness and policy compliance.

- Integrate approved receipt/operation evidence and retention controls.
- Test backup/PITR restore reconciliation and Cognito/session boundary with
  the owning systems.
- Run DynamoDB Local/S3-compatible integration and deployed E2E only after
  C1/C2 and policy approval.
- Review terminal work/agent lifecycle and Mays-Orders boundaries separately.

**Exit:** production GO only after legal retention approval, full-scope
  evidence, restore proof and deployed authorization checks.

## 9. Gate result

- **R08-C-G0:** PASS as an analysis and contract gate only.
- **R08-C1:** **BLOCKED** — the operation/retention/receipt contract is not
  policy-approved, the receipt journal is disabled, and the required
  subject-deleting write gate and durable operation/checkpoint store do not yet
  exist.
- No erasure implementation or real deletion was performed.
