# ApplicationV1 — RIS/Jobsearch Contract

**Status:** V1 contract baseline / implementation target

## Boundary

`ApplicationV1` is the durable RIS representation of a Jobsearch application.
It is owned by the authenticated RIS subject and is not a second profile or
identity system. The existing Cognito JWT, tenant claim, partner registry,
issuer binding, user profile, CV metadata and document lifecycle remain the
authoritative boundaries.

The Jobsearch-facing logical operations are preserved, but are exposed through
the existing RIS partner namespace:

| Logical operation | RIS route |
|---|---|
| create | `POST /v1/partner/me/applications` |
| list | `GET /v1/partner/me/applications` |
| read | `GET /v1/partner/me/applications/{applicationId}` |
| patch | `PATCH /v1/partner/me/applications/{applicationId}` |
| status | `POST /v1/partner/me/applications/{applicationId}/status` |
| history | `POST /v1/partner/me/applications/{applicationId}/history` |
| cover-letter version | `POST /v1/partner/me/applications/{applicationId}/cover-letter-versions` |
| export | `GET /v1/partner/me/applications/{applicationId}/export` |
| delete | `DELETE /v1/partner/me/applications/{applicationId}` |

The unversioned Jobsearch `/api/*` endpoints remain stateless and unchanged.

## Identity and ownership

The server derives `applicationId`, `userId`, `tenantId`,
`partnerApplicationId`, and `issuer` from the verified request context. Client
values for these fields are rejected, not ignored. Every read, update, status
transition, history append, export and delete is scoped by all five values.

## Resource shape

```json
{
  "schemaVersion": 1,
  "applicationId": "server-generated",
  "job": { "jobId": "source-specific", "source": "provider", "title": "", "company": "", "location": "" },
  "profileRef": { "profileId": "existing-profile-id", "version": 1 },
  "cvRef": { "cvId": "existing-cv-id", "version": 1 },
  "coverLetterVersionIds": [],
  "status": "DRAFT",
  "submittedAt": null,
  "version": 1,
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```

Allowed statuses are `DRAFT`, `READY`, `SUBMITTED`, `WITHDRAWN`, and
`ARCHIVED`. `SUBMITTED` requires an explicit `confirm: true` request field;
there are no automatic model or agent calls.

History and cover-letter versions contain metadata/text supplied explicitly by
the authenticated client. CV raw bytes, access tokens, credentials and
presigned URLs are never stored in an application item.

## Mutation rules

- Create accepts an optional `idempotencyKey`; the server persists only its
  hash and returns the original application for a semantic retry.
- Updates require `expectedVersion`; stale writes return `409 VERSION_CONFLICT`.
- Status changes validate the state machine and append a history event in one
  DynamoDB transaction where supported.
- Pagination uses a signed, scope-bound cursor; arbitrary DynamoDB keys are
  not accepted from clients.
- Foreign, missing, or cross-issuer IDs return the same `404 NOT_FOUND` shape
  to avoid resource enumeration.

## Error envelope

```json
{ "error": "human-readable safe message", "code": "VERSION_CONFLICT" }
```

No error response contains credentials, CV content, or DynamoDB expressions.
