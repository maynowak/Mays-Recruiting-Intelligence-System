# Threat Model – Partner User Dual Authentication

## Threats
1. Stolen RIS API Credential → Mitigated by server-side storage, rotation, revocation
2. Stolen user JWT → Limited to token lifetime, no credential exposure
3. Credential used by another partner → Binding to APIProfile + tenant prevents reuse
4. User from another tenant → JWT custom:tenant_id validated, tenant match enforced
5. Expired JWT → API Gateway rejects
6. Revoked credential → verify_api_credential denies
7. Suspended application → Registry status check denies
8. Unauthorized agent → Entitlement check denies
9. Browser exposure of backend secrets → Credential never sent to client
10. JWT substitution → Signature validation prevents
11. Replay → JWT exp + idempotency
12. Concurrent quota bypass → Server-side atomic counters
13. Incorrect tenant mapping → Tenant derived from JWT only
14. Missing user membership → User profile existence check
15. Confused deputy → User identity bound to credential via tenant

## Denial Behavior
All failures fail closed: 401 for auth failures, 403 for authorization failures.

## Monitoring
Authentication failures, credential verification failures logged without secrets.
