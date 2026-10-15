# Data Retention Matrix

| Data Category | Retention | Legal Basis | Deletion Mechanism |
| Cognito User | Until account deletion | Contract | Cognito admin delete |
| APIProfile | Until explicit deletion | Contract | Admin API |
| Credentials | ExpiresAt or revocation | Contract | Revoke + TTL |
| Entitlements | validUntil | Contract | TTL |
| User Profile | TTL 2 years | Consent | TTL + manual |
| Work Items | TTL 90 days | Legitimate interest | TTL |
| Documents S3 | Per policy | Contract | Lifecycle |
| CloudTrail | 90 days | Legal obligation | Auto delete |
| CloudWatch | 30 days | Legitimate interest | Auto delete |
| Backups | 30 days PITR | Legal | Configured expiry |

Legal retention exceptions apply for tax/audit.
