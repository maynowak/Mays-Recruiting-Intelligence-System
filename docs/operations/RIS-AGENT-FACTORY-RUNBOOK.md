# RIS Agent Factory — Operations Runbook

**Applies to:** ris-dev2 · account 262370457690 · region eu-central-1 · workspace ris-dev2
**Release:** RIS-AGENT-FACTORY-13, aligned with the Correction-14 code/test
baseline and the E1B analysis gate
**Status:** ris-dev2 test system · partner traffic NO-GO. Correction-14 is
prepared, **not applied**; the analysis Lambda and offers are not deployed.

---

## 1. Preconditions for every operation

1. Confirm identity and scope **before** any Terraform command:

   ```
   aws sts get-caller-identity          # account must be 262370457690
   git rev-parse --abbrev-ref HEAD      # the change's feature branch; never assume main
   git rev-parse HEAD                   # record in the change ticket
   ```

2. Confirm the workspace and state: workspace `ris-dev2`, backend
   `ris-dev2-tf-state-dev`, key `env:/ris-dev2/dev/terraform.tfstate`,
   lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`. A serial mismatch is a stop
   condition only for the change you are applying; record it.
3. Record the bundle hashes:
   - agent `terraform/lambda.zip`
   - reader `lambda/dist/orders-reader.zip`
4. Never run `terraform apply`, `destroy`, `state push` or direct `-target`,
   `-replace`, `-destroy` outside `installer.ris`. Protection is
   installer-side; direct runs bypass it.
5. Always pass the live transport flags explicitly for a managed installation:

   ```
   --var enable_agent_transport=true
   --var orders_agent_result_enabled=true
   ```

   Omitting them is **not** a teardown request; the guard refuses the plan.

## 2. Plan and apply

```
python -m installer.ris --project-name ris-dev2 --environment dev \
  --region eu-central-1 --backend-bucket ris-dev2-tf-state-dev \
  --backend-region eu-central-1 --backend-lock-table ris-dev2-tf-lock \
  --var enable_agent_transport=true \
  --var orders_agent_result_enabled=true \
  --out <plan-file> plan
```

Expected output includes one of:

| Gate message | Meaning | Action |
|---|---|---|
| `NO_SHARED_DESTROY` | no shared delete/replace | review the plan diff |
| `MISSING_OR_FALSE_TRANSPORT_FLAG` | a transport flag is not set | **STOP**; set the live flags, do not add an intent |
| `SHARED_DESTROY_WITHOUT_INTENT` | shared delete intended | **STOP**; requires a separate approved teardown |
| `SHARED_TEARDOWN_AUTHORIZED by <ref>` | explicit teardown | verify the reference and the plan SHA |
| `PLAN_SHAPE_INVALID` / `GUARD_UNREADABLE` | unreadable/incomplete plan | **STOP**; re-plan |

Review the plan: no delete/replace of SQS, Lambda, DynamoDB, Secrets Manager,
Cognito, API Gateway, CloudFront, IAM, S3, KMS, SNS or the shared modules.
A new plan always needs a new review and a new SHA.

`apply` refuses if the plan file disappears or changes between the gate and
the apply. `destroy` and a composite destroy require
`--shared-teardown-intent <approved-reference>`; without it they stop.

## 3. Agent lifecycle actions

The lifecycle CLI is local-state only; it does not call AWS.

```
python -m installer.agent_lifecycle --agent <dir> --action <action> \
  --inventory <inventory.json> --state-file <state.json> \
  --audit-log <audit.jsonl> [--execute] [--actor <id>] [--approval <ref>] \
  [--reason "<text>"] [--impact-report <path>]
```

**DISABLE** (stop new and running work)
1. Withdraw the agent-scoped entitlement rows (`scope: agent`). This is the
   only lever that stops the reader, dispatch and worker.
2. Set the catalog status INACTIVE via a reviewed Terraform change **only if**
   a catalog row exists.
3. Keep in-flight work and all history.

**ENABLE**
1. Re-grant the entitlement.
2. Restore the catalog status via Terraform if it was changed.
3. Verify with `STATUS`/`VERIFY` and one canary order.

**DETACH_PARTNER**
- Removes only agent-scoped entitlement rows.
- Keeps API profile, credential, partner application and client reservation.
- Marks external partner references PENDING; never edits a foreign repository.

**UNINSTALL**
- Requires an inventory with an explicit `openOrders` list.
- Blocks on open orders **and** open results.
- Idempotent: a second run reports `already_uninstalled` without rewriting
  state or resetting the purge grace anchor.
- Retains orders, work items, results, audit and all shared resources.

**PURGE**
- **BLOCKED.** Blockers: `purge_blocked_no_deletion_ledger` (no retention
  approval, no agent deletion ledger), plus confirmation/grace/open-work
  checks. Do not try to bypass this; it is a release gate, not a bug.

## 4. Monitoring and incidents

Known state: 20 alarms, **none with actions**, no SNS topic. Until that is
fixed, on-call must poll:

- SQS `ApproximateNumberOfMessages` and `...NotVisible` for
  `agent-dispatch`, `agent-dispatch-dlq`, `work-queue`, `work-dlq`,
  `agent-results`, `agent-results-dlq`.
- Worker/ingress Lambda `Errors`, `Throttles`, `Duration`.
- Orders reader `Errors`.
- Work items in `RUNNING` older than 15 minutes.

**Stuck `RUNNING`:** a work row that timed out cannot be re-admitted
(`WORK_ADMISSION_STATE_UNSAFE`). Recovery requires an approved manual
`RUNNING→FAILED` update, then redrive the dispatch DLQ; redelivery becomes
attempt N+1. Never delete the row.

**Permanent rejects:** dispatch and result invalid/signature records are
consumed with a log line only. There is no DLQ artifact. Capture the log
entry and the order/work IDs; do not re-send an unsigned record.

**Failed execution (Correction-14):** for order-linked WorkItems the shared
pipeline emits terminal `ORDER_FAILED` when the partner identity binding is
missing, the entitlement re-check denies, or the agent returns a permanent
`ValidationError`. Retryable failures do **not** emit `ORDER_FAILED`; they
remain retry/DLQ. A WorkItem that exhausts SQS retries reaches the existing
DLQ **without** `ORDER_FAILED` because no DLQ-consumer Lambda exists. Record
the work row state (`FAILED`/`DEAD_LETTER`) and escalate; this limit is open,
not a per-agent bug.

### 4.1 Order and result lifecycle (Correction-14)

```
Mays order (owner) -> ORDER_DISPATCH -> dispatch ingress
  -> persist WorkItem + enqueue -> work queue -> shared worker
  -> registry/AgentBody -> domain agent
  -> ORDER_RESULT (success) | ORDER_FAILED (terminal) -> Mays result consumer
```

- One order, one WorkItem. Composite agents use internal capabilities; they do
  not create additional orders or queues.
- The order fachlicher `status` is Mays-owned. The WorkItem status is
  RIS-owned. Do not equate them.
- Result retrieval is the **existing** Mays-Orders path:
  `GET /orders/{orderId}` -> `processing.status`, `processing.result`,
  sanitised `processing.error`. The RIS orders-reader exposes the same
  owner-scoped view. There is no analysis-specific result API.
- `ORDER_RESULT`/`ORDER_FAILED` are deduplicated by the Mays consumer and use
  stable message ids. RIS does not claim exactly-once delivery.
- **Automatic agent resume is OPEN / NOT IMPLEMENTED.** A parent agent that
  creates a child order does not enter a persisted `WAITING` state and is not
  woken by `ORDER_RESULT`/`ORDER_FAILED`. Parent fields exist in the schema but
  are not propagated end to end by the current dispatch/result builders.
  Treat agent-to-agent round trips as a separate platform track; do not claim
  them for a single analysis order.

## 5. Partner operations

- External references remain **PENDING**: partner credential/base URL, agent
  allowlist, static UI elements, quota/consent text, partner Cognito.
- Never change a foreign repository as part of an agent action.
- A detach removes only RIS-side agent bindings; partner confirmation is a
  separate change request.
- Do not enable partner traffic until the five BLOCKERs in the release report
  are closed.

### 5.1 Composite agent operations (`analysis-agent`)

- One agent (`analysis-agent`, `analysis.run`, work type
  `agent_analysis_agent`) with three DRAFT offers (`analysis.cv`,
  `analysis.job`, `analysis.match`). Catalog `ABSENT`, activation `false`,
  entitlements `PENDING_APPROVAL`.
- External entitlements `parse.cv`/`parse.job`/`compare.tags`/optional
  `analyze.job`; internal `parse.cv`/`parse.job`/`parse.ats` are technical
  subfunctions of the same WorkItem. They create no order and no separate
  charge.
- Existing call paths: RIS API execute (`agentId=analysis-agent`) or a Mays
  paid agent order (`agentOrder.target=analysis-agent`) -> the same
  `ORDER_DISPATCH` -> work queue -> worker.
- Result: existing Mays-Orders order view (`processing.status/result/error`)
  or the RIS owner-scoped reader. No new queue, table or result API.
- Identity: the RIS API path is JWT + `X-Api-Credential` with
  profile/tenant/entitlement/catalog checks. The Mays dispatch path carries a
  client-supplied `apiProfileRef`; Mays must bind it to the order
  owner/partner before real traffic. This is the open cross-repo finding C.
- Release gates: **A** exact technical apply (plan `9a0324a0…`, 4/3/0,
  `NO_SHARED_DESTROY`, not applied), **B** exact synthetic profile, **C** Mays
  `apiProfileRef` binding. Legal notice, entitlement and catalog remain
  separate. The analysis Lambda is not deployed.
- Monitoring: work queue/DLQ, worker/ingress errors, analysis Lambda and
  parser Lambda errors/duration. `ORDER_FAILED` does not cover DLQ exhaustion.
- Do not describe the analysis package as AWS-verified, publicly available or
  able to resume a parent agent automatically.

## 6. Recovery

| Situation | Action |
|---|---|
| Bad deploy | restore the previous reviewed plan/bundle via a new plan; do not use `-target` |
| Disabled by mistake | re-grant the entitlement, restore catalog, canary |
| Detached by mistake | new reviewed grant; shared rows were never removed |
| Uninstalled by mistake | fresh reviewed install (state flip alone is not enough) |
| Plan guard triggered | do **not** add an intent; fix the flags and re-plan |
| Plan changed after review | discard, re-plan, re-review |
| Stuck RUNNING | approved `RUNNING→FAILED`, redrive DLQ |
| DLQ growth | stop intake, capture message IDs, escalate to RIS runtime |
| No `ORDER_FAILED` after DLQ exhaustion | expected open limit; record work state, do not invent a result, escalate redrive decision |
| Parent agent did not resume | expected: automatic resume is not implemented; use the existing order GET/polling path |

## 7. Change evidence

Every change records:

- commit SHA, operator, approval/ticket reference
- plan SHA-256, gate decision (`NO_SHARED_DESTROY` or intent reference)
- bundle hashes, state serial before/after
- lifecycle audit line (`planDigest`, `lifecycleDigest`, `inventoryDigest`)
- result manifest and, where applicable, the removal-impact report

Keep the audit JSONL and result manifests with the ticket. They are the
compliance evidence; the terminal output alone is not.

## 8. Hard stops

1. Any shared delete/replace/forget without a reviewed intent.
2. Any plan whose SHA differs from the reviewed one.
3. Missing `ENTITLEMENTS_TABLE` or an unreachable entitlement store (the
   reader/ingress fail closed; treat as an incident).
4. PURGE without retention approval and an agent deletion ledger — currently
   always blocked.
5. Any ris-dev or production action without an explicit, separate scope.
6. Any attempt to fix a guard stop by adding an intent instead of the flags.
7. Claiming automatic parent-agent resume without an implemented, tested
   `WAITING`/wake-up and parent-correlation path.
8. Real order-driven analysis traffic while the Mays-Orders `apiProfileRef`
   ownership binding is unverified.
