# RIS-ANALYSIS-ECOSYSTEM-CORRECTION-14 — Dispatch→Work-SQS · Terminal ORDER_FAILED

**Date:** 2026-11-21
**Base:** RIS `c7fa5eb` (`feature/ris-analysis-integration-07`), Jobsearch
`e77ee94`, Mays-Orders read-only `9627eb2`
**Status:** **READY FOR FULL ECOSYSTEM CANARY REVIEW** (new plan not applied;
DLQ-exhaustion limit documented).
**No apply, no merge, no production change, no real data.**

---

## 1. Actual SQS topology

| Queue | Name | Producer | Consumer |
|---|---|---|---|
| Dispatch | `ris-dev2-dev-agent-dispatch` | Mays-Orders (`ORDER_DISPATCH`) | `dispatch_ingress` |
| Dispatch DLQ | `ris-dev2-dev-agent-dispatch-dlq` | dispatch redrive | operator |
| Work | `ris-dev2-dev-work-queue` | **ingress (new)** and API execute | shared worker `ris-dev2-dev-agent` |
| Work DLQ | `ris-dev2-dev-dlq` | work redrive (`maxReceiveCount`) | operator |
| Result | `ris-dev2-mays-orders-agent-results` | worker/ingress | Mays-Orders result consumer |
| Result DLQ | `ris-dev2-mays-orders-agent-results-dlq` | result redrive | Mays-Orders |

No queue was created or replaced.

## 2. Dispatch → work-queue transition

`dispatch_ingress` no longer executes `process_record`. It now:

1. validates Transport V1 and resolves the verified context (unchanged),
2. builds the canonical WorkItem (unchanged, pre-bound `workId`,
   `orderId`, `correlationId`, tenant/owner/profile/issuer),
3. persists it with the existing subject-fence transaction
   (`attribute_not_exists` on WorkItem and fence key),
4. sends it to `ris-dev2-dev-work-queue` with `workType`/`agentId` attributes,
5. sets an `enqueuedAt` marker.

Idempotency/recovery:

- duplicate dispatch with `enqueuedAt` → **no second queue message**;
- terminal duplicate (COMPLETED/CANCELLED/DEAD_LETTER) → no send;
- crash after persist before send → WorkItem has no marker, dispatch retry
  re-sends (worker de-duplicates by `workId`);
- send failure → partial batch failure, WorkItem stays QUEUED without marker,
  retry recovers;
- persist failure → partial batch failure, nothing queued.

No new envelope, queue, dispatcher or WorkItem schema. IAM adds
`sqs:SendMessage` on the existing work queue only.

## 3. WorkItem / retry / DLQ

The worker accepts a pre-persisted `QUEUED` row and claims it with a
conditional `QUEUED → RUNNING` update. A concurrent delivery that loses the
claim returns `duplicate/suppressed`; it does not re-execute. `FAILED` keeps
the existing new-attempt path, terminal states keep duplicate semantics, and
transient errors still raise for SQS redelivery/DLQ. No new state machine and
no exactly-once claim: persist/send and DynamoDB/SQS/Lambda are at-least-once;
idempotent work execution plus deduplicated delivery are the guarantee.

## 4. Terminal ORDER_FAILED

At the existing terminal result-delivery boundary (`pipeline`), ORDER_FAILED is
now emitted for order-linked WorkItems only when:

- partner identity binding is missing (terminal),
- entitlement re-check denies (terminal),
- the agent returns a permanent `ValidationError` (terminal).

It is **not** emitted for retryable failures. The envelope uses the existing
`result_from_work_item(..., message_type=ORDER_FAILED)` contract with a stable
`msg_<workId>_order_failed` id and idempotency key; the error payload is
reduced to `{message, type}` (no request/CV/job payload). Re-delivery re-emits
the same deterministic message; Mays-Orders de-duplicates. Non-order WorkItems
return `NOT_ORDER` and never resolve the result sender. ORDER_RESULT is
unchanged.

**Limit (documented, not hidden):** a WorkItem that exhausts SQS retries goes to
the existing DLQ; there is no DLQ-consumer Lambda, so this path cannot emit
ORDER_FAILED. A separate approved DLQ-redrive decision is required for that
case. The canary exercises terminal in-runtime failures.

## 5. Addition and Analysis E2E (synthetic)

The same chain is tested for both agents:

```
dispatch_ingress (persist+enqueue) → work queue message
  → process_record → registry → AgentBody
  → AdditionAgent (local) / LambdaAgentHandler → analysis Lambda (execution-only)
  → WorkItems COMPLETED
```

- Correct registry selection for `addition_agent` and `analysis-agent`.
- Analysis remote execution only for `analysis.run`; `_is_analysis_work`
  remains in the analysis Lambda.
- Duplicate queue/dispatch → one business run.
- Entitlement revoke after enqueue → DEAD_LETTER, no execution.
- Subject fence and cross-tenant checks remain in the existing path.
- Success → ORDER_RESULT (stable id); terminal failure → ORDER_FAILED
  (stable id); transient → retry/DLQ, no ORDER_FAILED.
- Analysis performs no order mutation; only WorkItems/result transport.

## 6. Mays-Orders consumer contract

Mays-Orders already accepts both types: `result_envelope.py` allows
`ORDER_RESULT` and `ORDER_FAILED`, verifies the HMAC signature and matches
order/work/correlation before touching the stored order (`result_consumer.py`).
No Mays-Orders code or lifecycle was changed. Dispatch stays
ORDER_DISPATCH; results stay ORDER_RESULT/ORDER_FAILED.

## 7. Security / least privilege

- Analysis Lambda remote mode needs **no WorkItems write and no Entitlements
  read**. The dedicated data policy was reduced to PartnerProfiles read only.
- Analysis role keeps documents `tenant/*` read, jobs `jobs/*` RW, logs and
  parser invoke (standalone runner path is no longer deployable under this
  role; the worker path is authoritative).
- Worker/ingress invoke the analysis function through resource-based Lambda
  permissions; no shared IAM policy is modified.
- Ingress role gains only `sqs:SendMessage` on the existing work queue.
- Consent/entitlement gates unchanged; no real data.

## 8. Terraform plan (new; old plans retired)

| | |
|---|---|
| Adds / Changes / Destroys / Replacements | **4 / 3 / 0 / 0** |
| Plan SHA-256 | `4a0a02f5a9bd7f16a1295d046798c314a9faac8425e2864d02ec442ed304d033` |
| Plan JSON SHA-256 | `e13e7631aa08ed5cf13eb3867060d055076c405eaaeb326d618227e24c1df7a2` |
| State serial / lineage | 67 / `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Guard | **`NO_SHARED_DESTROY`** |
| Worker bundle | `0d49527e3a74c7e84d0a7ac9c6e0fcfa3673ae510a17ad075848f2e30fc61b37` (115 files) |
| Analysis bundle | `83eef8e691e15ada27bd9afa109b551c00dae766fe0b8a57c4ce1fc637df1184` (113 files) |

Adds: two analysis invoke permissions, analysis Lambda, reduced data policy.
Changes: ingress role policy (`SendToWorkQueue`), ingress Lambda (code +
`WORK_QUEUE_URL` + analysis env), worker Lambda (code + analysis env).
No queue/table/secret/Cognito/CloudFront/DNS change.

## 9. Tests

| Area | Result |
|---|---|
| Work-queue persist/enqueue/idempotency/recovery | 5 |
| Dispatch ingress (enqueue, no execution, duplicate, queue failure) | 18 |
| ORDER_RESULT / ORDER_FAILED / stable ids / retry | 11 |
| Addition+Analysis dispatch→queue→worker | 9 |
| Existing worker/fence/entitlement/transport | 96 |
| Broad focused set (24 files) | **349 passed, 9 skipped** |

## 10. Open approvals

1. Apply approval for the new 4/3/0 plan; old 2/0/0 and 4/2/0 plans retired.
2. Synthetic environment approval (`ANALYSIS_*` remains deny-by-default).
3. DLQ-exhaustion ORDER_FAILED decision (separate, needs a redrive consumer).
4. Legal/entitlement/catalog approvals unchanged; no real users.

## 11. Verdict

**READY FOR FULL ECOSYSTEM CANARY REVIEW.** Dispatch now enters the existing
work queue, the worker owns WorkItem/attempt/retry, analysis runs through the
existing registry/AgentBody with the existing result transport, and terminal
ORDER_FAILED is emitted at the existing boundary. No apply was performed; the
DLQ-exhaustion limitation is explicit and requires a separate decision.
