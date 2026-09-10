# G0.4 Agent API Runtime — Execution Log

**Task**: Agent API & May's Orders Integration Boundary  
**Date**: 2026-09-10  
**Branch**: master  
**Git HEAD**: Current state after G0.3.1

---

## Current Status: ⏳ IN PROGRESS

## Architecture Review

### Existing Structure

```
User
  ↓
Cognito (JWT with sub, email, tenant_id, groups, custom:agent_id)
  ↓
API Gateway → JWT Authorizer
  ↓
Lambda Handler
  ├── /platform → Platform info
  ├── /me → User context
  ├── ├── /me/profile → User profile
  └── /agents → Filtered agent catalog

May's Orders (Work System)
  ├── SQS: work_queue, cv_queue, ats_queue, match_queue, dlq
  ├── DynamoDB: work_items, agent_state
  └── Lambda: processes work via SQS
```

### Key Observations

1. **API Routes**: Already defined in terraform/modules/api/main.tf for platform endpoints
2. **User Context**: Extracted from JWT claims (sub, email, tenant_id, cognito:groups, custom:agent_id)
3. **Agent Catalog**: user_profile, agent_catalog, entitlements tables for filtering
4. **Work Items**: SQS queue + DynamoDB table pattern established
5. **Agent Contract**: process_work(), validate_work(), get_status() defined

---

## G0.4 Requirements

### Agent API Routes

Need to add routes for:
- `POST /api/agents` - Submit work to an agent
- `GET /api/agents/{agentId}` - Get agent details
- `POST /api/agents/{agentId}/execute` - Execute agent with capability
- `GET /api/agents/{agentId}/work/{workId}` - Get work status

### Agent Context

Standardized context to pass to agents:
```json
{
  "context": {
    "userId": "string (from JWT sub)",
    "tenantId": "string (from custom:tenant_id)",
    "agentId": "string (requested agent)",
    "agentVersion": "string (from catalog)",
    "capability": "string (requested capability)",
    "requestId": "string (UUID per request)",
    "requestTime": "ISO8601",
    "groups": ["string"] (from Cognito groups)
  }
}
```

### Capabilities

Each agent can have multiple capabilities. For example:
- ATS Agent: analyze_cv, create_job_posting
- Matching Agent: match_jobs, recommend_positions
- Job Search Agent: search_jobs, save_search

### May's Orders Integration

Agent creates work items in May's Orders via:
1. SQS message to appropriate queue based on agent type
2. DynamoDB work item registration

---

## Implementation Plan

### Phase 1: Agent API Routes
- [ ] Add POST /api/agents route
- [ ] Add GET /api/agents/{agentId} route
- [ ] Add POST /api/agents/{agentId}/execute route
- [ ] Add GET /api/agents/{agentId}/work/{workId} route

### Phase 2: Agent Handler Logic
- [ ] Implement agent selection with entitlement check
- [ ] Implement capability validation
- [ ] Implement context extraction
- [ ] Implement work item creation

### Phase 3: Work/Order Contract
- [ ] Define agent -> May's Orders work creation
- [ ] Handle idempotency
- [ ] Propagate tenant/user context

### Phase 4: Tests
- [ ] Authentication tests
- [ ] Authorization tests
- [ ] Capability tests
- [ ] Work creation tests

---

## Detailed Findings

### Cognito Claims Available
From API Gateway event:
- `event.requestContext.authorizer.jwt.claims.sub` → userId
- `event.requestContext.authorizer.jwt.claims.email` → email
- `event.requestContext.authorizer.jwt.claims['custom:tenant_id']` → tenantId
- `event.requestContext.authorizer.jwt.claims['cognito:groups']` → groups
- `event.requestContext.authorizer.jwt.claims['custom:agent_id']` → agentId (if any)

### DynamoDB Tables for G0.4
- `user_profile` - Already exists (tenant isolation verified)
- `agent_catalog` - Already exists (for agent metadata)
- `entitlements` - Already exists (for access control)
- `work_items` - Already exists (for work tracking)

### SQS Queues for G0.4
- Need to determine which queue for which agent type
- Current: work_queue, cv_queue, ats_queue, match_queue, dlq

---

## Risks

1. **Complexity vs Scope**: Need to avoid over-engineering. G0.4 is about boundaries, not implementing specific agents.

2. **Tenant Isolation**: Must ensure work items are always created with correct tenant context.

3. **Capability Model**: Need to define how capabilities map to work item types.

4. **Idempotency**: Must use the existing work_id/idempotency_key pattern.

---

## Open Questions

1. Should there be a separate `/api/v1/` prefix for agent API routes, or use existing `/api` prefix?

2. How to handle agent-specific queues? Should we use:
   - Single queue with agent-type in payload
   - Per-agent queues
   - Dynamic queue selection based on agent catalog

3. Should capabilities be pre-defined in agent catalog, or arbitrary strings?

4. What's the relationship between the existing Lambda handler and new agent API routes?

---

## Resume Point

Analyzing existing Lambda handler pattern to determine:
1. How to integrate new routes without breaking existing functionality
2. Whether to extend handler.py or create separate handler for agent API
3. How to structure routes: `/api/agents/{agentId}` vs `/agents/{agentId}`

**Next Step**: Review handler.py and determine integration approach.