# Cross-repository privacy contract (proposed acceptance contract)

**Status:** PARTIAL — requirements are documented; end-to-end conformance is not established. Applies to RIS, Mays-Orders pin `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`, and Jobsearch Main reviewed at `c298d223e38407781b4f63426be9f9228ccb4467`.

## Identity and subject linkage

- Each service derives identity from its authenticated server-side context; never trust browser-supplied subject, tenant, owner or timestamps.
- Use a documented opaque cross-service correlation key; do not send raw email/CV data as a key.
- Every persisted personal-data-bearing object, including RIS-originated AgentOrders, must be discoverable by the authorized subject-rights workflow or an explicitly documented exception.
- Current blocker: RIS dispatch writes do not include Orders `gsi2pk`; Orders privacy queries cannot be assumed to locate all such orders. No change to Orders pin is authorized by this contract.

## Inspect/export

- Return inventory/category, purpose, owning controller/service, status and evidence level; separate systems and identify unavailable domains.
- Export only subject-owned data, redact other persons and secrets, include machine-readable format/version and an auditable manifest.
- Never include raw tokens, credentials, internal keys, presigned URLs, or unneeded CV/prompt content in receipts. CV content export requires a separate explicit policy and secure delivery decision.
- Each service returns `complete`, `partial`, or `unsupported` with reason; no aggregator may translate missing evidence into complete.

## Erasure/anonymization

- Request is idempotent, authenticated, tenant-bound, scope-bound and resumable; protect concurrent writes and report partial failures.
- Enumerate primary rows, embedded snapshots, indexes, child records, object versions/delete markers, queues/results, logs, backups, caches and provider copies.
- Where physical deletion is not immediate or lawful, isolate/restrict, minimize or irreversibly anonymize under an approved policy and state the retention basis/expiry. “Delete current object” is not “purge all versions.”
- Before `completed`, require per-domain verification, queue/worker safety, restore/replay control and explicit legal exception accounting. Backups/provider copies are not claimed erased without independent evidence.

## Security, evidence and change control

- Service credentials are server-only, least-privilege, rotatable/revocable and never logged; secret retrieval and rotation status are separately evidenced.
- Receipts contain opaque IDs, categories, timestamps and evidence level only. They do not themselves prove physical erasure.
- Conformance is evaluated at exact source and deployment pins; tests use synthetic identities/data. Live state, legal approval and user-facing notice require separate gates.

## Proposed interface outcomes

`inspect(subject)`, `export(subject, requestId)`, and `erase(subject, requestId, scope)` return `operationId`, per-domain status, evidence level, blockers, and retention caveats. This is a design proposal, not a claim that a shared public API exists. Existing RIS and Orders internal API contracts remain authoritative within their boundaries.
