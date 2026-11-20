# Analysis Agent — Operations

- Capability `analysis.run`; work type `agent_analysis_agent`.
- Validates the versioned request, resolves CV/job inputs and runs only the
  requested parsers through the Node CLI boundary.
- Identity: tenant/user from the runtime; entitlements and consent injected by
  the service layer.
- Errors: contract violations are terminal `ValidationError`; parser runtime
  failures are retryable.
- No queue, table, Lambda or secret of its own; shared transport only.
