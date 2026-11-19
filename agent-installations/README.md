# Agent Installation Packages

Versioned installation and lifecycle contracts for RIS agents. A package is a
reviewable contract, not executable third-party software.

## Layout per agent

```
agent-installations/<agent-id>/
  manifest.yaml          # identity, capability, source pin, contract versions
  lifecycle.yaml         # discovery, shared/exclusive resources, bindings,
                         # uninstall and retention rules, purge boundaries
  contracts/             # wire contracts owned by this agent
  tests/                 # package-level tests
  risks.md
  operations.md
  handoff.md
  uninstall.md           # two-lever procedure, drain, retention, idempotency
  partner-bindings.md    # binding matrix, P1/P2/P3, external PENDING items
  retention.md           # per-artifact retention and purge boundaries
```

`_template/` is the starting point for a new agent. It contains **all** of the
files above and is excluded from discovery. It is never a deployable package;
the installer rejects template status and placeholder pins (`<...>`).

## Install stages (contract validation only)

```
python -m installer.agent_install --root agent-installations
python -m installer.agent_install --agent <id> --stage validate --status-file <path>
```

Stages: DISCOVER → ANALYZE → COMPATIBILITY → RISK REVIEW → PACKAGE → VALIDATE →
PLAN → APPLY → E2E → HANDOFF. Status is idempotent and resumable; `APPLY`
refuses without `--execute --allow-apply --yes`. `APPLY` records `executed:
false` — it is an approval record, not a Terraform run.

## Lifecycle actions (local state, no AWS)

```
python -m installer.agent_lifecycle --agent <id> --action <action> \
  --inventory <inventory.json> --state-file <state.json> \
  --audit-log <audit.jsonl> [--execute] [--actor <id>] [--approval <ref>] \
  [--reason "<text>"] [--impact-report <path>]
```

Actions: INSTALL, UPDATE, DISABLE, ENABLE, DETACH_PARTNER, UNINSTALL, PURGE,
STATUS, VERIFY. Every action has dry-run, impact, dependency check,
idempotency, audit and a result manifest.

Rules:

- DISABLE must withdraw the agent-scoped entitlement; catalog status alone does
  not stop the worker or the order reader.
- DETACH_PARTNER removes only `scope: agent` bindings and keeps shared
  profile/credential/application; external references stay PENDING.
- UNINSTALL blocks on open orders **and** open results, and is idempotent.
- **PURGE is blocked** until retention approval and an agent deletion ledger
  exist (`purge_blocked_no_deletion_ledger`).
- Shared queues, Lambdas, tables, Cognito and the HMAC secret are never removed
  for one agent.

## Infrastructure safety

The installer refuses a plan that deletes/replaces/forgets shared
infrastructure unless an explicit `--shared-teardown-intent <reference>` is
provided. Missing `enable_agent_transport` / `orders_agent_result_enabled` /
`orders_lifecycle` are reported as the cause, never as a teardown request.
Plans are hash-checked before apply; unreadable or incomplete plans stop.

## Live baselines

- `ats-agent` 1.0.0 — live E2E PASS on ris-dev2, catalog ACTIVE.
- `addition-agent` 1.0.0 — live E2E PASS, catalog ABSENT (dispatch-only).
- `cv-parser-agent` 1.0.0 — LOCAL VERIFIED (`parse.cv`), catalog ABSENT.
  Live enablement PENDING: the Python Lambda has no node runtime.
- `job-parser-agent` 1.0.0 — LOCAL VERIFIED (`parse.job`), catalog ABSENT.
  Live enablement PENDING (same runtime gap).

All four use the same dispatch/result transport; there are no per-agent queues.

## Adding an agent

> „Agent `<agent-id>` aufnehmen, Paket validieren, Risiken und Partnerwirkungen
> analysieren, vorhandene Runtime/Transport nutzen, in ris-dev2 testen und
> ris-dev-Handoff erzeugen."

Copy `_template/`, replace every placeholder, declare the capability and
workType that the runtime actually registers, add the entitlement binding with
`scope: agent`, and follow the runbook. No new queue, Lambda, table, Cognito
client or agent framework without proven necessity.
