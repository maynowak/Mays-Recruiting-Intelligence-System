# CV Parser Agent — Risks

- **Runtime BLOCKER:** the Python Lambda has no `node`; the shared parser CLI
  cannot run there. Enablement is PENDING (Node Lambda/container or runtime
  switch). Until then the agent is LOCAL VERIFIED only.
- **Input handling:** CV text is untrusted data. It is parsed locally, never
  sent to an AI provider by this agent, and never persisted by the agent.
- **PII:** the parsed result can contain name/email/phone. Callers own storage
  and retention; the agent keeps no state.
- **Determinism:** rule-based extraction; confidence is per field and may be
  `low` for free-form experience/education lines.
- **No second parser:** all parsing goes through the versioned jobsearch
  library. A divergent copy is a defect.
- **No events:** the agent registers no EventHook and cannot trigger follow-up
  work, cost or data transfer.
- **Size guard:** 20..100000 characters; larger input is rejected before the
  adapter.

## Stop conditions

- Missing parser CLI or node runtime -> do not enable; LOCAL only.
- Parser schema/version mismatch -> stop, do not add a fallback parser.
- Any request to add a second parser engine -> stop and escalate.
