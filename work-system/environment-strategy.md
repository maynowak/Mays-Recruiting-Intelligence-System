# DEV / TEST / PROD Environment Strategy

## Overview

Ground Zero supports three deployment environments: Development, Test, and Production. Each environment provides isolated resources for safe testing and deployment.

## Environment Characteristics

| Environment | Purpose | Access | Deployment |
|-------------|---------|--------|------------|
| DEV | Feature development | Open to developers | Automated |
| TEST | Integration testing | Restricted | Manual |
| PROD | Production serving | Restricted | Manual approval |

## Terraform Structure

```
terraform/
├── modules/
│   ├── api/
│   ├── lambda/
│   ├── dynamodb/
│   ├── sqs/
│   ├── iam/
│   ├── cognito/
│   └── monitoring/
├── main.tf              # Root module
├── variables.tf
├── outputs.tf
├── dev.tfvars           # DEV configuration
├── test.tfvars          # TEST configuration
└── prod.tfvars          # PROD configuration
```

## Environment Configuration

### Naming Convention

All AWS resources follow the pattern:

```
<project>-<component>-<environment>
```

Example:
- `mays-ris-api-dev`
- `mays-ris-lambda-cv-test`
- `mays-ris-dynamodb-prod`

### Resource Isolation

| Resource Type | DEV | TEST | PROD |
|---------------|-----|------|------|
| AWS Account | Shared | Shared | Separate |
| VPC | Shared | Shared | Dedicated |
| DynamoDB Tables | Prefixed | Prefixed | Separate |
| SQS Queues | Prefixed | Prefixed | Separate |
| Lambdas | Prefixed | Prefixed | Separate |
| Cognito | Shared | Shared | Separate |
| S3 Buckets | Prefixed | Prefixed | Separate |

## Deployment Pipeline

### CI/CD Stages

```
Git Commit → Build → Test → Plan → Apply(DEV) → Manual Approve → Plan(PROD) → Apply(PROD)
```

### Stages

1. **Build**: Compile code, run unit tests
2. **Test**: Run integration tests against test environment
3. **Plan**: Generate Terraform plan
4. **Apply DEV**: Deploy to development
5. **Manual Approve**: Human approval required
6. **Plan PROD**: Generate production plan
7. **Apply PROD**: Deploy to production

### CI/CD Configuration

Using GitHub Actions with environment protection:

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: terraform init
      - run: terraform plan -var-file="prod.tfvars"

  apply:
    needs: plan
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - run: terraform init
      - run: terraform apply -var-file="prod.tfvars"
```

## Environment Variables

### Common Variables

```terraform
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = var.environment in ["dev", "test", "prod"]
    error_message = "Environment must be dev, test, or prod."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}
```

### Environment-Specific Variables

| Variable | DEV | TEST | PROD |
|----------|-----|------|------|
| endpoint | http://localhost:5000 | https://test.example.com | https://api.example.com |
| debug | true | false | false |
| log_level | DEBUG | INFO | ERROR |
| monitoring_enabled | true | true | true |

## State Management

### State Storage

Each environment has its own S3 bucket for Terraform state:

```
mays-ris-tf-state-{environment}
    ├─ terraform.tfstate
    ├─ terraform.tfstate.backup
    └─ lock table
```

### Locking

```terraform
terraform {
  backend "s3" {
    bucket         = "mays-ris-tf-state-${var.environment}"
    key            = "terraform.tfstate"
    region         = "eu-central-1"
    encrypt        = true
    dynamodb_table = "mays-ris-tf-lock"
  }
}
```

## Secrets Management

### Parameter Store

Store secrets in AWS Systems Manager Parameter Store:

```
/mays-ris/{environment}/
├── /database/secret
├── /cognito/client-secret
├── /api/jwt-secret
└── /ai/provider-key
```

### Secret Rotation

- Automatic rotation for critical secrets
- Manual rotation process documented
- Access via IAM policies only

## Cost Management

### Environment Budgets

| Environment | Monthly Budget | Alert Threshold |
|-------------|----------------|-----------------|
| DEV | $50 | 50% |
| TEST | $200 | 75% |
| PROD | $500 | 80% |

### Cost Allocation Tags

All resources tagged with:

```
Project = mays-recruiting-intelligence-system
Environment = dev|test|prod
Component = api|lambda|dynamodb|sqs
```

## Security Considerations

### Environment Isolation

1. **Network Isolation**: Each environment in its own VPC (PROD only)
2. **Data Isolation**: Separate DynamoDB tables/keys
3. **Queue Isolation**: Separate SQS queues
4. **IAM Isolation**: Separate execution roles

### Access Controls

| Role | DEV | TEST | PROD |
|------|-----|------|------|
| Developer | Full | Read | Read |
| QA | Read | Full | Read |
| Admin | Full | Full | Full |
| Deploy Bot | Write | Write | Write |

## Testing Strategy

### Test Environments

| Type | Environment | Purpose |
|------|-------------|---------|
| Unit Tests | Any | Test individual functions |
| Integration Tests | Test | Test component integration |
| End-to-End Tests | Test | Test full workflow |
| Load Tests | Test | Test performance |
| Smoke Tests | DEV | Verify deployment is working |

### Test Data

- DEV: Minimal data, fixtures
- TEST: Representative data
- PROD: Production data (masked)

## Migration Process

### Adding a New Agent

1. Create test cases
2. Deploy to DEV
3. Validate functionality
4. Deploy to TEST
5. Run integration tests
6. Deploy to PROD with approval

### Environment Promotion

```
Feature Branch → DEV
                 ↓
             Pull Request → MESOMerge to main → TEST
                                                   ↓
                                              Manual approval → PROD
```

## Rollback Procedures

### Terraform Rollback

```bash
# Rollback to previous state
terraform state rollback <state-version>
terraform apply

# Or use target to undo specific changes
terraform plan -target=module.component
terraform apply -target=module.component
```

### Database Rollback

For schema changes:
1. Maintain backward compatibility
2. Deploy new version
3. Run migration
4. Verify
5. Deploy next version

## Environment Health Checks

### DEV

- Daily checks
- Run on every commit
- Report in PR comments

### TEST

- Hourly checks
- Run after each deployment
- Alert on failures

### PROD

- Continuous monitoring
- All metrics and alerts active
- SLA monitoring