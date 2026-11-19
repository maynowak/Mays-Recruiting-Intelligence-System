# Agent Parsers — CV and Job (RIS-JM-AGENT-STANDARDIZATION-01)

Three standardized agents now share one parser implementation:

| Agent | Capability | Work type | Parser code |
|---|---|---|---|
| `ats-agent` | `analyze.job` | `ats_process` | ATS analysis (unchanged) |
| `cv-parser-agent` | `parse.cv` | `agent_cv_parser_agent` | shared `parse.cv` |
| `job-parser-agent` | `parse.job` | `agent_job_parser_agent` | shared `parse.job` |

## Reuse map (no second platform, no second parser)

| Concern | Existing component | Change |
|---|---|---|
| Body/routing | `agents/runtime/pipeline.py` + `AgentBody` | two `register_*` calls |
| Registry/discovery/eligibility | `agents/ecosystem/*` | descriptors only |
| WorkItem/idempotency/retry | `agents/runtime/pipeline.py` | unchanged |
| Transport | `agents/transport/*` | unchanged |
| Parser logic | `maynowak/mays-jobsearch: api/_lib/parsers/ris.mjs` v1.0.0 | new versioned library reusing `api/_lib/ats.mjs` |
| Cross-runtime call | `agents/parsers/node_adapter.py` | new, single boundary |
| Packages | `agent-installations/<id>/` | new packages |

## Gates

- Catalog: discovery / API only. Neither parser agent has a catalog row
  (`visibility: ABSENT`), so both are dispatch-only.
- Entitlement: reader admission, dispatch ingress and worker execution.
- The agents register no EventHook and emit no events. They cannot trigger
  follow-up orders, cost or data transfer.
- No new HTTP endpoint, no new queue, table, Lambda or secret.

## Contracts

`parse.cv`
: input `{text}` (20..100000 chars) → `data` with name/email/phone/skills/
  experienceLevel/targetRoles/location plus education/languages/experience/
  totalYears; per-field `confidence`; `stableId`.

`parse.job`
: input `{job:{title|descriptionPlain,...}}` → `data` with `stableId`,
  title/company/location, `requirements.required/preferred`, skills,
  experienceYears, metadata; per-field `confidence`.

Both envelopes: `schemaVersion 1.0`, `capability`, `parserVersion` (library
version), `data`, `confidence`.

## Runtime (PENDING)

The parser library is Node ESM. AWS Lambda Python 3.14 has no `node` binary.
Options, none implemented/deployed here:

1. Node Lambda/container invoked internally from the Python agent (recommended).
2. Switch both agents to a Node runtime.
3. Vendor a statically linked node into the bundle.

Until one is approved: **LOCAL VERIFIED only, do not enable in ris-dev2**.
The adapter fails closed with `ParserUnavailable` when `RIS_PARSER_CLI` or
`node` is missing; it never falls back to a second parser.

## Error and retry behaviour

- Invalid payload or parser rejection (`ValidationError`) → terminal.
- Missing runtime / timeout / invalid envelope (`ParserUnavailable`) → FAILED
  and retried by the existing SQS semantics.
- Determinism: identical input yields an identical `stableId`; the parser has
  no network or AI call.

## Security

- CV/job text is untrusted data, parsed locally, never persisted by the agent.
- CV output may contain PII (name/email/phone); the caller owns retention.
- No secrets are read; the CLI receives only the payload.
- Size limits prevent unbounded input; the adapter rejects before spawning.

## Tests

`python -m pytest tests/test_parser_agents.py -q` — 16 tests, including a real
jobsearch CLI round trip when the CLI is present.

## Pre-existing defect fixed in jobsearch

`extractExperience` and the education regex in `api/_lib/ats.mjs` lacked the
`g` flag inside `while (exec())` loops, which hangs on text containing "years"
or a degree word. Both patterns now use `g`.
