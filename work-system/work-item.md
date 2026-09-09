# WorkItem System

## Overview

The WorkItem system provides a standardized, reliable mechanism for asynchronous job processing in Ground Zero. It implements exactly-once semantics despite at-least-once message delivery from SQS.

## WorkItem Schema

### Primary Structure

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
  "status": "string",
  "attempt": 0,
  "claimedBy": null,
  "claimedAt": null,
  "completedAt": null,
  "resultRef": null,
  "error": null
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| workId | UUID | Yes | Unique work item identifier |
| type | string | Yes | Work item type (e.g., "cv.process") |
| tenantId | string | Yes | Tenant identifier for multi-tenancy |
| entityId | string | Yes | Related entity ID (e.g., candidate ID) |
| requestedBy | string | Yes | User or service that requested |
| idempotencyKey | string | Yes | Stable key for deduplication |
| payloadVersion | string | Yes | Version of payload schema |
| agentVersion | string | Yes | Version of agent that will process |
| status | string | Yes | Current status (see states) |
| attempt | int | Yes | Retry attempt number |
| claimedBy | string | No | Worker identifier that claimed |
| claimedAt | timestamp | No | When work was claimed |
| completedAt | timestamp | No | When work completed |
| resultRef | string | No | Reference to result storage |
| error | object | No | Error details if failed |

## Status States

### State Machine

```
CREATED ──► QUEUED ──► RUNNING ──► COMPLETED
                    │
                    ├── FAILED ──► RETRY ──► QUEUE
                    │              │
                    │              └───► DEAD_LETTER (max retries)
                    │
                    ├── CANCELLED
                    │
                    └── EXPIRED (TTL reached)
```

### State Definitions

| State | Description | Next States |
|-------|-------------|-------------|
| CREATED | Work item created | QUEUED |
| QUEUE | Waiting in SQS | RUNNING |
| RUNNING | Being processed | COMPLETED, FAILED |
| COMPLETED | Successfully finished | - |
| FAILED | Processing error | RETRY, DEAD_LETTER |
| RETRY | Scheduled for retry | QUEUED, DEAD_LETTER |
| DEAD_LETTER | Max retries exceeded | - |
| CANCELLED | Manually cancelled | - |
| EXPIRED | TTL reached | - |

## Idempotency Strategy

### Goal

Achieve exactly-once business outcomes despite at-least-once message delivery.

### Mechanisms

1. **Stable Idempotency Keys**: Consistent keys for identical operations
2. **Work Registry**: Track work status in DynamoDB
3. **Atomic Claims**: Conditional writes for ownership
4. **Result Checks**: Verify completion before reprocessing

### Implementation

```python
def process_work_item(work_item):
    # Check if already completed (idempotency guard)
    existing = dynamodb.get_item(
        TableName=TABLE_NAME,
        Key={'workId': {'S': work_item['workId']}}
    )
    
    if existing.get('status') == 'COMPLETED':
        return existing
    
    # Atomic claim
    try:
        dynamodb.update_item(
            TableName=TABLE_NAME,
            Key={'workId': {'S': work_item['workId']}},
            UpdateExpression='SET #status = :running, claimedBy = :worker, claimedAt = :time',
            ConditionExpression='attribute_not_exists(claimedBy) OR #status = :created',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':running': 'RUNNING',
                ':created': 'CREATED',
                ':worker': WORKER_ID,
                ':time': datetime.utcnow().isoformat()
            }
        )
    except dynamodb.exceptions.ConditionalCheckFailedException:
        # Already claimed by another worker
        return None
    
    # Process and store result
    result = do_work(work_item)
    store_result(work_item['workId'], result)
    
    # Mark completed
    update_work_status(work_item['workId'], 'COMPLETED', result)
```

## Retry Strategy

### Exponential Backoff

```
Attempt N: delay = base × (2^(N-1)) + jitter
```

Where:
- Base delay: 1 second
- Jitter: Random value 0-100ms

### Max Attempts

- Default: 3 attempts
- Configurable per work type
- After max, message goes to DLQ

### Dead Letter Queue (DLQ)

```
Primary Queue
    │
    └── Max retries exceeded
            ↓
       DLQ
            │
            └── Manual inspection
```

DLQ handlers should:
1. Log failed items
2. Alert operators
3. Provide reprocessing capability
4. Archive for audit

## DynamoDB Schema

### Work Items Table

```terraform
resource "aws_dynamodb_table" "work_items" {
  name         = "${var.project_name}-work-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "workId"

  attribute {
    name = "workId"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }
}
```

### Global Secondary Index

For querying by status:

```terraform
resource "aws_dynamodb_table" "work_items" {
  # ...

  global_secondary_index {
    name               = "StatusIndex"
    hash_key           = "tenantId"
    range_key          = "status"
    projection_type    = "ALL"
  }
}
```

### Access Patterns

| Pattern | PK | SK |
|---------|----|----|
| Get by ID | workId | - |
| List by tenant/status | tenantId | status |
| History query | tenantId | createdAt |

## SQS Configuration

### Visibility Timeout

- Default: 300 seconds
- Should be 2x expected processing time
- Configurable per queue

### Queue Attributes

```terraform
resource "aws_sqs_queue" "work_queue" {
  name                       = "${var.project_name}-${agent}-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600  # 14 days
  max_message_size           = 256000   # 256KB
  delay_seconds              = 0
  receive_wait_time_seconds  = 20       # Long polling
  
  redrive_allow_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}
```

## Lambda Event Source Mapping

```terraform
resource "aws_lambda_event_source_mapping" "work_processor" {
  event_source_arn  = aws_sqs_queue.work_queue.arn
  function_name     = aws_lambda_function.agent.arn
  batch_size        = 5
  maximum_batching_window_in_seconds = 5
}
```

## Monitoring

### CloudWatch Metrics

- `ApproximateNumberOfMessagesVisible` - Queue depth
- `NumberOfMessagesSent` - Throughput
- `NumberOfMessagesDeleted` - Processing rate
- Lambda `Duration` - Processing time
- Lambda `Errors` - Error count
- Lambda `Throttles` - Concurrency limit

### Alarms

| Metric | Threshold | Action |
|--------|-----------|--------|
| Queue Depth | > 1000 | Alert team |
| Error Rate | > 5% | Page on-call |
| Duration | > 60s | Investigate |
| Dead Letters | > 0 | Investigate |

## Testing Idempotency

### Test Cases

1. **Duplicate Message**: Same message delivered twice
   - Expected: Business outcome happens once

2. **Worker Restart**: Worker crashes mid-processing
   - Expected: Work can be retried safely

3. **Partial Failures**: Partial state changes
   - Expected: Atomic commit with transactions

4. **Timeout Failures**: Processing takes too long
   - Expected: Work returns to queue, can be reprocessed

## Best Practices

1. **Always check idempotency** before processing
2. **Use DynamoDB transactions** for atomic updates
3. **Log all state transitions** for debugging
4. **Implement circuit breakers** for external services
5. **Use system time** for timestamps (avoid client time)
6. **Encrypt sensitive data** at rest and in transit
7. **Version work items** for schema evolution