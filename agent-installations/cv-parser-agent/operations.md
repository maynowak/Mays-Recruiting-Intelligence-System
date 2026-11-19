# CV Parser Agent — Operations

- **Capability:** `parse.cv`; work type `agent_cv_parser_agent`.
- **Runtime:** shared worker/dispatch transport; no per-agent queue, table,
  Lambda or secret.
- **Adapter:** `agents/parsers/node_adapter.py`; requires `RIS_PARSER_CLI`
  (path to `scripts/ris-parser-cli.mjs` in the jobsearch deployment) and a
  `node` binary. If either is missing the agent fails with
  `ParserUnavailable` (retryable), not a validation error.
- **Input:** `payload.text`, 20..100000 characters.
- **Output:** `data` (name/email/phone/skills/education/experience/
  experienceLevel/targetRoles/location), `confidence`, `parserVersion`,
  `stableId`.
- **Failure:** invalid CV input → `ValidationError` (terminal);
  runtime/timeout → `ParserUnavailable` (FAILED, retried).
- **Deactivation:** withdraw the agent-scoped entitlement; the reader returns
  403 and the worker denies execution. No catalog row exists.
- **Monitoring:** same worker/queue/DLQ path as other agents; no extra alarms.
- **VERIFY:** one canary WorkItem with synthetic text; expect `success:true`
  and a stable `stableId` across two runs.
