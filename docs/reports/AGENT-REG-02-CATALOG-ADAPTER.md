# AGENT-REG-02 — Catalog Adapter Foundation

## TASK

Bridge the DynamoDB `agent_catalog` to the runtime `AgentRegistry`.

---

## CURRENT STATE

### DynamoDB agent_catalog (terraform/modules/dynamodb/main.tf:87-114)

- Table: `{project}-{env}-agent-catalog`
- Primary key: `agentId`
- GSI: `status`
- Attributes: `agentId`, `status`, TTL
- Billing: PAY_PER_REQUEST

### Lambda Handler (lambda/handler.py:555-581)

**Function**: `_get_agent_catalog()`

Returns: `Dict[str, Dict]` mapping agentId to raw DynamoDB item.

### Agent Registry (agents/ecosystem/registry.py)

- In-memory registry
- `AgentDescriptor` dataclass with capabilities, status, runtime, etc.
- Used in tests, NOT in production Lambda

---

## GAP ANALYSIS

### Missing Connection

```
DynamoDB agent_catalog
        │
        ▼
    _get_agent_catalog()  ← Read operation
        │
        ▼
    plain dict        ← NOT AgentDescriptor
        │
        ▼
    AgentRegistry     ← NOT populated
        │
        ▼
    AgentDiscovery
        │
        ▼
    EligibilityCheck
```

**Problem**: The `AgentRegistry` is never populated from DynamoDB in production code.

---

## IMPLEMENTATION

### CatalogAdapter (agents/ecosystem/catalog_adapter.py)

Created adapter that:

1. **Reads from DynamoDB**: Uses `_get_agent_catalog()` logic
2. **Converts to AgentDescriptor**: Maps DynamoDB fields to descriptor fields
3. **Populates Registry**: Uses `registry.register()`

**Key Features**:
- Lazy DynamoDB initialization
- Full field mapping
- Error handling
- Thread-safe for Lambda

### Integration

Updated `agents/ecosystem/__init__.py` to export:
- `CatalogAdapter`
- `populate_registry_from_catalog()`

---

## FIELD MAPPING

| DynamoDB Field | AgentDescriptor |
|---------------|-----------------|
| agentId | agent_id |
| status | status |
| version | version |
| capabilities | capabilities |
| description | description |
| (custom) | metadata |

---

## NEXT STEPS

1. Integrate adapter with Lambda initialization
2. Consider hot-reloading on catalog changes
3. Add tenant-aware filtering
4. Cache considerations

---

## VERIFICATION

```bash
python3 -c "
from agents.ecosystem import CatalogAdapter, populate_registry_from_catalog
from agents.ecosystem.registry import get_registry

# Test adapter
adapter = CatalogAdapter()
print(f'Found agents: {len(adapter.get_all_agents())}')

# Test population  
registry = get_registry()
count = populate_registry_from_catalog(registry)
print(f'Registered: {count} agents')
"
```

---

## FILES CHANGED

| File | Action |
|------|--------|
| `agents/ecosystem/catalog_adapter.py` | CREATED |
| `agents/ecosystem/__init__.py` | MODIFIED (added exports) |

---

## Git Status

```
Branch: main
Status: CLEAN (to be committed)
```

---

## STATUS: IDENTIFICATION + IMPLEMENTATION

**IMPLEMENTATION COMPLETE**:

- CatalogAdapter reads from DynamoDB
- Converts to AgentDescriptor format
- Can populate AgentRegistry
- Exported from ecosystem module

**NOT IMPLEMENTED** (out of scope):
- Integration with Lambda handler
- Hot reload on catalog changes
- Caching strategy

---

## REFERENCES

- `terraform/modules/dynamodb/main.tf:87-114` — Table schema
- `lambda/handler.py:555-581` — Existing catalog read
- `agents/ecosystem/registry.py` — Registry definition
- `docs/AGENT_REGISTRY_ARCHITECTURE.md` — Architecture doc
