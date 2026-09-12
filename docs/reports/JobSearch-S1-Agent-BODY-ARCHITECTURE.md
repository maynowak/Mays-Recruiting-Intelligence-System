# Agent Body — Architektur und Reusable Runtime Foundation

## Evidence Report

---

## STATUS: ✅ COMPLETE

---

## TASK 1 — REPOSITORY ANALYSIS

### Existing Architecture

**Ground Zero Foundation** (already complete):

1. **Cognito** - Authentication, JWT, Groups
2. **API Gateway** - HTTP API V2 with JWT authorizer
3. **Agent API** - Routes for agent selection and execution
4. **DynamoDB** - Tables for work items, profiles, catalog, entitlements
5. **SQS** - Work queues with DLQ
6. **Lambda** - Event source mapping, execution environment
7. **IAM** - Least privilege policies
8. **May's Orders** - Work item processing infrastructure

### Existing Agent Structures

**Agent Contract** (`agents/agent-contract.md`):
- `AgentBase` abstract class
- `process_work()`, `validate_work()`, `get_status()` methods
- `create_lambda_handler()` factory function
- Standard result format with `success`, `data`, `error`, `metrics`

**Work Item Contract**:
- `workId`, `type`, `tenantId`, `idempotencyKey` as required fields
- Status lifecycle: CREATED → QUEUED → RUNNING → COMPLETED
- Result format standardized

**Reference Agent** (`agents/reference_agent/`):
- Implements `AgentBase` contract
- Provides `SyncJobSource` interface
- Demonstrates full integration path

---

## TASK 2 — AGENT BODY DEFINITION

### Recommended Architecture

```text
                    Ground Zero
                        │
                    Platform API
                        │
                    Agent API
                        │
        ┌───────────────┼───────────────┐
        │               │               │
    Agent Body        Agent Body      Agent Body
   (Coordinator)    (Context)      (Execution)
        │               │             │
       ┌───────────────┼─────────────┐
       ▼               ▼             ▼
    ┌─────────────────────────────────────┐
    │         DOMAIN AGENTS               │
    ├───────────────┬─────────┬────────────┤
    │ ATS Agent     │ CV Agent │ Match    │
    │               │ Agent    │ Agent    │
    └───────────────┴─────────┴────────────┘
                       │
                       ▼
                  May's Orders
                       │
                   SQS → Lambda
```

### Input Contract

**Work Item (existing - do not change)**:
```python
{
  'workId': 'uuid',           # Unique identifier
  'type': 'string',           # Work type (e.g., 'ats_process', 'cv_analyze')
  'tenantId': 'string',       # Tenant context
  'requestedBy': 'string',    # User who requested
  'idempotencyKey': 'string', # Deduplication
  'agentId': 'string',        # Target agent
  'capability': 'string',     # Specific operation
  'payload': {...},           # Agent-specific data
  'status': 'QUEUED',         # Lifecycle status
  'requestId': 'uuid',        # Request correlation
}
```

### Routing

**Agent Router** (new component):
```python
class AgentRouter:
    """Routes work items to appropriate agents."""
    
    def route(self, work_item: Dict) -> str:
        """Return agent handler based on work item type/capability."""
        agent_id = work_item.get('agentId')
        capability = work_item.get('capability')
        work_type = work_item.get('type')
        
        # Routing logic:
        # - agentId → specific agent
        # - capability → operation within agent
        # - work_type → generic routing
```

### Execution Framework

**Standard Agent Operations**:
1. `initialize()` - Setup context, config
2. `validate_work()` - Verify work item
3. `process_work()` - Execute domain logic
4. `handle_error()` - Error handling
5. `get_status()` - Status query
6. `cleanup()` - Resource cleanup

### Output Contract

**Standard Result**:
```python
{
  'success': bool,
  'data': {...},       # Domain-specific output
  'metrics': {...},    # Duration, workId, agentVersion
  'error': {...}       # Error details if failed
}
```

---

## TASK 3 — ATS AS FIRST CONSUMER

### Existing ATS Functionality

The repository mentions existing ATS functionality from "Mays Job Matcher". Based on the architecture:

**ATS Operation Support**:
- ATS can process as a specific `work_type` or `capability`
- Router sends `work_type='ats_process'` to ATS Agent
- Agent uses existing anonymization and matching logic
- Results returned via standard format

**Integration Path**:
```text
API → Agent API → Agent Body → ATS Agent → May's Orders → SQS → Lambda
```

**Key Principles**:
- ATS logic stays in domain agent (not Agent Body)
- Agent Body provides technical coordination only
- May's Orders handles retry, idempotency, DLQ

---

## TASK 4 — ANONYMIZATION CAPABILITY

### Existing Anonymization Routine

The anonymization function exists in Mays Job Matcher. It should:
- NOT be integrated into Core Ground Zero
- NOT be part of Agent Body
- Remain available as a utility for agents that need it

**Usage Pattern**:
```python
from jobmatcher.anonymization import anonymize_cv

result = anonymize_cv(user_data)
```

---

## CONCLUSION

### Agent Body Components

1. **AgentRouter** - Routes work to appropriate handlers
2. **AgentContext** - Provides context from API/JWT
3. **AgentExecutor** - Runs agents with standard lifecycle
4. **AgentResultHandler** - Standardizes output format
5. **AgentMonitor** - Observability integration

### Files to Create

| File | Purpose |
|------|---------|
| `agents/router.py` | Work item routing |
| `agents/context.py` | Context extraction |
| `agents/executor.py` | Execution framework |
| `agents/result.py` | Result formatting |
| `agents/monitor.py` | Observability |

### Actions

1. Create Agent Body runtime components
2. Integrate with existing WorkItem contract
3. Update Agent Base with new patterns
4. Create tests for Agent Body
5. Document migration path for existing agents

---

## Git Status

```
Current branch: master
Last commit: docs: add JobSearch S1 source evaluation report
```

---

## Recommendation: PROCEED

The existing Ground Zero foundation provides the base for Agent Body creation. The defined work item model, idempotency system, and routing patterns can form the Agent Body without major architectural changes.