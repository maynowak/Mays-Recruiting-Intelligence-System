# RIS-APPLICATION-E2E-06A — Harness Design & Security Boundary

**Result:** **PASS — LOCAL HARNESS DESIGN READY / DEV2 BLOCKED**

## 1. Scope

This phase defines a local ApplicationV1 integration harness. It does not add
production code, authentication bypasses, HTTP routes, Lambda environment
variables, Cognito identities, partner bindings or Terraform resources.

## 2. Existing seams reused

The harness reuses the existing test-only seams already present in the
repository:

- `jobsearch.application_repository.ApplicationRepository`;
- `jobsearch.application_contract.ApplicationContext`;
- existing Moto DynamoDB table shape and `gsi-owner` fixture;
- existing `ApplicationErasureExecutor` contract;
- existing contract/security tests for identity-field rejection and scoped
  ownership.

`ApplicationContext` is an explicitly trusted internal repository input. The
harness constructs it only inside the test process with deterministic synthetic
values. It does not make this context injectable through the deployed handler,
API Gateway, Lambda events or any public endpoint.

## 3. Security boundary

### LOCAL mode

- runs only under the local test runner;
- uses Moto/in-memory AWS mocks and static local-only test configuration;
- never calls the real AWS SDK endpoint;
- never creates or validates JWTs;
- never calls API Gateway or Lambda;
- never disables production credential verification;
- uses synthetic owner, tenant, partner and issuer references only.

### DEV2 mode

DEV2 is a separate, explicit mode and is not enabled by the local tests. It may
only use the existing `ris-dev2-dev-applications` table after a separate
live-mutation approval. It may not touch Cognito, partner tables, APIProfiles,
credentials, entitlements, Terraform state, CloudFront, DNS, ACM or any other
RIS resource.

Without that approval, DEV2 is **BLOCKED** and no live write is attempted.

## 4. Synthetic fixture contract

The local fixture uses stable, non-personal values such as:

- user: `synthetic-user-application-v1-a`;
- tenant: `synthetic-tenant-application-v1`;
- partner: `synthetic-partner-application-v1`;
- issuer: `https://synthetic.invalid/issuer/application-v1`;
- job IDs: `synthetic-job-application-v1-*`;
- synthetic cover-letter text with no names, emails, documents or credentials.

Server-generated application IDs remain server-generated and are never supplied
by the client fixture.

## 5. Planned local coverage

The local integration suite covers:

- create/get/list/update/delete;
- status transitions and explicit submit confirmation;
- history and immutable cover-letter versions;
- version conflicts and concurrent stale writes;
- idempotent create and payload mismatch;
- signed pagination cursors, tampering, expiry/shape rejection and identity
  binding;
- cross-user, cross-tenant, cross-partner and cross-issuer isolation;
- client identity-field rejection;
- export/privacy scoping and absence of internal ownership fields;
- resumable/idempotent ApplicationErasureExecutor behavior and failure
  propagation;
- cleanup of only the local Moto table's synthetic records.

No test claims Cognito, API Gateway authorizer, partner credential or public
HTTP authentication behavior. Those remain blocked by the 05B authorization
gate.

## 6. DEV2 preflight and live mode

The later 06C read-only preflight must verify account `262370457690`, profile
`default`, region `eu-central-1`, workspace `ris-dev2`, state serial `24`,
state lineage, table name, GSI and IAM scope. A successful preflight alone does
not authorize writes.

06D requires a separate explicit approval. Until then:

```text
DEV2 DATA TEST BLOCKED
```

No live data is read or mutated by 06A.
