# ADR-2026-10-10: M2M Client / APIProfile Authoritative Binding

## Status
PROPOSED – Awaiting architecture review

## Context
Mays-RIS uses Cognito for authentication and opaque RIS credentials for product-level authorization. M2M access currently uses a single shared confidential Cognito client with client_credentials flow. Route isolation is achieved via separate API Gateway authorizers. No server-side binding exists between a Cognito M2M client identity and a specific APIProfile.

Requirements:
- Server-side authoritative binding
- No partner-controlled mapping
- No authorization through `clientRef` metadata
- No cross-tenant / cross-product credential reuse
- Support rotation, revocation, suspension, deletion

## Decision
Adopt per-partner, per-application confidential Cognito M2M clients with an explicit Partner Application Registry.

Mapping chain:
```
Cognito User Pool Client (client_id, client_secret)
   -> Partner Application Registry record
        partner_id, application_id, cognito_client_id, api_profile_id, tenant_id, status
   -> APIProfile (apiProfileId)
        ownerUserId, tenantId, status, clientRef [optional metadata]
   -> Credentials (credentialId -> apiProfileId)
   -> Entitlements (userId/tenantId -> agentId)
   -> Agent Catalog
```

Authoritative binding is enforced at runtime in the Lambda handler:
1. API Gateway validates JWT and enforces scope `ris-api/m2m/execute` on machine route.
2. Lambda extracts `client_id` claim from JWT `aud`/`client_id`.
3. Lambda looks up Partner Application Registry by `client_id`.
4. Registry record must be ACTIVE and match `tenant_id` of the credential-derived APIProfile.
5. Credential verification proceeds as before. If registry lookup fails or status is SUSPENDED/DELETED, request is rejected 403.

`clientRef` remains metadata only. It is not used for security decisions.

## Existing infrastructure reuse
- DynamoDB `api-profiles`, `credentials`, `entitlements`, `user-profile` tables remain unchanged.
- No schema changes to existing tables.
- New table required: `partner-applications` with PK `applicationId`, GSI `gsi-client` on `cognitoClientId`.

Minimal schema:
- applicationId PK
- partnerId
- cognitoClientId UNIQUE
- apiProfileId
- tenantId
- status [ACTIVE|SUSPENDED|DELETED]
- createdAt, updatedAt, createdBy, updatedBy

## Operational model
- Provisioning: Terraform creates Cognito client per partner application via installer. Registry record created via admin API.
- Rotation: Cognito client secret rotation creates new secret, old secret remains valid until explicit revocation. Registry record updated atomically.
- Suspension: Set status SUSPENDED → all tokens still validate at Gateway but runtime rejects.
- Deletion: Set status DELETED, revoke all credentials linked to apiProfileId, disable Cognito client.

## Quotas and complexity
Cognito User Pool client quota: 500 per user pool standard. Per-partner client model scales to ~500 partners. For larger scale, use per-environment pools.

Pricing: Cognito client credentials tokens are free within MAU limits. Operational complexity increases with client lifecycle management.

## Consequences
+ Server-side authoritative binding
+ Partner isolation
+ Auditability
- New table and provisioning workflow required
- Client lifecycle management added

## GDPR notes
Partner Application Registry contains partner identifier and application metadata. May be personal data if partner is a natural person. Retention follows partner contract lifecycle.
