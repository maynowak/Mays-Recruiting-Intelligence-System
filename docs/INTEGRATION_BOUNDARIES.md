# Integration Boundaries

## Overview

This document defines the integration points between components and external systems in the Mays Recruiting Intelligence System.

---

## Boundary Map

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  USER PORTAL    │       │  JOB SEARCH     │       │ EXTERNAL        │
│  (Frontend)     │←API→ │  (External)     │       │ SYSTEMS         │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                           │                       │
         │ API                       │                       
         ▼                           ▼                        │
┌─────────────────────────────────────────────────────────────┼─┐
│                    Mays Recruiting Intelligence System       │ │
│                                                            │ │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐ │ │
│  │  AUTH           │    │  WORK SYSTEM    │    │ DATA    │ │ │
│  │  Cognito         │    │  SQS + Lambda   │    │ DDB+S3  │ │ │
│  └────────┬────────┘    └────────┬────────┘    └─────────┘ │
│           │                          │                     │
│           │                          │                     │
│           ▼                          ▼                     │
│  ┌─────────────────────────────────────────────┐          │
│  │           AGENT RUNTIME                     │          │
│  │  ┌─────────────┐    ┌─────────────┐          │          │
│  │  │ AGENT BODY  │    │ ECOSYSTEM   │          │          │
│  │  │ Execution   │    │ Management  │          │          │
│  │  └──────┬──────┘    └──────┬──────┘          │          │
│  │         │                  │                 │          │
│  │         │           ORDERSPORT          ┌────┴───────┐  │
│  │         │                  │             │ REAL     │  │
│  │         │            ┌────▼────┐        │ MAYS     │  │
│  │         └───────────►│ ADAPTER │───────►│ ORDERS   │  │
│  │                      └─────────┘        └──────────┘  │
│  └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

---

## A. User Authentication Boundary

### Direction
`User → Cognito → Application Context`

### Responsibility
- **Auth System** (Cognito): Authenticates users, issues JWT tokens
- **Platform**: Validates tokens, extracts identity

### Contract
- JWT in `Authorization` header
- Standard claim structure (sub, tenant, roles)

### What Crosses
- Valid JWT token
- User identity (sub, tenant)

### What Must NOT Cross
- Cognito user pool configuration
- Token private keys
- Raw password data

---

## B. Platform API Boundary

### Direction
`HTTP Request → Lambda → Response`

### Responsibility
- **API Gateway**: Request routing
- **Lambda Handler**: Business logic execution

### Contract (MaysJobsearchApi)
- REST/GraphQL endpoints
- Standard response format: `{ success: bool, data: {}, error: null }`

### What Crosses
- Request payload (validated)
- Response data

### What Must NOT Cross
- Internal routing logic
- Database access details

---

## C. Work System Boundary

### Direction
`Event → SQS → Lambda → WorkItem`

### Responsibility
- **SQS**: Message buffering and delivery
- **Lambda**: Event processing and response

### Contract (Work Item)
```json
{
  "workId": "uuid-v4",
  "type": "string",
  "tenantId": "string",
  "payload": {},
  "status": "CREATED|QUEUED|RUNNING|COMPLETED|FAILED"
}
```

### What Crosses
- WorkItem JSON
- Status updates

### What Must NOT Cross
- Internal state management
- Queue configuration

---

## D. Agent Execution Boundary

### Direction
`Work Item → Agent Body → Agent → Result`

### Responsibility
- **Agent Body**: Execution orchestration
- **Agent**: Domain logic processing

### Contract (Agent Contract)
```python
def process_work(work_item: Dict) -> Dict:
    """Process work and return result."""

def validate_work(work_item: Dict) -> bool:
    """Validate work item."""

def get_status(work_id: str, tenant_id: str) -> Dict:
    """Get work status."""
```

### Result Format
```json
{
  "success": true,
  "data": {},
  "metrics": { "durationMs": 100 },
  "error": null
}
```

### What Crosses
- WorkItem with payload
- Result with success/failure

### What Must NOT Cross
- Agent source code internals
- Debugging/debug sessions

---

## E. Agent Invocation Boundary

### Direction
`Agent A → Invocation Contract → Agent B`

### Responsibility
- **Invocation Contract**: Create work item for target agent
- **Agent Body**: Route to correct agent
- **Agent B**: Process and return result

### Contract (Invocation)
```python
class InvocationContract:
    target_agent_id: str
    capability: str
    payload: Dict
    parent_work_id: str  # Traceability
    tenant_id: str       # Isolation
```

### What Crosses
- Invocation parameters
- Parent work ID (for tracing)
- Tenant ID (for isolation)

### What Must NOT Cross
- Agent A's internal state
- Direct file system access

---

## F. OrdersPort Boundary

### Direction
`Agent → OrdersPort Interface → Adapter → External`

### Responsibility
- **OrdersPort**: Define interface contract
- **Development Adapter**: Local simulation
- **Real Adapter** (future): Production connector

### Contract (OrdersPort)
```python
class OrdersPort:
    @property
    def port_id(self) -> str: ...
    
    def submit_order(
        work_item: Dict,
        capability: str,
        payload: Optional[Dict] = None,
        tenant_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> OrderResult: ...
    
    def get_order_status(order_id: str) -> Optional[OrderResult]: ...
    
    def can_handle(capability: str) -> bool: ...
```

### What Crosses
- Work item and payload
- Capability string
- Result object

### What Must NOT Cross
- Amazon SQS internal messages
- Local queue names/ARNs
- Adapter-specific implementations

---

## G. Real May's Orders Connector (Future)

### Direction
`Development Adapter → Real Adapter → May's Orders API`

### Responsibility
- **Real Adapter**: Implements OrdersPort for May's Orders
- **May's Orders Team**: Own the external system

### Integration Requirements
1. Same OrdersPort interface
2. No assumptions about May's Orders internals
3. Graceful error handling for unavailable service
4. Rate limiting compliance

### What SHOULD Cross
- Standardized work item data
- Defined capability strings
- Result with proper status

### What MUST NOT Cross
- May's Orders internal data structures
- AWS account-specific configurations
- Undocumented API endpoints

---

## Boundary Characteristics

| Boundary | Sync/Async | Reliability | Observability |
|----------|------------|-------------|---------------|
| Auth (Cognito) | Sync | High | CloudWatch |
| API Gateway | Sync | High | CloudWatch |
| SQS Work | Async | High | SQS DLQ |
| Agent Execution | Sync | Medium | Agent Body |
| Invocation | Async | Medium | Tracing |
| OrdersPort | Sync | Medium | Logging |

---

## Boundary Verification

Each boundary should be verifiable without dependencies on other teams' internals:

### For Team Tests
- Mock external boundaries
- Test with interface contracts
- Verify boundary crossings via logs

### For Integration Tests
- Use Development Adapter for Orders
- Verify all contracts with test data
- Check boundary attributes (IDs, headers)

### For E2E Tests
- Full flow through all boundaries
- Realistic data sets
- End-to-end observability

---

## Boundary Ownership

| Boundary | Owner | Verification |
|----------|--------|--------------|
| User Authentication | Agent Team | Cognito docs |
| Platform API | Agent Team | OpenAPI spec |
| Work System | Agent Team | Terraform |
| Agent Execution | Agent Team | Agent contract |
| Agent Invocation | Agent Team | Invocation code |
| OrdersPort | Agent Team | Tests |
| May's Orders | External | Their integration |

---

## Changing Boundaries

To extend a boundary:

1. **Define new contract** (document)
2. **Get agreement** from affected team
3. **Implement in dev** (if internal)
4. **Update tests**
5. **Document** the change

To modify an existing boundary:

1. **DEPRECATED** old path
2. **Introduce** new contract
3. **Run both** during transition
4. **Remove** old after verification

---

## See Also

- `docs/Team_COLLABORATION.md` — Team responsibilities
- `docs/ARCHITECTURE.md` — Overall architecture
- `agents/agent-contract.md` — Agent interface
- `agents/orders/adapter.py` — OrdersPort interface
- `docs/ecosystem/DEVELOPMENT_ORDERS_ADAPTER.md` — Development adapter