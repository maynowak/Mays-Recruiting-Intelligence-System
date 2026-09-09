# Agent Contract

## Purpose

This document defines the standardized interface for all agents in the Ground Zero platform. Agents must follow this contract to ensure compatibility with the platform runtime.

## Agent Interface

### Required Functions

Every agent must implement the following interface:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class AgentContract(ABC):
    @abstractmethod
    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a work item and return the result.
        
        Args:
            work_item: WorkItem dictionary containing:
                - work_id: UUID
                - type: Work item type
                - tenant_id: Tenant identifier
                - payload: Work-specific data
                
        Returns:
            Result dictionary containing:
                - success: bool
                - data: Optional result data
                - error: Optional error message
        """
        pass
    
    @abstractmethod
    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        """
        Validate a work item before processing.
        
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    def get_status(self, work_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Get the status of a work item.
        
        Returns:
            Status dictionary
        """
        pass
```

### WorkItem Schema

```json
{
  "workId": "uuid-v4",
  "type": "string",
  "tenantId": "string",
  "entityId": "string",
  "requestedBy": "string",
  "idempotencyKey": "string",
  "payloadVersion": "string",
  "agentVersion": "string",
  "payload": {},
  "status": "CREATED|QUEUED|RUNNING|COMPLETED|FAILED|RETRY|DEAD_LETTER|CANCELLED|EXPIRED",
  "attempt": 0,
  "claimedBy": null,
  "claimedAt": null,
  "completedAt": null,
  "resultRef": null,
  "error": null
}
```

### Result Schema

```json
{
  "success": true,
  "data": {},
  "metrics": {
    "durationMs": 100,
    "workId": "uuid",
    "agentVersion": "v1.0.0"
  },
  "error": null
}
```

## Agent Registration

### Module Discovery

Agents are discovered by:

1. **Directory Convention**: `agents/{agent-name}/`
2. **Module Registration**: `registered_agents` list in `agents/__init__.py`
3. **Configuration**: Agent name maps to queue name and handler

### Required Files

```
agents/
├── __init__.py           # Agent registry
├── base.py               # Base class for agents
├── cv_agent/
│   ├── __init__.py
│   ├── handler.py        # Main handler
│   ├── service.py        # Business logic
│   └── model.py          # Data models
├── ats_agent/
│   └── ...
└── match_agent/
    └── ...
```

## API Contract

### Standard Endpoints

```
POST /api/v1/{agent-name}/work
  - Submit new work
  - Returns: { workId }

GET /api/v1/{agent-name}/work/{workId}
  - Get work status
  - Returns: { workItem }

GET /api/v1/{agent-name}/work
  - List work items (paginated)
  - Query params: status, limit, offset
  - Returns: { works: [], total }
```

### Request/Response Schema

**Submit Work:**
```json
// Request
{
  "type": "string",
  "entityId": "string",
  "payload": {}
}

// Response
{
  "workId": "uuid",
  "status": "QUEUED"
}
```

## Lambda Handler Template

```python
import json
from typing import Dict, Any

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Standard Lambda handler for agents."""
    try:
        # Parse SQS event
        for record in event.get('Records', []):
            body = json.loads(record['body'])
            work_item = body  # Or decode from SQS message attributes
            
            # Process work
            result = agent.process_work(work_item)
            
            # Store result
            if result.get('success'):
                store_result(work_item['workId'], result)
                update_work_status(work_item['workId'], 'COMPLETED')
            else:
                handle_error(work_item, result.get('error'))
        
        return {'statusCode': 200, 'body': json.dumps({'processed': len(event['Records'])})}
    
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
```

## Error Handling

### Standard Error Codes

| Code | Description | Action |
|------|-------------|--------|
| VALIDATION_ERROR | Work item invalid | Reject, don't retry |
| NOT_FOUND | Resource not found | Retry with backoff |
| RATE_LIMITED | Rate limit exceeded | Retry with backoff |
| INTERNAL_ERROR | System error | Retry with backoff |
| PERMISSION_DENIED | Access denied | Don't retry |

### Retry Strategy

- Max attempts: 3
- Backoff: Exponential (1s, 2s, 4s)
- Jitter: Add random factor

## Testing Requirements

### Unit Tests

- Test `process_work()` with mock work items
- Test `validate_work()` with valid/invalid inputs
- Test error handling paths

### Integration Tests

- Test with actual DynamoDB/S3
- Test idempotency with duplicate requests
- Test tenant isolation

### Test Structure

```
agents/{agent-name}/
├── __tests__/
│   ├── test_handler.py
│   ├── test_service.py
│   └── test_integration.py
```