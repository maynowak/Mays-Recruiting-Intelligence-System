# Analysis Agent — Risks

- **Node runtime:** the Python Lambda has no node; live enablement PENDING.
- **Optional processing:** only requested parsers run; ATS-only does not run
  the job parser.
- **CV privacy:** CVs are resolved server-side; no bytes in WorkItems or logs.
- **Comparison:** deterministic, no AI, no provider cost; the ATS score stays
  separate from the comparison score.
- **Job storage:** opaque refs, 2h default, 4h maximum, 1 MiB.

## Stop conditions

- Missing parser CLI or node -> do not enable.
- Missing consent/entitlement -> fail closed.
- Expired jobRef or cross-tenant access -> fail closed.
- Any request to add a second parser engine -> stop and escalate.
