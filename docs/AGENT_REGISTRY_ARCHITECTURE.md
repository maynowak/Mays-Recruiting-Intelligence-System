# Agent Registry Architecture — Mays Recruiting Intelligence System

## Overview

This document defines the persistent agent catalog → runtime registry foundation.

**Status**: Architecture & Documentation Only (No Code Changes)

---

## Current State

### A) Platform `agent_catalog` (DynamoDB)

**Location**: `terraform/modules/dynamodb/main.tf:87-114`

**Schema**:

| Key | Type | Description |
|-----|------|-------------|
| `agentId` | S (hash) | Unique agent identifier |
| `status` | S (gsi) | Agent status |

**Features**:
- Pay-per-request billing
- Global secondary index on `status`
- TTL for expiration

**Data Model** (from API handler analysis):

```python
# Agent catalog structure (inferred from handler.py)
{
    "agentId": "string",
    "name": "string",
    "description": "string",
    "version": "string",
    "capabilities": ["string"],
    "runtime": "string",      # e.g., "python3.14"
    "bodyVersion": "string",  # e.g., "1.0.0"
    "status": "string",       # active|inactive|deprecated
    "tenantId": "string?",    # Optional: tenant-specific capab.
    "config": {...}           # Optional: agent configuration
}
```

**What's Missing**:
- No clustering on capabilities
- No pre-built indexes for common queries
- Schema not fully defined (only `agentId` as hash key)

---

### B) Runtime `AgentRegistry`

**Location**: `agents/ecosystem/registry.py`

**Implementation**:
- In-memory dictionary (`Dict[str, AgentDescriptor]`)
- Not persistent (resets on Lambda cold start!)

**Key Classes**:

```python
@dataclass
class AgentDescriptor:
    agent_id: str
    name: str
    version: str
    status: AgentStatus = ACTIVE
    capabilities: List[str] = []
    supported_bodies: List[str] = ["1.0.0"]
    supported_runtimes: List[str] = ["python3.14"]
    execution_profile: ExecutionProfile = LAMBDA
    risk_level: str = "low"
    description: str = ""
    metadata: Dict[str, Any] = {}
```

**Methods**:
- `register()`, `unregister()`, `get()`, `list_all()`
- `list_by_capability()`, `list_by_status()`, `is_registered()`

---

### C) `AgentDiscovery`

**Location**: `agents/ecosystem/discovery.py`

**Purpose**: Find agents by capability or runtime.

**Implementation**: Searches in-memory `AgentRegistry`.

---

### D) `EligibilityCheck`

**Location**: `agents/ecosystem/eligibility.py`

**Purpose**: Determine if an agent can be invoked for a given task.

**Implementation**: Checks qualifications against `AgentDescriptor`.

---

### E) `ProcessingChain`

**Location**: `agents/ecosystem/chain.py`

**Purpose**: Sequences of agent invocations.

**Components**:
- `ChainStep`: Single step in a chain
- `ProcessingChain`: Sequence of steps
- `ChainExecutor`: Executes chains

---

### F) `AgentInvocation` / `AgentInvoker`

**Location**: `agents/agent_body/invocation.py`

**Purpose**: Agent-to-agent invocation.

---

### G) Agent Body

**Location**: `agents/agent_body/`

**Components**:
- `context.py`: Execution context extraction
- `executor.py`: Agent lifecycle management
- `router.py`: Work item routing
- `result.py`: Result handling
- `monitor.py`: Observability
- `invocation.py`: Invocation contract

---

### H) Lambda Handler / Worker

**Location**: `lambda/handler.py`

**Flow**:

```
API Gateway → Lambda Handler
                    │
               SQS Event
                    │
          _process_work_item()
                    │
             AgentBody.execute()
                    │
            ReferenceAgent.process()
```

---

## ARCHITECTURE GAP ANALYSIS

### Problem: In-Memory Registry

The `AgentRegistry` is **not persistent**. It's an in-memory Python dictionary.

**Consequences**:
- Cold starts lose registry state
- Cannot scale across multiple Lambda instances
- No connection to persistent `agent_catalog`

### Missing: Catalog → Registry Bridge

**No code exists** that reads from the DynamoDB `agent_catalog` table and populates the `AgentRegistry`.

---

## TARGET ARCHITECTURE

```text
┌──────────────────────────────────────────────┐
│              DynamoDB                        │
│        agent_catalog (persistent)            │
│                                              │
│  agentId (PK) ──────► AgentAttributes        │
│        ▲                                      │
│        │ sync                                 │
│        │                                      │
│  AgentRegistry (Runtime)                      │
│        │                                      │
│        ▼ populate()                            │
│    AgentDiscovery                              │
│        │                                      │
│        ▼ find()                                │
│    EligibilityCheck                            │
│        │                                      │
│        ▼ check()                               │
│    ProcessingChain                             │
│        │                                      │
│        ▼ execute()                             │
│    AgentInvocation                             │
│        │                                      │
│        ▼ invoke()                              │
│    Agent Body (Runtime)                        │
│        │                                      │
│        ▼ execute()                             │
│    Domain Agents                                 │
└──────────────────────────────────────────────┘
```

---

## PROPOSED CHANGES (DOCUMENTATION ONLY)

### 1. Catalog Sync Mechanism

A background or on-demand process that:

1. Scans `agent_catalog` table (or uses DynamoDB Streams)
2. Creates `AgentDescriptor` for each item
3. Populates `AgentRegistry`

### 2. Hybrid Approach

- **Development**: In-memory registry (no DB calls)
- **Production**: Read from DynamoDB, cache in registry

### 3. Discovery Enhancement

Extend `AgentDiscovery` to:
- Query DynamoDB directly if registry empty
- Use GSI on `status` and `capabilities` (needs adding)

---

## CLOUDTRAIL AUDITABILITY

For runtime registry operations, CloudTrail logs:
- Lambda invocations
- DynamoDB access

---

## OWNERSHIP

| Component | Owner | Change Procedure |
|-----------|-------|------------------|
| `agent_catalog` table | Platform Team | Terraform PR + Review |
| `AgentRegistry` | Agent Team | Code PR + Review |
| `AgentDiscovery` | Agent Team | Code PR + Review |
| `EligibilityCheck` | Agent Team | Code PR + Review |
| `ProcessingChain` | Agent Team | Code PR + Review |

---

## ROADMAP

### Phase 1: Documentation (CURRENT)
- This document
- Update PROJECT_STATUS

### Phase 2: Schema Definition
- Define full `agent_catalog` schema
- Add GSIs for discovery

### Phase 3: Sync Implementation
- Build catalog → registry sync
- Test with cold starts

### Phase 4: Production Setup
- Enable DynamoDB Streams (optional)
- Add health checks

---

## STATUS MAP

| Component | Current | Target | Future |
|-----------|---------|--------|--------|
| agent_catalog | Schema Defined | Full Schema | - |
| AgentRegistry | In-Memory | Hybrid | Persistent |
| AgentDiscovery | Registry-only | Catalog-aware | Streaming |
| EligibilityCheck | Done | - | - |
| ProcessingChain | Done | - | - |

---

## References

- `terraform/modules/dynamodb/main.tf` — Table definitions
- `agents/ecosystem/registry.py` — Registry implementation
- `agents/ecosystem/discovery.py` — Discovery logic
- `agents/ecosystem/eligibility.py` — Eligibility check
- `docs/ARCHITECTURE.md` — Overall architecture
- `docs/INTEGRATION_BOUNDARIES.md` — System boundaries