# M2M Cost Control – Cognito Client Credentials

## Pricing assumptions (DEV)

- Cognito User Pool: first 50,000 MAUs free, thereafter $0.0055 per MAU. M2M client uses service-to-service tokens, counted as MAU? Client credentials tokens are issued for client_id, not user. AWS counts token issuances, not MAU, for client credentials? Per AWS pricing: Cognito charges per monthly active users for user pools, and per token request for advanced features.

Current scope: only DEV environment.

## Token request costs

- Cognito token endpoint is free for first 50,000 monthly active users; token generation beyond that incurs charges.
- Client credentials grant generates access tokens only (no refresh tokens). Token lifetime default 1 hour.
- Estimated token requests: M2M client will be used by worker Lambda for agent execution. Worker processes SQS batch 5, visibility 300s. Approximate executions per month in DEV: < 10k.

## Token caching strategy

- Lambda handler reuses JWT via API Gateway authorizer cache (TTL 5 min default). No extra calls.
- Client credentials tokens cached in worker memory for token lifetime (1h) to avoid re-request.
- Access token size minimal.

## Number of required M2M clients

- One confidential M2M client per environment: `mays-ris-dev-m2m-client`.
- Production may require separate client per product tenant isolation; current design uses single client with scope enforcement in runtime (scope `ris-api/m2m/execute`).

## Expected DEV monthly costs

- Cognito User Pool MAU: 0 (dev users < 50k)
- Token requests: negligible (< $0.01)
- No additional resource server charges.
- Total estimated DEV monthly cost for M2M auth: <$1.

## Prefer smallest viable implementation

- Single resource server `ris-api`, single scope `m2m/execute`.
- No additional Cognito clients beyond human client and one M2M client.
- No custom domain for Cognito, no extra WAF.
