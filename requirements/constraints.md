# Constraints

## Technical Constraints

### TC1: Runtime Constraints
- Lambda runtime: Python 3.14 only
- No additional compiled dependencies in Lambda
- Package size < 50MB (unzipped)

### TC2: Resource Constraints
- Default memory: 128MB (can be increased)
- Timeout: 30 seconds (configurable, max 900 seconds)
- Environment variables for configuration only

### TC3: Data Constraints
- DynamoDB item size: < 400KB
- S3 object size: < 5TB (soft limit)
- WorkItem ttl: 30 days for dead items

### TC4: API Constraints
- REST/JSON only (no GraphQL, gRPC in v1)
- Rate limiting per user: 100 requests/minute
- Request/response size: < 6MB

## Operational Constraints

### OC1: Deployment Constraints
- Terraform state stored remotely (S3 + DynamoDB lock)
- Manual approval required for production changes
- No automated production deployments

### OC2: Cost Constraints
- Development environment: <$50/month
- Sandbox environment: <$200/month
- No reserved instances or Savings Plans

### OC3: Security Constraints
- All traffic encrypted in transit (TLS 1.2+)
- Data at rest encrypted (AWS managed keys)
- No hardcoded credentials

### OC4: Availability Constraints
- No requirement for high availability in development
- Production: multi-AZ for DynamoDB, S3
- Single region deployment (no cross-region replication)

## Business Constraints

### BC1: Project Scope
- Ground Zero: Platform only, no business agents
- Agents are separate repositories/projects
- No UI development in this repository

### BC2: Documentation Constraints
- All code changes require documentation updates
- ADRs required for architecture decisions
- Reports required for each work session

### BC3: Timeline Constraints
- G0.1 - G0.6: Foundation (Weeks 1-2)
- G0.7 - G0.10: Core components (Weeks 3-4)
- G0.11 - G0.15: Finalization (Weeks 5-6)

## Environmental Constraints

### EC1: Environment Constraints
- DEV: Shared AWS account, isolated resources
- TEST: Separate resources from DEV
- PROD: Separate AWS account recommended

### EC2: Region Constraints
- Primary region: eu-central-1 (Frankfurt)
- Future: us-east-1, ap-northeast-1 for global rollout

### EC3: Service Quotas
- Lambda: 1000 concurrent executions (soft limit)
- SQS: 120,000 messages/second (regional)
- DynamoDB: On-demand mode initially