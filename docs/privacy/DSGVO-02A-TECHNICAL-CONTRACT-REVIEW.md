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
