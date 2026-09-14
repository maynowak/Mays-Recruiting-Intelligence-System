# Processing Chain Execution — S2.14

## Purpose

Provides a standardized mechanism for chaining agent operations, enabling sequences like:
```
Agent A → ProcessingChain → Agent B → Agent C → Result
```

## Architecture

```
Agent
  ↓
Invocation Contract
  ↓
ProcessingChain
  ↓
ChainExecutor
  ↓
Eligibility Check
  ↓
Agent Body
  ↓
Router → Executor → Target Agent
  ↓
Result → Next Step
```

## Components

### ChainStep
```python
@dataclass
class ChainStep:
    agent_id: str          # Target agent identifier
    capability: str        # Capability to invoke
    description: str = ""  # Optional description
    required: bool = True  # Fail if step fails
    optional: bool = False # Continue on failure
```

### ProcessingChain
```python
@dataclass
class ProcessingChain:
    name: str
    steps: List[ChainStep]
    description: str = ""
    
    def is_valid(registry: AgentRegistry) -> bool: ...
    def validate(registry: AgentRegistry) -> bool: ...
```

### ChainExecutor
```python
class ChainExecutor:
    def execute(
        self,
        chain: ProcessingChain,
        input_data: Dict[str, Any],
        parent_work_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> ProcessingResult: ...
```

### ProcessingResult
```python
@dataclass
class ProcessingResult:
    success: bool
    data: Optional[Dict[str, Any]]  # Final output
    error: Optional[Dict[str, Any]]  # Error details
    chain_results: Optional[List]   # Per-step results
    last_step: Optional[str]        # Failed step, if any
```

## Integration Flow

### Setup
```python
from agents.ecosystem.chain import ProcessingChain, ChainStep, ChainExecutor
from agents.agent_body import AgentBody

# Create agent body with registered handlers
body = AgentBody()
body.router.register(capability='step.a', handler=handler_a)
body.router.register(capability='step.b', handler=handler_b)

# Create chain
chain = ProcessingChain(
    name='my_chain',
    steps=[
        ChainStep(agent_id='agent_a', capability='step.a'),
        ChainStep(agent_id='agent_b', capability='step.b')
    ]
)

# Execute
executor = ChainExecutor(registry=registry, agent_body=body)
result = executor.execute(
    chain=chain,
    input_data={'start': 'data'},
    parent_work_id='parent-123',
    tenant_id='tenant-dev'
)
```

### Invocation Integration
```python
from agents.agent_body.invocation import InvocationContract

contract = InvocationContract(
    target_agent_id='reference_agent',
    capability='reference.echo',
    payload=data
)

# Chain executor uses same contract for internal step invocation
```

## Features

### 1. Data Propagation
Each step's output (`result['data']`) becomes the next step's input:
```python
# Step A returns: {'output': 'result'}
# Step B receives: {'output': 'result', 'input': 'data'}
```

### 2. Traceability
Maintains parent_work_id through all steps:
```python
parent_work_id = 'parent-123'
# All steps preserve this for audit trail
```

### 3. Context Preservation
Tenant ID and actor context flow through:
```python
tenant_id = 'tenant-dev'
actor_id = 'user-123'
```

### 4. Error Handling
- Required steps must succeed
- Optional steps can fail without stopping chain
- Errors include step number and details

### 5. Optional Steps
```python
ChainStep(
    agent_id='optional_agent',
    capability='opt.cap',
    optional=True  # Failure doesn't stop chain
)
```

## Governance Alignment

Per G2.11 Target Model:

| Aspect | Implementation |
|--------|----------------|
| Resource Metadata | NOT stored on agents |
| Identity Context | Runtime (actor_id param) |
| Governance | Process-level |
| Environment | Not defined in chain |

## Testing

Run tests with:
```bash
python3 tests/test_processing_chain.py
```

Test coverage:
- ✅ Single step execution
- ✅ Multi-step (A→B→C) propagation
- ✅ Context preservation
- ✅ Error handling
- ✅ Optional steps

## Future Enhancements

1. **Orchestration**
   - Conditional steps (if/else branching)
   - Parallel execution
   - Timeouts per step

2. **Integration**
   - Orders adapter for external processing
   - Step-level validation
   - Idempotent replay

3. **Observability**
   - Per-step metrics
   - Failure analysis
   - Performance tracing

## Files

| File | Purpose |
|------|---------|
| `agents/ecosystem/chain.py` | Core implementation |
| `tests/test_processing_chain.py` | Test suite |
| `docs/ecosystem/DEVELOPMENT_ORDERS_ADAPTER.md` | Adapter pattern |

## Git History

```
fef3296 test: add processing chain execution tests (S2.14)
ff73f66 feat: add Development Orders Adapter
...
```