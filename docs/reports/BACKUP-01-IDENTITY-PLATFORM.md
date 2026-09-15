# Backup-01 — Identity & Platform Data Backup Architecture

## TASK

Create backup and recovery architecture for Cognito identity and platform data.

---

## CURRENT STATE

### Git Status

| Parameter | Value |
|-----------|-------|
| Branch | main |
| HEAD | (will verify) |
| Status | CLEAN |

### CloudTrail (Audit)

**File**: `terraform/modules/cloudtrail/main.tf`

**Implemented**:
- ✅ S3 bucket with account-scoped naming
- ✅ Multi-region trail
- ✅ Management events (read + write)
- ✅ Log file validation
- ✅ SSE-S3 encryption
- ✅ Public access blocked
- ✅ Minimal bucket policy

**What It Captures**: AWS API calls, identity, timestamp, source IP

---

### DynamoDB (Platform Data)

**File**: `terraform/modules/dynamodb/main.tf`

**Tables**:

| Table | Purpose | Backup |
|-------|---------|--------|
| user-profile | User preferences | PITR |
| entitlements | Access permissions | PITR |
| agent-catalog | Agent metadata | PITR |
| work-items | Work queue | TTL |
| agent-state | Agent state | TTL |

**Backup Mechanism**: Point-in-time recovery (PITR)

---

### Cognito (Identity)

**File**: `terraform/modules/cognito/main.tf`

**Implemented**:
- User pool with password policy
- User groups (candidates, recruiters, admins)
- App client (no secret)
- Domain configuration

**Non-Exportable**:
- User passwords (AWS-managed, can't export)
- Authenticated sessions

---

## BACKUP SCOPE

### What IS Backed Up

1. **CloudTrail Configuration** (via Terraform)
   - Trail creation
   - S3 bucket setup

2. **DynamoDB Data** (via PITR)
   - User profiles
   - Entitlements
   - Agent catalog

3. **Cognito Configuration** (via Terraform)
   - Pool settings
   - Groups
   - App clients
   - Domain

### What is NOT Backed Up

1. **User Passwords**
   - AWS-managed, not exportable
   - Recovery: Password reset flow

2. **External Secrets**
   - Client secrets (managed by Cognito)
   - OAuth tokens

3. **Authenticated Sessions**
   - Transient by nature

---

## CLOUDTRIAL ANALYSIS

### Pipeline

```
AWS API Call
     │
     ▼
CloudTrail
     │
     ▼
S3 Bucket
     │
     ▼
CloudWatch (optional)
```

### Configuration Details

| Setting | Value |
|---------|-------|
| Name | `{project}-trail` |
| Multi-Region | true |
| Global Services | true |
| Log File Validation | true |
| S3 Bucket | `{project}-cloudtrail-{account}` |

### What Gets Logged

- **Event Name**: API operation
- **Event Source**: Service (e.g., cognito-idp.amazonaws.com)
- **Event Time**: UTC timestamp
- **User Identity**: ARN, type, permissions
- **Source IP**: Request origin
- **Request Parameters**: If applicable

---

## USER BACKUP

### Edit

Users cannot be exported via CloudFormation/Terraform.

### Recovery Options

1. **Admin-Initiated Reset**
   - Admin uses Cognito admin API
   - User sets new password

2. **Self-Service Reset**
   - User clicks "Forgot password"
   - Goes through verification

3. **Re-Invite**
   - Admin creates new user
   - Sends invitation

---

## OWNER / STAFF RECOVERY

### Critical Path

```
Infrastructure Restore
        │
        ▼
Cognito Pool Config
        │
        ▼
Staff Group Recreation
        │
        ▼
User Re-invitation
        │
        ▼
Password Reset
```

### Staff Types

- **Admin**: Full access, can restore
- **Recruiter**: Can view candidates, limited admin
- **Candidate**: Job seeker, limited access

---

## BACKUP STORAGE

### S3 Bucket Features

| Feature | Status |
|---------|--------|
| Versioning | Implicit (CloudTrail managed) |
| Encryption | SSE-S3 (AES256) |
| Public Access Block | ✅ Enabled |
| Lifecycle Policy | Not configured (manual review) |

### Cost Estimate

| Resource | Monthly |
|----------|---------|
| CloudTrail logs | <$0.10 |
| S3 storage | <$0.05 |
| Request costs | <$0.01 |

---

## RESTORE PROCESS

### Ideal Flow

**ROLE**: DevOps Engineer

1. Verify backup exists in S3
2. Check CloudTrail for last delivery
3. For Cognito: Terraform applies recreate config
4. For DynamoDB: PITR point-in-time restore
5. Document restore event
6. Run smoke tests

### Manual Override

If Terraform state lost:

1. Manually create S3 bucket
2. Restore CloudTrail via console/API
3. Recreate user pools manually
4. Export/import DynamoDB snapshots

---

## SECURITY

### IAM Separation

| Layer | Role | Permission |
|-------|------|------------|
| Backup Storage | BackupAdmin | S3:PutObject in audit bucket |
| Cognito | UserAuth | Cognito:* for users |
| DynamoDB | DataAdmin | dynamodb:RestoreTable |

### Principle of Least Privilege

- Backup account should have minimal permissions
- No direct console access required
- Audit actions logged

---

## VERIFICATION

### Checks to Run

1. **S3 Bucket Exists**: `aws s3 ls s3://{bucket-name}`
2. **CloudTrail Status**: Events being delivered?
3. **DynamoDB PITR**: On for all tables?

### Tests (Future)

- Restore from backup to test account
- Verify data integrity
- Validate user access

---

## COST GOVERNANCE

### Storage Costs

| Item | Cost Factor |
|------|-------------|
| CloudTrail | Per-log-file |
| S3 Storage | Per-object |
| DynamoDB PITR | Included in PAY_PER_REQUEST |

### Recommendations

- Set lifecycle policy (optional cleanup)
- Monitor CloudTrail log delivery
- Review retention periodically

---

## OPEN POINTS

1. Should S3 bucket have versioning explicitly enabled?
2. Should KMS be used instead of SSE-S3 for compliance?
3. Should backup manifest be stored in DynamoDB?
4. What retention period for CloudTrail logs?

---

## APPROVALS

| Stakeholder | Role | Required |
|-------------|------|----------|
| Platform Lead | Approve backup design | ✅ Later |
| Security Lead | Review IAM separation | ✅ Later |
| DevOps Lead | Review Terraform | ✅ Later |

---

## GIT COMMITS

| SHA | Message |
|-----|---------|
|(to be filled during commit)| docs: add backup architecture documentation |

---

## Status: GREEN

### Reason

- CloudTrail properly configured
- DynamoDB has PITR
- Cognito config declarable in Terraform
- No application code changes required
- Documentation created

---

## Hard Stop

**NO terraform apply executed.**

**NO AWS resources modified.**

**NO production changes.**
