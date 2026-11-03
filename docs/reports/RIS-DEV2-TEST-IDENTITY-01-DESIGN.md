# RIS-DEV2-TEST-IDENTITY-01 — Identity Design

**Status:** DESIGN COMPLETE / OFFLINE VALIDATION NEXT / APPLY BLOCKED

## 1. Decision

Use the existing Terraform identity architecture with an explicit
`identity_mode = "managed"` overlay for the project `ris-dev2`. Do not modify
the external pool `eu-central-1_ojbmoiYGM` and do not create a second identity
implementation.

The current `identity_mode` implementation is already capable of declaring a
new pool in the Foundation account. No production authentication bypass or
new HTTP authentication seam is required.

## 2. Existing implementation reviewed

`terraform/main.tf` sets `module.cognito.count` to `1` only for managed mode.
The existing `terraform/modules/cognito` module declares:

- a project/environment-named user pool;
- a public Human app client without a client secret;
- `USER_PASSWORD_AUTH` and refresh-token auth;
- optional authorization-code OAuth with explicit callback/logout URLs;
- a tenant attribute `custom:tenant_id` on fresh pool creation;
- an M2M client and `ris-api/m2m:execute` resource scope;
- a prefix domain only when no custom domain is enabled;
- no custom domain, DNS or ACM resource when the DEV2 overlay leaves custom
  domain disabled.

The API module receives the managed pool issuer and client IDs. Both existing
JWT authorizers are therefore updated to validate the managed pool issuer and
corresponding Human/M2M audience. All protected routes continue to use JWT
authorizers; no route becomes anonymous.

## 3. DEV2-specific configuration

The proposed non-secret overlay is limited to `ris-dev2` and will set:

```text
identity_mode = managed
orders_lifecycle = disabled
identity_oauth_enabled = true
identity_oauth_scopes = [openid, email, profile]
identity_oauth_callback_urls = [http://localhost:5173/auth/callback]
identity_oauth_logout_urls = [http://localhost:5173/]
identity_custom_domain_enabled = false
```

The localhost callback is explicit and non-production. API CORS remains at its
existing deployed value to avoid an unrelated API configuration update. No
wildcard origin, custom domain, ACM ARN, DNS record, external IdP, secret, password or token is
stored in the overlay.

## 4. Identity and test-user contract

The managed Human client is public (`generate_secret = false`) and supports
authorization code + PKCE. The existing client also supports the repository's
local/test sign-in flow using `USER_PASSWORD_AUTH`; any future test user must
be created only after a separately approved post-apply operation, with a
synthetic email and synthetic `custom:tenant_id`.

No test user, password, token, client secret or group membership is created by
Terraform in this phase. No user should be added to an administrative group for
ApplicationV1 storage tests.

The M2M client is an existing module contract and is generated with a secret.
That secret is not supplied in Git, reports or command output. The resulting
Terraform state must be treated as sensitive backend state; a plan/apply must
not print or export its value. This is an existing design consideration and
must be explicitly reviewed before approval.

## 5. Partner and credential boundary

Managed Cognito alone does not create an RIS Partner Application Registry
binding, APIProfile or opaque credential. The existing partner routes and
credential contract remain separate. No direct DynamoDB seed, credential issue,
or entitlement grant is included in this identity change.

ApplicationV1 storage itself does not require an agent entitlement. A future
positive partner HTTP E2E run needs a separately approved, isolated partner/
APIProfile/credential provisioning procedure after the pool and authorizers are
deployed.

## 6. Protected-resource boundary

The plan must contain no action for:

- external Cognito pool/account/client;
- CloudFront or OAC;
- Route 53/DNS;
- ACM;
- Jobsearch or `ris-dev`;
- Orders;
- unrelated Lambda, DynamoDB, S3, SQS or privacy resources.

The current external-to-managed switch is potentially state-significant. The
saved plan, not this design, is authoritative for whether existing authorizer
updates are safe and whether any unexpected delete/replacement exists.

## 7. Apply gate

This design authorizes no AWS mutation. The workflow is:

1. add the non-secret `ris-dev2` overlay;
2. run offline validation and regression tests;
3. create one saved plan against the verified `ris-dev2` backend/state;
4. inspect every action and hash the plan;
5. STOP for explicit approval of that exact plan.

No apply, Cognito user creation, partner provisioning or live E2E test is
permitted before that approval.
