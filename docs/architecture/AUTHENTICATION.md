# Authentication Architecture – Mays-RIS & Mays-Jobsearch

## Scope
This document defines the authentication contract between Mays-Jobsearch frontend and Mays-RIS backend, with Cognito as identity provider.

## Current Baseline
- AWS Account: 240571105849
- Region: eu-central-1
- Profile: mayaws
- Project: mays-ris / dev
- Cognito User Pool: DEV environment, Essentials plan
- Custom login domain: auth.mays-job-matcher.app (planned)
- RIS API Gateway JWT Authorizer active for all routes including GET /health

## Authentication Flow
Browser → Mays-Jobsearch → Amazon Cognito → OAuth2 Authorization Code + PKCE → Jobsearch callback → Application session → Mays-RIS API → JWT validation → Tenant/User Profile/Entitlements → Authorized Agent Execution

## Token Usage
- ID Token: client-side user profile
- Access Token: API authorization to Mays-RIS
- Refresh Token: token rotation
- Cognito sub → RIS user identity mapping

## DEV / PROD Separation
DEV: auth.mays-job-matcher.app, existing DEV User Pool
PROD: Separate User Pool, proposed domain auth.mays-job-matcher.com (requires approval)

## Identity & Tenant
- Authoritative tenant source: Cognito custom:tenant_id claim
- Never trust tenant ID from browser
- Mapping: Cognito sub ↔ RIS user profile ↔ entitlements

## Security Requirements
Authorization Code + PKCE, state validation, JWKS rotation, least privilege, secure token storage, CORS, CSRF protection

## Open Decisions
- Login UI approach: Cognito Managed Login vs custom forms integration
- Registration flow ownership
- Production domain final approval
- Tenant provisioning workflow

## References
- docs/architecture/SYSTEM-ARCHITECTURE.md
- docs/api/API-STANDARD.md
