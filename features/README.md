# Features — Ground Zero Platform

This document describes the platform capabilities available in Ground Zero.

## Feature Status

| Feature | Status | Description |
|---------|--------|-------------|
| G0.1 Repository | ✅ COMPLETE | Foundation and documentation |
| G0.2 AWS/Terraform | ✅ COMPLETE | Infrastructure foundation |
| API Gateway | ✅ COMPLETE | HTTP API with JWT auth |
| Authentication | ✅ COMPLETE | Cognito-based JWT |
| Work System | ✅ IMPLEMENTED | SQS-based processing |
| Idempotency | ✅ IMPLEMENTED | DynamoDB work registry |
| Lambda Runtime | ✅ COMPLETE | Python 3.14 worker |
| DynamoDB | ✅ COMPLETE | Work items table |
| S3 Storage | ✅ COMPLETE | Data bucket |
| IAM Security | ✅ COMPLETE | Least privilege |
| Observability | ✅ PARTIAL | CloudWatch logs |
| CI/CD | ✅ COMPLETE | GitHub Actions |

## Working Features

### Ground Zero Core

- **Repository Structure**: Organized for scalability
- **Infrastructure**: Full Terraform modules
- **Authentication**: Cognito user pool setup
- **Work Queue**: SQS with DLQ configured
- **Data Storage**: DynamoDB with GSI
- **Agent Runtime**: Lambda handler template

### Development Features

- **Agent Contract**: Standardized interface
- **Work Item Model**: Complete lifecycle
- **Build System**: Lambda packaging script
- **Documentation**: Comprehensive guides
- **Deployment**: CI/CD with policy gates

## Partial Features

| Feature | Status | Notes |
|---------|--------|-------|
| Observability | PARTIAL | Basic monitoring, full dashboard needs work |
| VPC | REFERENCE | Structure defined, not deployed |
| Cost Optimization | PLANNED | Needs tuning after deployment |

## Future Features

| Feature | Priority | Notes |
|---------|----------|-------|
| PDF/CV Processing Agent | High | For later phases |
| ATS Integration Agent | Medium | External API integration |
| Matching Agent | High | AI-powered matching |
| Notification System | Medium | Email/SNS support |

---

## Feature Evaluation Criteria

Before adding new features, evaluate:

1. **Purpose**: Does it fit Ground Zero?
2. **Scope**: Is it platform or agent logic?
3. **Cost**: AWS resource impact?
4. **Complexity**: Development overhead?
5. **Dependencies**: What does it need?

---

## Notes

- Platform features (G0.1, G0.2, API, Auth, Work System) are **COMPLETE**
- Agent features (CV, ATS, Match) are **FUTURE**
- Infrastructure features are working but may need tuning after deployment