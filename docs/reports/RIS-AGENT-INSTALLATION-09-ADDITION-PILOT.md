# RIS Agent Installation 09 — Addition Agent Pilot

**Status:** **PASS**. ris-dev2 test scope only; no new AWS resources; no
ris-dev/production change; partner traffic remains disabled.
**Date:** 2026-11-18
**Machine-readable:** `docs/releases/ris-agent-installation-09-addition.json`

## 1. Result

The existing installation workflow and the deployed transport were reused for
`addition_agent` (`math.add`) without a new queue, Lambda, table or contract.

- Package: `agent-installations/addition-agent`, version 1.0.0.
- Orchestrator stages: discover, analyze, compatibility, risk-review, package,
  validate; validate re-run returned `SKIPPED` (resume/idempotency).
- Terraform post-apply plan: **no changes** (no new AWS resources).
- Live canary: `math.add(17, 25)` = **42**.

## 2. Live evidence

| Item | Value |
|---|---|
| Order | `ord_71c3c1003ce9492d5acbb601` |
| Work item | `work-efc33036efaece37` |
| Work status | `COMPLETED` |
| `orderResultDelivery` | `SENT` |
| Orders `processing` | `COMPLETED` |
| Result `sum` | `42` |
| Order status | `PENDING` (unchanged by the result) |
| Owner read | `200` |
| Foreign owner | `404 ORDER_NOT_FOUND` |
| Invalid token | `401` |
| Duplicate dispatch | no second write |
| Dispatch/result DLQ | `0` |

ATS regression through the same runtime and queues:
order `ord_ac7755a61dd172ed0a0046a9`, work `COMPLETED`, delivery `SENT`,
Orders `processing=COMPLETED`, `bodyVersion=2.0`, numeric score `100`.

## 3. Tests

- Targeted local addition/worker/dispatch/orchestrator: **54 passed / 10 skipped**.
- Orchestrator suite: **5 passed**.
- Live addition: **PASS**; live ATS regression: **PASS**.
- Existing full RIS baseline remains **2654 passed / 134 skipped** with the same
  29 known failures and 4 collection errors.

## 4. Risks

- The addition agent shares the transport with ats-agent; do not change the
  transport contract for an agent-specific change.
- Reader POST has no request-level idempotency; duplicate dispatch is safe,
  duplicate create is not.
- No new operational risk beyond the known ATS/transport risks; partner traffic
  remains disabled.

## 5. Reusable flow for Agent Z

1. Create `agent-installations/<agent>/` with manifest, contracts, tests,
   risks, operations, handoff.
2. Run `python -m installer.agent_install --agent <agent> --stage validate
   --status-file <path>`; repeat for resume (passed stages are skipped).
3. Run local contract/agent tests.
4. Reuse the existing dispatch/result transport; add no queue unless the
   manifest proves it is required.
5. Provision synthetic user, ACTIVE profile and an agent-specific entitlement.
6. Run an isolated canary and verify work `COMPLETED`/`SENT`, Orders
   `processing`, owner 200 / foreign 404.
7. Revoke test data; update handoff and release JSON.

## 6. Cleanup

Synthetic users and entitlement rows deleted; test profiles revoked; two
addition orders and one ATS regression order plus their work rows remain as
evidence. The secret still has exactly one `AWSCURRENT`.

**HARD STOP before any ris-dev or production change.**
