# RIS Agent Factory — Operations Runbook

**Applies to:** ris-dev2 · account 262370457690 · region eu-central-1 · workspace ris-dev2
**Release:** RIS-AGENT-FACTORY-13
**Status:** ris-dev2 test system · partner traffic NO-GO

---

## 1. Preconditions for every operation

1. Confirm identity and scope **before** any Terraform command:

   ```
   aws sts get-caller-identity          # account must be 262370457690
   git rev-parse --abbrev-ref HEAD      # expected feature/ris-dev2-ats-agent-pinned-core-01
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

**Failed execution:** no `ORDER_FAILED` is emitted; the order stays `PENDING`
with no `processing`. Record the work row state (`FAILED`/`DEAD_LETTER`) as
evidence and escalate.

## 5. Partner operations

- External references remain **PENDING**: partner credential/base URL, agent
  allowlist, static UI elements, quota/consent text, partner Cognito.
- Never change a foreign repository as part of an agent action.
- A detach removes only RIS-side agent bindings; partner confirmation is a
  separate change request.
- Do not enable partner traffic until the five BLOCKERs in the release report
  are closed.

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
