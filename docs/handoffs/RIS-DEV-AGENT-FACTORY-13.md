# RIS-DEV Handoff — Agent Factory 13

**From:** ris-dev2 agent factory
**To:** ris-dev operations
**Date:** 2026-11-19
**Baseline commit:** `fd38288ddffc36ee7380cd36bc5a63f9501ac78a` (branch `feature/ris-dev2-ats-agent-pinned-core-01`)
**Status:** ready for **review**, not for automatic adoption. Partner traffic is **NO-GO**.
**No ris-dev or production change was made by this release.**

Status labels used below:

- **LIVE VERIFIED** — observed in ris-dev2 in this baseline
- **LOCAL VERIFIED** — proven by tests in this repository
- **PENDING** — needs an external change or a separate approval
- **BLOCKED** — must not be executed

---

## 1. Agent inventory and capabilities

| Agent | Capability | Work type | Version | Catalog | Status |
|---|---|---|---|---|---|
| `ats-agent` | `analyze.job` | `ats_process` | 1.0.0 | ACTIVE | LIVE VERIFIED |
| `addition_agent` | `math.add` | `agent_addition_agent` | 1.0.0 | ABSENT (dispatch-only) | LIVE VERIFIED |
| `reference_agent` | `reference.echo` | — | — | ACTIVE | catalog only, no package |
| `jobsearch-agent` | `jobsearch.*` | — | — | ACTIVE | catalog only, no package |

Contracts: WorkItem 1.0, AgentOrder 1.0, Transport 1, runtime 1.0.0,
ATS contract 1.2, ATS result body 2.0. ATS depends on
`https://mays-jobsearch.vercel.app`; addition has no external dependency.

## 2. Source pins and reproducible build

| Item | Value |
|---|---|
| RIS source (agent code / packages) | `fd38288ddffc36ee7380cd36bc5a63f9501ac78a` |
| Orders generated module (builder pin) | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| Orders component clone pin (composite path) | `5cf50a0a8e4221348c264c59432ff4c8dc580c8b` |
| Jobsearch reference pin | `29d8b730bb0660d48d1ba774c773e88d9aa7142e` |
| Agent bundle SHA-256 | `5258c99ee62b4e66da25874d2941b18cd14871796baadbdb0e1fe5751eb98e1` |
| Reader bundle SHA-256 | `464b991f784f0ea14da761fca355e676490f9a399209d4d3c2149165c25b1c4d` |

Reproduce:

```
python lambda/build_zip.py --bundle all
python -m installer.build_mays_orders_module --project-name <project> --check
```

**PENDING:** the clone pin (`5cf50a0…`) and the builder pin (`016cdfd6…`) refer
to the same upstream repository but different revisions. The deployed managed
module uses `016cdfd6…`; the clone pin belongs to the legacy composite path.
Align the clone pin before using the composite installer.

## 3. Install / update / disable / enable / detach / uninstall

All local actions use `installer/agent_lifecycle.py`; infrastructure is
changed only through a reviewed `installer.ris` plan.

```
# local plan (no AWS)
python -m installer.agent_lifecycle --agent ats-agent --action disable \
  --inventory <inventory.json> --state-file <state> --impact-report <json>

# apply local state
python -m installer.agent_lifecycle --agent ats-agent --action disable \
  --inventory <inventory.json> --state-file <state> --audit-log <jsonl> \
  --execute --actor <id> --approval <ticket> --reason "<text>"
```

| Action | Effect | Order |
|---|---|---|
| INSTALL | enable entitlement, catalog ACTIVE if a row exists | entitlement → catalog → canary |
| UPDATE | code/contract change via shared bundle | reviewed plan → canary |
| DISABLE | withdraw entitlement (reader/most dispatch/worker stop), catalog INACTIVE if row exists | entitlement first |
| ENABLE | re-grant entitlement, catalog ACTIVE | entitlement → catalog → canary |
| DETACH_PARTNER | remove only `scope: agent` rows; keep shared profile/credential/application | inventory → detach → verify |
| UNINSTALL | block on open orders/results, withdraw entitlement, retain history | drain → uninstall |
| PURGE | **BLOCKED** | do not run |

Detailed procedures: `docs/operations/RIS-AGENT-FACTORY-RUNBOOK.md`.

## 4. Catalog, entitlement and partner bindings

- Catalog (`agent-catalog`) gates discovery and the API execute routes only.
  It is **not** a worker gate. `catalogAloneBlocksExecution = false`.
- Entitlement rows gate `POST /orders`, dispatch and worker execution.
- Only entitlement rows bind `agentId`. API profile, credential, partner
  application and client reservation are shared and must survive a detach.
- Offers/grants are shared packages; never edit `agentIds` for one partner.
- DETACH removes only agent-scoped entitlements and marks external references
  PENDING.

## 5. External references (PENDING)

| Reference | Owner | Status |
|---|---|---|
| Partner `RIS_API_CREDENTIAL` / `RIS_API_BASE_URL` | partner | PENDING |
| Partner agent allowlist (hard-coded) | partner | PENDING |
| Static partner UI elements bound to an `agentId` | partner | PENDING |
| Quota/consent/privacy text | partner/legal | PENDING |
| Partner Cognito pool/client/domain | partner | PENDING (never part of an agent detach) |

## 6. Shared resources and deletion prohibitions

Never delete for a single agent:

`agent-dispatch` + DLQ + ingress Lambda, `agent-results` + DLQ + consumer,
worker Lambda, orders-reader Lambda, work-items, mays-orders, agent-catalog,
entitlements, api-profiles, credentials, partner-applications, Cognito,
HMAC result secret, cursor secret, documents bucket, IAM roles.

A shared teardown requires an explicit `--shared-teardown-intent <approved
reference>` and a reviewed plan; missing transport flags are **not** a
teardown request.

## 7. Retention, audit, recovery and PURGE

- Orders, work items, results and audit are retained. TTL: work items 30 d in
  code (matrix says 90 d — **PENDING**); order-correlated rows omit
  `expiresAt`.
- Audit: append-only JSONL with actor/approval/reason and
  plan/lifecycle/inventory digests; written before the state mutation.
- Recovery: re-grant entitlement (ENABLE), reviewed re-install after
  UNINSTALL, approved `RUNNING→FAILED` for stuck rows.
- **PURGE is BLOCKED** (`purge_blocked_no_deletion_ledger`): no retention
  approval and no agent deletion ledger exist. Do not work around it.

## 8. Monitoring, DLQ and incident requirements

- **BLOCKED:** 20 alarms, **0 with actions**, 0 SNS topics. Dispatch/result
  queues and DLQs have no alarms. This must be fixed before partner traffic.
- Poll queue depth/age, DLQs, Lambda errors/throttles/duration and
  `RUNNING` work older than 15 minutes.
- No `ORDER_FAILED`: owners see `PENDING` with no `processing` for a failed
  execution.
- No DLQ replay tool: recovery is manual and approval-gated.
- Preflight/verification commands and stop conditions are in the runbook.

## 9. Risks before partner traffic

**BLOCKER**

1. No alarm notification path; agent queues/DLQs unmonitored.
2. Permanent rejects deleted without DLQ artifact or metric.
3. Batch/timeout can strand a `RUNNING` row permanently.
4. No `ORDER_FAILED` / failure projection.
5. No partner result retrieval route (`GET /work` not exposed) for the 202
   contract.

**REQUIRED BEFORE PRODUCTION**

- Reader POST idempotency; profile expiry enforcement.
- Monitoring calibration and coverage (worker only today).
- API-enqueued work not executable (`WORK_ADMISSION_STATE_UNSAFE`).
- Eligibility fails open on body/runtime mismatch.
- Tenant-global entitlement rows; unparsable validity bounds.
- No Terraform-native `prevent_destroy`; direct Terraform/state operations
  are unguarded.
- Composite Orders destroy not plan-inspected; `state push` unguarded.
- PURGE lacks retention approval and a deletion ledger.
- Partner execution context can lose `partnerApplicationId`/issuer.

## 10. Test evidence and release criteria

- **LOCAL VERIFIED:** 456 passed, 18 subtests across guard (31), lifecycle
  (25), orchestrator (9), reader gate (10), dispatch env (3), ATS, addition,
  reader, worker, partner boundary and catalog seed.
- **LIVE VERIFIED:** addition order `ord_dce286fa42aa192773f67276` (sum 42),
  ATS order `ord_120536c300e188f7c0a244dd` (body 2.0), disabled order rejected
  with 403 and no row, direct work `DEAD_LETTER`, ATS/retail unaffected,
  re-enabled order `ord_e79d7cc716b61af254bc8577` (sum 42); queues 0/0.
- **LIVE VERIFIED:** state serial 64, 266 resources, worker/ingress code
  unchanged, reader gate deployed.
- **Release criterion:** all five BLOCKERs closed, a working alarm notification
  path, reader idempotency, and a retention decision for PURGE.

## 11. Concrete first steps for ris-dev

1. Read `docs/reports/RIS-AGENT-FACTORY-RELEASE-13.md` and this handoff.
2. Verify the baseline commit and bundle hashes above.
3. Run the read-only preflight/plan in the ris-dev scope with explicit
   transport flags; expect `NO_SHARED_DESTROY`.
4. Decide the alarm/SNS ownership and retention policy (the two open gates).
5. Onboard each agent with the package standard:
   `agent-installations/README.md` and `_template`.
6. Do not adopt automatically; treat this as a reviewed change request.

## Stop conditions

- Any shared delete without a reviewed intent.
- Any plan SHA different from the reviewed one.
- Missing entitlement store / unreachable authorization.
- PURGE attempt.
- Any ris-dev/production action outside an explicit approved scope.
