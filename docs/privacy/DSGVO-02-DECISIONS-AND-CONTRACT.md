# DSGVO-02 — Privacy Decision Package and XRepo Subject Identity Contract

**Package state:** DOCUMENTATION COMPLETE; DECISION GATE OPEN.
**Technical implementation:** NOT STARTED / NOT AUTHORIZED.
**Evidence baseline:** RIS `e25e900667a18f9123a89a2ea7fdc0ca96e7b553`; Mays-Orders pin `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; Jobsearch Main reviewed `c298d223e38407781b4f63426be9f9228ccb4467`. This document proposes contracts and work orders; it does not change any repository integration contract or legal position.

## 1. Decision statement

The current system does not have a demonstrated, complete cross-repository subject key. Mays-Orders privacy functions query `gsi2pk = SUBJECT#<subjectId>`, while the RIS dispatch evidence says its AgentOrder rows do not carry `gsi2pk`/`subjectId`. Mays-Orders auth ownership uses verified `(iss, sub)` and derives a SHA-256 `owner_key`, but that Orders owner key is not proven to be a RIS↔Jobsearch canonical subject ID. Jobsearch has a separate site identity boundary; matching email, equal-looking `sub`, or client-provided IDs are not acceptable identity joins.

**Decision requested:** approve one canonical identity-resolution model and its owner before DSGVO-03 implementation. Until then, subject-linked cross-repository inspect/export/erase must report `PARTIAL`/`BLOCKED`, never `COMPLETE`.

## 2. Proposed XRepo Subject Identity Contract (draft v1)

### Identity inputs and trust

1. Each source service authenticates its caller and derives a native principal from verified server-side issuer + subject (`iss`, `sub`); tenant is derived from trusted server-side context. Email, profile fields, browser values, request timestamps and raw client subject IDs are not identity proof.
2. A cross-service association between RIS and Jobsearch principals requires a separately approved, authenticated account-linking/subject-resolution flow. Neither repository may assume the separate site Cognito pools identify the same person.
3. Only the designated identity resolver may create a canonical cross-repository mapping. Mapping creation, removal, conflicts and audit evidence require an approved policy. No raw `iss`, `sub`, email or CV data is sent to Mays-Orders as an index key.

### Opaque reference proposal — decision required

Candidate canonical reference:

```text
subjectRef = "sref:v1:" + BASE64URL_NO_PADDING(
  HMAC-SHA-256(K_v1,
    UTF8("MAYS-PRIVACY-SUBJECT\0" + tenantRef + "\0" + canonicalPrincipalRef)))
)
```

`canonicalPrincipalRef` is an internal resolver output bound to the authenticated source principal(s), not a client field. `K_v1` is a dedicated purpose-scoped secret, not a general application/API secret. `tenantRef` is normalized server-side and included to prevent unintended cross-tenant linkage. Each service treats `subjectRef` as opaque, versioned and sensitive pseudonymous data; it is not anonymous data and is not proof of consent.

This keyed design is a proposal, not an accepted cryptographic or operational choice. Privacy, Security and platform owners must decide: HMAC vs existing unkeyed SHA-256 owner-key reuse; resolver ownership; tenant inclusion/normalization; secret storage/access/rotation/compromise recovery; whether all systems can receive the same reference; and the handling of future identity/tenant changes. Never substitute raw `sub` or email to avoid a blocker.

### Propagation and record rules

- Resolver issues the reference only after verified identity and permitted mapping; service-to-service calls authenticate the caller independently and bind requested `subjectRef` to authorized scope. A caller may not enumerate arbitrary references.
- Proposed Orders mapping: store `subjectId = subjectRef`, `gsi2pk = "SUBJECT#" + subjectRef`, with required GSI sort key `gsi2sk` per an approved deterministic record ordering. Apply to every in-scope order write/update path, including retries, result transitions, manual/admin writes and supported imports. Confirm exact key semantics against Orders schema before implementation.
- Never overwrite `ownerKey`/order ownership semantics with a privacy reference. Ownership authorization and privacy discovery are separate concerns.
- RIS WorkItems, results, profiles, application records, document metadata and operation records must either carry a service-local subject association resolvable by the coordinator or declare a bounded unsupported/retention result.
- Receipts and logs contain opaque operation references and minimal categories only, not the raw identity tuple, HMAC key, raw CV, prompt, token, or object key.
- API responses report a per-domain outcome (`COMPLETE`, `PARTIAL`, `BLOCKED`, `UNAVAILABLE`) and evidence level. Global completion is only possible after every required domain is verified or an explicitly approved legal exception is recorded.

### Compatibility and versioning

This is a proposed contract version, not a public endpoint change. Existing `OrdersPort`, generated module outputs, HTTP APIs, `AgentOrder` schema and result transport remain protected until separately approved. The Mays-Orders pin remains exact. Any implementation requiring schema changes must be additive/backward-compatible, versioned and tested against the integrated pin. Do not hand-edit generated modules.

### DSGVO-02A technical resolution (proposal supersedes HMAC as default)

The parallel technical review recommends **a persistent random opaque `subjectRef` plus a protected identity-mapping registry** as the preferred direction for owner decision. The HMAC construction above remains an alternative only; neither design is approved. A persistent reference avoids having every downstream index depend on a rotating derivation secret and can support rediscovery after a native login, but it requires a durable, access-controlled, recoverable mapping.

Draft mapping requirements: key each native principal by source/service namespace + normalized verified issuer + subject, with trusted tenant binding; never use email. The resolver returns a high-entropy opaque `subjectRef` only after normal authentication. Linking a second principal from another site/pool requires separately verified control of both accounts and an approved user-facing linking flow. Mapping data is sensitive personal data, not anonymous; access, retention, backup/restore, unlink/conflict and DSAR semantics must be decided. Orders uses the ref only for its privacy lookup index; keep its owner key/GSI3 authorization unchanged.

If a durable mapping is rejected, owners must explicitly choose a versioned keyed HMAC alternative and decide key custody, rotation/dual-resolution, tenant normalization, compromise recovery and historic reindex. A raw `sub`, email, or existing unkeyed `owner_key` is not an acceptable automatic substitute. See [DSGVO-02A review](DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md) for rationale and evidence.

## 3. Operator, legal and security decisions (must be recorded)

| ID | Decision | Required decision owner | Current state / blocker |
|---|---|---|---|
| D02-01 | Controller/processor/joint-controller allocation per RIS, Orders, Jobsearch, each provider and activity | Privacy/Legal + product/service owners | OPEN; no technical inference |
| D02-02 | Article 6 basis per purpose; Article 9 condition/safeguards for CV-derived special categories; profiling/automated-decision assessment | Privacy/Legal | OPEN; candidate bases are not decisions |
| D02-03 | Consent necessity/validity, withdrawal effects, notices, purpose registry alignment and actual rollout scope | Privacy/Legal + product owners | OPEN for general use; technical pilot references do not imply broad approval |
| D02-04 | Canonical principal resolver and secure account-linking method across separate identity pools | Identity/Security + RIS/Jobsearch owners | OPEN; no cross-pool equivalence may be assumed |
| D02-05 | SubjectRef algorithm, version/tenant scope, key owner, key rotation and recovery | Security + platform + service owners | OPEN; proposed HMAC is unapproved |
| D02-06 | Retention/erasure schedule, legal holds, receipt/ledger duration and backup expiry | Privacy/Legal + service/platform owners | OPEN; existing TTL/config is not policy |
| D02-07 | DSAR workflow, verification, timeline, exceptions, response format and contact route | Privacy/Legal + support owner | OPEN |
| D02-08 | Processor/subprocessor list, DPAs, locations and international-transfer safeguards | Procurement/Legal + service owners | OPEN; active deployed provider map not confirmed |
| D02-09 | DPIA requirement and, if required, completed assessment/consultation | Privacy/Legal/controller | OPEN; pre-screen is not a DPIA |
| D02-10 | Authorization for any historical data discovery/backfill, production change, live synthetic exercise or release | Named system owner + release approver | NOT GRANTED by this task |

## 4. Follow-up implementation work orders

### DSGVO-03 — Mays-Orders subject linkage and DSAR

**Ownership:** Orders `lambda/src/order_service.py`, `index.py`, `order_types.py`, tests and import behavior owned by Mays-Orders; RIS `agents/orders/real.py`, dispatch/result producer and compatibility tests owned by RIS. Separate changes/PRs; no generated module edits.
**Depends on:** approved resolver/ref and tenant contract (D02-04/05); legal field/retention policy (D02-01/02/03/06); source pin/module contract reconfirmed.
**Tasks:** cover `create_order`, `_create_agent_order`, dispatch/result/status/SQS updates and seed/import path; add subject discovery attributes without changing ownerKey/GSI3; permit only trusted service-context propagation (never request-body passthrough); enumerate/sanitize nested `agentOrder`, `processing.result`, customer and owner fields under policy; make legacy rows explicitly unresolved or mapped via verified mapping; prepare but do not run backfill. GSI2 is already declared; verify schema, do not assume new Terraform is needed.
**Acceptance:** synthetic producer tests for every write path; retries/results preserve index; no spoof/bypass; privacy queries find created fixtures; export excludes internals/secrets; anonymization asserts complete residual field state; migration counts and unresolved category reconcile. Extend Orders `test_order_service.py`, `test_order_description.py`, `test_ownership.py`, `test_index.py`, `test_result_handoff.py`, `test_result_consumer_lambda.py`, seed tests as applicable and RIS `test_agent_order_dispatch_e2e.py`, `test_real_orders_adapter.py`, `test_orders_reader.py`. See review §B.

### DSGVO-04 — RIS privacy orchestration

**Ownership:** RIS privacy/runtime and data-store owners; service calls remain scoped to Orders/Jobsearch owners.
**Depends on:** approved D02 identity/policy; DSGVO-03 linked lookup and DSAR outcome contract.
**Tasks:** extend existing `ErasureOperationV1`/operation repository/checkpoint and G5/domain executors; add explicit Orders and Jobsearch adapter contracts, per-domain terminal state and evidence; preserve write-freeze, idempotency, retry/resume, tenant authorization; do not duplicate erasure engines or start execution before separate approval.
**Acceptance:** original RIS privacy tests listed in review §C; synthetic adapter contract, missing-adapter blocker, failure/resume, scope denial and no false global completion. Receipts/checkpoints contain opaque minimal evidence only.

### DSGVO-05 — retention, backup, queue and security

**Ownership:** RIS platform/operations, Orders/Jobsearch operators and Security; Privacy/Legal decides policy.
**Depends on:** D02 legal/retention/processor decisions; 03/04 category inventories. Policy/design can proceed in parallel; implementation requires separate task authorization.
**Tasks:** cover S3 versions/PITR/ledger/restore, WorkItems/results/SQS/DLQ, CloudWatch/CloudTrail, receipts, caches/providers and internal secrets; define no-resurrection, stale-message, PII minimization, rotation/revocation and evidence expiry. Do not run redrive or AWS actions.
**Acceptance:** approved schedules/exceptions, synthetic-only restore/queue/security tests and explicit residual-state reporting. No live state proof inferred. See review §C/D.

### DSGVO-06 — Unified Privacy CI/CD gate

**Ownership:** RIS CI owner with Orders and Jobsearch CI owners.
**Depends on:** approved contract vectors; gate implementation consumes stable 03–05 tests. Gate design may start now.
**Tasks:** reuse RIS pinned Unified QA runner and native Orders unittest/Jobsearch npm tools; separate repository jobs/processes and exact SHAs; run Jobsearch API node tests explicitly (Vitest excludes `api/**`); fail closed on skipped/unavailable coverage; publish provenance manifest. No shared writable checkout or new test framework.
**Acceptance:** synthetic-only CI blocks on fail/skip/missing SHA, contains no ambient AWS credentials and produces auditable result; manual human gate remains separate. See review §D.

### DSGVO-07 — Synthetic XRepo acceptance

**Ownership:** coordinator plus all three repository owners; Security and Privacy review.
**Depends on:** approved D02 identity/legal/operational decisions; 03–06 implemented and reviewed in separate authorized PRs at immutable SHAs.
**Tasks:** new synthetic subject lifecycle from identity proof/link through every Orders write, RIS adapter, Jobsearch consent/storage boundary, export/erase, queue/result, retained data and backup restore; reconcile record counts and each partial/excluded outcome.
**Acceptance:** exact SHA matrix; original and new suites; cross-tenant negatives; complete per-domain evidence or approved exception; no false completion or restore resurrection; human sign-off. No live redrive/deployment or real PII.

## 5. Contract, migration and RED/GREEN test plan

### Contract tests

- **RED baseline (expected to fail against current gap):** RIS-produced synthetic AgentOrder lacks Orders `subjectId`/`gsi2pk`; Orders inspect/export/erase query returns no RIS-created fixture even though ownership fields exist. This is an expected gap test, not a claimed current test execution.
- **GREEN target:** each producer persists the exact approved versioned `subjectRef`, GSI partition/sort values; all mutations preserve or deliberately remove it; direct user-supplied identifiers are ignored/rejected; service credential + authorized operation scope are both required.
- Deterministic test vectors: use synthetic issuer, subject and tenant plus injected fixed test key. Assert same input/same ref; issuer, subject, tenant, version or key change changes ref; normalization only as approved; no raw tuple in emitted order/receipt. Never put a production secret in fixtures.
- Ownership/privacy separation: wrong owner cannot mutate/read; authorized privacy job can find by subject index without weakening ordinary owner checks; one tenant cannot query another tenant's ref.
- Export/anonymization: public projection excludes internal DynamoDB keys, credential material and unrelated owner data; test all nested AgentOrder fields, description and result snapshots per approved field policy.

### Migration / compatibility rehearsal (plan only)

1. Freeze approved source/schema versions and define a read-only inventory query/reconciliation method. No scan or production read is authorized by DSGVO-02.
2. Classify legacy Orders as mappable only where a verified server-side identity mapping exists; otherwise mark unresolved and retain as blocked, not guessed by email.
3. Produce counts and duplicate/conflict report in a synthetic/local fixture; calculate index/backfill impact and rollback path; ensure dual-read compatibility during any separately approved migration.
4. Future migration would require a separately scoped approval, dry-run artifact/hash, idempotent conditional writes, throttling/cutover/rollback plan, no public exposure of subject keys, post-write reconciliation and audit record. This document does not authorize it.

### Required original suites and additions

| Repo | Reuse original tests | Add after implementation (not run now) |
|---|---|---|
| RIS | `tests/test_agent_order_dispatch_e2e.py`, `tests/test_partner_privacy_inspection.py`, `tests/test_privacy_erasure_contract.py`, `tests/test_privacy_erasure_repository.py`, `tests/test_privacy_erasure_security.py`, `tests/test_application_privacy_contract.py`, `tests/test_application_erasure.py` | producer-wide subject-ref contract; retry/result update preservation; adapter-level cross-tenant contract; all-store completeness and partial/resume tests |
| Mays-Orders | `lambda/tests/test_order_service.py`, `lambda/tests/test_index.py`, `lambda/tests/test_result_handoff.py`, `lambda/tests/test_result_consumer_lambda.py` | every create/update/import path indexes subject; cursor pagination/coverage; export redaction; anonymize embedded fields; legacy unresolved accounting; rotation/auth-negative tests |
| Mays-Jobsearch | Current Main's consent/API tests and CI (`npm run build`, API syntax checks, `npm test`) per its repo instructions | identity-linking proof contract; no identity joins by email; consent-purpose ↔ RIS version mapping; storage/export/delete boundary status; synthetic provider/cache outcomes |

Test execution must use each repository's own supported isolated workflow and exact pins. Orders E2E needing deployed AWS is not a local gate and is excluded absent separate authorization. No test is claimed as run or passing in DSGVO-02.

## 6. Stop/approval gate

This package is complete as a proposal, not as an approved contract. Required next action is named owner review of D02-01…D02-10 and approval/rejection/versioning of the identity design. **STOP HERE.** DSGVO-03 through 07 are prepared work orders only. No code, schema, migration, secret, Terraform, AWS, deployment, queue, Main merge or real-person data processing is authorized.
