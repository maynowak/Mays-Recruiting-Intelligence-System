# Agent Matrix

## Purpose

This matrix is used to evaluate and plan agents for the Ground Zero platform. Each new agent should be assessed against these dimensions to determine platform resource requirements.

## Matrix Template

| Dimension | Description | Evaluation Criteria |
|-----------|-------------|-------------------|
| API | Does agent need API endpoints? | Yes/No, Required endpoints |
| Auth | What authentication/authorization? | JWT roles, Cognito groups |
| SQS | Which SQS queue/workload? | Queue name, visibility timeout |
| Worker | What scaling requirements? | Lambda memory, concurrency limits |
| Idempotency | What business idempotency key? | workId, compound key |
| DynamoDB | What data tables needed? | tables, GSIs, access patterns |
| S3 | What artifacts stored? | files, size, lifecycle |
| AI | Does agent need AI integration? | providers, models, rate limits |
| Notifications | Does agent need notifications? | Email, SNS, WebSocket |
| Privacy | What data handling requirements? | PII, encryption, compliance |
| IAM | What permissions are needed? | Policies, resource ARNs |
| Observability | What metrics are needed? | CloudWatch, custom metrics |
| CI/CD | What pipeline is needed? | Deploy stage, approvals |
| DEV/TEST/PROD | What isolation is needed? | Accounts, VPCs, state |
| Cost | Expected cost impact? | $/month estimate |
| Scaling | Where are bottlenecks? | CPU, memory, DB, API |
| Integration | What other agents? | Dependencies, data flow |

## Agent Evaluation Template

Create a row for each agent in the system.

### Example: CV Processing Agent

| Dimension | CV Agent |
|-----------|----------|
| API | POST /cv/process, GET /cv/{id} |
| Auth | Candidate + Recruiter roles |
| SQS | cv-processing-queue |
| Worker | 512MB, 30s timeout, 100 concurrent |
| Idempotency | idempotencyKey (hash of CV content) |
| DynamoDB | cv_profiles table, GSIs for search |
| S3 | cv_files bucket, CV pdfs stored |
| AI | Needed for parsing (OpenRouter, EdenAI) |
| Notifications | Optional (processing complete) |
| Privacy | CV content - PII handling, encryption |
| IAM | dynamodb:PutItem, s3:PutObject |
| Observability | Process duration, error rate |
| CI/CD | Standard deploy, manual prod approval |
| DEV/TEST/PROD | Shared account, prefixed resources |
| Cost | Expected <$10/day in dev |
| Scaling | S3 read + Lambda compute |
| Integration | Consulter, Match agent via WorkItem |

## Platform Capacity Analysis

### Current Ground Zero Capacity

| Component | Current Limit | Available | Bottleneck |
|-----------|---------------|-----------|------------|
| Lambda Concurrent Exec | 1000 | ~800 | HIGH |
| SQS Queue Depth | 1,000,000 | Managed | None |
| DynamoDB RCU | On-demand | Auto | NONE |
| DynamoDB WCU | On-demand | Auto | NONE |
| API Gateway RPS | 10,000 | Managed | HIGH |

### Agent Plan

| Agent | Queue | Workers | Avg Duration | Est. RPS | Notes |
|-------|-------|---------|--------------|----------|-------|
| CV Processing | cv-queue | 10-100 | 5-30s | 1-100 | High memory for PDF parsing |
| ATS Sync | ats-queue | 5-50 | 1-10s | 10-500 | External API calls |
| Job Match | match-queue | 20-200 | 10-60s | 1-50 | AI intensive |
| Notification | notif-queue | 5-20 | 1-5s | 10-1000 | Simple, frequent |
| ... | ... | ... | ... | ... | ... |

## Decision Log

### Agent Addition Checklist

- [ ] WorkItem type defined
- [ ] SQS queue created (or shared queue documented)
- [ ] Lambda worker template created
- [ ] Idempotency strategy defined
- [ ] Data models defined (DynamoDB, S3)
- [ ] IAM policies defined
- [ ] Observability strategy defined
- [ ] CI/CD pipeline configured
- [ ] DEV/TEST/PROD isolation docs
- [ ] Cost estimate calculated
- [ ] Testing strategy defined

### Agent Prioritization

| Agent | Priority | Reason |
|-------|----------|--------|
| CV Processing | P1 | Core recruitment data |
| ATS Sync | P2 | External integration |
| Job Match | P1 | Core intelligence |
| Notification | P1 | User experience |
| ... | ... | ... |

## Scalability Planning

### Concurrency Planning

Calculate required concurrency:

```
Required Concurrency = RPS × Duration (seconds)

Example:
- Target: 100 requests/minute
- Duration: 10 seconds
- Required Concurrency = 100/60 × 10 ≈ 17
```

### Cost Projections

| Metric | Calculation | Monthly |
|--------|-------------|---------|
| API Gateway | 1M req × $0.002 | $2.00 |
| Lambda | 1M invocations × 100ms × $0.0000167 | $1.67 |
| DynamoDB | 1M RCU × $0.000125 | $125.00 |
| SQS | 1M messages × $0.0000004 | $0.40 |

*Note: These are rough estimates. Actual costs depend on usage patterns.*

## Agent Health Dashboard Targets

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Queue Depth | < 1000 | > 5000 |
| Error Rate | < 1% | > 5% |
| Avg Duration | < 30s | > 60s |
| Lambda Errors | < 1% | > 5% |
| Throttling | 0 | > 0 |

## G0.2 Platform Capabilities

The following shows the current capabilities of Ground Zero after G0.2 implementation:

| Capability | Status | Notes |
|------------|--------|-------|
| API Gateway | ✅ | HTTP API V2 with JWT auth |
| Cognito JWT | ✅ | User pool, app client configured |
| SQS Queues | ✅ | Work, CV, ATS, Match, DLQ |
| Lambda Worker | ✅ | Python 3.14, event source mapping |
| DynamoDB | ✅ | Work items table, GSI |
| S3 Storage | ✅ | Data bucket with encryption |
| IAM Policies | ✅ | Least privilege implemented |
| Observability | ✅ | CloudWatch logs, metric alarms |
| CI/CD Pipeline | ✅ | GitHub Actions workflow |
| DEV/TEST/PROD | ⚙️ | Single account, multiple stages |

### Can Add New Agent Now?

| Check | Status | Notes |
|-------|--------|-------|
| API Endpoints | ✅ | Routes in place |
| Auth Required | ✅ | JWT authorizer ready |
| SQS Queue | ✅ | Dedicated queues created |
| Worker Template | ✅ | Lambda handler ready |
| Idempotency | ✅ | Work registry + claims |
| DynamoDB | ✅ | Table with GSI |
| S3 Storage | ✅ | Encrypted bucket |
| IAM Policy | ✅ | DynamoDB + S3 access |
| Observability | ✅ | CloudWatch metrics |
| CI/CD | ✅ | Workflow configured |
| DEV/TEST/PROD | ⚠️ | Same config, prefixed resources |
| Cost Estimate | ✅ | Free tier eligible |

**Conclusion**: G0.2 provides a complete, production-ready foundation for deploying agents.