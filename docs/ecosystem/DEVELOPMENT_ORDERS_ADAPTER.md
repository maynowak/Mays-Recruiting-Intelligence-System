# Development Orders Adapter — S2.13

## Purpose

The Development Orders Adapter provides a controlled, local-order processing system
for Agent development while May's Orders is being built.

## Architecture

```
Agent
  ↓
Invocation Contract
  ↓
OrdersPort (Interface)
  ↓
DevelopmentOrdersAdapter  (development)
  ↓
Result
```

Later:
```
Agent
  ↓
Invocation Contract  
  ↓
OrdersPort (Interface)
  ↓
RealMaysOrdersAdapter  (production)
  ↓
May's Orders
```

## Key Principles

### 1. No Architecture Changes

The adapter does NOT:
- Create new queues
- Create new workers
- Implement new lifecycle management
- Replace May's Orders
- Require AWS infrastructure

### 2. Deterministic

- Same input → Same output
- Configurable for testing
- No external network calls

### 3. Extensible

The `OrdersPort` interface allows future `RealMaysOrdersAdapter` to implement
the same contract.

## Contract

### OrdersPort

```python
class OrdersPort:
    @property
    def port_id(self) -> str:
        """Unique identifier for this port."""
    
    def submit_order(
        self,
        work_item: Dict[str, Any],
        capability: str,
        payload: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> OrderResult:
        """Submit processing request."""
    
    def get_order_status(self, order_id: str) -> Optional[OrderResult]:
        """Get order status."""
    
    def can_handle(self, capability: str) -> bool:
        """Check capability support."""
```

### OrderResult

```python
@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    result_type: Optional[OrdersResultType] = None
    reason: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
```

## Integration

### With Agent Body

```python
from agents.orders import DevelopmentOrdersAdapter

adapter = DevelopmentOrdersAdapter()

# In agent invocation
result = adapter.submit_order(
    work_item=work_item,
    capability="reference.echo",
    payload=payload,
    tenant_id=tenant_id,
    actor_id=actor_id,  # from JWT context
    idempotency_key=work_item.get('idempotencyKey')
)
```

### With Invocation

```python
from agents.agent_body.invocation import InvocationContract

contract = InvocationContract(
    target_agent_id="agent-b",
    capability="some.capability",
    parent_work_id="parent-123",
    tenant_id="tenant-x"
)

# Adapter can process the invocation
result = adapter.submit_order(
    work_item=contract.to_work_item(),
    capability=contract.capability,
    tenant_id=contract.tenant_id,
    # actor from JWT context
)
```

## Configuration

Development adapter supports:

| Parameter | Purpose | Default |
|-----------|---------|---------|
| `auto_approve` | Auto-approve orders | `True` |
| `simulate_delay` | Test timing | `0.0` |
| `simulate_failure_rate` | Test failures | `0.0` |

## Migration to Production

When May's Orders is ready:

1. Create `RealMaysOrdersAdapter` implementing `OrdersPort`
2. Switch configuration from Development to Real adapter
3. No agent code changes required

## Files

- `agents/orders/__init__.py` — Package exports
- `agents/orders/adapter.py` — OrdersPort interface
- `agents/orders/development.py` — Development implementation

## Testing

Run the adapter verification:

```bash
python3 -c "from agents.orders import DevelopmentOrdersAdapter; ..."
```