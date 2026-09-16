# Runtime Registry Integration Guide

## Overview

This document describes how to integrate the CatalogAdapter with the Lambda runtime for consistent registry lifecycle management.

---

## Lambda Cold Start Lifecycle

### Current Flow

```
Lambda Start (Cold Start)
    │
    ▼
Module-level imports
    │
    ▼
AGENT_BODY = AgentBody()     ← Global instance
    │
    ▼
Handler ready for requests
```

### Problem

The global registry is empty. Agents are registered via `register_agent()` which must be called explicitly.

DynamoDB catalog is read on-demand, not integrated.

---

## Target Flow

```
Lambda Start (Cold Start)
    │
    ▼
Module-level imports
    │
    ▼
Catalog Initialization
    │
    ▼
AgentRegistry ← Population from DynamoDB
    │
    ▼
AgentDiscovery ← Linked to Registry
    │
    ▼
Handler ready (with populated catalog)
```

---

## Required Integration

Add to `lambda/handler.py` after AgentBody initialization:

```python
# Initialize catalog in registry
try:
    from agents.ecosystem import populate_registry_from_catalog
    from agents.ecosystem.registry import get_registry
    
    adapter = CatalogAdapter()
    agents = adapter.get_all_agents()
    for agent_id, agent_data in agents.items():
        from agents.ecosystem.registry import AgentDescriptor
        # Create and register descriptors
except Exception as e:
    logger.warning(f"Catalog initialization: {e}")
```

---

## References

- `lambda/handler.py` — Lambda entry point
- `agents/ecosystem/catalog_adapter.py` — Adapter
- `agents/ecosystem/registry.py` — Registry
