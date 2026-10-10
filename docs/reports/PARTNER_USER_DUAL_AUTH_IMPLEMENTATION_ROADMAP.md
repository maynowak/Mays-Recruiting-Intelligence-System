# Implementation Roadmap – Partner User Dual Auth

## Phase 1 – Design Review
Approve ADR and threat model.

## Phase 2 – API Contract
Define route POST /v1/partner/agents/{agentId}/execute
Document request/response schemas.

## Phase 3 – Runtime Changes
Extend Lambda handler to validate both JWT and RIS credential for partner route.
Enforce user+partner binding.

## Phase 4 – Partner Application Registry
Ensure registry supports user-initiated requests.

## Phase 5 – Vercel Integration
Create server-side proxy route, secure env vars, error handling.

## Phase 6 – Testing
Security tests for dual auth, tenant isolation, credential revocation.

## Phase 7 – Monitoring
Usage accounting metrics per application.

## Phase 8 – GDPR Review
Verify deletion lifecycle covers dual auth.

No AWS mutations in this phase.
