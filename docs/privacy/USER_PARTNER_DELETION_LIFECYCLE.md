# User and Partner Deletion Lifecycle

## States
ACTIVE → SUSPENDED → DELETION_REQUESTED → DELETION_IN_PROGRESS → DELETED
DELETION_BLOCKED_LEGAL_RETENTION

## User deletion
1. Verify identity and authority via Cognito JWT + admin role check.
2. Set user profile status SUSPENDED, revoke all credentials via gsi-owner.
3. Invalidate sessions: Cognito global sign-out, refresh token revocation.
4. Identify related data: APIProfiles owned, credentials, entitlements, work items, documents.
5. Check legal retention duties.
6. Delete or anonymize: profile, credentials metadata, entitlements, work items per TTL.
7. Record deletion evidence: timestamp, actor, scope, requestId. No secrets.
8. Prevent recreation: soft-delete marker, unique constraint.

## Partner application deletion
1. Admin confirmation.
2. Suspend partner application registry record.
3. Disable Cognito client.
4. Revoke all credentials linked to apiProfileId.
5. Delete application metadata after grace period.

## Partner organization deletion
Cascades to all applications owned by partner. Requires explicit confirmation and admin approval.

## Idempotency
Deletion operations are idempotent. Repeated requests succeed with same result.

## Audit
All state transitions logged to CloudTrail and audit table. No personal data in logs.
