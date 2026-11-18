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
