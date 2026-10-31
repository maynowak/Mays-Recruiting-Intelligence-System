# Data Retention Matrix

> R08-G0: This file is historical. The current, gap-aware matrix is
> `RIS_PRIVACY_DATA_INVENTORY_V1.md`. All legal retention values below are
> **REVIEW REQUIRED**, not legal decisions.

| Data Category | Retention | Legal Basis | Deletion Mechanism |
| Cognito User | Until account deletion | Contract | Cognito admin delete |
| APIProfile | Until explicit deletion | Contract | Admin API |
| Credentials | ExpiresAt or revocation | Contract | Revoke + TTL |
| Entitlements | validUntil | Contract | TTL |
| User Profile | TTL 2 years | Consent | TTL + manual |
| Work Items | TTL 90 days | Legitimate interest | TTL |
| Documents S3 | Per policy | Contract | Lifecycle |
| Partner profiles (Manual/CVSP/ATS/CV metadata) | Until delete | REVIEW REQUIRED | R08-C (not G5) |
| Cursor records | 15 min | Service operation | TTL + explicit expiry |
| Idempotency records | 24 h | Service operation | TTL + conditional reuse |
| Capacity/lifecycle records | Until resource/parent gone | Service operation | R08-C |
| S3 versions/delete markers | Object lifecycle | REVIEW REQUIRED | R08-C purge |
| CloudTrail | 90 days | Legal obligation | Auto delete |
| CloudWatch | 30 days | Legitimate interest | Auto delete |
| Backups | 30 days PITR | Legal | Configured expiry |

Legal retention exceptions apply for tax/audit.
