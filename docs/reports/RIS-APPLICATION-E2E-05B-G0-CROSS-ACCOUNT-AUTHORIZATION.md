# RIS-APPLICATION-E2E-05B-G0 — Cross-Account Authorization

**Decision:** **05B PROVISIONING BLOCKED**

This checkpoint was read-only. No Cognito user, password, group, client, role,
partner application, APIProfile, credential, DynamoDB item, Terraform artifact,
token or API mutation was created. No foreign AWS profile was tried.

## 1. Executive summary

The external Cognito ownership boundary is now unambiguous, but no authorized
cross-account provisioning path is available in the current session. The
Foundation `default` profile is limited to account `262370457690`; the local
AWS configuration contains no additional profile, and no documented role-hop
for the external owner account was verified.

The RIS APIProfile and credential routes are deployed, but a valid RIS admin
principal and authorization mapping are not present. The external Human OAuth
flow and secure token handoff are also not currently verifiable.

```text
COGNITO OWNER AUTHORIZATION BLOCKED
OAUTH TEST FLOW BLOCKED
RIS ADMIN PROVISIONING BLOCKED
CREDENTIAL HANDOFF BLOCKED
05B PROVISIONING BLOCKED
```

## 2. RIS account/state checkpoint

| Check | Result |
|---|---|
| Repository root | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1` |
| Branch | `feature/ris-application-persistence-v1` |
| HEAD | `6544208e343d2cb5acbf1fa0a576aa5f50fd0e2a` |
| Working tree | Clean at start |
| AWS profile | `default` only |
| STS account | `262370457690` — PASS |
| Region | `eu-central-1` — PASS |
| Terraform workspace | `ris-dev2` — PASS, read-only |
| State serial | `24` — PASS |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` — PASS |
| Terraform operations | None executed |

## 3. Cognito ownership and authorization

### Verified identity contract

| Element | Value/status |
|---|---|
| Owner account | `240571105849` — verified from the state pool ARN |
| Pool | `eu-central-1_ojbmoiYGM` |
| Issuer | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM` |
| Human client/audience | `7ldhihlpdgsgcl3puvu4oi7ksv` |
| Foundation account | `262370457690` |

The target-account Cognito lookup returned `ResourceNotFoundException`, which
is consistent with the pool being external. No cross-account role assumption
was attempted because no explicitly documented role, purpose-bound principal,
or approved profile for this test was found.

### Existing authorization evidence

- The repository contains historical references to the external account and
  older `mayaws` operations, but historical reports are not current
  authorization and the local AWS configuration exposes only `[default]`.
- No owner-authorized test-provisioning principal was documented for this
  ApplicationV1 test.
- No minimal IAM policy, trust relationship, role ARN, or approved owner
  handoff was provided for a future `cognito-idp` read/write operation.
- No user, password, group, tenant attribute, OAuth configuration or existing
  access credential was inspected or changed.

**Result: `COGNITO OWNER AUTHORIZATION BLOCKED`**

## 4. OAuth/JWT contract

### Verified from live RIS authorizer and code

- API Gateway uses the external issuer above and human audience/client
  `7ldhihlpdgsgcl3puvu4oi7ksv`;
- the runtime requires a Cognito **access** token (`token_use=access`) and
  verified `sub`;
- the partner context uses `client_id`, with server-side registry resolution;
- `custom:tenant_id`, if present, is authoritative and must not contradict the
  registry/credential tenant;
- API Gateway validates issuer and audience before Lambda; no caller-supplied
  owner or tenant is trusted;
- the deployed API authorizer does not provide evidence of OAuth callback or
  token issuance configuration by itself.

### Missing current evidence

The external pool could not be described from the RIS account. Consequently,
the following were not verified for the current pool/client:

- allowed human OAuth flows;
- PKCE/callback/logout configuration;
- allowed scopes and token endpoint behavior;
- access-token lifetime;
- MFA/verification requirements;
- whether the synthetic `custom:tenant_id` attribute can be set by the owner
  procedure.

Historical M2M `client_credentials` evidence is not used as Human OAuth
evidence and does not establish a valid ApplicationV1 user token flow.

**Result: `OAUTH TEST FLOW BLOCKED`**

## 5. RIS admin provisioning

### Live route availability

Read-only API Gateway discovery found 12 deployed JWT-protected management
routes under `/v1/apiprofiles`, including:

- APIProfile create/list/get/patch/status;
- credential issue/list/get/rotate/disable/enable/revoke.

All use the existing authorizer `9i4w8r`. Route presence is not an
authorization grant.

The Partner Application Registry has no public admin route in the inspected
API surface. Its existing code contract is wrapped by `tools/ris_admin partner
create`, which performs the atomic registry operation. This is not an
authorization to execute it.

### Required RIS authorization

The existing `ris_admin` contract fails closed unless all of these are present:

1. the authenticated AWS principal is obtained through STS;
2. a local authorization JSON mapping exists;
3. the mapping is owned by the invoking user and not group/other writable;
4. the exact principal is mapped to an allowed role and tenant;
5. the operation is authorized for that role and tenant.

No authorization file was present at the documented local candidate paths, and
no matching RIS admin handoff was available. No API call was made because a
valid admin JWT/credential was not available either.

The minimal future RIS sequence would be:

1. create a dedicated APIProfile through the existing admin API/CLI;
2. activate it with an explicit test reason;
3. register the human client, APIProfile and synthetic tenant through the
   existing atomic partner-registry contract;
4. issue one short-lived opaque credential to a secure once-only destination;
5. verify metadata only, never print or log its value.

No agent entitlement is needed for ApplicationV1 storage and must not be added
as unnecessary authority.

**Result: `RIS ADMIN PROVISIONING BLOCKED`**

## 6. Secure credential handoff

The credential implementation provides a suitable future contract:

- opaque `opaque-bearer-v1` value;
- raw value generated once and not recoverable from stored digest;
- secure output destination required by the admin CLI;
- no secret in standard output, audit fields or logs;
- explicit expiry and terminal revoke operations.

However, no approved operator, secure output destination, local injection
mechanism, or revocation owner was provided for this test. No credential was
generated or read.

Required future handoff controls:

- owner-approved local secret channel outside Git;
- restrictive file permissions and bounded lifetime;
- no React/frontend, Terraform state, report or CloudWatch exposure;
- explicit revoke before cleanup and on every partial-failure path;
- secret destruction confirmation without recording the secret value.

**Result: `CREDENTIAL HANDOFF BLOCKED`**

## 7. Minimum permissions for a future approval

These are planning requirements only and are not granted by this report.

### External Cognito owner

For one synthetic user only, the owner would need a tightly scoped approved
administrative path for the existing pool, potentially including:

- create the dedicated synthetic user;
- set/confirm the synthetic user's authentication state through the approved
  owner procedure;
- set the approved synthetic tenant attribute;
- obtain/delete the synthetic user during cleanup.

No group membership, client creation, pool change, OAuth change, domain change
or access to existing users is required for ApplicationV1 storage tests.

### RIS operator

The existing RIS admin contract requires tenant-scoped authorization for:

- APIProfile create and activation;
- partner registry create/deactivate;
- credential issue and revoke;
- metadata-only verification and cleanup.

No direct ad-hoc DynamoDB write, Terraform permission, CloudFront/DNS/ACM
permission, Cognito owner permission or agent entitlement is required.

## 8. Final authorization matrix

| Gate | Ergebnis | Fehlender Nachweis |
|---|---|---|
| RIS Account Guard | PASS | — |
| Cognito Owner Authorization | **BLOCKED** | Owner-approved principal/role and purpose-bound cross-account access |
| OAuth Test Flow | **BLOCKED** | Current human flow, scopes, PKCE/callback and token handoff |
| RIS Admin Provisioning | **BLOCKED** | Authorized RIS operator and valid authorization mapping/JWT |
| Credential Handoff | **BLOCKED** | Approved secure destination, injection and revoke procedure |
| ApplicationV1 Storage Scope | **VERIFIED** | Existing handler contract; active bindings still absent |
| Agent Entitlement | **NOT REQUIRED** | — |

## 9. Required next steps

Before requesting Phase 05B approval, obtain and record references—not secret
values—for:

1. the external Cognito owner's authorized test-provisioning principal and
   permitted pool scope;
2. current human OAuth flow/scopes and a secure access-token handoff;
3. the RIS operator principal and tenant-scoped authorization mapping;
4. the approved `ris_admin`/registry sequence and cleanup owner;
5. short expiry, terminal revoke and partial-failure handling;
6. separate approval for additional identities required by cross-user,
   cross-tenant and cross-partner isolation tests.

Until then:

```text
05B PROVISIONING BLOCKED
```

No production, GDPR, Jobsearch or protected-infrastructure approval is implied.
