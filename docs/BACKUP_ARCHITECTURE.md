# Backup Architecture — Mays Recruiting Intelligence System

## Overview

This document defines the backup and recovery architecture for the Ground Zero platform.

**Version**: 1.0.0  
**Status**: DESIGN DOCUMENTATION  

---

## Current State

### 1. CloudTrail (Audit Backup)

**Status**: ✅ IMPLEMENTED in `terraform/modules/cloudtrail/main.tf`

| Resource | Configuration |
|----------|---------------|
| S3 Bucket | Account-scoped with unique naming |
| Multi-Region | ✅ Yes |
| Management Events | ✅ Yes (Read + Write) |
| Log File Validation | ✅ Yes |
| Encryption | SSE-S3 (AES256) |
| Public Access Block | ✅ Enabled |
| Bucket Policy | ✅ Least privilege |

**What It Captures**:
- AWS API calls (Read/Write)
- Global service events (IAM, etc.)
- Timestamp, identity, source IP, event name

**What It Does NOT Capture**:
- User passwords (not exposed)
- User profile data
- Entitlements

### 2. Tenant Data (User Profile, Entitlements, Agent Catalog)

**Status**: ✅ IMPLEMENTED in `terraform/modules/dynamodb/main.tf`

| Table | Backup Mechanism |
|-------|------------------|
| user-profile | Point-in-time recovery (PITR) |
| entitlements | Point-in-time recovery (PITR) |
| agent-catalog | Point-in-time recovery (PITR) |
| work-items | TTL enabled, expiration |
| agent-state | TTL enabled |

**What DynamoDB Provides**:
- Point-in-time recovery (PITR)
- On-demand backups

### 3. Cognito User Pool

**Status**: PARTIALLY BACKED UP

**What CAN be restored from Terraform**:
- User pool configuration (name, policies)
- User groups (candidates, recruiters, admins)

**What CANNOT be exported/restored**:
- User passwords (AWS-managed, not exportable)
- Authenticated sessions (transient)
- User-specific data beyond profile tables

---

## Backup Scope Definition

### Identity Layer (Cognito)

**Exportable Configuration**:
- User Pool settings (password policy, attributes)
- User Groups (candidates, recruiters, admins)
- App Client configuration
- Domain configuration

**Non-Exportable**:
- User passwords (inherently not exportable)
- User-specific data stored in Cognito

**Recovery Strategy**:
- Terraform state restores the infrastructure
- Users must be recreated/re-invited if needed
- Password reset flow must be initiated

### Platform Data Layer

**Backup Mechanism**:
- DynamoDB PITR provides continuous backup
- Point-in-time recovery available for 35 days (default)

**Tables**:
- `user-profile`: User preferences and profile data
- `entitlements`: User-agent access permissions  
- `agent-catalog`: Available agent metadata

### Audit Layer

**CloudTrail**:
- All AWS API calls logged to S3
- Multi-region, validated
- Retain for compliance

---

## Recovery Design

### User Recovery Flow

```
1. User reports account issue
2. Admin verifies identity via support process
3. Cognito password reset initiated (ефеrн)
4. User sets new password
5. Profile data remains intact in DynamoDB
6. Entitlements persist in DynamoDB
```

### Infrastructure Recovery

```
1. Terraform state restored
2. Resources recreated:
   - Cognito User Pool (config only)
   - User Groups (recreated)
   - App Clients (recreated)
   - DynamoDB Tables (PITR or restore from backup)
   - CloudTrail (recreated)
   - Monitoring (recreated)
3. Data restored:
   - DynamoDB via PITR point-in-time
   - Users re-invited via admin flow
```

---

## Secrets Management

### What is NOT Backed Up

- Cognito client secrets (managed via Cognito)
- External provider secrets
- API keys (if any)
- OAuth tokens

### Secret Recovery

- Secrets must be re-configured after restore
- Use AWS Secrets Manager for external secrets
- Document secret locations and rotation procedures

---

## Backup Storage

### CloudTrail Bucket

- Name: `{project}-cloudtrail-{account-id}`
- Location: terraform/modules/cloudtrail/main.tf:19
- Features:
  - Versioning enabled (implicit via CloudTrail)
  - Encryption at rest (SSE-S3)
  - Public access blocked
  - Minimal IAM policy

### Cost Considerations

| Resource | Monthly Estimate |
|----------|-----------------|
| CloudTrail (few MB/day) | ~$0.05 |
| S3 Storage | Negligible |
| DynamoDB PITR | Included in PAY_PER_REQUEST |

---

## Integrity Verification

### Manifest Concept

Each backup should have:
- `backup_id`: Unique identifier
- `timestamp`: UTC timestamp
- `environment`: dev/test/prod
- `component`: cognito|dynamodb|cloudtrail
- `version`: Schema/backup version
- `hash`: Checksum for integrity

### Verification Steps

1. Check S3 object exists
2. Verify CloudTrail log delivery
3. Validate DynamoDB backup (via AWS console)

---

## OWNER: Staff Recovery

**Critical**: Staff members (admins, recruiters) must be able to restore:

1. Admin credentials via Cognito admin flow
2. Staff group membership from Terraform
3. Entitlements for staff agents

---

## KMS Considerations

**Current**: SSE-S3 with AWS-managed keys

**Future**: Consider SSE-KMS for:
- Compliance requirements
- Audit trail for key access
- Separation of duties

---

## Next Steps

1. Define backup manifest structure
2. Create restore test procedure
3. Document owner/staff recovery
4. Create backup verification tests

---

## References

- `terraform/modules/cloudtrail/main.tf` — CloudTrail configuration
- `terraform/modules/dynamodb/main.tf` — Backup mechanisms
- `terraform/modules/cognito/main.tf` — User pool configuration
- `lambda/handler.py` — User profile access
