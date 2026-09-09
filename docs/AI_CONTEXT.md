# AI Context — Ground Zero

This document describes the context for AI coding agents working on Ground Zero.

## Project Overview

Ground Zero is the modular platform core for the Mays Recruiting Intelligence System. It provides:

- Standardized interfaces for agent development
- Serverless infrastructure on AWS
- Asynchronous processing via SQS
- Idempotent work item handling
- Multi-tenant support

## Key Concepts

### Agent Architecture

```
GROUND ZERO
    │
    └── Agent Slot
           │
           ├── CV Agent (Future)
           ├── ATS Agent (Future)
           ├── Match Agent (Future)
           └── +++++ (Future Agents)
```

### WorkItem System

Work items flow through SQS to Lambda workers:

```
Submit → SQS → Lambda → DynamoDB → Result
```

### Idempotency

SQS provides at-least-once delivery. Ground Zero ensures exactly-once outcomes via:

1. Stable idempotency keys
2. Work registry in DynamoDB
3. Atomic claims
4. Result verification

## Technical Stack

- **Language**: Python 3.14
- **Infrastructure**: Terraform 1.5+
- **AWS Services**: API Gateway, Cognito, DynamoDB, Lambda, SQS, S3, CloudWatch
- **Deployment**: CI/CD via GitHub Actions

## Agent Workflow

1. ANALYSIS → Understand codebase
2. DESIGN → Plan changes
3. DOCUMENT → Update docs
4. IMPLEMENT → Code changes
5. TEST → Validate
6. REPORT → Document results
7. STOP → Ready for next task

## AWS Context

- **Region**: eu-central-1 (default)
- **Pattern**: API → SQS → Lambda
- **State**: Terraform-managed
- **Security**: Cognito JWT, IAM least privilege

## Critical Rules

- No business agent logic in Ground Zero
- All agents must use WorkItem contract
- Follow idempotency pattern
- Protect against duplicate processing
- Use environment variables for config
- No hardcoded secrets

## Documentation Files

| File | Purpose |
|------|---------|
| docs/PROJECT_STATUS.md | Current project state |
| docs/CHANGELOG.md | Version history |
| docs/TEAMS.md | Roles (see AI_TEAM.md) |
| docs/BUILD.md | Build instructions |
| docs/DEPLOYMENT.md | Deployment process |
| docs/TERRAFORM_POLICY_GATE.md | Governance rules |