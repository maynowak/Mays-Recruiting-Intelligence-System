# Agent Ecosystem Metadata & Governance

## Purpose

This document establishes the metadata and governance model for the Agent Ecosystem,
aligned with May's Orders tagging and role governance principles.

**Status**: ✅ S2.9 Implementation Complete

---

## Governance Principle

May's Orders provides the governance principle:

    Resource/Object Metadata  ≠  Identity / Actor Metadata  ≠  Governance / Approval Metadata

The Agent Ecosystem adopts this principle:

- **Agent Metadata** - Describes the agent itself
- **Identity / Actor** - Describes who/what is invoking (runtime context)
- **Governance** - Describes approval/deployment policy (process-level)

---

## Classification Framework

### A. Agent/Object Metadata

Metadata for agent discovery, execution, and lifecycle.

| Field | Type | Description | Used For |
|-------|------|-------------|----------|
| agent_id | string | Unique agent identifier | Discovery, Routing |
| version | string | Agent version | Lifecycle, Compatibility |
| capabilities | list | Supported capabilities | Discovery, Eligibility |
| supported_bodies | list | Compatible agent body versions | Compatibility |
| supported_runtimes | list | Compatible runtimes | Eligibility |
| status | enum | Lifecycle status | Discovery, Eligibility |
| risk_level | enum | Risk classification | Eligibility |

### B. Identity / Actor Metadata

Metadata describing the invoking entity. NOT static agent properties but runtime context.

| Field | Type | Description |
|-------|------|-------------|
| invokingActor | string | Entity invoking agent |
| principal | string | Authentication principal |
| serviceId | string | Service identifier |

### C. Governance Metadata

For deployment and approval policies. NOT implemented as tags.

| Field | Type | Description |
|-------|------|-------------|
| approvalPolicy | string | Required approval level |
| deploymentPolicy | string | Deployment requirements |

---

## What is NOT Implemented

Per May's Orders governance analysis:

| Feature | Status | Reason |
|---------|--------|--------|
| Environment tag | ❌ DEFER | Not needed for agent processing |
| IAM roles per agent | ❌ DEFER | Uses global Lambda role |
| Agent-level tags | ❌ DEFER | Structured metadata sufficient |
| ApprovalPolicy field | ❌ DOCUMENT ONLY | Process-level, not resource |

---

## Audit Trail

For traceability across agent invocations:

    Invocation
    ├── invocation_id
    ├── parent_work_id
    ├── agent_id
    ├── capability
    └── result

REUSES existing work item tracking - no duplicate infrastructure.

---

## References

- May's Orders Tag/Role/Governance Analysis (TAG-ROLE-GOVERNANCE-REVIEW-EXECUTION-LOG.md)
- Agent Body Runtime Guide
