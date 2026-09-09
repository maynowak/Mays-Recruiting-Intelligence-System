# Ground Zero Architecture

## Core Vision

Ground Zero is a modular platform core that enables the deployment of multiple recruiting intelligence agents. It provides:

- Standardized interfaces for agent slots
- Secure authentication and authorization
- Asynchronous processing with exactly-once semantics
- Observability and monitoring
- DEV/TEST/PROD environment management

## Architecture Overview

### High-Level Flow

```text
                    GROUND ZERO
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             ▼             ▼
         AUTH           WORK           DATA
       ┌───────┐      ┌──────┐      ┌───────┐
       │Cognito│      │ SQS  │      │Dynamo │
       │  IAM  │      │WorkItem│     │  S3   │
       └───────┘      └──────┘      └───────┘
           │             │             │
           └─────────────┼─────────────┘
                         ▼
                  AGENT RUNTIME
                         │
              ┌───────────┼───────────┐
              │           │           │
              ▼           ▼           ▼
            CV Agent   ATS Agent   MATCH Agent
```

## Components

### 1. Authentication Layer (AUTH)

**Services:**
- Amazon Cognito User Pools
- IAM for service-to-service

**Features:**
- JWT-based authentication
- Role-based access control
- User pool groups for roles (Candidate, Recruiter, Admin)
- Multi-tenant support via tenantId in JWT claims

### 2. Work System Layer (WORK)

**Services:**
- Amazon SQS (queues per agent type)
- Lambda Event Source Mapping

**Features:**
- Decoupled asynchronous processing
- WorkItem model for job tracking
- Idempotency protection
- Worker queue isolation
- DLQ for dead messages

### 3. Data Layer (DATA)

**Services:**
- Amazon DynamoDB (work items, agent state)
- Amazon S3 (CV files, generated documents)

**Features:**
- Serverless persistence
- Multi-tenant data isolation
- TTL for cleanup
- Fine-grained access control

### 4. Agent Runtime

**Pattern:**
```text
SQS Queue
    │
    ▼
Lambda Event Source Mapping
    │
    ▼
Agent Handler
    │
    ├── Process WorkItem
    ├── Update Status
    └── Store Results
```

**Features:**
- Slot-based agent execution
- Standardized contracts
- Observability hooks
- Error handling

## WorkItem Lifecycle

```text
CREATED → QUEUED → RUNNING → COMPLETED
                   ↳ FAILED → RETRY → DEAD_LETTER
                   ↳ CANCELLED
                   ↳ EXPIRED
```

### WorkItem States

| State | Description | Transition To |
|-------|-------------|---------------|
| CREATE | Created, not yet processed | QUEUED |
| QUEUED | In SQS queue, waiting for worker | RUNNING |
| RUNNING | Being processed by worker | COMPLETED, FAILED |
| COMPLETED | Successfully finished | - |
| FAILED | Processing error | RETRY, DEAD_LETTER |
| RETRY | Will retry with backoff | QUEUED, DEAD_LETTER |
| DEAD_LETTER | Max retries exceeded | - |
| CANCELLED | Manually cancelled | - |
| EXPIRED | TTL reached | - |

## Agent Slot Concept

Each agent is a modular component with standardized interfaces:

### Agent Interface

```python
class Agent:
    def process_work(self, work_item: WorkItem) -> Result:
        """Process work item and return result."""
        pass
    
    def validate_work(self, work_item: WorkItem) -> bool:
        """Validate work item before processing."""
        pass
    
    def get_status(self, work_id: str) -> Status:
        """Get status of a work item."""
        pass
```

### Agent Slot Components

```text
Agent
├── API Contract (REST endpoints)
├── Work Contract (WorkItem schema)
├── SQS Queue
├── Lambda Worker
├── Business Logic
├── AI Integration Layer
├── Persistence
├── Tests
├── Observability
└── DEV/TEST/PROD
```

## API Architecture

### API Gateway Structure

```
/CDK           # Authentication
├── POST /signup
├── POST /login
└── GET /me

/agents         # Agent-specific endpoints
├── POST /cv/process
├── POST /ats/sync
├── POST /match/evaluate
└── GET /work/{id}

/work           # Work management
├── POST /work
├── GET /work/{id}
└── GET /work
```

### Authentication Flow

```
Client → Cognito (USER_PASSWORD_AUTH) → JWT
Client → API Gateway (JWT Authorizer) → Lambda
```

## SQS Work System

### Queue Structure

- **Per Agent Type** (optional, depends on workload isolation)
- **Per Tenant** (if tenant isolation is required at queue level)

### WorkItem Processing Flow

```python
def lambda_handler(event, context):
    for record in event['Records']:
        work_item = json.loads(record['body'])
        
        # Idempotent claim check
        if not claim_work(work_item.id):
            continue
        
        try:
            result = agent.process_work(work_item)
            store_result(result)
            mark_completed(work_item.id)
        except Exception as e:
            handle_failure(work_item, e)
```

### Reliability Mechanisms

1. **Idempotency Keys**: Prevent duplicate processing
2. **Atomic Claims**: Use DynamoDB conditional writes
3. **Retry Logic**: Exponential backoff with jitter
4. **DLQ**: Dead letter queue for failed items

## Multi-Tenancy

### Tenant Isolation Levels

| Level | Implementation | Cost | Security |
|-------|----------------|------|----------|
| Table | Separate DB tables | High | High |
| Queue | Separate SQS queues | Medium | Medium |
| Item | Single table/queue with tenantId | Low | Medium |

Ground Zero uses **Item-level isolation** for cost efficiency with proper encryption and access controls.

### Tenant Context Propagation

```python
def get_tenant_from_jwt(jwt_token):
    claims = decode_jwt(jwt_token)
    return claims.get('tenant_id')

def with_tenant_context(func):
    @wraps(func)
    def wrapper(event, context):
        tenant_id = get_tenant_from_jwt(event['headers']['Authorization'])
        return func(event, context, tenant_id=tenant_id)
    return wrapper
```

## Observability

### Metrics

- Lambda: Invocation count, duration, errors
- SQS: Queue depth, messages processed
- DynamoDB: Read/Write capacity, throttles
- API Gateway: Request count, latency, 4xx/5xx

### Logging

Structured JSON logs with:
- Request ID (correlation ID)
- Tenant ID
- Work ID
- Timestamp
- Log level

### Tracing

X-Ray integration for:
- Request tracing
- Performance analysis
- Error diagnosis

## DEV/TEST/PROD Environment Strategy

### Environment Isolation

```
┌────────┐    ┌────────┐    ┌────────┐
│ DEV    │    │ TEST   │    │ PROD   │
│        │    │        │    │        │
│ Shared │    │ Shared │    │ Dedicated│
│ Wallet │    │ Wallet │    │ Wallet │
└────────┘    └────────┘    └────────┘
```

Environment variables:
- `ENV=development|test|production`
- `TARGET_ACCOUNT=...`
- `TF_STATE_BUCKET=...`

### Terraform Structure

```
terraform/
├── main.tf           # Root module
├── variables.tf      # Root variables
├── outputs.tf        # Root outputs
├── prod/             # Production workspace
├── staging/          # Staging workspace
└── dev/             # Development workspace
```

## Security Model

### IAM Roles

| Role | Permissions | Scope |
|------|-------------|-------|
| User | API access, limited DB access | Per tenant |
| Service | Full Lambda permissions | Resource ARN |
| Admin | All permissions | Account |

### Cognito Groups

- `Candidates`: Limited API access
- `Recruiters`: Read/write to tenant resources
- `CompanyAdmins`: Manage tenant resources
- `PlatformAdmins`: Full platform access

## Cost Optimization

### Optimization Strategies

1. **Serverless**: Pay only for execution time
2. **On-demand DynamoDB**: No provisioning waste
3. **SQS**: No polling costs
4. **CloudWatch Logs**: Retention policies
5. **API Gateway**: HTTP API (cheaper than REST)

### Free Tier Configuration

| Service | Free Tier | Usage |
|---------|-----------|-------|
| Lambda | 1M invocations | ✓ |
| DynamoDB | 25 GB storage | ✓ |
| SQS | 1M requests | ✓ |
| API Gateway | 1M requests | ✓ |
| CloudWatch | 5GB logs | ✓ |

## Future Extensibility

### Planned Integrations

- AI Execution Layer (centralized AI calls)
- Notification System (SES for emails)
- Billing Integration (for cost tracking)
- Analytics Pipeline (for insights)

### Versioning Strategy

- API Versioning: v1, v2, ...
- Agent Contracts: Backward compatible
- Terraform Modules: Semantic versioning