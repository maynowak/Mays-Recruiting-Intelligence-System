# Analysis Agent — Operations

## Execution model

- One composite agent: `agentId=analysis-agent`, capability `analysis.run`,
  work type `agent_analysis_agent`.
- Three DRAFT offers (`analysis.cv`, `analysis.job`, `analysis.match`) share one
  outer WorkItem and, when ordered through Mays-Orders, one outer order.
- Internal `parse.cv`, `parse.job` and `parse.ats` calls are technical
  subfunctions. They are not separately orderable agents, do not create
  additional orders and are not billed separately.
- Runtime reuse: registry/Discovery/Eligibility, AgentBody, WorkItems, dispatch
  ingress, shared work queue, shared worker and result transport. No per-agent
  queue, table, order state machine or result contract.

## Request and result

- Validate the versioned request (`schemaVersion` 1.0) and run only the
  requested parsers.
- Resolve CVs server-side; structured CV data skips the parser. Job input is
  inline text (max 32,000 chars) or a temporary `jobRef` (2 h default, 4 h max,
  1 MiB).
- Result bodies: `CVParserResultBody` 1.0, `JobParserResultBody` 1.0,
  `ATSAnalysisResultBody` 2.0 (optional/additive) and
  `ComparisonResultBody` 1.0.
- Identity: tenant/user/partner/issuer from the verified runtime context;
  entitlements and consent are injected by the service layer. Fail closed when
  they are missing.

## Error and lifecycle semantics

- Contract violations are terminal `ValidationError`; parser runtime failures
  are retryable.
- For order-linked work, the shared pipeline emits `ORDER_RESULT` on success
  and terminal `ORDER_FAILED` for missing identity binding, terminal
  entitlement denial or permanent `ValidationError`. Retryable failures do not
  emit `ORDER_FAILED`.
- SQS DLQ exhaustion still cannot emit `ORDER_FAILED`; this is an open
  ecosystem item, not an analysis feature.
- The agent has no order state and never mutates an order.

## Result retrieval and resume

- Result retrieval is owned by Mays-Orders:
  `GET /orders/{orderId}` returns `processing.status`, `processing.result` and
  a sanitised `processing.error`. The RIS orders-reader exposes the same
  owner-scoped view.
- Polling the order is the supported path. Email/webhook wake-up and automatic
  resume of a parent agent after `ORDER_RESULT`/`ORDER_FAILED` are **not
  implemented**; they are a separate platform track.

## Runtime

- Parser adapter: `agents/parsers/node_adapter.py` (local CLI) or
  `agents/parsers/lambda_adapter.py` (dedicated Node Lambda).
- Approved 16C2 Apply A installed and verified the Python Analysis Lambda,
  dedicated Node parser Lambda, scoped IAM and shared-worker bindings
  in ris-dev2 (4 add / 3 change / 0 destroy, state 69). The Terraform
  variable still defaults to false for new installations; current
  Analysis runtime remains deny-by-default until separate B/C and
  product gates. Python Analysis Lambda contains no Node runtime;
  it invokes the dedicated parser Lambda.
- No public endpoint and no shared agent-transport policy.
