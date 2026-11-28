# RIS-DEV2 Live Canary Preflight — 20A

**Decision: DEPLOYMENT PASS; LIVE CANARY NO-GO / STOP at the 20B approval gate.**
The existing 19F8 harness and order-description contract are suitable as the
test basis, but no verified live test identity/entitlement or billing ceiling
is available. The configured synthetic Analysis validity timestamp has
expired. This run was read-only: **no order, invocation, entitlement write,
queue receive, redrive, AWS mutation, Terraform plan, or Apply**.

## 1. Deployment readiness

Read-only checks on 2026-11-27 confirmed:

- Branch `feature/ris-analysis-integration-07`; local and remote HEAD
  `a496fcddee753fbb61dc3ecdb5cb694dcc5bbc02`.
- AWS account `262370457690`, region `eu-central-1`.
- RIS-DEV2 State serial `76`, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, S3 VersionId
  `M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T`.
- Agent-Worker and Dispatch-Ingress are `Active` / `Successful` and have
  `CodeSha256=UHvBfbny7gky5C3gOaUIqz8B47srVRDqefLlT5WzpY0=`, corresponding to
  Worker ZIP SHA-256
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
- Analysis and Orders-Reader still match 19H code hashes and configuration
  fingerprints. `ANALYSIS_SYNTHETIC_MODE=true` remains set.
- The live Analysis configuration also has
  `ANALYSIS_SYNTHETIC_EXPIRES_AT=2026-11-26T17:40:28Z`, which is in the past
  on this preflight date. It was not changed or renewed.
- Dispatch, work, and result-consumer SQS event-source mappings are enabled;
  the seven relevant queue/DLQ ARNs match State. Read-only queue attributes
  confirmed the configured visibility, retention, and redrive policies.
  No queue message API was called; message contents and counts were not read.
- `POST /orders` and owner `GET /orders/{orderId}` are API Gateway JWT routes
  using the configured Cognito issuer/client audience. No access token was
  obtained or stored.
- The existing Worker configuration points the ATS adapter at
  `https://mays-jobsearch.vercel.app`; `agents/ats_agent/agent.py` posts the
  job/profile to `/api/ats-analysis`. A future live run therefore causes an
  outbound call to that separate Mays Jobsearch service; synthetic data
  handling and any service-side cost must be explicitly approved.

Machine-readable, non-secret deployment evidence is in
`docs/reports/evidence/20A/deployment-readiness.json`.

## 2. Identity, entitlement, and cost gates

### Authentication

The deployed order-create and owner-read routes require a Cognito JWT. That
proves route configuration only; it does not prove that an approved test user
or a usable token exists. 19F8’s local harness uses an in-memory fake owner,
profile, and claims. It is not a live Cognito identity or authorization test.
No live test subject or active owner-bound APIProfile was supplied or verified.
No user list or entitlement table was scanned, and no credentials were
requested or committed.

### Entitlement

19F8’s harness injects an in-memory `ats-agent` entitlement without testing a
live entitlement record, expiration, tenant binding, or available balance.
Consequently a current entitlement for the selected test identity,
`ats-agent` / `analyze.job`, and the matching tenant is **not established**.
No grant was created, extended, or modified.

Separately, the deployed Analysis Lambda’s configured synthetic-validity time
expired on 2026-11-26. If the approved workflow relies on that internal
synthetic Analysis allowance, 20B must not proceed until a separately
authorized owner resolves that expiry and a later read-only preflight verifies
the resulting live configuration. This 20A task did not renew it.

**Required separate authorization/evidence:** an authorized owner must identify
an existing synthetic Cognito subject and existing ACTIVE APIProfile through
an approved secure channel; attest that owner and tenant bindings match; and
provide read-only evidence of an active, unexpired `ats-agent` / `analyze.job`
entitlement for that same owner/tenant. If any entitlement must be granted or
renewed, that requires a separate explicitly scoped authorization and task;
20A does not authorize the write.

### Billing and external service

The draft below uses one ATS item with `unitPrice: 1`, currency EUR, solely as a
schema-valid proposal. The meaning/charge treatment of that value, whether a
test SKU is non-billable, any Mays-Orders billing side effect, and the ATS
service’s usage costs were not verified. **No price or maximum cost is approved.**
The Mays-Orders owner must confirm the exact test SKU/price semantics and an
explicit maximum charge; the Jobsearch service owner must approve one request
with synthetic-only data. No zero-cost assumption is made.

## 3. 19F8 contract reuse and blocked canary draft

19F8 is reused as requested: its existing E2E test covers Create 201, exact
`orderDescription` persistence/readback, dispatch, WorkItem, the initial claim,
agent execution, signed `ORDER_RESULT`, result consumption, `COMPLETED`, owner
GET 200, and foreign-owner denial. The extended E2E is a **local mocked test**
(DynamoDB/SQS/HTTP boundaries are faked); original Mays `orderDescription`
tests passed 15/15 at source commit
`db4f9e79980443de1cd3d5b688a33c0cf0eb771f`. Neither result is live entitlement,
external ATS, billing, or production readback evidence.

A synthetic schema-valid draft is recorded in
`docs/reports/evidence/20A/canary-contract.json` with a new correlation ID and
idempotency key. It targets `ats-agent` / `analyze.job`, has one `ATS` item,
synthetic job/profile input, and a canonical serialized AgentOrder V1 in
`orderDescription` (545 characters, below the 1,024-character limit). It has
**two deliberate execution blockers**: `apiProfileRef` is an unresolved
placeholder because no approved live profile is known, and the proposed price
has no approved billing ceiling. Its recorded payload hash is only for the
placeholder draft; after secure profile resolution, the exact final payload
must be regenerated, hashed, and included in the separate 20B approval.

The payload uses only reserved example contact data and synthetic job text.
It does not include a real candidate, employer, vacancy, token, or credential.
The serialized AgentOrder is sent only through `orderDescription`; no root
`agentOrder` field is added to the Mays OrderV1 body.

## 4. 20B observation contract (proposed; not authorized)

If—and only if—identity, entitlement, synthetic-validity, external-service,
price/cost, payload, and explicit 20B approval gates pass:

1. Submit **one** authenticated `POST /orders`. Require HTTP 201 and exact
   `orderDescription` in the create response. Any timeout, ambiguous response,
   non-201 result, or missing/mismatched description is STOP. Never retry the
   create; do not infer that an ambiguous request failed.
2. Correlate exclusively by the approved `requestId`/correlation ID,
   idempotency key, and returned order ID. Dispatch is expected through the
   existing dispatch queue/event mapping, then to the shared work queue and
   Agent-Worker mapping. Do not read or receive SQS messages.
3. Use only narrowly scoped read-only CloudWatch observations for the exact
   correlation/work ID to distinguish initial claim from actual ATS agent
   execution. Require evidence of execution; `CLAIM_WITHOUT_EXECUTION`, missing
   execution evidence, or any unexpected identity is STOP.
4. Require successful synthetic-only ATS analysis; a correctly signed
   `ORDER_RESULT`; successful result-consumer processing; and public
   `processing.status=COMPLETED`.
5. Poll only the authorized owner GET endpoint, at most once every 20 seconds,
   for at most 15 polls / five minutes after the create response. Require HTTP
   200 and byte-for-byte/string-exact `orderDescription` equality. At timeout,
   terminal error, or mismatch, STOP: no retry, recovery, cleanup, or redrive.
6. Overall wall-clock cap: 10 minutes from the single create attempt. No
   additional orders, Lambda direct invocation, queue receive/delete/visibility
   change, DLQ access, or automated retry. Capture only status, IDs, hashes,
   and redacted correlation evidence; never tokens, secrets, job-candidate PII,
   or full external response bodies.

This is a proposed observation limit, not execution authority. The exact 20B
approval must separately authorize one order and the single asynchronous
execution it triggers.

## 5. Separate 20B approval template — NOT GRANTED

The following approval must be completed by the authorized service and budget
owners **after** all blockers are resolved. Blank/placeholder fields mean NO-GO.
Do not put credentials or personal identity data in Git.

```text
I explicitly authorize one RIS-DEV2 synthetic live canary (20B), at most one
authenticated POST /orders and its single queue-driven agent execution, followed
by read-only observations only.

Account / region / workspace: 262370457690 / eu-central-1 / ris-dev2
Branch / reviewed source HEAD: feature/ris-analysis-integration-07 /
  a496fcddee753fbb61dc3ecdb5cb694dcc5bbc02
Worker bundle SHA-256:
  507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d
Mays source commit: db4f9e79980443de1cd3d5b688a33c0cf0eb771f
Test subject: [identify only through approved secure channel; do not paste token]
APIProfile owner/tenant binding evidence: [reference]
Entitlement evidence for ats-agent / analyze.job, expiry and remaining scope:
  [reference; must already be active; no implicit grant/renewal]
Analysis synthetic allowance valid-through: [must be after execution window]
Final exact payload SHA-256: [recompute after resolving profile placeholder]
Correlation ID: corr-20a-9f959f34d8cf42c4be70636fb247ea35
Idempotency key: idem-20a-673c5a7706f34aeb88ad4aa4d988c0c2
Approved ATS test SKU / unit price / currency: [Mays owner confirmation]
Maximum total charge, including external ATS usage: [explicit amount/currency]
Mays Jobsearch owner approval for synthetic outbound request: [reference]
Observation cap: 10 minutes total; <=15 owner GET polls, 20-second interval
STOP behavior: no POST retry; no direct invoke; no queue receive; no redrive,
  recovery, cleanup, or automatic rollback. Ambiguous create = STOP.
Approver(s), role, timestamp, and approval reference: [required]

Approval decision: NOT GRANTED by this 20A preflight.
```

## Final gates

| Gate | Result |
|---|---|
| `DEPLOYMENT_IDENTITY` | PASS — account, region, branch, State, Lambda hashes/status and mappings verified |
| `SYNTHETIC_MODE` | PASS for flag (`true`); **BLOCKED** for expired synthetic validity timestamp |
| `AUTHENTICATION_READINESS` | BLOCKED — JWT route configured; no approved live test identity/profile/token evidence |
| `ENTITLEMENT_READINESS` | BLOCKED — 19F8 is mocked; active live owner/tenant-bound entitlement not verified |
| `CANARY_CONTRACT` | PASS as a local contract/draft only; live execution blocked |
| `ORDER_DESCRIPTION_CONTRACT` | PASS — serialized AgentOrder V1, 545 chars; exact live roundtrip remains unproven |
| `OBSERVATION_READINESS` | PASS as bounded proposal; no observation executed |
| `BILLING_SCOPE` | BLOCKED — price semantics, maximum charge and external usage cost unapproved |
| `LIVE_CANARY_READINESS` | **NO-GO — do not execute 20B until separate approvals/evidence are complete** |
| `NEW_ORDERS` | 0 |
| `LIVE_INVOCATIONS` | 0 |
| `REDRIVES` | 0 |
| `AWS_MUTATIONS` | 0 |
| `TERRAFORM_APPLIES` | 0 |

The pre-existing unstaged
`docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json` was not
touched. **STOP at the 20B live-execution approval gate. No automatic
continuation.**
