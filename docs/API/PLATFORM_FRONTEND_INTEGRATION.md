# Platform ↔ JobSearch Integration Contract

## Overview

This document defines the **binding contract** between the Ground Zero Platform Core and the JobSearch frontend application.

**Purpose**: Enable JobSearch to integrate with authentication, user context, and agent catalog without knowledge of internal AWS or Ground Zero implementation details.

---

## Architecture

```
┌─────────────────┐
│ JobSearch UI    │
│ (Exits Process) │
└────────┬────────┘
         │ HTTPS / JSON
         ▼
┌─────────────────────────────────┐
│        Platform API             │
│   (Ground Zero - Lambda)        │
│                                 │
│   ├── GET /platform             │
│   ├── GET /me                   │
│   ├── GET /me/profile           │
│   └── GET /agents               │
└────────┬────────────────────────┘
         │
    ┌────┴────┐
    │ Cognito │ (Authentication)
    └─────────┘
         │
         ▼
    User Identity
         │
         ▼
┌────────┴────────┐
│ JobSearch UI    │
│ Integration     │
└─────────────────┘
```

---

## 1. Login / Cognito Boundary

### Purpose

Cognito is the **authentication boundary**. The user authenticates via Cognito and receives a JWT.

### How It Works

1. User opens JobSearch
2. JobSearch redirects to Cognito or uses existing session
3. Cognito authenticates user
4. JWT is stored in frontend session
5. Frontend calls Platform API with JWT

### What Crosses This Boundary

- JWT token in `Authorization: Bearer <token>` header
- User identity (sub, email, tenant)

### What Must NOT Cross

- Cognito User Pool configuration
- JWT signing keys
- Raw AWS credentials

### Frontend Responsibilities

- Trigger authentication flow
- Store JWT securely
- Attach JWT to all API calls

### Backend Responsibilities

- Validate JWT signature
- Extract user identity from claims
- Reject invalid/missing tokens

---

## 2. SYNC vs ASYNC

### Important Distinction

```
SYNC (HTTP/JSON)                 ASYNC (SQS/DynamoDB)
   │                                  │
   ▼                                  ▼
Platform API                        Agent Execution
   │                                  │
   ▼                                  ▼
Response immediately           Work Item created
                                │
                                ▼
                          SQS Queue
                                │
                                ▼
                          Lambda Worker
                                │
                                ▼
                          Agent
                                │
                                ▼
                          Result
```

**JobSearch reads via**:
- Platform API (sync) → /me, /me/profile, /agents
- Agent API (sync) → execute, status check

**JobSearch does NOT directly**:
- Call SQS
- Invoke Lambda
- Query DynamoDB directly

---

## 3. GET /me

### Contract: User Context

**Endpoint**: `GET /me`

**Auth Required**: ✅ JWT

**Purpose**: Returns the authenticated user's context for identifying the current user and tenant.

**Request**:
```http
GET /me HTTP/1.1
Authorization: Bearer <JWT>
```

**Response** (200 OK):
```json
{
  "userId": "string - UUID from JWT sub claim",
  "email": "string - from JWT email claim",
  "tenantId": "string - from custom:tenant_id claim",
  "groups": ["string - from cognito:groups claim"]
}
```

**Error Responses**:
- `401 Unauthorized`: Token missing, invalid, or expired
- `403 Forbidden`: Token valid but user not authorized

**Security**:
- Tenant ID is server-side extracted from JWT
- Frontend cannot modify tenantId

**Used By**:
- JobSearch initializes user session
- Determine tenant context

---

## 4. GET /me/profile

### Contract: User Profile

**Endpoint**: `GET /me/profile`

**Auth Required**: ✅ JWT

**Purpose**: Returns the user's profile data for personalization and display.

**Request**:
```http
GET /me/profile HTTP/1.1
Authorization: Bearer <JWT>
```

**Response** (200 OK):
```json
{
  "userId": "string",
  "tenantId": "string",
  "email": "string",
  "firstName": "string?",
  "lastName": "string?",
  "company": "string?",
  "jobTitle": "string?"
}
```

**Error Responses**:
- `401 Unauthorized`: Token missing or invalid
- `404 Not Found`: Profile exists but not found (rare, profile should exist)

**Security**:
- Profile is tenant-isolated
- Only accessible by matching userId + tenantId
- Frontend does not query DynamoDB directly

**Responsibility**:
- Profile ownership: Platform (via DynamoDB)
- Profile schema: Platform-defined
- Profile updates: Not in this version

---

## 5. GET /agents

### Contract: Agent Catalog & Entitlements

**Endpoint**: `GET /agents`

**Auth Required**: ✅ JWT

**Purpose**: Returns list of agents the authenticated user is entitled to use.

**Request**:
```http
GET /agents HTTP/1.1
Authorization: Bearer <JWT>
```

**Response** (200 OK):
```json
{
  "agents": [
    {
      "agentId": "string",
      "name": "string",
      "description": "string",
      "version": "string",
      "capabilities": ["string"],
      "status": "string - active|inactive"
    }
  ]
}
```

**Security**:
- Frontend shows this list but **IS NOT** the security boundary
- Backend enforces entitlements server-side
- Each agent requires valid entitlement

**Important**:
- Frontend displays available agents
- Backend validates every execution
- Entitlements can change without frontend update

**Responsibility**:
- Catalog: Platform Team (DynamoDB)
- Entitlements: Platform Team
- Filtering: Backend

---

## 6. JobSearch → Agent Execution

### Workflow

```
JobSearch Frontend
       │
       ▼
POST /api/agents/{agentId}/execute
       │
       ▼
Work Item Created ──→ SQS ──→ Lambda ──→ Agent
       │                                │
       │                                ▼
       │                         Result
       │                           │
       │                           ▼
       │                      Stored in
       │                      DynamoDB
       │
       ▼
GET /api/agents/{agentId}/work/{workId}
       │
       ▼
Status Check
```

### POST /api/agents/{agentId}/execute

**Purpose**: Request an agent to process data.

**Request**:
```json
{
  "workType": "string",
  "payload": {
    "key": "value"
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "workId": "uuid",
  "status": "QUEUED"
}
```

### GET /api/agents/{agentId}/work/{workId}

**Purpose**: Check work item status.

**Response**:
```json
{
  "success": true,
  "workId": "uuid",
  "status": "COMPLETED|FAILED|RUNNING",
  "result": {}
}
```

---

## 7. Tenant Isolation

### How It Works

1. JWT contains `custom:tenant_id` claim
2. Platform validates claim against user
3. All profile/agent queries filter by tenant
4. Frontends cannot change tenant

### What Frontend Cannot Do

- ❌ Change tenantId in requests
- ❌ Access another tenant's profile
- ❌ See other tenants' agents

---

## 8. Responsibility Matrix

| Component | Owner | Can Change | Cannot Access |
|-----------|-------|------------|---------------|
| Cognito | Auth Team | User pool config | Code/Internal |
| Platform API | Agent Team | Endpoints, contracts | DB/SQS directly |
| JobSearch | JobSearch Team | UI, flows | Cognito internals |
| API Key | — | N/A | N/A |
| DynamoDB | Agent Team | Schema | JobSearch direct |
| SQS | Agent Team | Queue config | JobSearch direct |
| Lambda | Agent Team | Code | JobSearch direct |

---

## 9. Frontend Implementation Guide

### Step 1: User Authentication

```javascript
// Trigger Cognito auth
await cognitoAuth.login();

// Get JWT
const token = await getJwtToken();

// Store securely
sessionStorage.setItem('auth', token);
```

### Step 2: Get User Context

```javascript
const response = await fetch('/me', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const user = await response.json();
// { userId, email, tenantId, groups }
```

### Step 3: Get Profile

```javascript
const response = await fetch('/me/profile', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const profile = await response.json();
```

### Step 4: Get Agents

```javascript
const response = await fetch('/agents', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const { agents } = await response.json();
```

### Step 5: Execute Agent

```javascript
// Submit work
const executeResponse = await fetch(`/api/agents/${agentId}/execute`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ workType, payload })
});
const { workId } = await executeResponse.json();

// Check status
const statusResponse = await fetch(`/api/agents/${agentId}/work/${workId}`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const workItem = await statusResponse.json();
```

---

## 10. Error Handling

### Auth Errors

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired token"
  }
}
```

### Not Found

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Profile not found"
  }
}
```

### Forbidden

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Insufficient entitlements"
  }
}
```

---

## 11. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-09-15 | Initial contract definition |

---

## 12. See Also

- `docs/ARCHITECTURE.md` — Overall system architecture
- `docs/INTEGRATION_BOUNDARIES.md` — System boundaries
- `docs/Team_COLLABORATION.md` — Team responsibilities
- `docs/API/API_DOCUMENTATION_STANDARD.md` — Documentation standard
- `agents/agent-contract.md` — Agent interface contract

---

## 13. Stability

**Status**: ✅ STABLE

This contract is based on **verified implementation**:
- `/me` — implemented in `lambda/handler.py:183-201`
- `/me/profile` — implemented in `lambda/handler.py:204-225`
- `/agents` — implemented in `lambda/handler.py:228-264`

**Non-Goals**:
- Frontend implementation
- UI components
- Okta/SAML integration
- API versioning strategies

---

## 14. Hard Stop

This document establishes the **interface contract only**.

**NOT IMPLEMENTED**:
- OpenAPI specification (move to separate file)
- API gateway routes (already exist)
- Frontend code
- Unit tests for this contract

**NEXT STEPS**:
- Create OpenAPI spec from this contract
- Implement frontend integration
- Add contract tests

---

## 15. Contact

For questions about this contract:
- Review `docs/Team_COLLABORATION.md` for team ownership
- See `docs/INTEGRATION_BOUNDARIES.md` for architecture
- Check `lambda/handler.py` for implementation details