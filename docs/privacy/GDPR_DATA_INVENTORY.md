# GDPR Data Inventory – Mays-RIS

## Scope
Mays-RIS platform, DEV environment, AWS eu-central-1.

## Data categories

### Cognito User Pool
- Data: sub, email, preferred_username, custom:tenant_id, cognito:groups
- Purpose: authentication, tenant isolation, authorization
- Controller: Mays
- Legal basis: contract performance / legitimate interest
- Storage: AWS Cognito
- Retention: per Cognito user lifecycle, deletion on user request
- Subprocessors: Amazon Web Services

### APIProfiles DynamoDB
- Data: apiProfileId, ownerUserId, tenantId, name, description, status, clientRef, expiresAt, createdAt, updatedAt, createdBy, updatedBy
- Purpose: API usage context
- Personal data: ownerUserId, tenantId indirect
- Retention: until profile deleted, no TTL
- Deletion: admin API DELETE /v1/apiprofiles/{id}

### Credentials DynamoDB
- Data: credentialId, apiProfileId, ownerUserId, tenantId, label, credentialType, status, digest, expiresAt, lastUsedAt, revokedAt, revokedBy, revokeReason
- Purpose: opaque bearer authentication
- Personal data: ownerUserId, tenantId
- Retention: until credential revoked/expired
- Deletion: revoke + logical deletion, physical deletion per erasure

### Entitlements DynamoDB
- Data: entitlementId, userId, tenantId, agentId, validFrom, validUntil
- Purpose: agent access control
- Personal data: userId
- Retention: until entitlement expires

### User Profile DynamoDB
- Data: userId, tenantId, firstName, lastName, email
- Purpose: human profile
- Retention: TTL enabled

### Work Items DynamoDB
- Data: workId, tenantId, userId, status, payload references
- Purpose: agent execution tracking
- Retention: TTL

### S3 Documents
- Data: tenant/{t}/users/{sub}/documents/{uuid}
- Purpose: user documents
- Retention: per document lifecycle
- Encryption: SSE AES256

### CloudTrail
- Data: API calls, IAM principals
- Purpose: audit
- Retention: 90 days

### CloudWatch Logs
- Data: Lambda logs, API Gateway logs
- Purpose: observability
- Retention: 30 days

### Backups
- DynamoDB PITR, S3 versioning
- Retention: documented per table

## Processing summary
All processing is within EU. AWS is processor. International transfers via EU Standard Contractual Clauses.

Legal review required for legal basis of marketing data, consent management.
