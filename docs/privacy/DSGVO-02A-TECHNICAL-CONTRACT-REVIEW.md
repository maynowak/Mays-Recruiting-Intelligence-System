# DSGVO-02A — Parallel Technical Contract Review

**Status:** Technical evidence consolidated; proposed contract awaits owner decisions.
**Review baseline:** RIS `77e215282a661b5c1ce7dcb66d703e1eb4432212`; Orders `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; Jobsearch Main `c298d223e38407781b4f63426be9f9228ccb4467`.
**Method:** four independent read-only reviews; no tests run and no source files edited.

## A — Identity architecture review

### Verified contracts

- RIS derives user identity from verified JWT `sub`, issuer, and tenant context; erasure scoping includes user and tenant (`lambda/handler.py`; application erasure route and context helpers). Subject is not a client-provided body field.
- Mays-Orders `OwnerIdentity` treats `(normalized iss, sub)` as its ownership principal and derives `owner_key = SHA256(normalized_iss + NUL + sub)` (`lambda/src/identity.py`). Stored owner fields include issuer/subject and the owner key (`lambda/src/order_service.py`). The owner index is GSI3 and serves authorization/ownership; it is distinct from privacy lookup.
- Orders privacy operations query GSI2 using `gsi2pk = SUBJECT#<subjectId>` (`lambda/src/order_service.py::inspect_subject/export_subject/erase_subject`). That subject identifier is not shown to be the same thing as the Orders owner key or RIS user ID.
- Jobsearch BFF validates its own configured issuer/client and uses its verified native issuer/subject when calling RIS (`api/_lib/ris/auth.mjs`, `applicationsHandler.mjs`, `accountErasureHandler.mjs`). Jobsearch has a separate site identity boundary. No evidence supports joining accounts by email or coincidentally matching `sub`.

### Options and recommendation

| Option | Advantages | Risks/limitations |
|---|---|---|
| Raw `sub` as shared key | Small code delta | Issuer collisions; leaks a stable raw identifier; does not solve distinct Jobsearch/RIS principals; **not recommended**. |
| Reuse Orders unkeyed `owner_key` | Reuses an existing issuer-aware stable hash | It is ownership-specific and unkeyed; does not prove RIS/Jobsearch mapping, tenant semantics, or privacy-purpose separation; algorithm compatibility/legacy raw owner fields remain. |
| Persisted opaque random subject ID plus protected identity mapping | Decouples durable reference from source identity; key rotation does not reindex every record | Requires authoritative mapping store, account-linking proof, lookup/restore/backup controls, uniqueness and unlink/conflict lifecycle. **Minimal-risk preferred if a resolver already exists or is approved.** |
| Draft versioned tenant-scoped HMAC SubjectRef | Deterministic, no raw principal in subject index, can domain-separate and scope tenant | HMAC does not link separate accounts; key rotation/compromise, key availability, normalization, tenant migration and old-ref rediscovery require explicit key-version and dual-resolution policy. Cannot be treated as anonymization. |

**Recommendation:** prefer a persistent, random opaque canonical subject reference backed by a tightly protected, auditable mapping from each independently verified native principal. Do not derive a cross-repository identity from email or raw `sub`. This avoids making every store's index depend on a rotating pseudonym key and preserves DSAR rediscovery, provided mapping access, backup/recovery, unlinking, and retention are defined. If no mapping service/store is approved, retain the current proposed HMAC as an alternative—not an implicit choice—and block cross-repository completeness until resolver/key lifecycle decisions are made. This is a technical recommendation, not a legal identity-resolution mandate.

### Decisions and acceptance implications

1. Decide whether RIS and Jobsearch accounts are intentionally linkable and how both account holders prove control; otherwise treat them as separate data subjects/requests.
2. Name canonical resolver owner and approve tenant boundary, mapping data, access policy, conflict/unlink handling, retention and recovery.
3. Keep native auth and Orders owner authorization unchanged; subject reference is a discovery key only.
4. DSGVO-03 must support old/unmapped identities as `PARTIAL/BLOCKED`; never infer identity from email. Key rotation/mapping migration needs dry-run counts, dual-read/version support, recoverability and reconciliation before any separate migration approval.

**Blockers:** DSGVO-02 D02-04/D02-05 and D02-06/07 decisions. No scheme is approved by this review.

## B — Mays-Orders privacy review

### Write-path inventory at the exact pin

| Path | Source | Current subject index behavior |
|---|---|---|
| Retail order create | `lambda/src/index.py` → `lambda/src/order_service.py::create_order` | Writes order/customer, owner fields and GSI1/GSI3; no `subjectId`, `gsi2pk`, or `gsi2sk`. |
| Agent order create | `index.py` → `OrderService._create_agent_order` | Persists AgentOrder, fingerprint, owner fields and GSI1/GSI3; no GSI2 subject fields. |
| Dispatch preparation / sent marking | `OrderService.prepare_dispatch`, `mark_dispatch_sent` | Updates dispatch state/work identifiers only; no subject index. |
| Result handoff/consumer | `lambda/src/result_consumer.py`, `result_handler.py`, `OrderService.apply_result` | Authenticates signed result and correlation, updates processing/version; no subject index. |
| Public status update | `index.py` → `OrderService.update_order_status` | Conditional status update; no subject index. |
| Retail SQS status worker | `lambda/src/sqs_handler.py::_process_order` | Direct state/timestamp mutation; no subject index. |
| Seed import | `scripts/seed_orders.py::import_orders/write_items` | Writes normalized seed input; does not derive a verified subject mapping. |

GSI2 is provisioned (`terraform/modules/dynamodb/main.tf`) and key contract exists in `lambda/src/order_types.py`; the writer coverage gap is not solved by provisioning the index. The pinned internal direct-Lambda privacy actions in `lambda/src/index.py` call `inspect_subject`, `export_subject`, `erase_subject`, which query GSI2. Auth fails closed through project/action/secret checks. No public API or RIS caller to those internal actions is established by this source review.

### Anonymization gap

`OrderService.erase_subject(..., EXECUTE, ANONYMIZE)` replaces nested customer name/email and removes `subjectId`, GSI2 keys, and `orderDescription`. It does not remove or sanitize `agentOrder`, `processing.result`, or stored owner identity fields. Existing anonymization tests check that an update occurred/count changed, not the full residual nested data. The `agentOrder` may contain user-supplied input; `processing.result` may contain result material. Whether owner fields should be retained is a policy/security decision because removing them affects ordinary owner authorization and audit semantics.

The RIS compatibility assertion in `tests/test_agent_order_dispatch_e2e.py::test_internal_agent_order_is_mo_compatible` explicitly asserts that the stored AgentOrder has no GSI2 fields. Any future contract change must deliberately revise that assertion and preserve the established Orders request allowlist/`AgentOrder` schema/result transport. RIS `agents/orders/real.py::_create_body()` currently serializes approved request fields and does not forward arbitrary tenant/actor/context fields; do not add a client-supplied subject passthrough.

### Minimal implementation proposal and native tests

After the identity contract and coverage policy are approved:

1. Preserve `ownerKey`/GSI3 and its auth checks; add a distinct approved privacy subject reference to both Orders create paths and every required update/import path with conditional preservation.
2. Establish a trusted service-boundary mechanism for RIS-created orders. Do not treat `actor_id`, a request-body `subjectId`, or owner identity as the data subject without an approved mapping rule.
3. Extend `erase_subject` to policy-defined nested result/AgentOrder/customer fields and prove residuals; keep ownership and audit retention explicit. Report unsupported/legacy items instead of counting them complete.
4. Assess whether the GSI schema itself suffices; no Terraform index change is indicated by the current source finding. No generated module hand-edit or Orders pin change.

Original tests to retain/extend: `lambda/tests/test_order_service.py` (create/inspect/export/erase); `test_order_description.py`; `test_ownership.py::test_privacy_path_still_uses_its_own_index`; `test_index.py`; `test_result_handoff.py`; `test_result_consumer_lambda.py`; `scripts/tests/test_seed_orders.py` if importer behavior changes. RIS producer compatibility tests: `tests/test_agent_order_dispatch_e2e.py`, `tests/test_real_orders_adapter.py`, `tests/test_orders_reader.py`.

Required additions: each create/write branch indexes a synthetic approved ref; retry/result updates preserve it; body spoof/missing auth denied; inspect/export/erase finds producer-created records; export projection excludes internals/secrets; anonymization asserts every covered nested field and retention exception; legacy import rows are visibly unresolved. Test list is planned only—no test ran.

**Blockers:** approved subject mapping and scope; exact treatment of order/result/owner fields; legacy data strategy; Orders and RIS maintainers must coordinate versioned PRs. No Orders code or pin was changed.

## C — RIS privacy review

### Existing capabilities to reuse

- Ordered legacy account erasure: `agents/ecosystem/privacy_erasure.py::PrivacyErasure.erase()` revokes credentials/profiles, cancels nonterminal work, invokes bounded application/document steps, then handles UserProfile. Its own contract states Orders are untouched; terminal work and other retained categories need explicit outcomes.
- Resumable operation/checkpoint foundation: `privacy_erasure_contract.py` (`ErasureOperationV1`/execution context), `privacy_erasure_repository.py`, write-freeze repository and `AtomicG5MutationExecutor`.
- Existing domain components: `privacy_profile_erasure.py::ProfileOnlyErasureExecutor`, `privacy_document_erasure.py::DocumentErasureIntegration`, `privacy_application_erasure.py::ApplicationErasureExecutor`, and `privacy_s3_erasure.py::FencedS3ErasureOrchestrator` / versioned adapter.
- Receipts and deletion evidence: `privacy_receipt.py`, `privacy_receipt_journal.py`, `privacy_deletion_ledger.py`, and `privacy_durable_deletion_ledger.py`. These are evidence mechanisms, not proof that every domain has been visited.

### Coverage matrix

| Domain | Current RIS path/evidence | Gap / required adapter result |
|---|---|---|
| Credentials/API profiles, UserProfile | G5 ordered flow | Cognito account/session deletion is distinct; do not report account identity gone without verified outcome. |
| Partner profile hierarchy / CV metadata | Profile-only resumable executor | Scope-specific coverage needs tests and operation integration; document records are not deleted by profile-only executor. |
| S3 CV objects | Fenced versioned S3 executor and document integration | All-version/list reconciliation and live storage proof are separate; cannot infer from metadata deletion. |
| ApplicationV1 | Resumable Application erasure executor | Extend into common operation ledger only if missing; preserve owner/consent contract. |
| Jobsearch | No demonstrated identity resolver or inspect/export/erase adapter in RIS orchestration | Return `BLOCKED`/`UNAVAILABLE` until Jobsearch contract and account mapping exist; no email join. |
| Mays-Orders | No demonstrated RIS adapter/call for pinned internal privacy actions; legacy erasure explicitly excludes Orders | Requires approved subjectRef, versioned internal contract, and Orders-owned execution. |
| WorkItems/results/entitlements/jobsearch history | Existing G5 can cancel nonterminal work; terminal/retained records not globally covered | Per-domain policy and status; no completion from cancellation alone. |
| Logs/DLQ/backups/PITR/receipts | Contracts and partial local recovery/evidence components | Operational expiry/reconciliation and no-resurrection evidence remain separate; must be explicit partial/retention statuses. |

### Minimal extension plan

1. Do not replace existing G5 or domain executors. Add a versioned domain-adapter protocol to the resumable operation path only after identity and policy approval.
2. Each adapter declares its domain, required scope, operation/checkpoint fields, idempotency, retry behavior, evidence level, and terminal outcomes (`COMPLETE`, `PARTIAL`, `BLOCKED`, `UNAVAILABLE`, approved `RETAINED`). The coordinator must treat missing required adapters as blocking.
3. Add Orders and Jobsearch adapters behind owner-authenticated service contracts; domain mutation remains in the owning repository. Preserve tenant checks, write-freeze semantics and existing API/module contracts.
4. Keep distinct states for request accepted, provider/service request made, and independently verified deletion. Never make a receipt or queued request equivalent to physical erasure.
5. Update `ErasureOperationV1` progress contract additively with domain IDs/version and opaque evidence only; do not store raw keys, CV text, secrets, or external URLs in checkpoints.

Original RIS tests to reuse: `test_privacy_erasure_contract.py`, `test_privacy_erasure_repository.py`, `test_privacy_erasure_security.py`, `test_partner_privacy_inspection.py`, `test_application_privacy_contract.py`, `test_application_erasure.py`, `test_privacy_capability_planned.py`, `test_privacy_lifecycle_evidence.py`, `test_r08_c1a_profile_only_erasure.py`, `test_r08_c1b_document_erasure_integration.py`, `test_r08_c0f_s3_erasure.py`, `test_durable_deletion_ledger.py`, and `test_public_application_erasure.py`. Add synthetic adapter conformance, absent-adapter blocker, per-domain partial/retry/resume, cross-tenant denial and proof that no adapter can overstate global completion. Tests not run.

**Blockers:** DSGVO-02 identity and legal/retention decisions; DSGVO-03 service interfaces; separate platform/security approval for logs, queues, backups and secrets. No RIS runtime change was made.

## D — Unified Privacy QA review

### Existing suites and CI provenance

| Repository / exact source | Original tests to retain | Existing CI/workflow observation |
|---|---|---|
| RIS `77e215282a661b5c1ce7dcb66d703e1eb4432212` | Consent/notice: `test_consent_gate.py`, `test_consent_notice_lifecycle.py`, `test_consent_special_categories.py`; receipts: `test_privacy_receipt_contract.py`, `test_privacy_receipt_journal.py`; erasure: `test_privacy_erasure_contract.py`, `test_privacy_erasure_repository.py`, `test_privacy_erasure_security.py`, `test_public_application_erasure.py`, `test_r08_c1a_profile_only_erasure.py`, `test_r08_c1b_document_erasure_integration.py`; plus the RIS-specific list in §C. | `.github/workflows/mays-compatibility-qa.yml` is an existing model for pinned Orders source, isolated Unified QA profiles and evidence upload. `.github/workflows/ci-cd.yml` is Terraform-static validation, not a dedicated privacy acceptance gate. |
| Mays-Orders `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` | Core behavior: `lambda/tests/test_order_service.py`, `test_order_description.py`, `test_ownership.py`, `test_index.py`, `test_result_handoff.py`, `test_result_consumer_lambda.py`; backup-related: `cognito_backup/tests/test_manifest.py`, `test_restore.py`; seed/import tests if import contract changes. | Existing CI is not a demonstrated required full unit/privacy suite: `ci/buildspecs/validate.yml` documents unit-test skip; `.github/workflows/security.yml` is security/dependency oriented. Reuse repository-native `lambda` unittest command; coordinate an owner-approved CI job separately. |
| Mays-Jobsearch `origin/main` `c298d223e38407781b4f63426be9f9228ccb4467` | API: `tests/api/ris-consents.test.mjs`, `ris-account-erasure.test.mjs`, `ris-cvs.test.mjs`, `ris-applications.test.mjs`, `ris-search-profiles.test.mjs`, `ris-boundary.test.mjs`; UI/storage: `src/lib/storageConsent.test.ts`, `accountErasureApi.test.ts`, consent component tests; synthetic mocked BFF E2E: `tests/e2e/account-erasure.mjs`. | `.github/workflows/codeql.yml` runs npm CI/build/test with path filters. Per Jobsearch guidance, `npm test` excludes `api/**`; API node tests/syntax must be explicitly verified in the gate instead of assuming frontend Vitest covers them. Local checkout is a feature branch; source provenance for this review is `origin/main`, not that worktree HEAD. |

### Compact synthetic catalog

Reuse existing frameworks; no new test framework or shared writable checkout:

1. **Identity/linkage:** synthetic source principals; identity tuple issuer+subject; tenant separation; account-link proof required; email/forged client ID rejected; ref stable according to approved version; unlink/conflict and key/mapping rotation behavior.
2. **Orders writers/DSAR:** both retail and AgentOrder create, retries, every state/result mutation and import; GSI lookup discovers exactly the matching records; privacy inspect/export/erase; nested-field residual assertions and internal-field redaction.
3. **RIS orchestration:** domain adapter missing/unavailable blocks global completion; scoped auth and write freeze; idempotent partial/retry/resume; profile/application/document/S3 categories; third-party-requested vs verified outcome.
4. **Consent and Jobsearch boundary:** granted/withdrawn/missing purposes, invalid notice/version, identity mismatch; denied flow causes no durable write; API tests explicitly run; mocked BFF only.
5. **Retention/recovery/queue/security:** local fake restore no resurrection, manifest/project mismatch, stale WorkItem cancellation, DLQ payload minimization without any redrive, secret negative auth and redaction. Live AWS restore/queue tests are not part of this gate.

Use deterministic synthetic fixtures only. Tests should assert full record state and per-domain evidence, not only returned counts or HTTP success.

### Runner isolation and provenance

- One repository-native job/checkout per repository; no shared writable source tree and no global `MO_ORDERS_SRC` in RIS environment. RIS Unified QA already supports job-scoped child-process environments; keep Orders-only source restricted to its XRepo jobs.
- Disable ambient AWS discovery/credentials in test processes; mock service clients. Do not run deployed E2E, migrations, cleanup scripts, plan/apply or redrive in the privacy PR gate.
- Jobsearch CI uses its native Node/npm lockfile environment; run API node tests/syntax separately because Vitest excludes `api/**` per repo instructions.
- Evidence manifest records repository, immutable SHA, branch only as descriptive metadata, workflow/run ID, command, runtime, dependency-lock hash, fixture provenance (`synthetic`), pass/fail/skip, artifact digest and limitations. Cross-repo result is valid only when all three SHAs match the approved matrix; absent/skipped boundary is never PASS.
- CI is blocking/non-approving: it may reject missing or failing evidence, but cannot establish lawful basis, legal consent, live configuration, deployment authorization or real-data release.

**Limitations:** This is a source/workflow inventory and test design; no suite ran. Jobsearch `origin/main` differs from the local checked-out branch, so future CI must fetch/verify the immutable Main SHA instead of treating the local feature checkout as proof.

## Consolidated recommendation and decision gate

### Recommended XRepo identity contract

1. **Native principal:** verified source namespace + normalized issuer + subject, with tenant obtained from trusted server context. The native principal tuple is never accepted from a request body and is not replaced by email.
2. **Cross-site association:** separate RIS and Jobsearch principals remain distinct unless an approved flow proves control of both and an accountable resolver records the link. A valid token at one site alone does not prove ownership of a principal at the other site.
3. **Canonical reference:** prefer a high-entropy, randomly generated, persistent opaque `subjectRef` with a version prefix, held in a protected mapping registry. Mapping is tenant-bound and resolves each verified native principal to its reference. Only authorized service contexts may resolve it; owner authorization continues to use each service's native contract.
4. **Orders integration:** propagate the canonical reference only over an authenticated server-to-server path; use it for GSI2 privacy discovery while retaining Orders `ownerKey`/GSI3. Populate every required writer/update. Do not expose it to public clients or use it as an authorization credential.
5. **DSAR semantics:** mapping must allow a verified principal to find all linked references, records and aliases; link/unlink/conflict and unresolved legacy data are explicit. Any missing mapping/domain yields partial/blocked status, never silent success.
6. **Alternative:** tenant-scoped HMAC SubjectRef is acceptable only if owners reject the mapping registry and approve key custody, versioned dual-resolution/rotation, compromise recovery and historical reindexing. Existing unkeyed Orders owner_key is not the privacy index contract.

**Rationale:** A persistent random reference separates privacy discovery from native owner authorization and avoids requiring a secret-derived index to be recomputed after every key rotation. A mapping registry provides rediscovery, but creates its own sensitive dataset and retention/security obligations. HMAC reduces stored mapping state but still needs deterministic identity input, fails to link separate pools by itself, and makes key loss/rotation a data-discoverability risk. Neither option solves lawfulness or account-linking without an approved proof flow.

### Updated DSGVO-03…07 readiness

| Package | Technical readiness after 02A | Remaining gate |
|---|---|---|
| DSGVO-03 Orders subject linkage/DSAR | Concrete file-path/write-path and test proposal in §B and `DSGVO-02-DECISIONS-AND-CONTRACT.md`; no implementation | Approve identity resolver, scope, data-field erasure/retention and legacy handling; Orders/RIS owner authorization |
| DSGVO-04 RIS orchestration | Reuse path and missing adapter contract in §C; no implementation | DSGVO-03 adapter contract plus legal scope/retention and domain owner approvals |
| DSGVO-05 retention/backup/queue/security | Categories and owners identified in §C/D; design may proceed independently | Privacy/legal retention decisions, platform/security owner acceptance; separate mutation authorization |
| DSGVO-06 unified CI/CD | Existing runner/tooling and test gaps in §D; design can proceed | Approved contract vectors and stable 03–05 suites; CI owners approve workflow changes |
| DSGVO-07 synthetic XRepo acceptance | Synthetic catalog and evidence-manifest criteria in §D; no execution | 03–06 complete at exact SHAs, identity/retention decisions and human acceptance sign-offs |

### Decisions that remain explicitly open

- Resolver and cross-account-link proof, canonical mapping owner, tenant model, reference generation and map retention/recovery.
- Controller/processor roles; legal bases including Article 9 conditions; consent/notice/withdrawal; retention and legal exceptions; DPIA decision; processor/transfer terms; DSAR workflow and timing.
- Treatment of embedded Orders AgentOrder/result/customer/owner fields and legacy records; what can be erased vs retained, and on what approved basis.
- Production migration/backfill, secrets, logs, S3/PITR/restore, queue/terminal-result handling, and release approvals.

**Final status:** `DSGVO TECHNICAL CONTRACT READY FOR DECISION`. This is not `READY FOR IMPLEMENTATION`. No tests were run, no migration performed, no legal decision made, and no technical/runtime/operational mutation authorized. Stop here until named owners return explicit decisions and separately authorize the next package.
