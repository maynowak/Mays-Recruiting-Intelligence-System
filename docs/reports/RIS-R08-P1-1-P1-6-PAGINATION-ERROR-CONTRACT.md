# R08-P1-1 / P1-6 — Pagination & API Error Contract

**Status:** COMPLETE — local adapter compatibility gate
**Date:** 2026-11-01

## Baseline and scope

| Check | Result |
|---|---|
| Branch / baseline | `feature/ris-partner-profile-persistence-v1` @ `f241852` |
| Existing untracked files | 39 preserved |
| P0-1 through P0-5 | complete and retained |
| Jobsearch / Orders | unchanged; existing RIS repository/cursor interfaces reused |
| AWS / deployment / Terraform | none |
| Privacy / erasure / receipts | no new functions; receipt journal remains disabled |

## Contract decisions

### CV pagination

`GET /v1/partner/me/cvs` now returns exactly the existing flat page envelope:

```json
{"items": [...], "nextCursor": "opaque-token-or-null"}
```

The route uses the existing scoped server-side cursor codec and the repository
GSI query, not a table scan. Cursor scope includes user, tenant, partner,
issuer, resource type and page limit. Invalid, expired, tampered or foreign
cursors return `400`; an empty or final page returns `nextCursor: null`.
`limit` is validated as 1–50 and invalid values return `422`.

### Error contract

Existing flat `{"error": ...}` responses are preserved for client
compatibility; no `{data, meta}` wrapper was introduced. A stable `code` is
now included where the partner boundary/runtime produces the standardized
categories:

| Category | HTTP | Runtime code |
|---|---:|---|
| unauthorized | 401 | `unauthorized` |
| forbidden | 403 | `forbidden` |
| not found | 404 | `not_found` |
| validation | 400/422 | `validation` |
| conflict | 409 | `conflict` |
| capacity | 409 | `capacity_exceeded` |
| unavailable | 503 | `unavailable` |

Legacy human-readable `error` strings remain unchanged where clients may
depend on them. Capacity failures for the 10-CV, 2-search-profile and
5-ATS-profile guards are distinguishable from ordinary conflicts through the
code. Internal exception details remain excluded.

### Version transport

CV PATCH accepts canonical `expectedVersion` and `If-Match`, while retaining
legacy body `version` compatibility. Conflicting tokens are validation errors;
repository stale-version failures remain `409`. No new persistence or API
facade was introduced.

### Pending CV size semantics

The pending/ready distinction from P0-4 is explicit: pending responses omit
`sizeBytes` because no authoritative S3 size exists; ready responses include
`sizeBytes` only after the P0-5 `HeadObject` verification. This is represented
in OpenAPI by making `sizeBytes` optional on the common response and describing
its ready-only semantics. No zero or fabricated size is emitted.

## Security and compatibility

- Existing user/tenant/partner/issuer cursor binding is retained.
- CV IDs and document IDs remain server-owned and separate.
- P0-2 document security and P0-3 versioned UserProfile PATCH remain intact.
- P0-5 ownership and upload-completion verification remain intact.
- S3 keys, credentials, JWTs and internal exception details are not exposed.

## Verification

- Focused pagination/error/OpenAPI/CV suite: **117 passed, 252 subtests**.
- Full RIS regression selection: **741 passed, 45 skipped, 258 subtests**.
- DynamoDB Local was unavailable; existing in-memory conditional/cursor/
  capacity/ownership harnesses were used. This verification gap remains open.
- `git diff --check` is required before commit.

## Remaining risks / next gate

- Real DynamoDB Local/AWS adapter verification remains outstanding.
- Durable cleanup/retention of cursor records and S3 version receipts remains
  in the privacy/erasure roadmap and is not activated here.

**P1-7:** **GO for local implementation**. Product/AWS release remains
**BLOCKED** pending the next gate and AWS-equivalent verification.
