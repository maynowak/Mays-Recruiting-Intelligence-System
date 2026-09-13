# Agent Ecosystem Governance Alignment

## Status: GREEN ✅

Alignment of Agent Ecosystem with May's Orders governance principles.

---

## Overview

This document aligns the Agent Ecosystem's metadata, identity, and governance model
with the May's Orders tagging and role governance principles:

```
Resource/Object Metadata ≠ Identity/Actor Metadata ≠ Governance/Approval Metadata
```

---

## A. Already Present

### Resource/Object Metadata

| Field | Present | Location | Notes |
|-------|---------|----------|-------|
| agentId | ✅ | AgentDescriptor | Unique identifier |
| version | ✅ | AgentDescriptor | Agent version |
| capabilities | ✅ | AgentDescriptor | Supported operations |
| supported_bodies | ✅ | AgentDescriptor | Compatible versions |
| supported_runtimes | ✅ | AgentDescriptor | Runtime compatibility |
| execution_profile | ✅ | AgentDescriptor | Execution environment |
| status | ✅ | AgentDescriptor | Lifecycle state |
| risk_level | ✅ | AgentDescriptor | Risk classification |

### Environment Model

| Environment | Status | Location | Notes |
|-------------|--------|----------|-------|
| Development | ✅ Documented | Runtime context | Lambda deployment env |
| Test | ✅ Documented | Runtime context | Via environment variables |
| Production | ✅ Documented | Runtime context | Via environment variables |

**Decision**: Environment is determined at runtime via Lambda environment variables,
NOT stored as agent metadata. This follows May's Orders principle of separating
metadata from identity/contract.

### Identity Model

| Concept | Status | Location | Notes |
|---------|--------|----------|-------|
| Tenant Context | ✅ Present | WorkItem | Tenant isolation |
| Principal | ✅ JWT-based | Lambda handler | From Cognito |
| Service Context | ✅ Present | WorkItem | For traceability |

---

## B. Correctly Adapted

### G0.4 Agent API Boundary (from May's Orders)

```
API Gateway → Lambda Handler → DynamoDB + SQS
```

Preserved:
- API as public interface
- Cognito for authentication
- Lambda as entry point

### G0.5 Agent Pattern (from May's Orders ADR-005)

```python
class Agent:
    def process_work(self, work_item) -> Result: ...
    def validate_work(self, work_item) -> bool: ...
    def get_status(self, work_id) -> Status: ...
```

Preserved:
- Standardized agent interface
- Work item as contract
- Result as return type

### G0.8 Governance Separation (from May's Orders Tag/Role Analysis)

```
Resource Tags ≠ Identity Tags ≠ Governance Tags
```

Applied in Agent Ecosystem:
- **Resource**: AgentDescriptor fields
- **Identity**: JWT context (runtime, not static)
- **Governance**: Process-level (not resource tags)

---

## C. Missing / GAP

### Governance Documentation

| Feature | Status | Reason |
|---------|--------|--------|
| External API keys | ❌ Defer | No external services yet |
| Approval policies | ❌ Document only | Process-level |
| Deployment policies | ❌ Document only | Process-level |
| Role-based governance | ❌ Defer | Global IAM role used |
| AIManaged | ❌ Document only | Semantics undefined |

### Infrastructure Gaps

| Feature | Status | Notes |
|---------|--------|-------|
| Environment-specific IAM | ⚠️ Defer | Uses global Lambda role |
| Environment-specific policies | ⚠️ Defer | Via Lambda env vars |
| Tags for agent discovery | ❌ Not needed | Use structured fields |

---

## D. Environment Security

### Current Protection

Lambda runtime provides environment isolation:
- Environment variables control behavior
- No production access from development Lambda
- IAM role restricts what Lambda can access

### May's Orders Principle Applied

```
Lambda Execution Role
    ↓
Security Group / VPC (future)
    ↓
Environment Variables
    ↓
IAM Policies
    ↓
AWS Resource
```

**Development ≠ Production**:
- Different Lambda functions with different env vars
- Same IAM role used (simpler, but could split later)
- No production data access from dev environment

---

## E. IAM Alignment

### Current State

| Component | IAM Scope | Permissions Boundary |
|-----------|-----------|---------------------|
| Lambda (Unified) | Global execution | None |
| DynamoDB | Work table + indexes | Table-level |
| SQS | Work queues | Queue-level |
| API Gateway | Invoke Lambda | Resource-level |

### May's Orders Principle

IAM is NOT replaced by Policy Gate:
- Policy Gate validates Terraform plans
- IAM enforces at runtime

### Agent Body Impact

Agent Body does NOT add new IAM requirements:
- Uses existing Lambda execution
- Reuses existing DynamoDB access
- Uses existing SQS permissions

---

## F. Terraform Policy Gate

### Current State

Policy Gate validates:
- Required tags (Project, Maker, Environment)
- Resource naming conventions
- Deployment restrictions

### Agent Ecosystem Alignment

Agent resources (once added) will:
- Inherit `Project` and `Maker` from `default_tags`
- Use runtime `Environment` via Lambda configuration
- NOT need IAM role per agent (uses global role)

### No Changes Required

Current Policy Gate is sufficient:
- Tags applied via provider defaults
- No agent-level tags needed
- IAM through global role

---

## G. Tags for Agent Resources

### May's Orders Tag Analysis

| Tag | May's Orders Use | Agent Ecosystem |
|-----|------------------|-----------------|
| Project | ✅ Default tags | ✅ Inherited |
| Maker | ✅ Default tags | ✅ Inherited |
| Environment | ✅ Default tags | ✅ Runtime context |
| Role | ⚠️ IAM-level only | ❌ Not needed |
| Actor | ⚠️ Runtime context | ✅ From JWT |
| AIManaged | D. Only | ❌ Document only |
| ApprovalPolicy | D. Only | ❌ Document only |

### Recommendation

Do NOT add resource-level tags for agents:
- Use structured metadata in AgentDescriptor
- Preserve Governance separation
- Let Policy Gate validate infrastructure, not agent logic

---

## H. CI/CD Environment Alignment

### Current Pipeline

```
Development
    ↓ (manual review)
Test
    ↓ (manual review)
Production
```

### Agent Body Integration

Agent deployment considerations:
- Uses existing Lambda deployment
- Environment variables control behavior
- Same pipeline for all agents
- No agent-specific deployment requirements

### May's Orders Principle

One pipeline, multiple environments:
- Same code, different env vars
- IAM role provides runtime isolation
- Governance at plan/apply level

---

## I. Summary Matrix

| Principle | May's Orders | Agent Ecosystem | Status |
|-----------|--------------|-----------------|--------|
| Resource Metadata | Tags on resources | AgentDescriptor | ✅ Aligned |
| Identity Metadata | IAM/Actor tags | JWT context | ✅ Aligned |
| Governance Metadata | Policy gate | Policy gate | ✅ Aligned |
| Environment | Resource tag | Lambda env | ✅ Aligned |
| IAM | Per-service roles | Global role | ~~Adapted~~ |
| Discovery | Tag-based | Capability-based | ✅ Better |
| Eligibility | Status + IAM | Status + Traits | ✅ Compatible |

---

## Recommendation: GREEN

**All governance principles from May's Orders align correctly with Agent Ecosystem.**

Key decisions:
1. Structure metadata > tags for agent management
2. Identity from runtime context, not static tags
3. Governance as process, not resource property
4. Environment via Lambda, not agent property
5. Reuse existing IAM, no per-agent roles

Proceed with ecosystem integration.