# RIS-JOBSEARCH-APPLICATION-EXT-01 — Coverage Matrix

## Classification

- **IMPLEMENTED** — present in RIS source/configuration.
- **VERIFIED LOCAL** — supported by repository/domain or historical local test
  evidence; this audit did not rerun tests.
- **CONTRACT ONLY** — described by Jobsearch contract but not implemented in
  RIS.
- **NOT DEPLOYED** — no deployment evidence was established here.
- **NOT VERIFIED** — live API/auth/partner behavior was not exercised.
- **OPEN / INCOMPATIBLE** — current RIS shape cannot satisfy the Jobsearch
  requirement without a contract or persistence change.

Jobsearch evidence refers to the read-only `origin/main` snapshot at
`0fa799e66f056d68e2bb49075fbeaf14f6f5f8a0`; RIS evidence refers to branch
`feature/ris-jobsearch-application-ext-01` at the documentation commits listed
in the baseline.

## Matrix

| ID | UI-Funktion | Datenfeld/Aktion | Jobsearch-Evidence | RIS-API/Vertrag | Abdeckung | Lücke | Priorität | Testnachweis |
|---|---|---|---|---|---|---|---|---|
| COV-01 | Kompakte Karte | Titel, Arbeitgeber, Ort | `ApplicationCard.tsx`; UX-05B | `job` currently validates only `jobId` plus legacy `company`/`url` shape | PARTIAL / OPEN | Align `companyName`, `location[]`, `originalUrl` without losing legacy data | P1 | Jobsearch UX-05B report: 6 card tests; RIS contract tests historical only |
| COV-02 | Kartenstatus | Statuschip | UX-05B; statuses `draft`..`withdrawn` | RIS legacy `status` plus additive `stage` | IMPLEMENTED / VERIFIED LOCAL | Live API and later UI adapter remain unverified | P0 | EXT-02: 27 application tests passed, 18 security tests passed; Moto tests skipped |
| COV-03 | Karten dates | created/application date | `ApplicationCard.tsx`, UX-05B | RIS create/PATCH now validates and returns `applicationDate` | IMPLEMENTED / PARTIAL | Moto/live round-trip remains unverified | P1 | Contract tests passed; repository Moto skipped |
| COV-04 | Follow-up card | `dueOn`, open/completed label | `followUp.ts`, UX-04D/05B | RIS create/PATCH now validates and persists follow-up | IMPLEMENTED / PARTIAL | Moto/live round-trip remains unverified | P0 | Contract tests passed; repository Moto skipped |
| COV-05 | Cockpit metrics | total, drafts, submitted, interviews, open follow-ups | `ApplicationsSection.tsx`; UX-05A | RIS metrics route consumes all owner pages | IMPLEMENTED / PARTIAL | Moto/live DynamoDB query evidence remains open | P0 | Metrics unit test passed; Moto skipped |
| COV-06 | Cockpit filters/sort | status, overdue, follow-up due order | UX-05A | RIS list has signed cursor and descending query order | PARTIAL | Define server order and whether filtering is server-side or complete snapshot | P1 | Cursor code exists; filter semantics absent |
| COV-07 | Detail editing | channel, date, contact, notes, salary | `ApplicationEditForm.tsx`; UX-04A | RIS create/PATCH validates and serializes all fields | IMPLEMENTED / PARTIAL | Moto/live round-trip remains unverified | P0 | Contract tests passed; repository Moto skipped |
| COV-08 | Communication | feedback, interviews, notes | UX-04C; domain `history` union | RIS `add_history` accepts event mapping and atomically advances parent version | PARTIAL | Typed event validation and live contract remain open | P0 | Moto history/version path passed; no typed-event schema |
| COV-09 | Status history | append-only transition history | UX-04C/contract | RIS child history now retains legacy and stage transition fields | IMPLEMENTED / VERIFIED LOCAL | Typed history for other event kinds remains open | P0 | EXT-02 stage round-trip/export test passed |
| COV-10 | Cover-letter draft | current draft text | UX-04C and cover-letter fixes | RIS documents envelope accepts draft text | IMPLEMENTED / PARTIAL | Moto/live round-trip remains unverified | P0 | Contract validation passed; repository Moto skipped |
| COV-11 | Cover-letter versions | source, language, model, content, job binding | `contractTypes.ts`, UX-04C | RIS normalizes legacy text and persists metadata-bearing job-bound versions | IMPLEMENTED / PARTIAL | Export runtime evidence remains open | P0 | Static/API tests passed; Moto skipped |
| COV-12 | CV reference | `cvId`, optional `documentId`, label | UX-04C/04A; contract | RIS validates metadata-only `documents.cvReference`; configured profile ownership runtime remains open | PARTIAL / OPEN | Complete owner fixture and live ownership proof; legacy `cvRef` remains compatibility-only | P0 | Contract/static tests; no configured CV-store Moto fixture |
| COV-13 | Export | complete application and documents metadata | UX-04C/04E | RIS export now traverses all child pages and returns app/history/cover metadata | IMPLEMENTED / PARTIAL | Define stable ApplicationExportV1 envelope and live auth proof | P1 | Moto export path passed; live auth not verified |
| COV-14 | Delete | confirmed owner-scoped delete | UX-04C/04E | RIS DELETE is expected-version conditional and batched to 100 actions | IMPLEMENTED / PARTIAL | Idempotency-record cleanup, tombstone/retention and multi-batch receipt remain open | P1 | Moto stale-delete/cleanup passed; live verification absent |
| COV-15 | Session transfer | explicit preview/confirm, no loss | Jobsearch handoff contract; localId is session-only | No transfer route or migration port in RIS | CONTRACT ONLY / OPEN | Add explicit preview/confirm adapter and per-item result | P0 | No implementation evidence by design |
| COV-16 | Identity/isolation | verified owner, tenant, partner, issuer | Jobsearch handoff §2 | `_partner_profile_context`, `ApplicationContext`, owner GSI and signed cursor | IMPLEMENTED / NOT VERIFIED | Partner credential provisioning/live cross-owner proof remains open | P0 | Historical negative auth tests in RIS auditlog; no live positive path |
| COV-17 | Concurrency | stale requests, session switch, 409 | UX-04A/04C/05A | Detail, follow-up, history and cover mutations use parent expectedVersion | IMPLEMENTED / VERIFIED LOCAL | Live contention and multi-batch erasure remain open | P0 | Moto stale-delete and version tests passed |
| COV-18 | Pagination | complete list and signed cursor | Jobsearch metrics currently use in-memory collection | RIS signed cursor, GSI owner list and all-page metrics | IMPLEMENTED / VERIFIED LOCAL | Metrics are not a transactional snapshot; live scale remains open | P0 | Moto list/cursor/metrics tests passed |
| COV-19 | Credentials | no partner secret in browser | Jobsearch handoff §2/§10 | API requires JWT plus `X-Api-Credential`, resolved server-side | IMPLEMENTED / NOT VERIFIED | Exact Jobsearch BFF/delegation boundary and live credential path remain open | P0 | RIS auth/error tests historical; no production call |
| COV-20 | Deployment boundary | reachable live API | All Jobsearch UX reports explicitly no deployment | Terraform routes/table/IAM exist on RIS branch history | NOT DEPLOYED / NOT VERIFIED | Need approved ris-dev rollout and live evidence, outside this task | P0 | No deployment/test executed in this phase |

## Summary

The RIS persistence foundation is present: server-generated IDs, scoped access,
signed cursors, idempotent create, conditional version writes, routes, table
and IAM wiring. It is not yet a complete consumer of the Jobsearch contract.
The blocking gaps are status compatibility, detail fields, follow-ups,
complete document references, metrics independent of pagination, atomic child
mutations, and explicit session transfer.
