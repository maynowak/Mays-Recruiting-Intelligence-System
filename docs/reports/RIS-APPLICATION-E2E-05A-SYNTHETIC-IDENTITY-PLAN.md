# RIS-APPLICATION-E2E-05A — Synthetic Identity Provisioning Plan

**Decision:** **PROVISIONING BLOCKED**

Phase 05A was completed as read-only discovery and plan design. Phase 05B was
not authorized and was not executed.

## 1. Executive summary

The deployed ApplicationV1 contract can support a minimal synthetic positive
E2E context without an agent entitlement. The required storage boundary is:

```text
Cognito access JWT
  + active RIS APIProfile / opaque X-Api-Credential
  + active Partner Application Registry binding
  + matching tenant and server-derived iss + sub identity
```

The current `ris-dev2` tables contain zero active partner applications, API
profiles, credentials and entitlements. No explicitly authorized synthetic
Cognito user or secure credential handoff is available. The plan is therefore
concrete but not executable until the external Cognito owner and authorized
provisioning operator provide a separate Phase 05B approval.

```text
PROVISIONING BLOCKED
```

## 2. AWS/repository checkpoint

| Check | Result |
|---|---|
| Repository root | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1` |
| Branch | `feature/ris-application-persistence-v1` |
| Actual HEAD | `b377ca8479dac02571e98309719642ccf3d09205` |
| Working tree | Clean at discovery start |
| AWS profile/account/region | `default` / `262370457690` / `eu-central-1` |
| Workspace | `ris-dev2` |
| State serial/lineage | `24` / `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Terraform | No plan, init, validate, refresh or apply run |
| Protected infrastructure | No mutation performed |

The previously deployed ApplicationV1 table/GSI, nine JWT routes, Lambda and
health baseline remain outside this plan's write scope.

## 3. External Cognito ownership

The live API Gateway JWT authorizer and Terraform state agree on:

| Element | Verified reference |
|---|---|
| Identity mode | `external` |
| Pool ID | `eu-central-1_ojbmoiYGM` |
| Issuer | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM` |
| Human audience/client | `7ldhihlpdgsgcl3puvu4oi7ksv` |
| Pool ARN owner account | `240571105849` |
| Foundation account | `262370457690` |

The target Foundation account cannot describe this external pool and returned
`ResourceNotFoundException` for a direct pool lookup. No cross-account role,
user, password, confirmation, client, OAuth or domain operation was attempted.

The external pool's current human OAuth flow, scopes, password policy, MFA and
custom-attribute write policy are **BLOCKED for this session**. They must be
confirmed by the authorized owner before Phase 05B. The deployed authorizer
requires a valid access token with `token_use=access`; the runtime needs
`sub`, `client_id` (or the validated audience path), `iss`, and a tenant that
resolves consistently. If `custom:tenant_id` is present, it must match the
server-side credential/registry tenant.

## 4. RIS dual-auth contract

The inspected implementation establishes these checks:

1. API Gateway validates JWT signature, issuer, expiry and audience before the
   Lambda is invoked.
2. The partner route requires `token_use=access` and a non-empty verified `sub`.
3. `X-Api-Credential` is parsed separately from `Authorization`; the raw
   credential is not logged or returned.
4. The credential resolves to an APIProfile. The profile must be usable and
   contain owner and tenant context.
5. The Cognito client ID resolves through the Partner Application Registry.
6. Registry `status=ACTIVE`, registry `apiProfileId == credential profile`, and
   registry `tenantId == credential tenant` are required.
7. The owner is server-derived from verified JWT `sub` and the request cannot
   supply an alternative owner or tenant.
8. ApplicationV1 builds its context from `userId`, resolved tenant, partner
   application ID and JWT issuer.

### Entitlement decision

ApplicationV1 calls `_partner_profile_context`, which uses credential/profile
resolution and partner-registry checks. Its storage routes do **not** call
`verify_api_credential` or the agent entitlement resolver. The handler comment
explicitly states that agent entitlements are not reused as storage permission.

Therefore the minimal ApplicationV1 test context requires **no new agent
entitlement**. Creating an entitlement would add unnecessary authority and is
not part of this plan.

## 5. Existing test identities and bindings

| Item | Discovery result |
|---|---|
| Authorized synthetic Cognito user | Not found / not provided |
| Secure local JWT handoff | Not found |
| Active partner application | `0` active rows observed |
| Active APIProfile | `0` active rows observed |
| Active credential | `0` active rows observed |
| Active entitlement | `0` active rows observed |
| Second identity/tenant/partner/issuer | Not available |

Historical reports and historical users are not authorization and were not
reused. No token, password, credential secret, browser session or secret-bearing
file was read.

## 6. Minimal isolated test-partner context

The proposed future context is deliberately narrow:

| Element | Planned value/constraint |
|---|---|
| Environment | `ris-dev2` only |
| Human identity | One dedicated synthetic external-pool user, owner-approved |
| Tenant | Dedicated synthetic test tenant, e.g. `ris-e2e-application-v1`; exact value requires owner approval |
| Human client | Existing verified client `7ldhihlpdgsgcl3puvu4oi7ksv`; no new client |
| Partner application | Dedicated synthetic registry record, status `ACTIVE` |
| APIProfile | Dedicated profile owned by the synthetic `sub`, status `ACTIVE` |
| Credential | Existing opaque `opaque-bearer-v1`, short expiry, once-only secure handoff |
| Agent entitlement | None for ApplicationV1 storage |
| Data | Synthetic application fields only; no CV, real resume, PII or model call |
| Scope | ApplicationV1 CRUD/export/delete and authorized privacy checks only |

The test tenant must not overlap with an existing productive tenant. If the
external pool cannot safely issue an isolated synthetic identity/tenant claim,
the alternative is a separately approved isolated identity environment; no new
pool or client is created by this plan.

## 7. Planned write operations for separately approved 05B

These are a checklist, not executable authorization:

### External Cognito owner operation

1. Create one clearly labeled synthetic user in the existing external pool.
2. Set a temporary random password through the owner-approved method, or use
   the owner's approved OAuth test flow.
3. Confirm/verify the user only if required by the existing pool policy.
4. Set the approved synthetic tenant attribute if the pool contract supports it.
5. Obtain an access JWT through the existing human client and approved flow.
6. Do not create a client, pool, domain, OAuth setting or production user.

The owner must provide the approved OAuth flow/scopes and a secure token
handoff. No password or token belongs in Git, reports or logs.

### RIS APIProfile operation

Use the existing administrative contract, not a raw DynamoDB write:

1. Create a dedicated profile through the authorized `POST /v1/apiprofiles`
   path or the existing `tools/ris_admin apiprofile create` path with its
   authorization-file trust anchor.
2. Bind the profile owner to the synthetic Cognito `sub`; use only the
   operator-authorized test tenant.
3. Activate it through the existing lifecycle API/CLI with an explicit test
   reason.

The operator authorization mapping must prove that the operator is allowed to
write this test tenant. Profile creation must not alter existing profiles.

### Partner registry operation

Use the existing `ris_admin partner create` wrapper around the atomic
`create_partner_application` contract, with:

- a dedicated synthetic `applicationId`;
- the verified human client ID;
- the newly created APIProfile ID;
- the dedicated synthetic tenant ID.

The registry writer atomically creates the application and client reservation
and stores `status=ACTIVE`. It must not be replaced with an ad-hoc
`PutItem`. A prior review must confirm that this CLI path is the approved
cross-account administrative mechanism; otherwise provisioning remains blocked.

### Credential operation

Use the existing `ris_admin credential issue` contract against the active
profile:

- short explicit `expiresAt` within the approved test window;
- synthetic label and reason;
- secure output file supplied by the approved operator;
- no stdout secret, report value, Git file or CloudWatch value;
- verify only metadata and status, never the raw value after handoff.

The credential is `opaque-bearer-v1`, prefixed `ris_`, digest-backed and
once-only. Revoke it through the existing credential lifecycle before final
cleanup or on any failure.

## 8. Credential security and failure handling

- Store the once-only credential only in an approved local secret channel;
- restrict file permissions and remove it after revocation/verification;
- never put it in React/frontend code, Terraform state, logs, reports or Git;
- use a short expiry and explicit terminal revoke;
- if credential output succeeds but the handoff fails, do not re-issue blindly;
  locate the metadata and revoke the created credential through the approved
  lifecycle, then issue a new one only after review;
- if any partial resource remains, stop and record its non-secret identifier;
  do not guess or bulk-delete.

## 9. Phase 05C test matrix

### Positive identity and ApplicationV1

With the approved JWT and partner credential, execute only synthetic requests:

1. Create and verify server-generated ID, `draft` status, version and timestamps;
2. Get and list under the authenticated owner;
3. Create enough synthetic records for pagination and verify signed cursor
   binding to user, tenant, partner, issuer and scope;
4. Patch allowed fields and verify version increment;
5. Submit stale `expectedVersion` and verify conflict;
6. Exercise valid/invalid status transitions, history and ordering;
7. Add cover-letter versions and verify prior versions remain immutable;
8. Repeat create with the same idempotency key and verify no duplicate;
9. Reuse the key with a different payload and verify contract rejection;
10. Export and verify only the synthetic owner's application data;
11. Delete through the API, then verify Get/List behavior;
12. Revoke the partner credential and confirm subsequent access is denied.

### Isolation

Full live isolation requires additional explicitly approved fixtures:

- second synthetic user for cross-user;
- second tenant for cross-tenant;
- second partner application/client for cross-partner;
- second issuer only if an already-approved separate issuer exists.

No productive user or foreign tenant may substitute for these fixtures. Without
a second issuer, cross-issuer AWS evidence remains `BLOCKED`; local negative
coverage is separate evidence only.

### Privacy

Use the same synthetic context for authorized Privacy Inspect and Export. Verify
ApplicationV1 completeness, history and cover-letter versions, absence of
foreign data, and API-level cleanup. Only if an isolated, approved durable
erasure fixture and executor are available may resumability/idempotency be
tested. No global erasure flag may be enabled.

## 10. DSGVO/test-data safety and cleanup

- Test purpose: technical verification of ApplicationV1 authorization and CRUD;
- data: synthetic job reference, synthetic status/history, synthetic cover-letter
  text only;
- no real names, emails, CVs, resumes, job applications or documents;
- test identity and tenant explicitly labeled and time-bounded;
- cleanup order: delete ApplicationV1 records through the API, verify absence,
  revoke credential, deactivate partner registry record, disable/revoke profile,
  then remove the external synthetic Cognito user through the authorized owner;
- if a cleanup step fails, report `SYNTHETIC CLEANUP INCOMPLETE` with only
  non-secret resource identifiers;
- no direct DynamoDB deletion and no foreign-resource cleanup.

Cleanup is not executable under this 05A-only authorization.

## 11. Risks and blockers

1. **External Cognito owner handoff missing:** account ownership is identified
   as `240571105849`, but current session has no authorized cross-account user
   provisioning method.
2. **OAuth details unavailable:** flow, scopes, confirmation and tenant-claim
   policy require owner confirmation.
3. **No active RIS context:** partner/APIProfile/credential stores are empty for
   active rows.
4. **Registry administration approval missing:** the existing CLI is a concrete
   contract, but its use for this new test context needs explicit operator
   authorization.
5. **Isolation requires more identities:** one user cannot prove all requested
   cross-boundary cases.

Protected Cognito, clients, domain/OAuth, CloudFront/OAC, DNS/Route53, ACM and
existing RIS data remain unchanged.

## 12. Phase 05B approval template

Phase 05B may start only after an explicit approval records all of the
following:

- authorized owner/account for external Cognito operations;
- exact synthetic username/reference and permitted tenant scope, without
  placing passwords/tokens in Git;
- approved existing human client and OAuth flow/scopes;
- authorized RIS operator and authorization-file handoff;
- permission to create one APIProfile, one partner registry binding and one
  short-lived credential;
- confirmation that no entitlement, new client, pool, domain, Terraform plan,
  or protected-resource change is allowed;
- secure credential handoff, expiry, revoke and cleanup procedure;
- explicit stop/rollback handling for partial creation;
- separate approval for a second identity/tenant/partner if isolation evidence
  is required.

Until all items are approved:

```text
PROVISIONING BLOCKED
```

No general production approval, GDPR approval, Jobsearch integration approval
or infrastructure-change authorization is implied.
