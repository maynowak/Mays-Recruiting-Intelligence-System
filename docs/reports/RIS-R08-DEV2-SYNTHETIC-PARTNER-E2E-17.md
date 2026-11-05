# RIS-R08-DEV2-SYNTHETIC-PARTNER-E2E-17

## Final decision

**BLOCKED at Phase A — no temporary partner or credential was created.**

The existing provisioning code is safe and fail-closed, but the required
operator trust anchor is unavailable in this session:

```text
RIS_ADMIN_AUTHORIZATION_FILE_SET=NO
```

Because credential issuance and revocation require this tenant-scoped
authorization mapping, creating partial profile/registry records would risk an
unrevocable or unowned test credential. The requested test therefore stopped
before any AWS mutation.

## Environment guard

| Check | Result |
|---|---|
| AWS profile | `default` |
| Account | `262370457690` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` (no Terraform command executed) |
| Git HEAD | `f97487c` |
| Partner registry item count | 0 |
| API profile item count | 0 |
| Credential item count | 0 |
| Cognito/configuration/CloudFront/DNS | unchanged |

## Phase A — existing provisioning contract

The existing code was inspected; no parallel key management was introduced.

### API Profiles

`tools/ris_admin/apiprofiles.py` creates a server-generated `aprof_...` profile
with owner and tenant derived from the authenticated admin actor. New profiles
start `PENDING`; `PENDING -> ACTIVE` is an admin-only lifecycle transition.
The CLI has no tenant override for the operator actor.

### Partner Registry

`agents/ecosystem/partner_registry.py:create_partner_application` uses the
existing DynamoDB `TransactWriteItems` contract. It atomically writes the
application record and a `CLIENT#<cognitoClientId>` uniqueness reservation.
The registry binds:

```text
cognitoClientId -> applicationId -> apiProfileId + tenantId
```

No direct DynamoDB write was used.

### Credential issuance

`agents.ecosystem.credentials.issue_credential`:

* requires an existing usable ACTIVE profile;
* generates a random once-only secret;
* stores only the digest in DynamoDB;
* requires an expiry no later than the profile expiry;
* writes the plaintext only to a caller-supplied secure output destination;
* returns no secret on idempotent duplicate reuse;
* requires an authorized admin or permitted owner actor.

The CLI explicitly refuses to print secrets and requires `--output-file`.

### Revocation

`revoke_credential` is terminal, audited and immediately effective. The next
verification denies the credential; no cache is used. It requires the same
authorized actor boundary and a reason is recorded.

### Runtime dual-auth

Partner ApplicationV1 routes require:

```http
Authorization: Bearer <Cognito access JWT>
X-Api-Credential: <opaque RIS credential>
```

The deployed Lambda requires `token_use=access`, resolves the credential by
digest, checks ACTIVE credential/profile state and expiry, then cross-checks
`apiProfileId` and `tenantId` against the active Partner Registry. A present
JWT tenant claim must not contradict the server-side tenant. Identity remains
`iss + sub`; email is not an owner key.

### IAM

The previously verified DEV2 Lambda IAM policy scopes partner/profile/credential
access to the named DEV2 tables and required indexes. No IAM policy or role was
changed in this phase.

## Dry-run evidence

The existing CLI dry-run paths were exercised successfully for API profile
creation, credential issue and credential revoke. Each reported no mutation.
The real commands were not run because `RIS_ADMIN_AUTHORIZATION_FILE` is not
available.

## Tests not executed

The following gates remain **BLOCKED**, not passed:

| Gate | Status | Reason |
|---|---|---|
| Test Partner Provisioning | BLOCKED | no authorized admin trust anchor |
| Credential Authentication | BLOCKED | no temporary credential |
| JWT + Partner Binding | BLOCKED | no registry/profile binding |
| Metrics | BLOCKED | prerequisite credential absent |
| ApplicationV1 | BLOCKED | no authenticated partner context; no data created |
| Credential Revocation | BLOCKED | no credential to revoke |
| Cleanup | PASS — no-op | no test resources were created |
| Cognito Changes | NONE | no pool/client/configuration mutation |
| Jobsearch Changes | NONE | read-only boundary preserved |
| Gate B | NO-GO | integration evidence still absent |
| Production | BLOCKED | no production authorization |

## Required unblock

Provide an already-authorized, tenant-scoped `RIS_ADMIN_AUTHORIZATION_FILE`
for the AWS principal `arn:aws:iam::262370457690:user/devnemo`, or have an
authorized operator execute the existing provisioning lifecycle. Do not create
or self-sign this file in the test session.

After that prerequisite is independently available, the next run may create
one short-lived synthetic profile/registry/credential, run the bounded DEV2
E2E, revoke the credential, and verify all three metadata stores return to
their pre-test state.

No real Jobsearch key was read, changed or required.
