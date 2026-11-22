# RIS Agent Operations Handoff 10

**Status:** ris-dev2 test deployment is live and E2E-verified for two agents.
**Operations readiness for partner traffic: NO-GO** until the BLOCKERs below
are closed. No ris-dev/production change.
**Date:** 2026-11-18
**Machine-readable:** `docs/releases/ris-agent-operations-handoff-10.json`

## 1. Agents, versions, pins

| Agent | Capability | Version | Package | Live |
|---|---|---|---|---|
| `ats-agent` | `analyze.job` | 1.0.0 | `agent-installations/ats-agent` | PASS |
| `addition_agent` | `math.add` | 1.0.0 | `agent-installations/addition-agent` | PASS |

- RIS source: `f0c707c6e80638a6489194b3be98374718a6a522`
- Orders pin: `016cdfd6ac62565dcec9a2fee78cb898fb919e59`
- Agent bundle `5258c99e…`; reader bundle `464b991f…` (RIS-AGENT-LIFECYCLE-11); state serial 64.

## 2. Live E2E evidence

**ATS:** order `ord_0d23d52e98fb4c557e7aa920`, work
`work-a818f56a2f5ec0d0`, `COMPLETED`/`SENT`, Orders `processing=COMPLETED`,
`bodyVersion=2.0`, score 67, owner 200 / foreign 404 / invalid 401.

**Addition:** order `ord_71c3c1003ce9492d5acbb601`, work
`work-efc33036efaece37`, `COMPLETED`/`SENT`, Orders `processing=COMPLETED`,
`sum=42`, duplicate no second write. **ATS regression** through the same
runtime: `ord_ac7755a61dd172ed0a0046a9`, `bodyVersion=2.0`, score 100.

## 3. Shared infrastructure

Both agents use the same dispatch/result transport; no per-agent queues:

- `ris-dev2-dev-agent-dispatch` (+ DLQ; visibility 300 s, maxReceive 3)
- `ris-dev2-dev-agent-dispatch-ingress` (60 s, batch 5)
- `ris-dev2-mays-orders-agent-results` (+ DLQ; visibility 60 s, maxReceive 3)
- `ris-dev2-mays-orders-agent-result-consumer` (30 s, batch 10)
- `ris-dev2-mays-orders-agent-result-hmac` (container only, one `AWSCURRENT`)

Differences: `ats-agent` depends on the external ATS contract host; the
addition agent has no external dependency. Neither needs its own AWS resource.

## 4. Risks (classified)

### BLOCKER — before partner traffic

1. **No notification path:** all CloudWatch alarms have empty `AlarmActions`;
   no SNS topic; dispatch/result queues and DLQs have no alarms.
2. **Permanent rejects are deleted:** dispatch/result validation/signature
   errors are acknowledged with a log line only — no DLQ copy, no metric.
3. **Batch/timeout budget:** batch 5 × ATS 30 s inside a 60 s Lambda; a
   mid-flight timeout can leave a `RUNNING` work row permanently unprocessable
   (`WORK_ADMISSION_STATE_UNSAFE`).
4. **No `ORDER_FAILED`:** terminal agent/entitlement failures leave Orders with
   no `processing`; owners cannot distinguish running from failed.
5. **Catalog is not a worker execution gate:** `agents/runtime/pipeline.py` and
   `lambda/orders_reader.py` never read the catalog. DISABLE/UNINSTALL only
   stops execution by withdrawing the agent entitlement; a catalog status
   change alone is cosmetic for the dispatch path.

### AGENT LIFECYCLE STATUS (RIS-AGENT-LIFECYCLE-10 / -11)

- Contract implemented and tested locally: `installer/agent_lifecycle.py`
  with INSTALL/UPDATE/DISABLE/ENABLE/DETACH_PARTNER/UNINSTALL/PURGE/STATUS/VERIFY,
  dry-run, impact, dependency check, idempotency (`already_uninstalled`),
  actor/approval audit and result manifest. It never calls AWS.
- Both packages carry `lifecycle.yaml`, `uninstall.md`,
  `partner-bindings.md` and `retention.md`.
- **Enforcement is live in ris-dev2 (RIS-AGENT-LIFECYCLE-11):**
  `POST /orders` evaluates the agent entitlement before persisting and returns
  403 for a DISABLED/DETACHED agent; the dispatch ingress and worker re-check
  the same entitlement and terminate with `DEAD_LETTER`/`ENTITLEMENT_DENIED`.
  Canonical live proof: enabled 201 + COMPLETED, disabled 403 with no order
  row, direct work item `DEAD_LETTER`, ATS and retail unaffected, re-enabled
  201 + COMPLETED.
- Remaining boundary: the catalog still gates discovery/API, not execution.
  DISABLE must withdraw the entitlement; a catalog-only change is cosmetic.
- **Shared-infrastructure guard (RIS-AGENT-LIFECYCLE-12):** plan/apply/install/
  destroy refuse any delete/replace/forget of shared modules or resource types
  unless `--shared-teardown-intent <ref>` is supplied. A missing/false
  `enable_agent_transport`/`orders_agent_result_enabled`/`orders_lifecycle`
  is reported as the cause, not treated as a teardown request. Live proof:
  the Lifecycle-11 hazard plan now exits 1 with the 11 dispatch resources
  listed; the correct flags produce `NO_SHARED_DESTROY` and 0 changes.
- Still open: `addition_agent` catalog seed (dispatch-only today) and PURGE
  (blocked until retention is approved).


### REQUIRED BEFORE PRODUCTION

- Reader POST has no request-level idempotency; retry creates a second order.
- Profile `expiresAt`/derived `EXPIRED` is ignored.
- Ingress prefers `userId` over `ownerUserId`; queue-ARN pin and entitlement
  resolver can be skipped when env is missing.
- Secret shape is not enforced; a JSON rotation value silently kills every
  signature (permanent reject, no DLQ).
- Cross-tenant profile/entitlement integrity and duplicate-workId owner reuse
  need explicit checks.
- Worker role is shared/broad; dispatch path lacks subject-fence/erasure parity.
- No DLQ replay/break-glass path; worker ESM lacks partial-batch response;
  no ingress concurrency cap.

### OPTIONAL

Log-scope tightening, unused CMK variable, visibility ratio (2× result), dummy
agents on the production path, hardcoded table fallback.

## 5. Monitoring requirements

- SNS topic and non-empty alarm actions **before** traffic.
- DLQ depth/age alarms for both dispatch/result queues.
- Lambda errors/timeouts/duration for ingress and consumer.
- Metric filters for `dispatch rejected`, `result rejected`,
  `invalid service signature`, `WORK_ADMISSION_STATE_UNSAFE`.
- Alert on `orderResultDelivery != SENT`, `FAILED`/`DEAD_LETTER` rows, and
  `RUNNING` rows older than 15 minutes.

## 6. Test and approval checklist

- Apply only the reviewed plan in ris-dev2 test scope; no Cognito/CloudFront/
  DNS/ACM changes.
- Secret: one `AWSCURRENT`, bare 64-hex; recycle the consumer after rotation.
- Synthetic identity/profile/entitlement only; no real applicant data.
- One canary per agent: work `COMPLETED`/`SENT`, Orders `processing`, owner
  200/foreign 404/invalid 401.
- Duplicate dispatch no second write; invalid signature no write/no DLQ.
- Queues/DLQs zero; logs free of secret values, owner keys and synthetic emails.
- Written approval before partner traffic.

## 7. Recovery

- **Stuck RUNNING:** set the row `RUNNING → FAILED` (keep `attempt_no`), then
  redrive the dispatch DLQ; redelivery takes the `attempt+1` path. Do not wait
  for the visibility timeout.
- **Secret rotation:** quiesce, put new bare-hex `AWSCURRENT`, recycle worker and
  result consumer, canary; `AWSPREVIOUS` is the rollback point.
- **Rollback:** reviewed plan with both flags `false`; restore previous
  bundles; revoke test data; keep/delete the secret only via a reviewed step.

## 8. Responsibilities

**ris-dev platform:** AWS apply/deactivate, alarms/SNS, secret rotation,
ORDER_FAILED/idempotency decisions, partner-traffic approval.

**Agent owners:** manifest/contracts/tests/risks/operations/handoff, synthetic
canary data, source-SHA and compatibility updates.

## 9. Agent Z prerequisites

1. Copy `agent-installations/_template` to `agent-installations/<agent>/`.
2. Fill source SHA, capability, versions, contacts and contracts.
3. `python -m installer.agent_install --agent <id> --stage validate
   --status-file <path>`; repeat for resume.
4. Local tests, then an isolated synthetic canary with identity/profile/
   entitlement.
5. Reuse the shared transport; no new queue without proof.
6. No automatic enablement; separate approval.

## 10. Decision

**GO for the already-deployed ris-dev2 test infrastructure.**
**NO-GO for partner traffic/production** until the five BLOCKERs and the
REQUIRED items are closed and the monitoring path is proven with a real
notification.

**HARD STOP before any ris-dev/production change.**
