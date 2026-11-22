# Agent Package Template

Copy this directory to `agent-installations/<agent-id>/` and replace every
`<placeholder>`. Then:

1. Complete `manifest.yaml` (all required keys).
2. Describe contracts in `contracts/README.md`.
3. Add local and live test commands in `tests/README.md`.
4. Fill `risks.md`, `operations.md`, `handoff.md`.
5. Run `python -m installer.agent_install --agent <agent-id> --stage validate
   --status-file <path>` (repeat for resume).
6. Reuse the existing dispatch/result transport; add no queue unless the
   manifest proves it is required.
7. Do not enable the agent automatically. Activation is a separate approval.

The `_template` directory is excluded from discovery and is never a deployable
agent package.

## Composite agent option

Use `offers.yaml` when one agent exposes multiple offers. The package stays one
agent with one capability/workType and one outer order/WorkItem.

1. Set `agent.composite: true`, `agent.offers: offers.yaml`,
   `agent.internalCapabilities` and `agent.externalEntitlements` in
   `manifest.yaml`.
2. Fill `offers.yaml`: offer id, requested results, input, external
   entitlements, internal parser capabilities and result bodies.
3. Keep internal parser calls as technical subfunctions. They create no order,
   no queue and no separate billing.
4. Reuse registry/AgentBody/WorkItems, the shared work queue/worker and
   `ORDER_RESULT`/`ORDER_FAILED`. Do not add a second order state machine.
5. Prove server-side identity, APIProfile, entitlement, consent and
   owner/tenant fences. Fail closed.
6. Keep offers `DRAFT`, `activation: false`, catalog `ABSENT` and entitlements
   `PENDING_APPROVAL` until the separate approvals exist.
7. Do not document automatic parent-agent resume unless it is implemented and
   tested; result retrieval is the existing order view.

Reference: `agent-installations/analysis-agent/` (`analysis.run`,
`agent_analysis_agent`, offers `analysis.cv`, `analysis.job`, `analysis.match`).
