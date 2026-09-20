# SHARED-CONTRACT-01 — Shared Contract Inventory & Architecture Gate

**STATUS: GREEN**

## 1. Repository Baseline

### Mays-Recruiting-Intelligence-System

| Field | Value |
|-------|-------|
| Repository | Mays-Recruiting-Intelligence-System |
| Branch | main |
| HEAD | 13e4d84 |
| Work Tree | Clean |
| Remote | git@github.com:maynowak/Mays-Recruiting-Intelligent-System.git |
| Commits | 97 local |
| Divergence | 40 legacy, 0 current |

**Key Components:**
- Agent ecosystem (`agents/ecosystem/`)
- JobSearch module (`jobsearch/`)
- Lambda handler (`lambda/handler.py`)
- ATS Agent (`agents/ats_agent/`)

### Mays JobSearch (External - NOT ACCESSIBLE)

Cannot verify current state. Expected to contain:
- ATS Core (`/api/ats-analysis`)
- Job models
- ATS analysis functions

### Mays-Orders-AWS (External - NOT ACCESSIBLE)

Cannot verify current state. Expected to contain:
- Orders API/work representations
- OrdersPort adapter

## 2. Contract Discovery

### A) API Contracts

| Contract | Location | Definition |
|----------|----------|------------|
| Platform API | `lambda/handler.py` | `/platform`, `/me`, `/me/profile`, `/agents` |
| JobSearch API | `lambda/handler.py` | `/me/jobsearches` (GET, POST, PUT, DELETE) |
| Agent API | `lambda/handler.py` | `/api/agents`, `/api/agents/{id}/execute` |
| Work API | `lambda/handler.py` | `/work` endpoints |

### B) Identity Contracts

| Contract | Location | Definition |
|----------|----------|------------|
| User Context | `lambda/handler.py:151-177` | JWT claims → userId, email, tenantId |
| Tenant Isolation | `lambda/handler.py` | Enforced in all API handlers |
| Ownership | `lambda/handler.py` | User ID from JWT, never from client |

### C) Job Contracts

| Contract | Location | Definition |
|----------|----------|------------|
| Job | `jobsearch/models.py:26-124` | Canonical job representation |
| JobSearchRequest | `jobsearch/models.py:128-155` | Search request model |
| JobSearchResponse | `jobsearch/models.py:159-174` | Search response model |
| JobSearchResult | `jobsearch/models.py:178-182` | Per-source result |

### D) Profile Contracts

| Contract | Location | Definition |
|----------|----------|------------|
| UserProfile | `lambda/handler.py:565-594` | DynamoDB user-profile table |
| ATSSearchProfile | `jobsearch/domain_models.py:44-76` | ATS skills/keywords |
| SearchConfiguration | `jobsearch/domain_models.py:79-111` | Search parameters |

### E) JobSearch Contracts

| Contract | Location | Status |
|----------|----------|--------|
| JobSearch (domain) | `jobsearch/domain_models.py` | FULLY IMPLEMENTED |
| JobSearch (persistence) | `jobsearch/repository.py` | FULLY IMPLEMENTED |
| JobSearch (API) | `lambda/handler.py` | FULLY IMPLEMENTED |

### F) ATS Contracts

| Contract | Location | Status |
|----------|----------|--------|
| ATSAgent | `agents/ats_agent/agent.py` | IMPLEMENTED |
| ATSHttp | `agents/ats_agent/agent.py` | IMPLEMENTED |
| ATS API Client | `agents/ats_agent/agent.py` | CALLS EXISTING API |
| ATS Registry | `agents/ats_agent/registry.py` | FULLY IMPLEMENTED |
| analyze.job capability | `agents/ats_agent/registry.py` | DEFINED |

### G) Agent Contracts

| Contract | Location | Status |
|----------|----------|--------|
| AgentDescriptor | `agents/ecosystem/registry.py:36-74` | FULLY IMPLEMENTED |
| AgentRegistry | `agents/ecosystem/registry.py:77-125` | FULLY IMPLEMENTED |
| AgentDiscovery | `agents/ecosystem/discovery.py` | FULLY IMPLEMENTED |
| EligibilityCheck | `agents/ecosystem/eligibility.py` | FULLY IMPLEMENTED |
| InvocationContract | `agents/agent_body/invocation.py` | FULLY IMPLEMENTED |
| ProcessingEnvelope | `agents/ecosystem/event_hook.py` | FULLY IMPLEMENTED |

### H) Work Contracts

| Contract | Location | Status |
|----------|----------|--------|
| WorkItem | `lambda/handler.py:474-491` | FULLY IMPLEMENTED |
| Work processing | `lambda/handler.py:122-147` | FULLY IMPLEMENTED |

### I) Order Contracts

| Contract | Location | Status |
|----------|----------|--------|
| OrdersPort | NOT FOUND in current repo | NOT PRESENT |

The Order contracts from May's Orders are referenced in:
- `docs/INTEGRATION_BOUNDARIES.md` - Boundary specification
- `agents/orders/` - Adapter directory exists but may need external integration

### J) Event Contracts

| Contract | Location | Status |
|----------|----------|--------|
| Event Hook | `agents/ecosystem/event_hook.py` | FULLY IMPLEMENTED |
| TriggerType | `agents/ecosystem/event_hook.py` | FULLY IMPLEMENTED |
| ProcessingEnvelope | `agents/ecosystem/event_hook.py` | FULLY IMPLEMENTED |

### K) Error Contracts

| Contract | Location | Status |
|----------|----------|--------|
| HTTP Errors | `lambda/handler.py` | STANDARD {error: message} |
| Validation | Various | Via exceptions |

### L) Versioning

| Version | Location | Usage |
|---------|----------|-------|
| payloadVersion | WorkItem | `1.0` |
| agentVersion | WorkItem | From env |
| PLATFORM_VERSION | `lambda/handler.py` | Platform metadata |

## 3. Canonical Sources

| Concept | Canonical Source | File | Controller |
|---------|------------------|------|------------|
| Job | jobsearch/models.py | `Job` dataclass | Agent Body |
| JobSearch | jobsearch/domain_models.py | `JobSearch` dataclass | User-owned |
| ATSSearchProfile | jobsearch/domain_models.py | `ATSSearchProfile` | JobSearch |
| SearchConfiguration | jobsearch/domain_models.py | `SearchConfiguration` | JobSearch |
| AgentDescriptor | agents/ecosystem/registry.py | `AgentDescriptor` | AgentRegistry |
| WorkItem | lambda/handler.py | `_create_work()` | SQS Worker |
| User Context | lambda/handler.py | `_extract_user_context()` | Platform API |
| Capability | agents/ecosystem/registry.py | `supports_capability()` | Discovery |

## 4. Classification

| Contract | Classification | Reason |
|----------|----------------|--------|
| CanonicalJob | REUSE | Existing, stable, used by agents |
| JobSearch (domain) | REUSE | User-owned, implemented locally |
| JobSearch (API) | REUSE | Added to existing handler |
| ATSSearchProfile | REUSE | Part of JobSearch domain |
| AgentDescriptor | REUSE | Core ecosystem component |
| WorkItem | REUSE | Core platform component |
| User Context | REUSE | Core authentication |
| ATS API Contract | REFERENCE_ONLY | External, documented in ARCH-ATS-BOUNDARY-01.md |
| OrdersPort | LOCAL | Internal adapter, needs external definition |

## 5. API System Map

### Platform API (Internal)
```
GET    /platform        → _handle_platform
GET    /me              → _handle_me
GET    /me/profile      → _handle_me_profile
GET    /agents          → _handle_agents
```

### JobSearch API (Internal)
```
GET    /me/jobsearches  → _handle_jobsearch_list
POST   /me/jobsearches  → _handle_jobsearch_create
GET    /me/jobsearches/{id}  → _handle_jobsearch_get
PUT    /me/jobsearches/{id}  → _handle_jobsearch_update
DELETE /me/jobsearches/{id}  → _handle_jobsearch_delete
```

### Agent API (Internal → External boundary)
```
GET    /api/agents              → _list_agents
GET    /api/agents/{id}         → _get_agent
POST   /api/agents/{id}/execute → _execute_agent
GET    /api/agents/{id}/work/{id} → _get_agent_work
```

### ATS API (External - mays-jobsearch)
```
POST /api/ats-analysis
  → ATSAgent → ATSHttpClient → HTTP call → mays-jobsearch API
```

## 6. Data Flow Map

### JobSearch Flow (VERIFIED)
```
User
  ↓ JWT
Platform API
  ↓ user_context
JobSearch API (lambda)
  ↓ JobSearchRepository
    if DynamoDB: Table (JOBSEARCH_TABLE)
    else: Mock/Test
  ↓ JobSearch domain model
```

### Work Execution Flow (VERIFIED)
```
Frontend
  ↓ JWT
API Gateway
  ↓ Lambda
  ↓ WorkItem creation
  ↓ SQS
  ↓ Worker Lambda
  ↓ Agent Body
  ↓ Agent (ATS, Reference, etc.)
  ↓ Result
```

### ATS Integration Flow (VERIFIED)
```
JobSearch (user context)
  ↓
ATS Agent (analyze.job capability)
  ↓
ATSHttpClient
  ↓
POST /api/ats-analysis
  ↓
mays-jobsearch (external)
  ↓
Analysis Result
  ↓
Overall Result
```

## 7. Conflicts

**None found.** All contracts in the current repository are consistent and follow existing patterns.

## 8. Missing Contracts

**Genuinely missing:**
1. **OrdersPort contract** - Referenced in `docs/INTEGRATION_BOUNDARIES.md` but implementation requires May's Orders API access

2. **OpenAPI specification** - API documented in Markdown but no machine-readable spec

## 9. Shared Contract Decision

### What should be shared:
- **None** - The existing contracts are repository-local

### What should remain local:
- JobSearch domain models (user-owned, tenant-isolated)
- WorkItem structure (platform-specific)
- User context extraction (authentication-specific)

### What needs adapters:
- ATS API - already abstracted via HTTP client
- Orders API - needs external contract from May's Orders

### What should NOT be standardized:
- NoSQL table schemas (repository-owned)
- Internal work item formats
- Agent internal representations

## 10. Dependency Checker Preparation

The following metadata will be needed by DEPENDENCY-CHECK-01:

```json
[
  {
    "contractId": "canonical.job",
    "version": "1.0.0",
    "owner": "jobsearch",
    "producer": "jobsearch/models.py:Job",
    "consumers": ["agent/orders"],
    "repository": "Mays-Recruiting-Intelligence-System",
    "path": "jobsearch/models.py",
    "type": "DOMAIN",
    "compatibility": "stable"
  },
  {
    "contractId": "agent.descriptor",
    "version": "1.0.0",
    "owner": "agents.ecosystem",
    "producer": "agents/ecosystem/registry.py:AgentDescriptor",
    "consumers": ["agents/ecosystem/discovery.py", "lambda/handler.py"],
    "repository": "Mays-Recruiting-Intelligent-System",
    "path": "agents/ecosystem/registry.py",
    "type": "DOMAIN",
    "compatibility": "stable"
  },
  {
    "contractId": "jobsearch.api",
    "version": "1.0.0",
    "owner": "lambda",
    "producer": "lambda/handler.py",
    "consumers": ["frontend"],
    "repository": "Mays-Recruiting-Intelligence-System",
    "path": "lambda/handler.py",
    "type": "HTTP",
    "routes": ["/me/jobsearches"]
  },
  {
    "contractId": "work.item",
    "version": "1.0.0",
    "owner": "lambda",
    "producer": "lambda/handler.py:_create_work",
    "consumers": ["sqs.worker"],
    "repository": "Mays-Recruiting-Intelligence-System",
    "path": "lambda/handler.py",
    "type": "WORK",
    "compatibility": "stable"
  },
  {
    "contractId": "user.context",
    "version": "1.0.0",
    "owner": "lambda",
    "producer": "lambda/handler.py:_extract_user_context",
    "consumers": ["all handlers"],
    "repository": "Mays-Recruiting-Intelligence-System",
    "path": "lambda/handler.py",
    "type": "DOMAIN",
    "compatibility": "stable"
  }
]
```

## 11. Documentation

**No new documentation required.**
- Existing documentation covers contracts
- Reports created:
  - `docs/reports/JOBSEARCH-API-01.md`
  - `docs/reports/JOBSEARCH-PROFILE-01.md`
  - `docs/reports/ATS-REG-01-AGENT-REGISTRY.md`

## 12. Tests

**No implementation tests to run.**
This is an architecture inventory milestone.

Existing tests remain unchanged:
```
48 passed
```

## 13. AWS / Terraform

**NO CHANGES**

| Item | Status |
|------|--------|
| AWS changes | NO |
| Terraform apply | NO |
| DynamoDB modifications | NONE |

## 14. Git State

| Field | Value |
|-------|-------|
| Branch | main |
| HEAD | 13e4d84 |
| Working tree | Clean |
| Staged changes | None |
| Untracked files | None |

## 15. NEXT STEP

**DEPENDENCY-CHECK-01** - Implement dependency checker using the contract metadata above.

---

**HARD STOP** - This milestone is complete.
No implementation, no changes, no AWS modifications.