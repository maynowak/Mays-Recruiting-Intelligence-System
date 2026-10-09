# RIS Authentication Contract

## Responsibilities
- Mays-Jobsearch: initiate OAuth flow, manage session
- Cognito: identity, token issuance
- Mays-RIS: token validation, authorization

## Token Acceptance
Mays-RIS accepts Cognito Access Token with:
- iss: https://cognito-idp.eu-central-1.amazonaws.com/<user-pool-id>
- aud: <client-id>
- scope: appropriate

## User Identity Propagation
Cognito sub → RIS user_profile table
Tenant ID from custom:tenant_id claim

## Error Responses
401 Unauthorized – missing/invalid JWT
403 Forbidden – insufficient entitlements
