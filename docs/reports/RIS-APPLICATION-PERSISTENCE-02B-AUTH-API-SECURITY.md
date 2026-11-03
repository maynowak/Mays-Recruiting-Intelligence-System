# RIS-APPLICATION-PERSISTENCE-02B — Auth/API Security

**Status:** VERIFIED for offline route and boundary contracts

## Verified

- All nine ApplicationV1 API Gateway routes use the existing JWT authorizer.
- Lambda resolves the existing partner credential, active Partner Registry,
  tenant and issuer through `_partner_profile_context`.
- Application payloads reject `applicationId`, `ownerId`, `userId`, `tenantId`,
  `partnerApplicationId`, `issuer` and email-based identity fields.
- Foreign resources are intentionally represented as `404 NOT_FOUND`.
- Version/idempotency conflicts have stable `409` codes.
- Application handlers do not invoke agents or models.

## Browser boundary

Mays-Jobsearch must not receive a static `X-Api-Credential`. A trusted backend
or approved session-bound broker must attach the credential; otherwise the
handoff remains offline/session-only. No browser credential bypass is added.

## Evidence

`tests/test_application_api_security.py` verifies route authorization and
handler boundary reuse. OpenAPI/runtime parity remains covered by the existing
platform contract suite. JWT signature/issuer/audience verification itself is
owned by API Gateway and is not faked by local unit tests.
