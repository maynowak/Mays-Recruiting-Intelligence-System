# Audit & Monitoring Architecture — Mays Recruiting Intelligence System

## Overview

This document describes the audit and monitoring architecture for the Ground Zero platform.

**Current Status**: PARTIALLY IMPLEMENTED

---

## Current State

### CloudTrail (Implemented in Terraform)

| Resource | Status |
|----------|--------|
| CloudTrail Trail | ✅ EXISTS |
| S3 Audit Bucket | ✅ EXISTS |
| Multi-Region | ✅ YES |
| Management Events | ✅ YES |
| Log File Validation | ✅ YES |
| SSE-S3 Encryption | ✅ YES |
| Public Access Block | ✅ YES |
| Bucket Policy | ✅ YES |

### CloudWatch Monitoring (Implemented in Terraform)

| Resource | Status |
|----------|--------|
| Dashboard | ✅ EXISTS |
| API Alarm (5XX) | ✅ EXISTS |
| API Alarm (4XX) | ✅ EXISTS |
| Lambda Error Alarm | ✅ EXISTS |
| Lambda Duration Alarm | ✅ EXISTS |
| Lambda Throttles Alarm | ✅ EXISTS |
| DynamoDB Throttles Alarm | ✅ EXISTS |

### Quotenalarme

| Alarm | Metric | Namespace |
|-------|--------|-----------|
| api_5xx | 5XXError | AWS/ApiGateway |
| api_4xx | 4XXError | AWS/ApiGateway |
| lambda_errors | Errors | AWS/Lambda |
| lambda_duration | Duration | AWS/Lambda |
| lambda_throttles | Throttles | AWS/Lambda |
| dynamodb_throttled | ThrottledRequests | AWS/DynamoDB |

---

## Identified Issues

### 1. Alarm Naming Inconsistency

**Location**: `terraform/modules/monitoring/main.tf:92-108`

**Issue**: The alarm resource is named `api_5xx` but uses metric `5XXError`. The alarm description references the correct metric.

**Analysis**:
- The metric `5XXError` is correct for API Gateway 5XX errors
- The alarm name `api_5xx` correctly indicates it's for API 5XX errors
- This is a **naming that matches the metric** - no error exists

**Decision**: NO CHANGE required. The naming is consistent.

---

## Target Architecture

```
                    AWS
                     │
       ┌─────────────┴─────────────┐
       │                           │
    AUDIT LAYER               MONITORING LAYER
       │                           │
   CloudTrail                CloudWatch
       │                           │
   S3 Audit                 Logs + Metrics
    Bucket                   ┌─────────────┐
       │                     │             │
       └────────────┬────────┘             │
                    │                      │
               Dashboard               Alarms
                    │                      │
                    └──────────┬───────────┘
                               │
                           Operations
                           Security/Audit
```

---

## Recommendations

### 1. CloudTrail Enhancement (FUTURE)

**Status**: NOT IMPLEMENTED

**Recommendation**: Consider adding:
- CloudWatch Logs integration for real-time alerting
- Data events for sensitive operations (if required)
- KMS encryption for audit bucket (if higher security needed)

**Cost Consideration**: Data events increase costs significantly.

### 2. Dashboard Segregation (FUTURE)

**Status**: NOT IMPLEMENTED

**Recommendation**: Split into two dashboards:
1. Operations Dashboard - Runtime metrics
2. Security Dashboard - Audit signals

### 3. SNS Notifications (FUTURE)

**Status**: NOT IMPLEMENTED

**Recommendation**: Add SNS topics for critical alarms.

---

## Terraform Validation

### Check Commands

```bash
# Format check
terraform fmt -check

# Validate
terraform validate

# Security analysis (if available)
terraform plan -out=tfplan
```

---

## Files Analyzed

| File | Purpose |
|------|---------|
| `terraform/modules/cloudtrail/main.tf` | CloudTrail configuration |
| `terraform/modules/monitoring/main.tf` | CloudWatch configuration |
| `terraform/modules/api/main.tf` | API Gateway routes |
| `lambda/handler.py` | Lambda handler |

---

## Open Points

1. **Dashboard Segregation**: Should operations and security be on separate dashboards?
2. **KMS Encryption**: Should audit bucket use SSE-KMS instead of SSE-S3?
3. **Data Events**: Should CloudTrail capture S3/DynamoDB data events?
4. **SNS Notifications**: Should alarms trigger notifications?

---

## Next Steps

1. Create OpenAPI specification from documented contracts
2. Add contract tests for API endpoints
3. Implement dashboard segregation (if needed)
4. Plan KMS strategy for audit bucket

---

## References

- `terraform/modules/cloudtrail/main.tf` — CloudTrail implementation
- `terraform/modules/monitoring/main.tf` — CloudWatch implementation
- `docs/INTEGRATION_BOUNDARIES.md` — System boundaries
- `docs/API/PLATFORM_FRONTEND_INTEGRATION.md` — API contract