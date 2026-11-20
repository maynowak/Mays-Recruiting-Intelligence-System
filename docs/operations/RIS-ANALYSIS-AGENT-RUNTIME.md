# Dedicated Analysis Compute (RIS-ANALYSIS-AGENT-RUNTIME-11)

**Status:** prepared, Terraform-gated by `enable_analysis_runtime`; **not
applied**. No public endpoint, no shared IAM change, no catalog/entitlement
grant.

## Compute

| Item | Value |
|---|---|
| Function | `ris-dev2-dev-analysis` |
| Handler | `analysis_runner.handler` (own bundle) |
| Runtime / memory / timeout | `python3.14` / 512 MB / 60 s |
| Role | `ris-dev2-dev-analysis` (dedicated) |
| Parser backend | `RIS_PARSER_MODE=lambda` → `ris-dev2-dev-analysis-parser` |
| Trigger | internal `lambda:InvokeFunction` with a WorkItem; also accepts the SQS record shape |
| Public surface | none |

The function runs the **existing** runtime path:
`WorkItem` → AgentBody (analysis agent only) → `AnalysisOrchestrator` → parser
Lambda; results and idempotency are handled by `agents.runtime.pipeline`
(WorkItems table, conditional writes, attempt semantics). It does not create a
queue, a second routing system or a result transport.

## Agent factory integration

`lambda/analysis_runner.py` builds:

1. `AgentRegistry` + `AgentBody`,
2. `AnalysisAgent` with an explicit config and `AnalysisOrchestrator`
   (`NodeParser(mode="lambda")`, `RequestCvResolver`, `S3JobStore`),
3. `register_analysis_agent(..., agent=agent)`.

`process_record(..., analysis_agent=agent)` forwards the configured agent into
`ensure_reference_agent`, so the pipeline does not replace it with the default
analysis agent. The analysis agent reads identity from the original nested
WorkItem (tenant, user, partner application, issuer) and never from the request
body.

## Internal partner isolation

- Caller partner: `ris-internal` (config), verified at runtime.
- Executor identity: `ris-internal-analysis` / `analysis-agent`.
- CV owner: the authenticated user + tenant; owner/tenant re-checked at the
  CV record.
- Execution authorization: the existing DynamoDB entitlement re-check
  (`agentId=analysis-agent`) must pass **and** the agent's capability/consent
  checks must pass.
- Cross-tenant, cross-partner, missing entitlement and missing consent fail
  closed (`cv_access_denied`, `partner_mismatch`, `entitlement_denied`,
  `consent_required`, `consent_notice_not_approved`).

## Configuration (defaults deny)

| Env | Default | Meaning |
|---|---|---|
| `RIS_PARSER_MODE` | `lambda` | parser transport |
| `RIS_PARSER_FUNCTION` | parser name | internal parser |
| `RIS_PARSER_TIMEOUT_SECONDS` | `15` | client timeout, no retries |
| `ANALYSIS_ENTITLEMENTS` | **empty** | no capabilities until set |
| `ANALYSIS_CONSENT` | **false** | no consent until operator sets |
| `ANALYSIS_NOTICE_APPROVED` | **false** | notice stays DRAFT |
| `ANALYSIS_CALLER_PARTNER_ID` | `ris-internal` | internal caller |
| `WORK_ITEMS_TABLE`, `ENTITLEMENTS_TABLE`, `PARTNER_PROFILE_TABLE` | from root | existing contracts |
| `DOCUMENTS_BUCKET`, `ANALYSIS_JOBS_BUCKET` | from root | CV + temporary jobs |

A deployment without explicit operator values performs no analysis.

## IAM

The dedicated role gets, in addition to the existing documents read, jobs RW
and logs:

- WorkItems: `GetItem`, `PutItem`, `UpdateItem`, `Query` (table + index),
- Entitlements: `GetItem`, `Query` (table + index),
- Partner profiles: `GetItem`, `Query` (table + index).

No SQS, Secrets Manager, Orders queue or shared policy is touched. Parser
invoke remains scoped to the parser function.

## Bundle and timeout

`python lambda/build_zip.py --bundle analysis` builds
`terraform/analysis-lambda.zip` (analysis runner + `agents/` + `jobsearch/`).
It is separate from the shared agent bundle, so the shared worker function's
code hash does **not** change.

- Analysis Lambda timeout 60 s (validation ≥ 15 s), parser 15 s.
- Adapter: 15 s connect/read timeout, zero retries, 100 000-char payload.
- Inline job text is limited to 32 000 chars at the request contract.
- Timeout drill: Node CLI sleeper with a 1 s timeout and an SDK read-timeout
  both map to `ParserUnavailable`; the deployed Lambda's own 15 s timeout is
  configuration-pinned, not exercised (no controllable slow path).

## Logging

The runner logs only the failure type; it never logs WorkItem bodies, CV
bytes, job text or parser payloads. The parser Lambda logs only
START/END/REPORT (verified in CANARY-10B).

## Tests

- `tests/test_analysis_runner.py` — config defaults deny, event shapes,
  permanent vs retryable failures, no body in logs, runtime wiring.
- `tests/test_analysis_runner_pipeline.py` — real `process_record`: authorized
  completion and persistence, idempotent replay (no re-execution), PDF path
  without persisted bytes, entitlement/consent/cross-tenant denials, SQS shape.
- `tests/test_parser_timeouts.py` — CLI timeout, SDK read timeout, budgets.
- `tests/test_analysis_runtime_terraform.py` — gate, handler, runtime, default
  deny, least-privilege data policy, dedicated bundle.

## Plan (not applied)

With `enable_analysis_runtime=true` the read-only plan is **2 add / 0 change /
0 destroy**: the analysis Lambda and its dedicated data policy (`analysis` role
policy). Parser and base runtime resources are already in state from
CANARY-10B. With the flag off, the baseline is unchanged.
