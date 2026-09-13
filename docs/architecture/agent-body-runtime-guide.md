# Agent Body & Runtime — Architectural Development Guide

This document establishes the architectural foundation for the Agent Body runtime layer, defining the separation of concerns between infrastructure, agent coordination, and domain logic.

## Key Separation of Concerns

### Agent Function
Agent Function is the entry point for external systems. It receives requests, validates them, creates work items, and stores them in DynamoDB.

**Verification**: ✅ G0.4 IMPLEMENTED - `POST /api/agents/{agentId}/execute`

### Agent Body
Agent Body is the reusable technical runtime that coordinates agent execution. It provides:
- Routing (by work type, capability, or agent ID)
- Context extraction
- Execution lifecycle management
- Result formatting
- Observability hooks

**Verification**: ✅ S2.5 IMPLEMENTED - All components tested and working

### Runtime
Runtime is the underlying infrastructure (Lambda, SQS, DynamoDB) that executes work.

**Verification**: ✅ G0.2-G0.4 CONFIGURED

### Execution Profile
Execution Profile defines how agents are executed. Currently: Lambda. Future: MicroVM for isolation.

**Status**: Lambda is the current standard. MicroVM is a future capability.

---

## Component Matrix

| Component | Owned By | Responsibility |
|-----------|----------|----------------|
| API Gateway | Ground Zero | Request routing |
| Cognito | Ground Zero | Authentication |
| SQS Queue | Ground Zero | Work queuing |
| DynamoDB | Ground Zero | State persistence |
| Lambda Handler | Ground Zero | Event processing |
| Event Source Mapping | Ground Zero | SQS→Lambda trigger |
| **Agent Body** | **Agent Framework** | **Coordination layer** |
| **Router** | **Agent Body** | Work item routing |
| **Context** | **Agent Body** | Context extraction |
| **Executor** | **Agent Body** | Execution orchestration |
| **Result Handler** | **Agent Body** | Result formatting |
| **Monitor** | **Agent Body** | Metrics collection |
| Domain Agent | Agent | Business logic |
| May's Orders | External | Order processing |

---

## Identity, Sequence, Idempotency, Retry

These are **central standards** that apply across all agents:

### Central Identity
- `workId` - Unique identifier for each work item
- `tenantId` - Tenant isolation
- `requestId` - Request correlation

### Sequence & Attempt
- `attempt` - Retry count
- `createdAt` - Initiation timestamp
- `expiresAt` - TTL timestamp

### Idempotency
Managed by Ground Zero:
- DynamoDB conditional writes for work claiming
- Existing COMPLETED check before processing
- Result storage for verification

### Retry / Recovery
- SQS DLQ for max retries exceeded
- Exponential backoff with jitter
- Status transitions tracked in DynamoDB

### Ready Notification
Workers read from SQS and update DynamoDB when processing completes.

---

## Trigger & Dependencies

### Work Queue Trigger
```
SQS Message
    ↓
Event Source Mapping
    ↓
Lambda (Unified Handler)
    ↓
_process_work_item()
```

### Event Dependencies
The Lambda handler processes both:
- API Gateway events (HTTP API)
- SQS events (work processing)

---

## Failure / Retry / Recovery

### SQS-level Retry
1. Message fails processing → automatic retry
2. After configured attempts → DLQ
3. DLQ allows inspection and recovery

### Application-level Idempotency
```python
# Check if already processed
if work_item.status == 'COMPLETED':
    return existing_result

# Claim work atomically
table.update_item(
    Key={'workId': work_item['workId']},
    ConditionExpression='attribute_not_exists(status) OR status = :pending',
    UpdateExpression='SET #s = :running',
    ExpressionAttributeNames={'#s': 'status'},
    ExpressionAttributeValues={':running': 'RUNNING'}
)
```

---

## Agent Registration & Event Hook

### Agent Registration
Agents register handlers with the Router:

```python
router.register(work_type='agent_ats', handler=ats_agent.process_work)
router.register(capability='analyze.resume', handler=cv_agent.process_work)
```

### Event Hook
Workers can emit events for:
- Monitoring
- Metrics aggregation
- Alerting

---

## Development Orders Adapter

**Current State**: NOT IMPLEMENTED

### Purpose
During development, the Development Orders Adapter provides:
- Mock order processing
- Local testing capability
- Contract validation

### Architecture
```
Agent Platform
    ↓
DevelopmentOrdersAdapter
    ↓
[Same contract as May's Orders]
```

This allows development work to proceed before May's Orders is fully integrated.

**IMPORTANT**: This is a DEVELOPMENT bridge, NOT a permanent platform.

---

## Test Matrix

| Test Type | Scope | Status |
|-----------|-------|--------|
| Router Tests | Work item routing | ✅ PASS |
| Context Tests | Field extraction | ✅ PASS |
| Executor Tests | Lifecycle flow | ✅ PASS |
| Result Tests | Format validation | ✅ PASS |
| Integration Tests | Full path | ✅ PASS |
| ReferenceAgent Tests | Domain compatibility | ✅ PASS |

---

## CI/CD Goals

### Current State
- GitHub Actions configured
- Python compile checks
- Unit tests

### Future Goals
- Terraform validation
- Security scanning
- Performance benchmarks
- Multi-environment deployment

---

## Core Principles

1. **Separation of Concerns**: Agent Body does NOT implement business logic
2. **Infrastructure Reuse**: Agent Body uses existing Ground Zero SQS/DynamoDB
3. **Contract Preservation**: WorkItem and Result contracts are stable
4. **Future-proofing**: Architecture supports future execution profiles

---

## Work Item Model

```python
class WorkItem:
    workId: str          # Unique identifier
    type: str            # Work type (e.g., 'agent_ats')
    tenantId: str        # Tenant for isolation
    requestedBy: str     # User who requested
    agentId: str         # Target agent
    capability: str      # Capability to execute
    idempotencyKey: str  # Deduplication
    payload: dict        # Agent-specific data
    status: str          # Processing state
    attempt: int         # Retry count
    createdAt: str       # ISO timestamp
    expiresAt: str       # TTL timestamp
```

---

## Result Model

```python
class Result:
    success: bool
    data: dict | None    # Domain result
    error: dict | None   # Error details (if failed)
    metrics: dict        # Execution metrics
```

---

## MicroVM as Future Execution Profile

### Current: Lambda
- Standard execution environment
- Serverless, auto-scaling
- Limited execution time (15 min)

### Future: MicroVM
**Purpose**: Isolate untrusted or complex code execution

### Risk Isolation Matrix

| Risk Level | Current Solution | Future MicroVM |
|------------|------------------|----------------|
| R0: Trusted | Lambda Function | Lambda Function |
| R1: External Data | Lambda + Sandbox | Lambda or MicroVM |
| R2: Sensitive/Complex | Lambda or MicroVM | MicroVM |
| R3: Untrusted Code | Lambda or MicroVM | MicroVM + Network Control |
| R4: High Risk | Lambda or MicroVM | MicroVM + Restricted Network |

### Technology Options (Not Implemented)
- Firecracker microVMs
- AWS Nitro Enclaves
- Kubernetes + gVisor
- Container isolation

---

## May's Orders Integration Boundary

### Current Status: PENDING

May's Orders (external order processing system) should be integrated via:

```
Domain Agent
    ↓ uses
May's Orders API
```

OR

```
Domain Agent
    ↓ calls
May's Orders Service
```

**NOT**: May's Orders being the host of agents

The Agent Body runtime is **independent** and can execute agents without May's Orders.

---

## Development Orders Adapter (Future)

When May's Orders integration is needed during development:

1. Developer tests agent locally
2. Adapter provides mock orders
3. Later, real May's Orders integration replaces adapter

This allows parallel development before full SQS integration.