# Analysis Agent Contracts

## Composite execution

- One outer `agentOrder`/WorkItem (`agentId=analysis-agent`,
  `capability=analysis.run`, work type `agent_analysis_agent`).
- External entitlements: `parse.cv`, `parse.job`, `compare.tags` and optional
  `analyze.job` (for `ats.tags`).
- Internal parser capabilities: `parse.cv`, `parse.job`, `parse.ats`. These are
  technical subfunctions of the same WorkItem, not separate agents or orders.
- No per-offer queue, no second order state machine and no analysis-owned
  result contract. ORDER_DISPATCH, WorkItem, ORDER_RESULT and ORDER_FAILED stay
  in the shared transport/runtime.

## Request 1.0

- `schemaVersion` (`1.0`), `requestedResults`, `input.cv|job|profile`, optional
  `idempotencyKey`.
- `requestedResults`: `cv.tags`, `job.tags`, `ats.tags`, `comparison`.
- `input.cv`: `cvId` (owner PDF) or `structured`.
- `input.job`: inline `text` (max 32,000 chars) or temporary `jobRef`.
- `input.profile`: optional ATS input when no CV is supplied.

## Results

- `CVParserResultBody` 1.0
- `JobParserResultBody` 1.0
- `ATSAnalysisResultBody` 2.0 (additive `atsTags`; optional)
- `ComparisonResultBody` 1.0

The ATS projection is the shared parser's deterministic view, not a second ATS
product. The ATS score is exposed separately (`provenance.atsScore`) and is
never mixed into comparison coverage.

## Order / WorkItem / result semantics

- A Mays-Orders call is **one** order. Internal parser calls do not create
  orders and are not billed separately.
- The order owner is the authenticated human user; the analysis agent is the
  executor. It does not own or mutate the order.
- `ORDER_RESULT`/`ORDER_FAILED` are emitted by the shared runtime for
  order-linked WorkItems.
- Result retrieval stays with Mays-Orders (`GET /orders/{orderId}` ->
  `processing.status/result/error`); the RIS orders-reader provides the same
  owner-scoped view.
- Automatic parent-agent resume after a result is not part of this contract.

Canonical contract and examples:
`docs/reports/RIS-AGENT-ANALYSIS-ORCHESTRATION-04.md`.
