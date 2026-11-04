# RIS-JOBSEARCH-APPLICATION-EXT-01 — Bestandsaufnahme

## Scope and evidence

This report compares the Jobsearch application UX in the published
`origin/main` ref (`0fa799e66f056d68e2bb49075fbeaf14f6f5f8a0`) with RIS
`origin/main` after PR #3 merge (`37782f8462f515e0d860ba1ba64e976c7e14b8b9`).
Jobsearch was read-only. No live API, AWS, deployment, build, or test was
performed in this planning phase.

## Jobsearch capability inventory

The reference implements the complete local/session UX across
`ApplicationCard.tsx`, `ApplicationsSection.tsx`, `ApplicationEditForm.tsx`,
`src/lib/applications/contractTypes.ts`, `applicationDomain.ts`,
`sessionApplications.ts`, `sessionRepository.ts`, and `followUp.ts`.

Observed capabilities:

1. Cards show title, employer, optional location, status, application/creation
   date and follow-up state.
2. Cockpit metrics count all session records: total, drafts, submitted,
   interviews and open follow-ups; filters include overdue follow-ups.
3. Details edit channel, date, contact name/email/phone, notes and expectation
   and offer salary.
4. Communication stores feedback and interviews; history stores notes; status
   history is separate and append-only.
5. Follow-ups use real `YYYY-MM-DD` calendar dates, open/completed state,
   `completedAt`, notes, remove, complete and reopen semantics.
6. Documents contain a draft, versioned cover letters and a CV reference;
   export and deletion are explicit local actions.
7. Session protection includes expected versions, abort signals, generation
   invalidation, stale-operation protection, busy guards and session reset.

UX-04A through UX-05B and the full cover-letter display fix are integrated in
Jobsearch `origin/main` according to the fetched commit history. The local
`feature/arbeit` checkout is one contract commit ahead of its remote main but
was not changed or used as an implementation base.

## RIS capability inventory

RIS currently has a durable ApplicationV1 foundation in:

- `jobsearch/application_contract.py`
- `jobsearch/application_repository.py`
- `lambda/handler.py`
- `terraform/modules/api/main.tf`
- `terraform/modules/dynamodb/main.tf`
- `terraform/modules/lambda/main.tf`

The routes are explicit under `/v1/partner/me/applications` for create, list,
get, patch, status, history, cover-letter versions, export and delete. The
repository uses server UUIDs, a dedicated table, owner GSI, signed owner-bound
cursors, idempotency records and conditional version writes. The partner
context is resolved from the existing JWT plus partner credential boundary;
client identity fields are rejected.

The current contract is materially narrower than Jobsearch: it has five
uppercase statuses, only job/profile/CV references in create/patch, a free-form
history event, plain cover-letter text, and no follow-up or aggregate metrics.

## Required architectural decisions

1. Extend the existing ApplicationV1 contract and table/repository rather than
   creating a second application database or authentication system.
2. Use an explicit status mapping/version strategy. A simple many-to-one map is
   not lossless because `feedback`, `interview`, `offer`, and `rejected` must
   remain distinguishable. The preferred direction is to adopt the Jobsearch
   status vocabulary in a versioned ApplicationV1 schema while preserving
   legacy uppercase values through a read/write compatibility adapter and
   history migration.
3. Keep all server identity fields derived; do not accept `ownerId`, local IDs,
   tenant or partner identity from the browser.
4. Keep CV and cover-letter references metadata-only. Never copy PDF bytes,
   hashes, presigned URLs or internal S3 keys into the application resource.
5. Provide metrics as an owner-scoped server result or dedicated projection;
   never calculate global counts from one cursor page.
6. Make history, cover-letter, follow-up and status mutations participate in
   the same optimistic-concurrency contract.
7. Define explicit local-session transfer with preview, confirmation and
   per-item result; failures must leave the local item intact.

## Evidence limitations

Historical RIS audit entries document local tests and some read-only/deployment
gates, but they do not prove a currently reachable production API. No claim is
made here about live Cognito, partner credentials, `ris-dev`, `ris-dev2`, API
Gateway, DynamoDB contents, or deployment state.

The detailed row-level evidence is in
`RIS-JOBSEARCH-APPLICATION-EXT-01-COVERAGE.md`; stable unresolved questions
are in `RIS-JOBSEARCH-APPLICATION-EXT-01-OPEN-ITEMS.md`.
