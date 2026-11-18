# Agent Installation Packages

Versioned installation contracts for RIS agents. A package is a reviewable
contract, not executable third-party software.

Layout per agent:

```
agent-installations/<agent-id>/
  manifest.yaml
  contracts/
  tests/
  risks.md
  operations.md
  handoff.md
```

`_template/` is the starting point for Agent Z and is excluded from discovery.
It is never a deployable package.

## Workflow

```
python -m installer.agent_install --root agent-installations
python -m installer.agent_install --agent <id> --stage validate --status-file <path>
```

Stages: DISCOVER → ANALYZE → COMPATIBILITY → RISK REVIEW → PACKAGE → VALIDATE →
PLAN → APPLY → E2E → HANDOFF. Status is idempotent and resumable; `APPLY`
refuses without `--execute --allow-apply --yes`.

Creating or validating a package never enables an agent and never changes
another agent.

## Live baselines

- `ats-agent` 1.0.0 — live E2E PASS on ris-dev2 (2026-11-18).
- `addition-agent` 1.0.0 — live E2E PASS on the shared transport (2026-11-18).

Both use the same dispatch/result transport; no per-agent queues.
