# Job Parser Agent — Risks

- **Runtime BLOCKER:** the Python Lambda has no `node`; the shared parser CLI
  cannot run there. Enablement is PENDING (Node Lambda/container or runtime
  switch). Until then the agent is LOCAL VERIFIED only.
- **Input handling:** job text is untrusted data. It is parsed locally, never
  sent to an AI provider by this agent, and never persisted by the agent.
- **Determinism:** required/preferred split uses the existing ATS `importance`
  heuristic (`high` = required); confidence is reported per field.
- **No second parser:** all parsing goes through the versioned jobsearch
  ATS/parser library. A divergent copy is a defect.
- **No events:** the agent registers no EventHook and cannot trigger follow-up
  work, cost or data transfer.
- **Size guard:** description is capped at 100000 characters; no title and no
  description is rejected.

## Stop conditions

- Missing parser CLI or node runtime -> do not enable; LOCAL only.
- Parser schema/version mismatch -> stop, do not add a fallback parser.
- Any request to add a second parser engine -> stop and escalate.
