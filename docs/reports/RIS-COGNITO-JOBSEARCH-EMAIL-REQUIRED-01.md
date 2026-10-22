# RIS-COGNITO-JOBSEARCH-EMAIL-REQUIRED-01

**Status:** ANALYSIS
**Date:** 2026-10-22
**Scope:** Separate Cognito Jobsearch User Pool with mandatory email

## Phase 1 — Analysis

### 1. Current Cognito Dependencies
User Pool eu-central-1_ojbmoiYGM
- Name: ris-dev-dev-users
- Clients:
  * ris-dev-dev-client 7ldhihlpdgsgcl3puvu4oi7ksv – Human App Client, OAuth code, callbacks for mays-job-matcher
  * ris-dev-dev-m2m-client – Machine-to-machine
- Custom Domain: auth.mays-job-matcher.app
- Google IdP: Configured via Terraform, optional
- AutoVerifiedAttributes: ["email"]
- Email required: false in schema
- RIS components dependent: Kernel API, Agent Body, Orders integration, API Profiles / Credentials

### 2. Applications Using Existing Pool
- Mays RIS Kernel API authentication
- Mays-Jobs-Matcher frontend via Hosted UI / OAuth
- Mays-Orders integration via OrdersPort
- Admin users via Cognito admin groups
- API Profiles / Credentials auth flow

Shared pool means any change impacts all consumers.

### 3. Implications of Separate Jobsearch Pool
Pros:
- Isolate Jobsearch registration from RIS core
- Enforce email required=true safely
- Independent branding, password policies
- No impact on existing RIS users/admins

Cons:
- New User Pool, new Client IDs, new JWT issuer
- Frontend must change VITE_COGNITO_* env vars
- RIS tenant/entitlement mapping must be re-established
- Separate custom domain or sub-domain required
- Additional cost negligible

### 4. AWS Costs Estimate
Cognito free tier: 50k MAUs free
Beyond: $0.0055 per MAU
Custom domain: $0 + ACM cert
Hosted UI: included
Estimated cost: $0 for dev scale.

### 5. OAuth, Google IdP, Domain Requirements
Separate pool requires:
- New App Client with Authorization Code + PKCE
- Callback/Logout URLs for mays-job-matcher domains
- Optional Google IdP configuration
- Custom domain cannot be shared; needs new domain or sub-domain
- Existing domain auth.mays-job-matcher.app is tied to RIS pool

### 6. Migration & Rollback Plan
Migration:
1. Create new User Pool ris-dev-jobsearch-users
2. Configure email required, auto verification
3. Create App Client with PKCE
4. Configure Hosted UI branding
5. Coordinate frontend switch
6. Run parallel auth

Rollback:
- Keep existing pool untouched
- Frontend env vars revert to old pool
- No data loss

## Recommendation
Separate pool is safe and preserves existing RIS infrastructure.
Proceed to Phase 2 after approval.

Status: Analysis complete, awaiting approval.
