# ADR — Persistent ApplicationV1 in RIS

**Status:** Accepted for implementation; privacy retention gates open

## Decision

Persist applications in a dedicated DynamoDB table owned by RIS, using the
existing verified JWT/tenant/partner/issuer context and existing profile/CV /
privacy repositories. Use a server-generated application ID, conditional
writes, optimistic versions, scoped GSIs, and resumable erasure checkpoints.

Expose the logical Jobsearch application API under
`/v1/partner/me/applications`; do not create a parallel `/api` authentication
or profile system.

## Alternatives rejected

- Browser/local-only storage: not durable or suitable for privacy access/delete.
- A second Cognito/profile system: duplicates identity and breaks tenant
  isolation.
- Raw CV storage in the application table: violates minimisation and existing
  document ownership boundaries.
- Automatic cover-letter/model calls: outside persistence scope and requires a
  separate consent/purpose decision.

## Consequences

The application table adds an independently deployable data resource and IAM
permissions. Existing data remains untouched. Privacy export/delete must be
extended deliberately; no global erasure feature flag is enabled by this ADR.

## Open approvals

Legal basis, retention periods, backup deletion, special-category handling,
DPIA requirement, and external-partner controller roles remain explicit
approval points documented in `APPLICATION-V1-PRIVACY-MATRIX.md`.
