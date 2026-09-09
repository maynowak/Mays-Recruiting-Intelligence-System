# Technical Requirements

## Architecture Constraints

### G0.1: Serverless Foundation
- All compute via AWS Lambda
- No EC2, ECS, or self-managed infrastructure
- Event-driven architecture using SQS

### G0.2: AWS Managed Services Preference
- Prefer AWS-managed services over customer-managed
- Use AWS-free tier eligible services where possible
- Leverage AWS native integrations

### G0.3: Stateless Agents
- Agents must be stateless
- Shared state in DynamoDB or S3
- No local file system persistence between invocations

### G0.4: Single Responsibility Principle
- Each agent handles one domain of business logic
- Clear boundaries between agents
- Minimal inter-agent dependencies

## Technology Stack

### Core Services
| Layer | Service | Rationale |
|-------|---------|-----------|
| API Gateway | HTTP API (V2) | Lower cost, native JWT support |
| Authentication | Amazon Cognito | Managed user pools, JWT |
| Queue | Amazon SQS | Decoupled async processing |
| Compute | AWS Lambda | Serverless, auto-scaling |
| Database | DynamoDB | NoSQL, serverless, fast |
| Storage | S3 | Object storage, scalable |
| Monitoring | CloudWatch | Native AWS observability |

### Infrastructure
- **Terraform**: Infrastructure as Code
- **Python 3.14**: Lambda runtime
- **AWS SDK**: Service interactions

### Development
- **Terraform**: IaC
- **Python**: Agent development
- **Git**: Version control
- **CI/CD**: Standard pipeline

## Naming Conventions

### Resource Naming Pattern
```
{project-name}-{component}-{environment}
```

Example: `mays-ris-api-prod`, `mays-ris-lambda-cv-dev`

### Tagging Strategy
- `Project`: mays-recruiting-intelligence-system
- `Maker`: mays-ris
- `Environment`: Development | Test | Production
- `Component`: api, lambda, dynamodb, etc.

## Data Model Requirements

### WorkItem Schema
- `workId`: UUID, primary key
- `type`: Work item type
- `tenantId`: Tenant identifier
- `entityId`: Target entity
- `requestedBy`: Who requested
- `idempotencyKey`: For deduplication
- `status`: CREATED, QUEUED, RUNNING, COMPLETED, FAILED, RETRY, DEAD_LETTER, CANCELLED, EXPIRED
- `attempt`: Retry counter
- `claimedBy`: Worker identifier
- `claimedAt`: Timestamp
- `completedAt`: Timestamp
- `resultRef`: Result location reference
- `error`: Error details if failed

### Multi-Tenancy
- All data operations include tenant context
- DynamoDB tables support tenant isolation
- IAM policies enforce tenant boundaries

## API Requirements

### Authentication
- JWT issued by Cognito
- All API endpoints require valid JWT
- Roles configured in Cognito groups

### Endpoints
Standard endpoints for each agent:
- `POST /{agent}/work` - Submit work
- `GET /{agent}/work/{id}` - Get work status
- `GET /{agent}/work` - List work items (optional, with pagination)

## Deployment Requirements

### Environment Isolation
- DEV, TEST, PROD environments are fully isolated
- Separate AWS accounts or separate resources per environment
- No shared resources between environments

### Zero Downtime Deployments
- Blue-green or canary deployments for critical paths
- Database migrations must be backward compatible
- Feature flags for gradual rollout

### Idempotency
- All operations must be idempotent
- Use idempotency keys for write operations
- Detect and handle duplicate requests gracefully

## Monitoring Requirements

### Metrics
- Lambda invocation count
- Lambda duration (p50, p90, p99)
- Error rates
- SQS queue depth
- DynamoDB read/write capacity

### Logging
- Structured JSON logs
- Include correlation IDs
- Log levels: DEBUG, INFO, WARN, ERROR
- Logs retained for at least 30 days

### Alerting
- Error rate > 1% triggers alert
- SQS queue depth > 1000 triggers alert
- Lambda duration > 30s triggers alert
- Daily cost > budget triggers alert