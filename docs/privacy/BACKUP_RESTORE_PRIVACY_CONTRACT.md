# Backup and Restore Privacy Contract

## Existing mechanisms
- DynamoDB Point-in-Time Recovery enabled per table
- S3 versioning on documents bucket
- CloudTrail retention 90 days
- CloudWatch retention 30 days
- Terraform state in S3 + DynamoDB lock

## Requirements
A. Encryption at rest for all backups. AWS managed keys.
B. Access restricted to IAM roles with MFA.
C. Retention documented per data category.
D. Deletion follows retention and legal requirements.
E. Immutable backups integrity verified via checksums.
F. Deleted users must not become active after restore.
G. Authoritative deletion ledger maintained.
H. Restoration reconciles against deletion events before activation.
I. Deletions applied before systems resume.
J. Revoked credentials remain revoked.
K. Deleted users remain inaccessible.
L. Backup expiry documented.
M. Restoration tested quarterly.

## Deletion ledger
Table `deletion-ledger` with deletionId, subjectType, subjectId, deletedAt, actor, reason, legalHoldUntil. Contains minimal identifiers, no secrets. Retention 7 years for audit.

Restore procedure:
1. Restore to staging.
2. Replay deletion ledger to re-apply deletions.
3. Verify revoked credentials.
4. Promote to production.
