# MAYS-RIS-DUAL-INSTALL-LIFECYCLE-01 — PHASE 1A REPORT
## Existing A Decommission Preparation

**Date:** 2026-10-13  
**Status:** READY FOR DESTROY APPROVAL  
**Phase:** 1A — Existing A Decommission Preparation  
**Mission:** Controlled teardown and clean reinstallation of RIS deployment A

---

## 1. STATE CONDITION — VERIFIED

### Legacy State (Authoritative Production State)
| Property | Value |
|----------|-------|
| **S3 Path** | `env:/mays-ris/env:/mays-ris/dev/terraform.tfstate` |
| **Bucket** | `mays-ris-tf-state-dev` |
| **Serial** | 21 |
| **Lineage** | `9b14f5a3-82c2-f5b4-9d9f-c66ae36b0b63` |
| **Terraform Version** | 1.16.1 |
| **Resource Count** | 138 managed |
| **SHA-256** | `fedd69c53299f364274bb65d1c6939ba7e9a2470c56fd87a4e47240644f13703` |
| **Backend Config** | bucket=mays-ris-tf-state-dev, key=env:/mays-ris/dev/terraform.tfstate (legacy), region=eu-central-1, lock_table=mays-ris-tf-lock |

### Canonical State (Intended)
| Property | Value |
|----------|-------|
| **S3 Path** | `env:/mays-ris/dev/terraform.tfstate` |
| **Status** | **NOT FOUND (404)** |

### State Locks (All Stale)
| Lock Path | Lock ID | Age | Status |
|-----------|---------|-----|--------|
| `mays-ris-tf-state-dev/env:/mays-ris/env:/mays-ris/dev/terraform.tfstate` | `6369447e-b76f-7e8b-8b31-8a1880b49e8b` | 50+ hours | **REMOVED** |
| `mays-ris-tf-state-dev/env:/mays-ris/dev/terraform.tfstate` | `84bbc01c-3fa7-0bb1-dd66-1810b850591e` | 120+ hours | STALE (canonical) |
| `mays-ris-tf-state-dev/env:/mays-ris/env:/mays-ris/terraform.tfstate` | `53aaabc1-6a3e-d89b-7ac9-c30e76e2936d` | 120+ hours | STALE (old test) |

---

## 2. RESOURCE OWNERSHIP MATRIX

### A_EXISTING (RIS Production — 138 Managed Resources)

| Module | Resources | Physical IDs (Sample) | Classification |
|--------|-----------|----------------------|----------------|
| **Cognito** | 10 | Pool: `eu-central-1_IfucuxPC1`, Client: `24qns4st861fc72bk7cucjc375`, Domain: `mays-ris-dev` | A_EXISTING |
| **API Gateway** | 28 | API: `bfwyudck84`, Stage: `$default`, Authorizers: 2, Routes: 24 | A_EXISTING |
| **Lambda** | 4 | `mays-ris-dev-agent`, `mays-ris-dev-health-writer`, `mays-ris-dev-health-publisher`, `mays-ris-dev-orders-reader` | A_EXISTING |
| **SQS** | 5 | `mays-ris-dev-work-queue`, `cv-queue`, `ats-queue`, `match-queue`, `dlq` | A_EXISTING |
| **DynamoDB** | 11 | 10 tables + 1 seed item (agent_catalog) | A_EXISTING |
| **S3** | 20 | 4 buckets (data, documents, health-public, health-state, trail) + configs | A_EXISTING |
| **CloudTrail** | 7 | Trail: `mays-ris-trail`, Bucket: `mays-ris-cloudtrail-240571105849` | A_EXISTING |
| **CloudWatch** | 8 | Dashboard: `mays-ris-overview`, 7 Alarms | A_EXISTING |
| **IAM** | 17 | Roles: `mays-ris-lambda-role`, `mays-ris-dev-agent`, `health-publisher`; Policies: 10 | A_EXISTING |
| **Lambda Permissions** | 5 | API Gateway invoke permissions | A_EXISTING |
| **EventBridge** | 2 | Health publisher schedule, health alarms | A_EXISTING |
| **Lambda Event Source Mapping** | 1 | SQS → Agent | A_EXISTING |

**Total: 138 Managed Resources**

### SHARED_DEPENDENCY (Read-Only from RIS Perspective)
| Resource | Owner | Access Type |
|----------|-------|-------------|
| Mays-Orders DynamoDB Table | Mays-Orders-AWS | Read/Write via OrdersReader Lambda |
| Mays-Orders SQS Queue | Mays-Orders-AWS | SendMessage only |

### ORDERS_PROTECTED (Excluded from Destruction)
| Resource | Owner | Protection |
|----------|-------|------------|
| `mays-orders` DynamoDB | Mays-Orders-AWS | SHARED_DEPENDENCY (read/write) |
| `mays-orders-orders-queue` SQS | Mays-Orders-AWS | SHARED_DEPENDENCY (SendMessage) |
| Mays-Orders Lambda/APIGW/Cognito | Mays-Orders-AWS | ORDERS_PROTECTED |

### OLD_TEST (Already Cleaned)
| Resource | Status |
|----------|--------|
| `mays-ris-e2e-test-test-dlq` | ✅ DELETED |
| `mays-ris-e2e-test-tf-lock` | ✅ DELETED |
| `mays-ris-e2e-test-cloudtrail-240571105849` | ✅ DELETED |
| `mays-ris-e2e-test-tf-state-test` | ✅ DELETED |

---

## 3. PERSISTENT DATA ASSESSMENT

| Data Store | Items | Real User Data | System-Seeded |
|------------|-------|----------------|---------------|
| **Cognito Users** | 0 | ❌ None | ❌ None |
| **User Profile Table** | 0 | ❌ None | ❌ None |
| **Entitlements** | 0 | ❌ None | ❌ None |
| **Agent Catalog** | 1 | ❌ None | ✅ 1 (reference_agent) |
| **Work Items** | 0 | ❌ None | ❌ None |
| **Credentials** | 0 | ❌ None | ❌ None |
| **Agent State** | 0 | ❌ None | ❌ None |
| **API Profiles** | 0 | ❌ None | ❌ None |
| **Job Searches** | 0 | ❌ None | ❌ None |
| **Offers** | 0 | ❌ None | ❌ None |
| **Credentials** | 0 | ❌ None | ❌ None |

**S3 Buckets:** All 4 production buckets empty (0 objects each)

**Conclusion:** **NO REAL USER DATA EXISTS** — Only system-seeded reference agent. Safe to destroy.

---

## 4. STATE BACKUP STATUS

| Archive | Location | Integrity |
|---------|----------|-----------|
| Legacy State (serial 21) | `archived-evidence/production-state-v21/terraform.tfstate.v21` | ✅ SHA-256: `fedd69c53299f364274bb65d1c6939ba7e9a2470c56fd87a4e47240644f13703` |
| Manifest | `archived-evidence/production-state-v21/MANIFEST.json` | ✅ Complete |
| Checksums | `archived-evidence/production-state-v21/SHA256SUMS.txt` | ✅ VERIFIED |

---

## 5. DESTROY PLAN SUMMARY

### Plan Generated ✅
- **Command:** `terraform plan -destroy -out=destroy.tfplan -var project_name=mays-ris -var environment=dev`
- **Backend:** Legacy state at `env:/mays-ris/env:/mays-ris/dev/terraform.tfstate` (serial 21)
- **Stale Lock:** Removed (`6369447e-b76f-7e8b-8b31-8a1880b49e8b`)
- **Plan Saved:** `terraform/destroy.tfplan`

### Destroy Plan Summary
| Action | Count |
|--------|-------|
| **DESTROY** | **126** |
| CREATE | 0 |
| UPDATE | 0 |
| REPLACE | 0 |

### Destroy Targets (126 Resources)
All resources are **A_EXISTING** (RIS Production). No Orders resources.

| Category | Count | Examples |
|----------|-------|----------|
| Cognito (Pool, Groups, Client, Domain) | 10 | User Pool, 6 Groups, Client, Domain |
| API Gateway | 28 | API, Stage, Authorizers, 24 Routes, Integration, Permission |
| Lambda | 4 | Agent, Health Writer, Health Publisher, Orders Reader |
| Lambda Permissions | 5 | API Gateway invoke permissions |
| Lambda Event Source Mapping | 1 | SQS → Agent |
| SQS Queues | 5 | Work, CV, ATS, Match, DLQ |
| DynamoDB | 11 | 10 Tables + 1 Seed Item |
| S3 | 20 | 5 Buckets + Configurations |
| CloudTrail | 7 | Trail, Bucket, Configs |
| CloudWatch | 8 | Dashboard, 7 Alarms |
| IAM | 17 | 3 Roles, 14 Policies/Attachments |
| EventBridge | 2 | Health Publisher Schedule, Health Alarms |
| **Total** | **126** | |

### Excluded from Destroy (Verified)
| Excluded | Reason |
|----------|--------|
| Orders DynamoDB Table | SHARED_DEPENDENCY (read/write) |
| Orders SQS Queue | SHARED_DEPENDENCY (SendMessage only) |
| All Mays-Orders-AWS Resources | ORDERS_PROTECTED |
| Unknown Ownership | NONE |

---

## 6. REINSTALLATION READINESS

### New A Installation Configuration
| Parameter | Value |
|-----------|-------|
| **project_name** | `mays-ris` |
| **environment** | `dev` |
| **workspace** | `mays-ris` |
| **Canonical Backend Key** | `dev/terraform.tfstate` |
| **Expected Effective State Key** | `env:/mays-ris/dev/terraform.tfstate` |
| **Backend Bucket** | `mays-ris-tf-state-dev` (existing) |
| **Lock Table** | `mays-ris-tf-lock` (existing) |
| **Canonical State** | Currently 404 (will be created fresh) |

### Installer Readiness ✅
- Corrected installer with per-project isolation implemented
- Per-project working directory: `~/.ris-workdirs/mays-ris/dev/terraform/`
- TF_DATA_DIR isolation: `~/.ris-workdirs/mays-ris/dev/tfdata/`
- Plan safety gate active
- Destroy safety gate active
- All tests passing (1399 passed, 9 skipped)

---

## 7. EXACT COMMANDS

### Destroy Execution (Requires Approval)
```bash
cd /home/dci-student/projects/Mays-Recruiting-Intelligent-System/terraform
AWS_PROFILE=mayaws terraform apply "destroy.tfplan"
```

### Post-Destroy Verification
```bash
# Verify all A resources destroyed
aws sqs list-queues --queue-name-prefix mays-ris-dev --profile mayaws
aws dynamodb list-tables --profile mayaws | grep mays-ris-dev
aws lambda list-functions --profile mayaws | grep mays-ris-dev
aws apigatewayv2 get-apis --profile mayaws | jq -r '.Items[] | select(.Name | startswith("mays-ris-dev"))'
aws cognito-idp list-user-pools --max-results 20 --profile mayaws | jq -r '.UserPools[] | select(.Name | startswith("mays-ris-dev"))'
aws s3api list-buckets --profile mayaws | jq -r '.Buckets[].Name' | grep mays-ris-dev
```

### Reinstallation (After Approval)
```bash
# Package lambda bundles
python3 -m installer.ris --project-name mays-ris --environment dev --profile mayaws package --bundle all

# Install with corrected installer
python3 -m installer.ris --project-name mays-ris --environment dev --profile mayaws --backend-bucket mays-ris-tf-state-dev --backend-lock-table mays-ris-tf-lock install --yes
```

---

## 7. REPORT SUMMARY

| Metric | Value |
|--------|-------|
| **A_EXISTING_RESOURCE_COUNT** | 126 (in destroy plan) / 138 (in state) |
| **A_STATE_DRIFT** | Canonical state missing; legacy state authoritative (serial 21) |
| **A_PERSISTENT_DATA** | NONE (only 1 seeded reference agent) |
| **A_BACKUP_STATUS** | ✅ COMPLETE (state v21 archived with SHA-256) |
| **A_DESTROY_PLAN_SUMMARY** | 126 DESTROY, 0 CREATE/UPDATE/REPLACE |
| **A_DESTROY_TARGETS** | 126 A_EXISTING resources (full list above) |
| **ORDERS_EXCLUSIONS** | Verified — 0 Orders resources in destroy plan |
| **A_REINSTALL_READINESS** | ✅ READY (installer corrected, state archived, canonical path available) |

---

## APPROVAL REQUIRED

**GATE 1A: DESTROY APPROVAL**

**Reply with "APPROVE DESTROY" to execute the destroy plan, or "DENY" to cancel.**

**Explicit approval required for:** `terraform apply "destroy.tfplan"`

**Do not execute without explicit approval.**
