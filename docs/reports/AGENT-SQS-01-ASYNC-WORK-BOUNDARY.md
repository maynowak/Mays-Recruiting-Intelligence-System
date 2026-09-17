# AGENT-SQS-01 — Asynchronous Work Boundary Architecture

## TASK

Investigate and document the async boundary between Agent Ecosystem and Work infrastructure.

---

## SUMMARY

**Answer: YES, the existing Ground Zero SQS/Worker infrastructure IS the correct async execution boundary.**

No new infrastructure needs to be built.

---

## EXISTING INFRASTRUCTURE

### SQS Queues

| Queue | Purpose |
|-------|---------|
| work-queue | Generic work items |
| cv-queue | CV agent work |
| ats-queue | ATS agent work |
| match-queue | Matching agent work |
| dlq | Dead letter queue |

### Lambda Worker

```python
# terraform/modules/lambda/main.tf:211-217
resource "aws_lambda_event_source_mapping" "sqs_mapping" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.agent.arn
  batch_size       = 5
}
```

### Worker Processing

```python
# lambda/handler.py:744-787
def _process_work_item(work_item: Dict[str, Any]) -> Dict[str, Any]:
    """Process a work item through the Agent Body pipeline."""
    # Calls AGENT_BODY.execute(work_item)
```

---

## WORK ITEM FIELDS

| Field | Source | Notes |
|-------|--------|-------|
| workId | Generated uuid | Required |
| type | Derived | Required |
| tenantId | From event/context | Required |
| idempotencyKey | Generated | Required |
| agentId | RoutingDecision | Filled by ExecutionEngine |
| capability | Envelope | Optional |
| payload | Envelope | Required |
| parentWorkId | Envelope.processing_id | Traceability |

---

## BOUNDARY DEFINITION

### Producer Boundary (ExecutionEngine → WorkItem)

```
RoutingDecision
      │
      ↓
ExecutionEngine (AGENT-EXEC-01)
      │
      ↓
InvocationContract
      │
      ↓
InvocationContract.to_work_item()
      │
      ↓
WorkItem Dict → (optional: SQS)
```

### Consumer Boundary (SQS → Worker → Agent)

```
SQS
      │
      ↓
Event Source Mapping
      │
      ↓
Worker Lambda (_process_work_item)
      │
      ↓
AGENT_BODY.execute(work_item)
      │
      ↓
Agent
```

---

## NOCHT NOTWENDIG

- Keine neue Queue
- Kein neuer Worker
- Keine SQS-Änderung
- Keine Terraform-Änderung

---

## FUTURE WORK: AGENT-SQS-02

Add optional SQS dispatch from ExecutionEngine:

```python
class ExecutionEngine:
    def execute_and_queue(
        self,
        decision,
        envelope,
        sqs_client=None,
        queue_url=None
    ) -> dict:
        """Execute and optionally async via SQS."""
        work_item = self.create_work_item(decision, envelope)
        
        if sqs_client and queue_url:
            sqs_client.send_message(QueueUrl=queue_url, MessageBody=...)
            return {'status': 'queued', 'workItem': work_item}
        
        return self.execute_from_decision(decision, envelope)
```

---

## TESTS

All existing tests pass. No new AWS tests needed.

---

## ACCEPTANCE

| Criteria | Status |
|----------|--------|
| Worker is generic | ✅ |
| SQS → Worker → AgentBody | ✅ |
| WorkItem fields complete | ✅ |
| Idempotency supported | ✅ |
| No duplicate infrastructure | ✅ |
| No AWS changes | ✅ |

✅ **GREEN**

---

## NEXT STEPS

1. Agent-SQS-02: Add optional SQS dispatch from ExecutionEngine
2. Integration testing with real Lambda execution
3. Monitor and review in production

