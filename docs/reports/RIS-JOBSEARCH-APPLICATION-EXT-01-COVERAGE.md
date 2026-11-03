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
| COV-03 | Karten dates | created/application date | `ApplicationCard.tsx`, UX-05B | RIS create server timestamps only; no application date input | PARTIAL | Persist and return `applicationDate`, preserving calendar semantics | P1 | Jobsearch UX-04A date tests; RIS gap untested |
| COV-04 | Follow-up card | `dueOn`, open/completed label | `followUp.ts`, UX-04D/05B | RIS create/patch contract has no follow-up | OPEN / INCOMPATIBLE | Add validated calendar-date follow-up, completion and removal | P0 | Jobsearch UX-04D schema/domain tests; no RIS follow-up test |
| COV-05 | Cockpit metrics | total, drafts, submitted, interviews, open follow-ups | `ApplicationsSection.tsx`; UX-05A | RIS list returns page items and `nextCursor` only | OPEN / INCOMPATIBLE | Add owner-scoped aggregate/metrics contract independent of page size | P0 | Jobsearch UX-05A: 30 section tests; no RIS metrics evidence |
| COV-06 | Cockpit filters/sort | status, overdue, follow-up due order | UX-05A | RIS list has signed cursor and descending query order | PARTIAL | Define server order and whether filtering is server-side or complete snapshot | P1 | Cursor code exists; filter semantics absent |
| COV-07 | Detail editing | channel, date, contact, notes, salary | `ApplicationEditForm.tsx`; UX-04A | RIS `validate_patch` allows only job/profileRef/cvRef/version | OPEN / INCOMPATIBLE | Extend patch schema and repository serialization | P0 | Jobsearch UX-04A: 18 section/14 repository tests; RIS no field tests |
| COV-08 | Communication | feedback, interviews, notes | UX-04C; domain `history` union | RIS `add_history` accepts arbitrary `event` mapping and does not increment parent version | PARTIAL / OPEN | Normalize event schema, bind IDs/job owner, version atomically | P0 | RIS repository has no evidence of typed event validation |
| COV-09 | Status history | append-only transition history | UX-04C/contract | RIS child history now retains legacy and stage transition fields | IMPLEMENTED / VERIFIED LOCAL | Typed history for other event kinds remains open | P0 | EXT-02 stage round-trip/export test passed |
| COV-10 | Cover-letter draft | current draft text | UX-04C and cover-letter fixes | RIS create/patch does not accept `documents.coverLetterDraft` | OPEN / INCOMPATIBLE | Add document envelope and explicit update semantics | P0 | Jobsearch cover-letter reports; RIS add version only |
| COV-11 | Cover-letter versions | source, language, model, content, job binding | `contractTypes.ts`, UX-04C | RIS endpoint accepts plain `text`, generates only ID/time | PARTIAL / INCOMPATIBLE | Persist full `CoverLetterVersionV1`, validate `jobId`, expose in read/export | P0 | Existing RIS cover-letter repository path only |
| COV-12 | CV reference | `cvId`, optional `documentId`, label | UX-04C/04A; contract | RIS has legacy `cvRef` `{id,version}` and no ApplicationV1 document envelope | PARTIAL / OPEN | Map to owned reference, never PDF/S3 key; verify CV ownership | P0 | CV persistence exists separately; no application reference integration test |
| COV-13 | Export | complete application and documents metadata | UX-04C/04E | RIS export returns app plus child history/cover versions in custom shape | PARTIAL | Define ApplicationExportV1 envelope and include follow-up/doc references | P1 | Handler route implemented; live auth not verified |
| COV-14 | Delete | confirmed owner-scoped delete | UX-04C/04E | RIS DELETE requires `expectedVersion`, transactional children; response 204 | PARTIAL | Decide hard delete/tombstone, idempotent missing semantics, UI receipt contract | P1 | Historical repository tests; no live verification |
| COV-15 | Session transfer | explicit preview/confirm, no loss | Jobsearch handoff contract; localId is session-only | No transfer route or migration port in RIS | CONTRACT ONLY / OPEN | Add explicit preview/confirm adapter and per-item result | P0 | No implementation evidence by design |
| COV-16 | Identity/isolation | verified owner, tenant, partner, issuer | Jobsearch handoff §2 | `_partner_profile_context`, `ApplicationContext`, owner GSI and signed cursor | IMPLEMENTED / NOT VERIFIED | Partner credential provisioning/live cross-owner proof remains open | P0 | Historical negative auth tests in RIS auditlog; no live positive path |
| COV-17 | Concurrency | stale requests, session switch, 409 | UX-04A/04C/05A | patch/status/delete use expected version; history/cover do not atomically bump parent | PARTIAL / OPEN | Consistent mutation protocol and client abort/error mapping | P0 | Historical version tests; missing child concurrency test |
| COV-18 | Pagination | complete list and signed cursor | Jobsearch metrics currently use in-memory collection | RIS signed cursor and GSI owner list | IMPLEMENTED / PARTIAL | Metrics cannot be derived from first page; define aggregate endpoint/read model | P0 | Cursor binding code present; no metrics pagination test |
| COV-19 | Credentials | no partner secret in browser | Jobsearch handoff §2/§10 | API requires JWT plus `X-Api-Credential`, resolved server-side | IMPLEMENTED / NOT VERIFIED | Exact Jobsearch BFF/delegation boundary and live credential path remain open | P0 | RIS auth/error tests historical; no production call |
| COV-20 | Deployment boundary | reachable live API | All Jobsearch UX reports explicitly no deployment | Terraform routes/table/IAM exist on RIS branch history | NOT DEPLOYED / NOT VERIFIED | Need approved ris-dev rollout and live evidence, outside this task | P0 | No deployment/test executed in this phase |

## Summary

The RIS persistence foundation is present: server-generated IDs, scoped access,
signed cursors, idempotent create, conditional version writes, routes, table
and IAM wiring. It is not yet a complete consumer of the Jobsearch contract.
The blocking gaps are status compatibility, detail fields, follow-ups,
complete document references, metrics independent of pagination, atomic child
mutations, and explicit session transfer.
