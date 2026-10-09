# MAYS-RIS-PARTNER-PORTAL-FOUNDATION-01

## Executive Summary
Partner Developer Portal can be built on existing RIS architecture: Cognito, APIProfile, Credential, Offers, Entitlements, Agent Registry. Core backend components are implemented and tested. Missing: Partner-facing UI, application registration workflow, product catalog UI, credential management UI, API Playground.

## Existing System Verification
IMPLEMENTED:
- Cognito authentication and JWT authorizer
- APIProfile domain agents/ecosystem/api_profiles.py
- Credential lifecycle agents/ecosystem/credentials.py
- Offers and Entitlements agents/ecosystem/offers.py
- Agent Registry / Discovery / Execution
- Tenant isolation
- HTTP routes for APIProfile, Credential, Agent execution

TESTED:
- APIProfile CRUD, lifecycle, selection
- Credential issuance, rotation, revocation
- Entitlement evaluation
- Verification chain

DEPLOYED:
- Cognito DEV User Pool
- API Gateway with JWT authorizer
- DynamoDB tables for work items, agent catalog, etc.

MISSING:
- Partner registration UI
- Application registration workflow
- Product catalog UI
- Credential management UI
- API Playground
- Partner dashboard

## Partner Registration
Reuse user_profile for partner identity. APIProfile ownership maps to partner organization via ownerUserId + tenantId. No new tables required. Partner organization can be represented as tenantId + organization metadata in user_profile.

## Partner Dashboard Screens
1. Partner Registration – Cognito hosted UI
2. Login – Cognito hosted UI
3. Dashboard – list applications
4. My Applications – read APIProfile list
5. Create Application – create APIProfile PENDING
6. Product Catalog – list offers
7. Product Entitlements – request grants
8. API Credentials – issue/rotate/revoke credentials
9. Agent Catalog – discover agents
10. API Documentation – OpenAPI
11. API Playground – test agent execution

## Credential Generation
Reuse existing credential lifecycle. One-time secret display, digest storage, rotation, disable/enable/revoke, expiration, audit logging all implemented.

## Product Authorization
Chain Partner -> Application -> APIProfile -> Product/Offer -> Entitlements -> Agent Capabilities enforced via existing verification chain. Cognito JWT required, API Credential required, product status checked, entitlements evaluated, agent eligibility checked.

## Multi-Product Support
Architecture supports multiple independent APIProfiles per tenant with separate credentials and entitlements. Isolation enforced via tenantId and ownerUserId.

## Integration Contract
Machine route POST /v1/m2m/agents/{agentId}/execute requires Authorization: Bearer <Cognito JWT> + X-Api-Credential. External partner backends require Cognito client credentials flow or assumed role. Current Cognito clients are user-facing. Server-to-server Cognito token acquisition needs evaluation.

## Implementation Roadmap
P1 Partner identity and ownership – reuse user_profile
P2 Application registration – APIProfile creation workflow
P3 APIProfile provisioning – admin approval
P4 Product selection and approval – offers/entitlements
P5 Credential generation UI – reuse credential lifecycle
P6 Agent catalog and API documentation
P7 API Playground
P8 Usage and administration

## Security Blockers
P0: Server-to-server Cognito token acquisition for partners not verified. Existing clients are user-facing.
P1: No partner onboarding UI, manual admin steps required.
P2: Missing audit UI for partner actions.

## Next Checkpoint
MAYS-RIS-PARTNER-PORTAL-MVP-01 – implement partner application registration and credential issuance UI.
