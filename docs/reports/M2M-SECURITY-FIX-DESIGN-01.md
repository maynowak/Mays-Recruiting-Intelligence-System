# M2M Security Fix – Design Decision M2M Client / APIProfile Binding

## Context
Checkpoint W02-M2M-SECURITY-FIX-01 requires a server-side authoritative binding between the authenticated Cognito client and an APIProfile used with a RIS credential.

Current state:
- Single shared confidential M2M client `mays-ris-dev-m2m-client` with client_credentials flow.
- Resource server `ris-api` with scope `ris-api/m2m/execute`.
- API Gateway now uses two JWT authorizers:
  - `jwt` → human client audience
  - `jwt_m2m` → M2M client audience + scope enforcement on `POST /v1/m2m/agents/{agentId}/execute`
- Runtime verification `verify_api_credential` validates credential → APIProfile → tenant/owner → entitlement → agent catalog. It does NOT inspect Cognito `client_id` or scope.

## Options evaluated

1. Enforce `clientRef` binding for M2M requests
   - Extract `client_id` from Cognito JWT in Lambda, compare to APIProfile `clientRef`.
   - Pros: uses existing field, server-side, no schema change.
   - Cons: `clientRef` was explicitly decided as metadata-only in RIS-CREDENTIAL-CONTRACT-03. Re-interpreting it as security binding is a contract change without prior decision. With a single shared M2M client, `clientRef` would be identical for all partners → no isolation.

2. Per-partner confidential clients
   - Create one Cognito user pool client per partner, each with its own `client_id` and secret.
   - Map `client_id` → allowed `apiProfileId` / tenant in a new binding table or via `clientRef` populated per partner.
   - Pros: true partner identity, server-side authoritative, aligns with OAuth2 best practice.
   - Cons: requires architectural decision and client provisioning process; exceeds scope of “do not redesign APIProfile/Credentials/Entitlements”.

3. Keep credential-only binding, rely on gateway isolation
   - Gateway isolates human vs M2M routes via separate authorizers + scope.
   - Credential verification provides tenant/owner/entitlement isolation.
   - Pros: smallest change, preserves existing contracts.
   - Cons: does not bind a specific M2M client to a specific APIProfile; a valid M2M JWT can be used with any valid RIS credential.

## Decision
**DESIGN DECISION REQUIRED** – The binding requirement cannot be satisfied safely with the current single shared M2M client and existing `clientRef` metadata-only contract.

- Current implementation satisfies route isolation and scope enforcement at gateway level.
- APIProfile binding to Cognito client identity is not enforced in runtime.
- Changing `clientRef` from metadata to security enforcement is a contract decision and must be reviewed before implementation.
- Per-partner confidential clients are recommended for production partner isolation.

Implementation stops at this point for the binding component. Terraform isolation and documentation updates are complete and safe.

## Impact
- Human route isolation: PASS via separate authorizer.
- M2M route isolation: PASS via dedicated authorizer + `authorization_scopes`.
- Tenant isolation: PASS – unchanged, enforced by `verify_api_credential`.
- Credential revocation: PASS – unchanged.
- M2M client / APIProfile binding: DESIGN DECISION REQUIRED.

Next steps pending orchestration review.
