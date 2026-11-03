# RIS-BRANCH-CONSOLIDATION-01B — Functional Scope Review

## Scope and evidence boundary

This review covers the code present on `feature/ris-application-persistence-v1`
and the checked-in RIS reports/tests. The Jobsearch repository was inspected
read-only from `C:\Users\DCI-Student\projekte\mays-jobsearch`; no Jobsearch
file was changed.

The requested Jobsearch files `MAYS-RIS-PROFILE-PERSISTENCE-01-HANDOFF.md` and
`MAYS-RIS-APPLICATION-PERSISTENCE-HANDOFF-V1.md` were not present in the
available Jobsearch checkout. The available canonical Jobsearch data and
repository contracts, RIS reconciliation reports and
`docs/contracts/JOBSEARCH-APPLICATION-HANDOFF-V1.md` were used instead.

## Profile persistence

| Area | Evidence | Classification |
|---|---|---|
| UserProfile | `jobsearch/partner_profile_contract.py`, existing profile handlers and version/freeze tests | **IMPLEMENTED / VERIFIED LOCAL** |
| CVDocument metadata | Contract parser, partner CV routes, repository and lifecycle tests | **IMPLEMENTED / VERIFIED LOCAL** |
| Secure CV document storage | Presigned upload/complete/get routes and S3 erasure contracts; real S3 E2E remains open | **IMPLEMENTED / VERIFIED LOCAL / OPEN FOR RIS-DEV TEAM** |
| CVSearchProfile | Five explicit CRUD routes, v1 `searchConfig`, parent checks, 2-per-CV limit, idempotency and versioning | **IMPLEMENTED / VERIFIED LOCAL** |
| ATSSearchProfile | Five explicit CRUD routes, criteria validation, parent/owner checks, 5-per-parent limit and versioning | **IMPLEMENTED / VERIFIED LOCAL** |
| ManualSearchProfile | Explicit CRUD routes and independent profile model with matching preferences | **IMPLEMENTED / VERIFIED LOCAL** |
| MatchingPreferences | Embedded manual-profile contract; separate from CV search configuration and ATS criteria | **IMPLEMENTED / VERIFIED LOCAL** |
| Versioning/conflicts | Conditional writes, stale-version 409 behavior and repository tests | **VERIFIED LOCAL** |
| Idempotency | 24-hour identity-bound create idempotency and payload-conflict handling | **VERIFIED LOCAL** |
| Pagination | GSI queries plus signed, scope-bound cursors | **VERIFIED LOCAL / OPEN FOR RIS-DEV TEAM** for real DynamoDB evidence |
| Ownership/tenant isolation | User, tenant, partner and issuer checks with negative tests | **VERIFIED LOCAL** |

The profile hierarchy is `UserProfile → CVDocument → CVSearchProfile →
ATSSearchProfile`; ManualSearchProfile remains independent. The Jobsearch v1
contract defines capacities 10 CVs, 2 CV search profiles per CV and 5 ATS
profiles per CV search profile. The RIS implementation enforces these locally.

## ApplicationV1

| Area | Evidence | Classification |
|---|---|---|
| Application CRUD | `jobsearch/application_repository.py`, contract and API tests | **IMPLEMENTED / VERIFIED LOCAL** |
| Status/history | Explicit state machine, confirmation-required submit and transactional history path | **IMPLEMENTED / VERIFIED LOCAL** |
| Cover-letter versions | Immutable child records with expected-version checks | **IMPLEMENTED / VERIFIED LOCAL** |
| Conflict/version handling | Conditional writes and signed pagination tests | **VERIFIED LOCAL** |
| Export/delete | Scoped export and transactional child deletion | **IMPLEMENTED / VERIFIED LOCAL** |
| Privacy/erasure | Inspect/export integration and erasure orchestration hooks | **IMPLEMENTED / VERIFIED LOCAL / OPEN FOR RIS-DEV TEAM** for environment verification |
| Deployment status | Historical report records ApplicationV1 applied to `ris-dev2`; this is not evidence of `ris-dev` deployment | **VERIFIED DEV2 / NOT DEPLOYED TO RIS-DEV** |

Application identity is derived from the verified context. Client-submitted
identity fields are rejected. ApplicationV1 does not create a second Cognito
boundary and does not invoke agents or models.

## Jobsearch contract review

The current Jobsearch data contract is marked specified/proposed and not
deployed. It defines server-generated IDs, integer `schemaVersion: 1`,
phrase-preserving search configuration, explicit CV/ATS parentage, versioned
resources, capacities 10/2/5 and no persistence of model scores or raw CV
bytes. The repository contract defines cursor pagination, expected-version
updates, typed conflicts and idempotent migration boundaries.

RIS R05/R06 reports show the corresponding CV/ATS contract repairs are
implemented locally and tested. Remaining integration work is real DynamoDB
transaction/GSI behavior, S3 E2E, live HTTP smoke and the absent formal
Jobsearch handoff files. These are not silently classified as deployed.

## Environment separation

- `ris-dev2`: ApplicationV1 deployment evidence exists in historical reports;
  no new AWS operation was performed in this consolidation.
- `ris-dev`: no deployment or mutation was performed or inferred.
- Existing Cognito, CloudFront, DNS, ACM and DynamoDB data are not replaced by
  this review.

## Conclusion

The implementation and local contracts are sufficiently evidenced for a
controlled PR handoff. Real `ris-dev` integration remains an explicit follow-up
owned by the RIS-DEV team; it is not represented as complete here.
