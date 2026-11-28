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
