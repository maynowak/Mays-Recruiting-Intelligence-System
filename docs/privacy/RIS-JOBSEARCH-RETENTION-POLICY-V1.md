# RIS Jobsearch Profile Storage — Retention Policy v1

**Status:** PROPOSED / REVIEW_REQUIRED — no period is legally approved
**Gate:** R08-POLICY-01 · **Date:** 2026-11-01

“Technical period” is an observed implementation fact. “Proposed rule” is a
candidate for approval, not a final legal decision.

| Resource | Technical period now | Proposed clock/rule | Trigger / mechanism | Evidence | Status |
|---|---|---|---|---|---|
| UserProfile | No reliable applied expiry; documented 2y is REVIEW_REQUIRED | Account lifetime, then approved closure period | G5/R08-C scoped delete; Cognito separately | Consistent delete + operation record | REVIEW_REQUIRED |
| CVDocument metadata | No TTL in `partner-profiles` | While selected storage purpose exists; orphan grace period undecided | Parent-aware delete/reconciliation | Metadata and parent absence verified | REVIEW_REQUIRED |
| S3 PDF object | Versioning enabled; no lifecycle rule observed | Approved purpose period after confirmed upload | Version-aware deletion | Object/version listing proves scope | BLOCKED |
| S3 versions/delete markers | No approved expiry | Same approved PDF period; never indefinite because versioning is on | Enumerate and delete every version/marker | Repeated empty listing or explicit exception | BLOCKED |
| ManualSearchProfile | No TTL | Until user deletion or purpose end | Conditional repository delete | Item absent + later receipt | REVIEW_REQUIRED |
| CVSearchProfile | No TTL | With linked CV/purpose | Child-first guarded delete | Complete paginated child query | REVIEW_REQUIRED |
| ATSSearchProfile | No TTL | With parent purpose | Child-first guarded delete | Complete paginated child query | REVIEW_REQUIRED |
| PrivacyReceiptV1 | No TTL by design | Shortest approved evidence period; never indefinite by convenience | Policy-controlled delete/minimize | Inventory + deletion/minimization record | BLOCKED |
| Idempotency records | 24h contract | 24h from terminal operation | TTL/explicit expiry | TTL attribute and query | TECHNICAL |
| Cursor records | 15 min + explicit expiry | 15 min from issuance | TTL + explicit expiry check | Expiry rejection test | TECHNICAL |
| Capacity counters | No TTL | Until parent/resource deletion and reconciliation | Atomic cleanup | Parent/counter reconciliation | TECHNICAL |
| Lifecycle guards | Operation-scoped | Until operation ends plus bounded cleanup | Release/finalize path | State transition and absence | TECHNICAL |
| Logs / CloudTrail | Platform/config dependent; docs mention 30d/90d | Minimum approved security/legal period | CloudWatch/trail lifecycle | Config and sampling audit | REVIEW_REQUIRED |
| Backups/PITR | Provider/config dependent; not covered by G5 | Separate schedule and restore-erasure rule | Provider lifecycle + deletion ledger | Config and restore test | BLOCKED |

## Binding rules

- The retention clock must name its event: confirmed upload, creation, last
  use, account closure or request completion. It must not be inferred from an
  arbitrary write timestamp.
- Logical deletion, physical deletion and verified purge are distinct claims.
  Current-object deletion is not proof that S3 versions, markers or backups
  are gone.
- Exceptions need authority, scope, start/end, access restriction and owner.
- Receipt retention is separate from CV retention. A receipt may survive
  subject-data deletion only if approved and minimized.
- No receipt TTL or production journal write is authorized by this document.
