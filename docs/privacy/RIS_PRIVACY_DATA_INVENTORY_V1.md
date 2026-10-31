# RIS Privacy Data Inventory v1 (R08-G0)

Status: **SPECIFIED / REVIEW REQUIRED** for legal bases and retention.
This inventory supersedes the shallow lists in `GDPR_DATA_INVENTORY.md` and
`DATA_RETENTION_MATRIX.md` for the R07/R08 scope; those files remain as history.

| Category | Owner | Purpose | Legal basis | Storage | Retention | Export | Delete | Evidence | Gap |
|---|---|---|---|---|---|---|---|---|---|
| Cognito identity (sub, email, tenant claim, groups) | RIS | auth, tenant isolation | REVIEW REQUIRED | Cognito | account lifetime | admin/user export | Cognito admin delete + revoke tokens | server_verified | not in G5 erasure |
| UserProfile (name, email, tenant) | RIS | app profile | REVIEW REQUIRED | DynamoDB `user-profile` | TTL `expiresAt` (docs: 2y; REVIEW REQUIRED) | user export | delete row | server_verified | no export/receipt |
| CVDocument metadata (name, size, status, documentId) | RIS | CV management | REVIEW REQUIRED | DynamoDB `partner-profiles` | until delete + legal retention | user export | R08-C; G5 does not cover | server_verified | P1-1 naming/status |
| CVSearchProfile (search config, target roles, location) | RIS | job matching | REVIEW REQUIRED | DynamoDB `partner-profiles` | until delete | user export | R08-C | server_verified | not in G5 |
| ManualSearchProfile | RIS | manual search | REVIEW REQUIRED | DynamoDB `partner-profiles` | until delete | user export | R08-C | server_verified | not in G5 |
| ATSSearchProfile (skills, roles, criteria) | RIS | ATS matching | REVIEW REQUIRED | DynamoDB `partner-profiles` | until delete | user export | R08-C | server_verified | not in G5 |
| S3 CV objects (all versions + delete markers) | RIS | document storage | REVIEW REQUIRED | S3 `${p}-${e}-documents` | object lifecycle / legal | presigned user download | R08-C purge all versions | server_verified after verify | G5 deletes current only |
| Cursor records (`CursorToken`) | RIS | pagination | service operation | DynamoDB `partner-profiles` | 15 min TTL + explicit check | not user content | R08-C delete | server_verified | not in G5 |
| Idempotency records | RIS | safe retry | service operation | DynamoDB `partner-profiles` | 24 h | no | R08-C/TTL | server_verified | not in G5 |
| Capacity counters | RIS | 10/2/5 limits | service operation | DynamoDB `partner-profiles` | until resource/parent gone | no | R08-C derive keys | server_verified | no direct user index |
| Lifecycle guards | RIS | delete safety | service operation | DynamoDB `partner-profiles` | until operation ends | no | R08-C | server_verified | no direct user index |
| Credentials / APIProfiles | RIS | machine auth | REVIEW REQUIRED | DynamoDB `credentials`, `api_profiles` | expiry/revocation | metadata export | G5 revokes; physical delete later | server_verified | registry remains |
| Entitlements | RIS | agent access | REVIEW REQUIRED | DynamoDB `entitlements` | TTL `validUntil` | user export | TTL/erasure policy | server_verified | G5 retains |
| Work items (non-terminal/terminal) | RIS | execution tracking | REVIEW REQUIRED | DynamoDB `work-items` | TTL 90 days (docs) | references only | G5 cancels non-terminal; terminal retained | server_verified | terminal payload retention |
| Jobsearches | RIS | job search history | REVIEW REQUIRED | DynamoDB `jobsearches` | TTL `expiresAt` | user export | R08-C | server_verified | not in G5 |
| Partner registry / applications | RIS | partner auth | REVIEW REQUIRED | DynamoDB `partner-applications` | partner lifetime | admin metadata | partner offboarding | server_verified | not user erasure |
| CloudTrail | RIS | audit | legal/legitimate interest REVIEW REQUIRED | S3 trail bucket | 90 days (docs) | admin | retention only | server_verified | no immediate erasure |
| CloudWatch Logs | RIS | observability | legitimate interest REVIEW REQUIRED | CloudWatch | 30 days (docs) | admin | retention only | server_verified | PII minimization needs review |
| Terraform state/backups | RIS | operations | operations | S3 + lock | operational | no | destroy/version purge | server_verified | may contain resource IDs |
| Backups/PITR | AWS/RIS | recovery | REVIEW REQUIRED | AWS backups | provider/config | no | not erased by G5 | not_provable/third_party | restore ledger needed |
| Browser session/local storage | Jobsearch/browser | UI session | REVIEW REQUIRED | browser | session | browser export | client sign-out | client_reported | outside RIS |
| Jobsearch cache | Jobsearch | UI performance | REVIEW REQUIRED | browser/unknown | unknown | unknown | unknown | not_provable | separate boundary |
| AI provider data | external provider | matching assistance | REVIEW REQUIRED | provider | provider contract | provider evidence | provider deletion | third_party_confirmed only | no RIS server AI call found |
| Mays-Orders orders | Mays-Orders-AWS | order service | REVIEW REQUIRED | Orders DynamoDB | Orders policy | Orders internal | Orders internal | server/third-party | no running instance assumed |

## Retention gaps

- Partner-profile resource items have no TTL (`expiresAt` is absent); they
  persist until explicit deletion. Only cursor/idempotency items use TTL.
- UserProfile TTL and WorkItem TTL are documented but **not a legal decision**;
  REVIEW REQUIRED.
- S3 versioning retains old versions/delete markers beyond current-object
  deletion.
- Backups/PITR are not covered by application erasure.
- Logs/audit retention is time-based, not subject-erasure-based.
- No deletion ledger currently exists; the receipt journal is specified, not
  implemented.

## Evidence levels by source

| Source | Maximum evidence |
|---|---|
| RIS server-side write/read/delete result | `server_verified` |
| Verified provider/API response | `third_party_confirmed` |
| Browser/client event | `client_reported` |
| Request queued but not executed | `requested` |
| Backup/provider deletion without independent proof | `not_provable` |
