# Repository Architecture — Mays Recruiting Intelligence System

## Overview

This document provides the central architecture overview for the Mays Recruiting Intelligence System.

**Repository Purpose**: Ground Zero Platform Core for Recruiting Intelligence Agents

This is NOT the individual recruiting agents. It is the platform core that enables AI-driven recruiting capabilities.

---

## System Architecture

```text
                     GROUND ZERO (Platform Core)
                          │
                      AUTH & PROXY
                    (Cognito, API Gateway)
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   USER AUTH        WORK SYSTEM        DATA LAYER
   (Cognito)        (SQS, Lambda)      (DynamoDB, S3)
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                   AGENT RUNTIME
                          │
               ┌──────────┼──────────┐
               │          │          │
               ▼          ▼          ▼
        SCALING     ROUTING     RESULTS
        (Queue)    (Router)    (Handler)
               │          │          │
               └──────────┼──────────┘
                          │
                    ┌─────┴─────┐
                    │           │
                    ▼           ▼
    AGENT BODY (EXECUTION)  ECOSYSTEM (MANAGEMENT)
                    │           │
                    ▼           ▼
              Domain Agents  Processing Chains
```

---

## Component Boundaries

### What EXISTS in THIS Repository

| Component | Status | Description |
|-----------|--------|-------------|
| Ground Zero Platform | ✅ IMPLEMENTED | Core infrastructure for agent execution |
| Agent Body | ✅ IMPLEMENTED | Reusable agent runtime (S2.5, G2.8) |
| Agent Ecosystem | ✅ IMPLEMENTED | Registry, Discovery, Processing Chain (G2.9) |
| Development Orders Adapter | ✅ IMPLEMENTED | OrdersPort for development (S2.13) |
| Reference Agent | ✅ IMPLEMENTED | Example agent demonstrating contract |
| Processing Chain | ✅ IMPLEMENTED | Agent-to-agent workflows (G2.9) |
| Terraform Infrastructure | ✅ IMPLEMENTED | AWS infrastructure as code |
| CI/CD Workflows | ✅ IMPLEMENTED | GitHub Actions for deployment |

### What is NOT in THIS Repository

| Component | Reason |
|-----------|--------|
| May's Orders AWS | External team-owned system |
| ATS Domain Logic | Planned as a domain agent |
| CV Intelligence | Planned as a domain agent |
| Matching Intelligence | Planned as a domain agent |
| API Keys for Clients | Future work |
| Promotion/Media Systems | Future work |
| S3 Media Processing | Future work |
| MicroVM Execution | Architecture-only future planning |
| Production Hardening | Cloud-level operations |

---

## Main Components

### 1. Ground Zero — Platform Core

**Purpose**: Provide standardized, secure foundation for running recruiting agents.

**Key Features**:
- Cognito-based authentication
- SQS for async work queues
- DynamoDB for work items and state
- Lambda for agent execution
- CloudWatch for observability

**Responsibility**: Infrastructure and runtime orchestration. NOT business logic.

### 2. Agent Body — Execution Layer

**Purpose**: Reusable, standardized agent runtime.

**Components** (implemented):
- `Context` — Extract execution context from events
- `Executor` — Manage agent lifecycle
- `Router` — Route work items to agents  
- `Result` — Standardize output format
- `Monitor` — Observability and tracing
- `Invocation` — Agent-to-agent calling

**Key Files**:
- `agents/agent_body/executor.py` — Main execution pipeline
- `agents/agent_body/router.py` — Agent routing
- `agents/agent_body/invocation.py` — Invocation contract

### 3. Agent Ecosystem — Management Layer

**Purpose**: Discover, register, and chain agents.

**Components** (implemented in G2.9):
- `AgentRegistry` — Central agent registry
- `AgentDescriptor` — Agent capabilities metadata
- `AgentDiscovery` — Find agents by capability
- `EligibilityCheck` — Access control validation
- `ProcessingChain` — Sequences of agent invocations

### 4. OrdersPort — Integration Boundary

**Purpose**: Abstract interface for order/processing systems.

The OrdersPort pattern:
- Defines contract (not implementation details)
- Allows plug-and-play adapters
- Isolates agents from external system changes

**Two Adapters**:
1. `DevelopmentOrdersAdapter` — Local testing (implemented)
2. `RealMaysOrdersAdapter` — Future production connector (NOT IMPLEMENTED)

---

## External System Relationships

### Job Search (External)

```
Job Search Frontend
    ↓
MaysJobsearchApi (API contract)
    ↓
↓── User requests job search──→
↓── Searches for jobs ───────→
```

- **Ownership**: Job Search team
- **Purpose**: User-facing job search interface
- **Integration**: Consumes standardized API contracts

### Mays Orders AWS (External)

```
Agent
    ↓
Invocation Contract
    ↓
OrdersPort (Interface)
    ↓
DevelopmentOrdersAdapter  ← Currently used
    ↓
Future: RealMaysOrdersAdapter
    ↓
↓── May's Orders AWS ─────→
```

**LIMITATIONS IN THIS REPOSITORY**:
- Mays-Orders-AWS is NOT implemented here
- It is developed externally by another team
- Integration is mediated through OrdersPort interface
- Development adapter provides local simulation only

---

## Current Development Status

| Component | Stage | G/F | Date |
|-----------|-------|-----|------|
| Ground Zero | Complete | G0.5 | 2026-09-10 |
| Agent Body Integration | Complete | G2.5 | 2026-09-12 |
| Worker → Agent Body | Complete | G2.7 | 2026-09-12 |
| Agent Invocation | Complete | G2.8 | 2026-09-13 |
| Agent Ecosystem | Complete | G2.9 | 2026-09-13 |
| Dev Orders Adapter | Complete | S2.13 | 2026-09-14 |
| IAM Governance | Verified | S2.16 | 2026-09-14 |
| S2.15 Runtime Recovery | Complete | S2.15 | 2026-09-14 |

---

## Architecture Layers

### Layer 1: Authentication Boundary
- Cognito for user/tenant auth
- JWT for identity propagation
- IAM for AWS permissions

### Layer 2: Platform API Layer
- API Gateway (HTTP API V2)
- Request routing
- Entitlement checks

### Layer 3: Work System
- SQS queues
- Lambda workers
- DynamoDB work items

### Layer 4: Agent Execution
- Agent Body runtime
- Routers and executors
- Result handlers

### Layer 5: Ecosystem Management
- Agent registry
- Discovery services
- Processing chains

### Layer 6: External Integration
- OrdersPort abstraction
- Adapters for external systems

---

## What is Implemented Now

### Canvas: Completed

1. **Ground Zero Platform Foundation** (G0.1-G0.5)
   - AWS infrastructure via Terraform
   - Authentication, storage, queues
   - CI/CD pipeline

2. **AgentBody Runtime** (G2.5, G2.7, G2.8)
   - Execution pipeline
   - Invocation contract
   - Router, Context, Result, Monitor

3. **Agent Ecosystem** (G2.9)
   - Registry and discovery
   - Processing chains
   - Eligibility checks

4. **Development Orders Adapter** (S2.13)
   - OrdersPort interface
   - Local simulation for testing

---

## What is Planned

| Item | Status | Notes |
|------|--------|-------|
| Real Mays-Orders Connector | PLANNED | Interface exists, impl pending |
| ATS Domain Agent | PLANNED | Not yet implemented |
| CV Processing Agent | PLANNED | Not yet implemented |
| Matching Agent | PLANNED | Not yet implemented |
| API Keys | FUTURE | Security feature |
| MicroVM Execution | FUTURE | Architecture alternative |
| Production Hardening | FUTURE | Environments, policies |

---

## Governance Model

### Layers Separation

```
USER → Auth → API → Agent → Orders
                   ↓              ↓
              Internals     External
```

### Authorization Boundaries

| Layer | Auth Type | Implementation |
|-------|-----------|--------------|
| User Access | Cognito JWT | ✅ Done |
| API Access | Entitlements | ✅ Documented |
| Agent Execution | IAM Roles | ✅ Terraform |
| Orders Access | Contract | ✅ OrdersPort |

### Audit Requirements

- All agent invocations logged
- Work items traced via IDs
- Results stored for verification
- See `docs/AI_AUDITLOG.md`

---

## Documentation Map

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE.md` | This file — central overview |
| `docs/PROJECT_STATUS.md` | Current status and completion |
| `docs/CHANGELOG.md` | History of changes |
| `docs/AI_AUDITLOG.md` | Audit trail for operations |
| `docs/Team_COLLABORATION.md` | Cross-team collaboration |
| `docs/INTEGRATION_BOUNDARIES.md` | System interfaces |
| `agents/agent-contract.md` | Agent interface specification |
| `agents/ecosystem/*.md` | Ecosystem documentation |
| `terraform/` | Infrastructure as code |

---

## Current Next Step

**S2.16-DOC**: Establish repository architecture and collaboration documentation.

After this documentation is complete, the next step will be determined by the architecture decisions made.

**NOT NEXT**: Real Mays-Orders integration (that is a separate milestone for when the external system is ready).

---

## References

- Agent Contract: `agents/agent-contract.md`
- Agent Matrix: `agents/agent-matrix.md`
- Orders Adapter: `docs/ecosystem/DEVELOPMENT_ORDERS_ADAPTER.md`
- Governance: `docs/ecosystem/GOVERNANCE_ALIGNMENT.md`
- Processing Chain: `docs/ecosystem/PROCESSING_CHAIN_EXECUTION.md`
- Terraform: `terraform/main.tf`