# Team Collaboration Model

## Overview

This document defines the collaboration model between teams working on the Mays Recruiting Intelligence System.

---

## Teams & Responsibilities

### 1. Agent Team (This Repository)

**Ownership:**
- Agent runtime (`agents/` directory)
- Ground Zero platform infrastructure
- Agent ecosystem management
- Testing and validation

**Responsibilities:**
- Develop domain intelligence agents
- Maintain the agent execution environment
- Ensure security and isolation between agents
- Provide integration points for external systems

### 2. Job Search Team (External)

**Ownership:**
- User-facing job search interface
- Frontend application
- Job search API (`MaysJobsearchApi`)

**Responsibilities:**
- User experience for job searching
- Job display and filtering
- Results presentation

**Integration Contract:** Standardized API contract for job search / agent results.

### 3. May's Orders AWS Team (External)

**Ownership:**
- Generic order/processing infrastructure
- AWS infrastructure implementation
- IAM deployment and governance
- Order lifecycle management

**Responsibilities:**
- Provide reliable order processing
- Maintain infrastructure as code
- Implement security and compliance

**Integration Contract:** OrdersPort interface.

---

## Collaboration Model

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│    Agent Team                      Job Search Team            │
│    ──────────                      ───────────────            │
│    • agents/                       • Frontend                   │
│    • platform core                 • MaysJobsearchApi           │
│    • execution runtime             • job sources              │
│    • ecosystem                     • user interface           │
│                                                               │
│                    ↑                                            │
│                    │                                            │
│                    ↓                                            │
│    ┌─────────────────────────────────────────────┐             │
│    │   OrdersPort (Interface Contract)          │             │
│    ──────────────────────────────────────────────             │
│                    │                                            │
│                    ↓                                            │
│    ┌─────────────────────────────────────────────┐             │
│    │   Development Orders Adapter (Current)    │             │
│    ──────────────────────────────────────────────             │
│                    │                                            │
│                    ↓                                            │
│    ┌─────────────────────────────────────────────┐             │
│    │   May's Orders AWS (External Team)        │             │
│    ──────────────────────────────────────────────             │
│                                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Contracts & Boundaries

### Defined Contracts

1. **Agent Contract** (`agents/agent-contract.md`)
   - What agents must implement
   - WorkItem and Result schemas
   - Error handling conventions

2. **OrdersPort Interface** (`agents/orders/adapter.py`)
   - `submit_order()` signature
   - `get_order_status()` signature
   - Result types and structures

3. **Processing Chain Interface** (`agents/ecosystem/chain.py`)
   - Chain definition format
   - Step capabilities
   - Input/output propagation

### What MUST be Agreed Before Integration

| Integration Point | Agreement Required | Status |
|-------------------|-------------------|--------|
| Job Search → Agent API | API contract, response format | DOCUMENTED |
| Agent → OrdersPort | Interface contract | IMPLEMENTED |
| OrdersPort → May's Orders | Eventual contract alignment | PLANNED |

### What MUST NOT Cross Boundaries

| Boundary | Must NOT Cross | Reason |
|----------|----------------|--------|
| Agent ↔ Job Search | Internal agent code | Separation of concerns |
| Agent ↔ May's Orders | Internal May's Orders impl | Distributed ownership |
| Local ↔ Production | Development adapters | Cannot depend on prod state |

---

## Communication Channels

### Synchronous

- **Code Reviews**: All changes via PR with required reviews
- **Architecture Decisions**: Document in ADRs or reports

### Asynchronous

- **Git Issues**: For tasks and bugs
- **Documentation**: Primary source of truth
- **Reports**: For milestone verification

---

## Ownership Matrix

| Component | Owner Team | Contact | Integration |
|-----------|------------|---------|-------------|
| Agent Contract | Agent Team | Code review | Reference agents |
| Agent Body | Agent Team | Code review | Internal |
| Agent Ecosystem | Agent Team | Code review | Internal |
| Dev Orders Adapter | Agent Team | Code review | External teams |
| Terraform | Agent Team | Code review | AWS |
| Job Search API | Job Search Team | External | API contract |
| May's Orders Connector | External Team | External | OrdersPort |

---

## Integration Workflow

### Adding a New Agent

1. Create agent in `agents/{name}/`
2. Implement `process_work()` per contract
3. Add to registry in `agents/__init__.py`
4. Update documentation
5. Add tests

### Integrating with External Systems

1. Define interface contract (not implementation)
2. Create adapter in `agents/orders/` or new location
3. Verify no internal details leak through
4. Document contract clearly
5. Test locally first

---

## START HERE

**BEFORE** any implementation work, check:

1. Is the contract documented?
2. Is the boundary clear?
3. Who owns what?
4. What external dependencies exist?

**AFTER** any implementation work, verify:

1. Documentation is updated
2. Tests pass
3. Boundaries are not crossed
4. External systems are not affected

---

## Key Principles

1. **Contracts First**: Define interface before implementation
2. **No Assumptions**: Don't assume internal details of other teams
3. **Document Everything**: Every agreement in writing
4. **Test Boundaries**: Verify integration points work
5. **Preserve Independence**: Teams can work separately