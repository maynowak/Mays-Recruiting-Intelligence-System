# RIS-JOBSEARCH-APPLICATION-ORCH-03A — Document Ownership

## Result: LOCAL PARTIAL PASS

`ApplicationRepository` can now receive the existing `PartnerProfileRepository`
and, when `PARTNER_PROFILE_TABLE` is configured, resolves legacy `profileRef` /
`cvRef` references through the authenticated user, tenant, partner and issuer
boundary. New `documents.cvReference` values are fail-closed when the profile
repository is not configured. `documentId` must match the owned CV document.

ApplicationV1 stores metadata only. No PDF bytes, S3 keys, presigned URLs,
tokens or credentials are copied into ApplicationV1.

## Evidence

- Positive owned CV/document reference: passed.
- Cross-user ownership rejection: passed.
- Document mismatch rejection: passed.
- Missing profile-store dependency for new document reference: passed closed.
- Full ApplicationV1 runtime selection: **48 passed**.

## Remaining boundary

The existing synthetic application harness intentionally carries legacy profile
references without a profile table for backward compatibility. A configured
profile-store Moto fixture and live S3/DynamoDB ownership test remain open for
RIS-DEV. Export/delete remove application metadata only; referenced CV objects
remain governed by the existing profile/document lifecycle.
