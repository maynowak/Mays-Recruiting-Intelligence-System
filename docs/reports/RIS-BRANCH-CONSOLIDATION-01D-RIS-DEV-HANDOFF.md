# RIS-BRANCH-CONSOLIDATION-01D — RIS-DEV Integration Handoff

## Purpose and boundary

This is an integration handoff, not a deployment approval. It describes the
RIS components present on the reviewed development branch for separate
integration into `ris-dev`.

`ris-dev2` and `ris-dev` are strictly different environments. Historical
`ris-dev2` apply evidence must not be reused as a `ris-dev` plan, state, or
approval. The RIS-DEV team must generate and review a new environment-specific
Terraform plan.

## 1. Components being handed over

- `jobsearch/partner_profile_contract.py`: canonical profile resource/value
  contracts and validation;
- `jobsearch/partner_profile_repository.py`: scoped DynamoDB repository with
  capacity, idempotency, pagination, conditional versions and erasure freeze;
- partner profile/CV/ATS/manual handlers in `lambda/handler.py`;
- ApplicationV1 contract/repository in `jobsearch/application_contract.py` and
  `jobsearch/application_repository.py`;
- ApplicationV1 handler, API contract/OpenAPI additions and privacy/erasure
  integration;
- Terraform API, DynamoDB, Lambda IAM/environment and packaging changes;
- focused tests, fixtures and contract reports.

Jobsearch source was not changed. The Jobsearch-side contracts are a consumer
reference and remain specified/proposed until its own team integrates a remote
adapter.

## 2. API routes

### Profile and CV routes

Existing partner-boundary routes cover UserProfile and ManualSearchProfile. The
CV/document lifecycle uses:

```text
GET    /v1/partner/me/cvs
POST   /v1/partner/me/cvs
GET    /v1/partner/me/cvs/{cvId}
PUT    /v1/partner/me/cvs/{cvId}
DELETE /v1/partner/me/cvs/{cvId}
POST   /v1/partner/me/cvs/{cvId}/document/upload
POST   /v1/partner/me/cvs/{cvId}/document/complete
GET    /v1/partner/me/cvs/{cvId}/document
```

CV search profiles:

```text
GET/POST /v1/partner/me/cvs/{cvId}/search-profiles
GET/PUT/DELETE /v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}
```

ATS profiles:

```text
GET/POST /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles
GET/PUT/DELETE /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/{atsSearchProfileId}
```

Manual profiles:

```text
GET/POST /v1/partner/me/manual-search-profiles
GET/PUT/DELETE /v1/partner/me/manual-search-profiles/{profileId}
```

### ApplicationV1 routes

```text
POST   /v1/partner/me/applications
GET    /v1/partner/me/applications
GET    /v1/partner/me/applications/{applicationId}
PATCH  /v1/partner/me/applications/{applicationId}
POST   /v1/partner/me/applications/{applicationId}/status
POST   /v1/partner/me/applications/{applicationId}/history
POST   /v1/partner/me/applications/{applicationId}/cover-letter-versions
GET    /v1/partner/me/applications/{applicationId}/export
DELETE /v1/partner/me/applications/{applicationId}
```

All routes use the existing partner authentication boundary and explicit
Terraform-managed API routes. No wildcard proxy or new authentication
mechanism is introduced.

## 3. Profile and CV data models

The durable hierarchy is:

```text
UserProfile
└── CVDocument [maximum 10 per user]
    └── CVSearchProfile [maximum 2 per CV]
        └── ATSSearchProfile [maximum 5 per CVSearchProfile]
ManualSearchProfile [independent; product limit remains open]
```

`CVDocument` stores metadata and a secure document reference, never raw CV
bytes. `CVSearchProfile` stores the phrase-preserving `searchConfig`:
`skills`, `targetRoles`, `city`, nullable `radiusKm`, `workModes` and
`employmentTypes`. `ATSSearchProfile` stores ATS `skills`, `targetRoles` and
restricted `criteria` (`requiredSkills`, `preferredSkills`, `excludedTerms`).
Manual profiles store `searchConfig` plus `MatchingPreferences`.

IDs, owner/tenant/issuer, timestamps and versions are server-owned. Parent
links are immutable and all operations enforce user, tenant, partner and issuer
isolation. Creates use an identity-bound idempotency key; updates/deletes use
expected versions and return conflicts rather than overwriting newer data.

## 4. ApplicationV1 data model

The application item contains server `applicationId`, job metadata,
`profileRef`, `cvRef`, cover-letter version IDs, status, submission timestamp,
timestamps and optimistic `version`. Statuses are `DRAFT`, `READY`,
`SUBMITTED`, `WITHDRAWN` and `ARCHIVED`; submission requires explicit
`confirm: true`.

History and cover-letter versions are immutable child records in the same
partition. Export returns application metadata plus scoped history and cover
letter versions. Raw CV bytes, credentials, tokens and presigned URLs are not
stored in ApplicationV1.

## 5. Tables and indexes

### Existing/new profile table

```text
<project>-<environment>-partner-profiles
PK: resourceId
GSI gsi-user: userId / resourceType
GSI gsi-parent: parentId
Billing: PAY_PER_REQUEST
```

Persistent resource types are CVDocument, CVSearchProfile,
ATSSearchProfile and ManualSearchProfile. UserProfile and
MatchingPreferences are contract/embedded data, not separate profile tables.

### ApplicationV1 table

```text
<project>-<environment>-applications
PK: applicationId
SK: entityKey
GSI gsi-owner: ownerKey / updatedAt
Billing: PAY_PER_REQUEST
```

The owner GSI is queried only with the complete server-derived owner scope.
Existing DynamoDB tables and records must not be replaced or overwritten.
Table creation/migration must be represented by a newly reviewed `ris-dev`
plan; no `ris-dev2` plan is reusable.

## 6. Document S3 lifecycle

The CV lifecycle is metadata-first: create CV metadata, request a presigned
upload, upload through the controlled document path, complete/verify the
object, then expose a scoped document read/download path. S3 keys and
presigned URLs are not persisted in profile/application DTOs. Erasure uses the
existing freeze and durable S3 phase machinery; incomplete or failed cleanup
must remain visible rather than being reported as complete.

Real S3/DynamoDB E2E and live HTTP verification remain RIS-DEV integration
tasks.

## 7. Terraform and migration guidance

Terraform changes are in the RIS root and local modules:

- explicit API Gateway routes for CV/profile/ApplicationV1 operations;
- `partner-profiles` and `applications` DynamoDB resources/indexes;
- Lambda environment variables for the table names;
- least-privilege Lambda IAM access to the profile/application tables and
  required GSIs;
- deterministic `terraform/lambda.zip` packaging.

Do not modify the Mays-Orders builder clone as part of this handoff. Do not
replace Cognito pools, CloudFront/OAC, DNS or ACM resources. Keep
`orders_lifecycle` disabled unless separately approved. Do not run a data
migration or destroy/recreate an existing table. If an existing `ris-dev`
table conflicts with the proposed names/schema, stop and produce a migration
plan rather than relying on Terraform replacement.

## 8. IAM and application permissions

The Lambda role requires only the profile/application table actions and their
indexes needed by the repositories: scoped reads/queries, conditional writes,
transactions and deletes. S3 permissions remain bounded to the secure document
lifecycle. Partner credentials are resolved through the existing protected
runtime boundary; no credential is placed in a report, fixture or client
payload.

## 9. Identity and environment configuration

Use the existing Cognito JWT, tenant claim, partner registry and issuer
binding. Do not create a second login, PKCE flow, Cognito pool or M2M boundary.
`ris-dev` values for project name, environment, backend, API IDs, table names,
issuer and protected credentials must be obtained from the `ris-dev`
installation context, not copied from `ris-dev2`.

Never commit secrets, partner credentials, tokens, presigned URLs or raw CV
content. No values from the local `ris-dev2` overlay are a default for
`ris-dev`.

## 10. Packaging and deployment prerequisites

1. Build with `python lambda/build_zip.py --bundle all`.
2. Verify ZIP structure, handler import, dispatcher fix and deterministic hash.
3. Run the focused profile/ApplicationV1/privacy/API tests.
4. Run `terraform -chdir=terraform init -backend=false`, scoped `fmt` and
   `validate` locally.
5. Authenticate/read the `ris-dev` account, region, workspace, backend,
   state serial/lineage and protected-resource baseline.
6. Generate a new `ris-dev` plan; inspect every action and hash.
7. Obtain a separate approval before any controlled apply.

Already-applied `ris-dev2` plans and saved plans must not be reused.

## 11. Test evidence

The consolidation regression selected **453 passed, 297 subtests passed**;
packaging passed **6 tests** with two explicit live tests skipped for missing
`mayaws` credentials. Python 3.14.10 compileall and scoped Terraform format/
validation passed. These are local/branch results, not GitHub CI results and
not `ris-dev` live verification.

## 12. Privacy and erasure boundaries

Identity and tenant isolation are mandatory for inspect, export, update and
delete. Application export excludes internal owner/entity/idempotency fields
and secret-like values. Erasure is ordered and checkpointed across profile,
application and document resources, but legal retention/backup/DPIA decisions
remain review gates. No report claims production DSGVO completion or complete
S3 erasure without live evidence.

## 13. Open RIS-DEV tasks

- obtain and review the missing formal Jobsearch handoff documents;
- reconcile any remaining CVDocument field/status mapping decisions;
- verify real DynamoDB transaction, GSI consistency and conditional-write
  behavior;
- perform controlled S3/document lifecycle and erasure E2E;
- create a fresh `ris-dev` Terraform plan and review migrations/drift;
- run authenticated live HTTP smoke without replacing existing identity or
  protected infrastructure;
- separately approve retention, backup and DPIA decisions.

## 14. Recommended integration order

1. Review this handoff and the contract/reconciliation reports.
2. Confirm the `ris-dev` state and protected-resource baseline read-only.
3. Reconcile contracts with the current Jobsearch main branch.
4. Build and locally validate the Lambda artifact.
5. Validate Terraform root/modules and inspect a fresh `ris-dev` plan.
6. Apply only newly approved additive resources/routes/IAM changes through
   Terraform.
7. Verify API authorization, profile/application CRUD, conflicts, pagination,
   S3 lifecycle and erasure in `ris-dev`.
8. Record results separately; do not infer them from `ris-dev2`.

This handoff does not authorize deployment.
