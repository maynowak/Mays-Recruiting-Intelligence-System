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

### DSGVO-03 — Provider contract compliance and subject linkage

**Ownership:** Mays-Orders owns provider capability and source changes; RIS owns consumer contract verification and adapter requirements. Separate repositories/PRs.
**Depends on:** approved resolver/ref and tenant contract (D02-04/05), provider owner response to 02B CR drafts, policy for data scope and retention, exact immutable pin confirmation.
**Tasks:** consume provider `inspect_subject`, `export_subject`, `erase_subject`; verify current pin support and distinguish current provider Main from the pin. Resolve, with the provider, trusted subjectRef delegation on create, direct-Lambda invoke authorization/secret contract, and operation outcome semantics. Do not recreate provider operations or change the pin. Mark unsupported subject binding and legacy rows `BLOCKED/UNAVAILABLE`; no body-provided identity and no backfill.
**Acceptance:** source/contract matrix at both SHAs; provider original tests cited (not duplicated); written provider-owner disposition of CR-01/02; exact input/output/auth/error/partial semantics documented. No implementation or test pass implied. See `DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md`.

### DSGVO-04 — RIS Privacy Adapter

**Ownership:** RIS privacy/runtime owner; Orders owns its privacy execution and status.
**Depends on:** DSGVO-03 provider-supported contract, approved subject resolver and policy; separate RIS runtime authorization.
**Tasks:** add a RIS-side adapter to the existing resumable operation path only. Invoke provider internal actions using approved IAM + secret handling; preserve action permission and project scope; gate EXECUTE separately from PREVIEW; map COMPLETED/PARTIALLY_COMPLETED/BLOCKED and transport-unknown faithfully; prevent blind execute retries without provider reconciliation. Persist only minimized evidence. Do not implement Orders inspect/export/erase logic in RIS.
**Acceptance:** synthetic adapter contract, auth/secret negative cases, tenant/scope isolation, preview nonmutation, explicit execute gate, timeout/partial/resume handling and no false global completion. No provider secret or payload in receipts.

### DSGVO-05 — XRepo Integration Tests

**Ownership:** RIS QA owner and Mays-Orders test owner; each repository runs its own suite.
**Depends on:** approved provider contract and exact source SHAs; isolated child-process jobs.
**Tasks:** reuse provider Lambda unit suites and RIS compatibility tests; add only RIS-to-provider contract cases: create binding, inspect/export lookup, erase preview, authorized execute outcome, spoof denial, action auth, timeout ambiguity and partial result. Do not develop a new shared framework or run provider AWS E2E.
**Acceptance:** synthetic fixtures only, exact SHA manifest, tests assert provider semantic statuses not merely invocation/HTTP success; missing/skipped integration test fails the gate. No test is run under this documentation work order.

### DSGVO-06 — Unified Privacy QA

**Ownership:** RIS CI owner plus Mays-Orders CI owner; Jobsearch only where its contracts participate.
**Depends on:** stable 03–05 contract vectors and native test commands; CI owner approval.
**Tasks:** reuse `scripts/unified_tests.py`/existing compatibility workflow and provider-native unit suite. Execute RIS, provider and XRepo jobs in separate processes/checkouts with explicit immutable SHAs; do not inject provider source into RIS-native jobs or provide ambient AWS credentials. Keep Jobsearch API tests explicit if in scope. Distinguish current integrated pin from provider Main; no implicit upgrade.
**Acceptance:** blocking on missing SHA, skipped suite, or boundary failure; evidence manifest identifies commands, exact source SHAs, fixture type and artifacts. Green CI is technical evidence only, not legal, deployment or live-state approval.

### DSGVO-07 — Provider Integration Review / Acceptance

**Ownership:** RIS coordinator, Mays-Orders provider owner, Security/Privacy reviewers.
**Depends on:** approved decisions and 03–06 implementation/test work in separately authorized PRs; no pin upgrade unless explicitly scoped elsewhere.
**Tasks:** review synthetic provider contract evidence and per-domain outcomes; confirm source provenance and unresolved gaps; obtain provider disposition for separate CRs. No live invocation, deployment, real PII or production approval in this package.
**Acceptance:** exact SHA matrix, provider-owned test evidence, RIS adapter evidence and explicit blocked/partial limitations. Human review remains separate from CI.

### DSGVO-02B — Provider alignment supersession

The provider-specific contract, evidence distinctions, RIS adapter design and separate unsubmitted provider change requests are consolidated in [`DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md`](DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md). Where earlier 02A wording could be read as assigning Orders privacy implementation to RIS, this provider-first work-order set supersedes that interpretation. No provider feature is reimplemented in RIS.

## 5. Contract, migration and RED/GREEN test plan (proposal; provider scope clarified by 02B)

This section remains a proposed test/migration design, not authorization. For Mays-Orders, its implementation and native tests belong to the provider repository; RIS work is limited to consumer contract tests and adapter behavior. The provider-specific split and the fact that trusted subject delegation is currently unsupported are defined in [`DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md`](DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md). No provider changes or pin upgrades are implied by the test vectors below.

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
