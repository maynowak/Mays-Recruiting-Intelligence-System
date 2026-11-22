# Job Parser Agent — Operations

- **Capability:** `parse.job`; work type `agent_job_parser_agent`.
- **Runtime:** shared worker/dispatch transport; no per-agent queue, table,
  Lambda or secret.
- **Adapter:** `agents/parsers/node_adapter.py`; requires `RIS_PARSER_CLI`
  (path to `scripts/ris-parser-cli.mjs`) and a `node` binary. A missing
  runtime yields `ParserUnavailable` (retryable), not a validation error.
- **Input:** `payload.job` with `title` or `descriptionPlain`; description
  max 100000 characters.
- **Output:** `stableId`, title/company/location, required/preferred
  requirements, skills, experienceYears, metadata, `confidence`.
- **Failure:** invalid job input → `ValidationError` (terminal);
  runtime/timeout → `ParserUnavailable` (FAILED, retried).
- **Deactivation:** withdraw the agent-scoped entitlement. No catalog row
  exists.
- **VERIFY:** one canary WorkItem with a synthetic posting; expect
  `success:true` and an identical `stableId` across two runs.
