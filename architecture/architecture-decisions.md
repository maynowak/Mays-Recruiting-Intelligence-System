# Architecture Decisions

This document records architecture decisions made for the Ground Zero platform.

## ADR-001: Serverless Architecture (Lambda + SQS)

**Status:** ACCEPTED

### Context

We need a scalable, cost-effective architecture for processing recruitment intelligence tasks. These tasks vary in duration and volume, and we want to avoid managing servers.

### Decision

Use AWS Lambda for compute and SQS for queuing.

### Rationale

- **Scalability**: Lambda auto-scales with queue backlog
- **Cost**: Pay-per-use, no idle resources
- **Performance**: SQS provides exact-once delivery semantics
- **Simplicity**: No server management

### Alternatives Considered

| Option | Evaluation |
|--------|------------|
| EC2 | Management overhead, over-provisioning |
| ECS/Fargate | More complex than needed |
| Step Functions | Adds unnecessary complexity for simple workflows |

### Consequences

- Cold starts may affect latency
- Limited execution time (15 min max)
- Need for idempotency

---

## ADR-002: DynamoDB for Work Items

**Status:** ACCEPTED

### Context

We need persistent storage for work items that supports:
- High write throughput
- Query by status and tenant
- TTL for cleanup

### Decision

Use DynamoDB with on-demand capacity and a GSI for status queries.

### Rationale

- Serverless
- Flexible schema
- Strong query capabilities
- Built-in TTL

### Attributes

- Hash key: workId
- GSI: tenantId + status

---

## ADR-003: Cognito for Authentication

**Status:** ACCEPTED

### Context

We need user authentication and role-based access control.

### Decision

Use Amazon Cognito with JWT tokens.

### Rationale

- Managed service
- JWT support
- Group-based roles
- Social identity provider support

### Groups

- Candidates
- Recruiters
- CompanyAdmins
- PlatformAdmins

---

## ADR-004: Idempotency via Work Registry

**Status:** ACCEPTED

### Context

SQS provides at-least-once delivery. We need exactly-once business outcomes.

### Decision

Store work status in DynamoDB and check before processing.

### Implementation

1. Check DynamoDB for existing COMPLETED status
2. Atomic claim via conditional write
3. Store result on completion

### Rationale

- Ensures no duplicate processing
- Works with SQS's delivery model
- Provides audit trail

---

## ADR-005: Agent-as-a-Module Pattern

**Status:** ACCEPTED

### Context

We need to support multiple agents (CV, ATS, Match) with common patterns.

### Decision

Define a standard Agent interface that all agents implement.

### Interface

```python
class Agent:
    def process_work(self, work_item): ...
    def validate_work(self, work_item): ...
    def get_status(self, work_id): ...
```

### Benefits

- Consistent behavior across agents
- Easier to add new agents
- Standard contracts

---

## ADR-006: Per-Agent SQS Queues

**Status:** PROPOSED

### Context

Different agents have different processing characteristics and scaling requirements.

### Decision

Use separate SQS queues for each agent type.

### Benefits

- Independent scaling
- Better monitoring
- Isolated failures

### Trade-offs

- More queues to manage
- Slightly more complex

---

## ADR-007: Terraform Module Structure

**Status:** ACCEPTED

### Context

We need maintainable, reusable infrastructure code.

### Decision

Create Terraform modules for each major component.

### Structure

```
terraform/
├── modules/
│   ├── api/
│   ├── lambda/
│   ├── dynamodb/
│   ├── sqs/
│   ├── iam/
│   └── monitoring/
├── main.tf
├── variables.tf
└── outputs.tf
```

### Benefits

- Reusable
- Testable
- Versionable

---

## Decision Matrix

| ADR | Topic | Decision Date | Status |
|-----|-------|---------------|--------|
| ADR-001 | Architecture | 2026-09-09 | ACCEPTED |
| ADR-002 | Database | 2026-09-09 | ACCEPTED |
| ADR-003 | Authentication | 2026-09-09 | ACCEPTED |
| ADR-004 | Idempotency | 2026-09-09 | ACCEPTED |
| ADR-005 | Agent Pattern | 2026-09-09 | ACCEPTED |
| ADR-006 | Queue Strategy | 2026-09-09 | PROPOSED |
| ADR-007 | Terraform | 2026-09-09 | ACCEPTED |