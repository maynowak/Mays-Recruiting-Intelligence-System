# AGENT-REG-01 — Agent Registry Foundation

## TASK

Build the missing architecture link between persistent `agent_catalog` and Agent Ecosystem.

---

## CURRENT STATE

### Git Status

| Parameter | Value |
|-----------|-------|
| Branch | main |
| HEAD | f1da6d3 |
| Status | CLEAN |

### A) Platform agent_catalog

**File**: `terraform/modules/dynamodb/main.tf:87-114`

**Table**: `{project}-{env}-agent-catalog`

**Schema**:
- `agentId` (S, hash key)
- `status` (S,gsi)
- TTL enabled

**IMPLEMENTED**: ✅ Yes (Terraform)

### B) Runtime AgentRegistry

**File**: `agents/ecosystem/registry.py`

**Implementation**: In-memory `AgentRegistry` class with `AgentDescriptor` dataclass

**IMPLEMENTED**: ✅ Yes (but in-memory only)

### C) AgentDiscovery

**File**: `agents/ecosystem/discovery.py`

**Purpose**: Find agents by capability/runtime

**IMPLEMENTED**: ✅ Yes

### D) EligibilityCheck

**File**: `agents/ecosystem/eligibility.py`

**Purpose**: Verify agent can handle request

**IMPLEMENTED**: ✅ Yes

### E) ProcessingChain

**File**: `agents/ecosystem/chain.py`

**Purpose**: Agent workflows

**IMPLEMENTED**: ✅ Yes

### F) AgentInvocation

**File**: `agents/agent_body/invocation.py`

**Purpose**: Agent-to-agent calls

**IMPLEMENTED**: ✅ Yes

---

## ARCHITECTURE GAP

### PROBLEM: No Catalog → Registry Bridge

**Current State**:
- `agent_catalog` is a **persistent** DynamoDB table
- `AgentRegistry` is an **in-memory** registry
- **NO CODE EXISTS** that syncs them!

**Implications**:
1. Cold starts lose registry state
2. Cannot scale across Lambda instances
3. Catalog changes require restart

### Analysis of Current Files

| File | Contains | Runtime Use |
|------|----------|-------------|
| `registry.py` | In-memory dict | Used at startup |
| `discovery.py` | Registry queries | Works with memory |
| `eligibility.py` | Descriptor checks | Works with memory |
| `chain.py` | ChainExecutor | Uses registry |
| `handler.py` | Lambda handler | Calls AgentBody |

**KEY FINDING**: No code reads `agent_catalog` from DynamoDB into registry!

---

## SOLUTION ARCHITECTURE

### Option 1: Lazy Load on Startup

```python
def populate_registry_from_dynamodb():
    """Load agent catalog from DynamoDB into registry."""
    table = dynamodb.Table('agent-catalog')
    response = table.scan()
    for item in response['Items']:
        descriptor = AgentDescriptor(
            agent_id=item['agentId'],
            # ... map other fields
        )
        registry.register(descriptor.agent_id, descriptor)
```

**Pros**: Simple, works with cold starts
**Cons**: Cold start delay, no updates

### Option 2: DynamoDB Streams

Configure stream to trigger Lambda on catalog changes.

**Pros**: Always up-to-date
**Cons**: More complexity, additional Lambda

### Option 3: Hybrid (Recommended)

- Startup: Load from DynamoDB
- Runtime: Keep in memory
- Optional: Stream for updates

---

## CLOUDTRAIL AUDIT

Actions that should be logged:

| Action | CloudTrail Event |
|--------|------------------|
| Lambda invoke | `lambda:InvokeFunction` |
| DynamoDB access | `dynamodb:Query|Scan|GetItem` |
| Registry load | Custom (via Lambda logs) |

---

## VERIFICATION COMMANDS

```bash
# Check if catalog is actually used
grep -r "agent_catalog" .

# Check registry population
grep -n "populate\|load\|scan" agents/ecosystem/

# Check Lambda cold start
grep -n "cold\|init" lambda/handler.py
```

---

## COST ANALYSIS

| Resource | Monthly |
|----------|---------|
| DynamoDB (catalog) | <$0.10 (few KB) |
| Stream (if enabled) | ~$1 + events |

---

## OPEN POINTS

1. Should catalog be tenant-scoped?
2. Should discovery use batches for large catalogs?
3. What fields map to AgentDescriptor?
4. Should we add capabilities GSI?

---

## STATUS: IDENTIFICATION ONLY

This task is **NOT** implementing the sync.

It is documenting the gap and preparing for future implementation.

---

## Git Status

```
On branch main
Nothing to commit, working tree clean
HEAD -> f1da6d3
```

---

## NEXT STEP

Implement lazy-load mechanism for DynamoDB → Registry sync.
