# AGENT-HOOK-02 — Discovery & Eligibility Pipeline

## TASK

Connect ProcessingEnvelope to AgentDiscovery and EligibilityCheck.

Target:

```
ProcessingEnvelope
      ↓
AgentDiscovery
      ↓
EligibilityCheck
      ↓
Eligible Candidates
```

❌ NO Routing
❌ NO Ranking
❌ NO Selection
❌ NO SQS
❌ NO May's Orders

---

## IMPLEMENTATION

### Files Modified

| File | Change |
|------|--------|
| `agents/ecosystem/discovery.py` | Added `find_from_envelope()` method |
| `agents/ecosystem/eligibility.py` | Added `EligibilityPipeline`, `EligibilityPipelineResult` |
| `agents/ecosystem/__init__.py` | Added exports |
| `tests/test_event_hook_pipeline.py` | New test file |

---

## DISCOVERY ENHANCEMENT

### find_from_envelope()

```python
def find_from_envelope(self, envelope: ProcessingEnvelope) -> List[DiscoveryResult]:
    """
    Discover agents matching a processing envelope.
    
    Uses envelope's:
    - agent_id (explicit candidate)
    - capability from input
    - runtime compatibility
    - body version compatibility
    - status (ACTIVE only by default)
    """
```

---

## ELIGIBILITY PIPELINE

### EligibilityPipeline

```python
class EligibilityPipeline:
    def check_candidates(
        self, 
        candidates: List[DiscoveryResult],
        envelope: ProcessingEnvelope
    ) -> EligibilityPipelineResult:
        """
        Check eligibility for a list of candidates.
        
        Considers:
        - Agent registration status
        - Agent status (rejects RETIRED, DEPRECATED)
        - Capability support
        - Body compatibility
        - Runtime compatibility
        - Tenant context
        """
```

### EligibilityPipelineResult

```python
@dataclass
class EligibilityPipelineResult:
    eligible: List[EligibilityCheck]
    rejected: List[EligibilityCheck]
```

---

## ARCHITECTURE

### Pipeline Flow

```
Event (external)
     │
     ▼
EventHook
     │
     ▼
ProcessingEnvelope
     │
     ├── agent_id (optional)
     ├── capability (from input)
     ├── tenant_id
     ├── trigger_type
     └── runtime/body info
     │
     ▼
AgentDiscovery.from_envelope()
     │
     ├── Candidates from registry
     └── Filtered by capability, runtime, body
     │
     ▼
EligibilityPipeline.check_candidates()
     │
     ├── Check status (ACTIVE only)
     ├── Verify capability support
     ├── Check runtime compatibility
     ├── Check body compatibility
     └── Preserve tenant context
     │
     ▼
Eligible [A, B, C] ← Multiple candidates returned
```

---

## TESTS

10 tests, all passing.

| Test Class | Description |
|------------|-------------|
| TestDiscoveryFromEnvelope | Capability search, explicit agent_id, multiple candidates |
| TestEligibilityPipeline | Eligible agents, rejected agents, retired handling |
| TestFullPipeline | End-to-end from envelope to results |
| TestNoRouting | Ensures no selection occurs |

---

## VALIDATION

- Pipeline returns multiple candidates without ranking
- Tenant context preserved throughout
- No agent auto-selected
- Capability from payload used correctly
- Status filtering applied

---

## GIT STATUS

```
Commits: +1
```

Commit:
```
aa39950 feat: add EligibilityPipeline for AGENT-HOOK-02
```

---

## REMAINING WORK

Next milestone (AGENT-HOOK-03 or routing milestone):
- Agent Selection / Winner Determination
- Possibly Ranking based on capability matching
- Integration with Lambda handler for event processing

---

## ACCEPTANCE

| Criteria | Status |
|----------|--------|
| ProcessingEnvelope connects to Discovery | ✅ Yes |
| Discovery uses existing AgentRegistry | ✅ Yes |
| Existing capability structure used | ✅ Yes |
| Trigger compatibility considered | ✅ Yes |
| Explicit agent_id works | ✅ Yes |
| Unknown agent_id handled | ✅ Yes |
| Multiple candidates returned | ✅ Yes |
| Eligibility receives all candidates | ✅ Yes |
| Tenant context preserved | ✅ Yes |
| Agent status considered | ✅ Yes |
| Runtime/body compatibility kept | ✅ Yes |
| No auto-selection | ✅ Yes |
| No ranking | ✅ Yes |
| No AI routing | ✅ Yes |
| No agent execution | ✅ Yes |
| No SQS | ✅ Yes |
| No May's Orders change | ✅ Yes |
| No AWS change | ✅ Yes |
| Tests passing | ✅ Yes |
| Documentation updated | ✅ Yes |
| AI Audit Log updated | ✅ Yes |
| Git clean | ✅ Yes |

✅ **GREEN**

