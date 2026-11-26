# RIS-DEV2-CANARY-RECOVERY-18

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **BLOCKED — PARTIALLY VERIFIED**

## 1. Preflight

Preflight passed at 12:16Z, and state/account were rechecked immediately
before the queue operation:

- STS `262370457690`, region `eu-central-1`, Terraform workspace `ris-dev2`.
- State Serial **75**, Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`.
- S3 VersionId `oacaI13gBig4EZiLdlTGuGHb_WB6ksmQ`.
- Fix-16B Lambda hashes matched and all update statuses were Successful;
  `ANALYSIS_SYNTHETIC_MODE=true` and configured expiry
  `2026-11-26T17:40:28Z`.
- Synthetic entitlement valid at the time; API profile, partner binding and
  analysis offer active.
- Target order `ord_a566f415ef9d77720cd97cd4` was PENDING; WorkItem
  `work-2c26e835ee8fee7c` absent.
- Dispatch queue empty; dispatch DLQ had exactly one visible message and no
  in-flight message. Source redrive policy pointed to that DLQ.

## 2. One controlled manual redrive

Received at most one DLQ message. Its envelope and payload matched the
approved canary before sending:

| Field | Verified value |
| --- | --- |
| OrderId | `ord_a566f415ef9d77720cd97cd4` |
| WorkId | `work-2c26e835ee8fee7c` |
| CorrelationId | `corr-canary-07-02` |
| ContextRef / apiProfileId | `aprof_cdbd3b6f803744bf` |
| Dispatch idempotency key | `ord_a566f415ef9d77720cd97cd4:work-2c26e835ee8fee7c:ORDER_DISPATCH` |
| Payload idempotency key | `canary-07-job-tags-02` |
| Message type / target | `ORDER_DISPATCH` / `analysis-agent`, `analysis.run` |
| Message payload | exact previously approved synthetic `job.tags` payload |

The message body and user attributes were forwarded to the configured source
queue. `SendMessage` returned success (destination MessageId
`382b96fc-79a3-40bc-a439-78a69cc68151`); **only then** the exact source DLQ
receipt was deleted (HTTP 200). The DLQ source MessageId was
`816b5bef-d544-460a-b039-452d1b9ce7b5`.

Exactly one receive, one send and one source delete were attempted. No
redrive/retry followed. An earlier read-only queue-attribute preflight call
used an unsupported `FifoQueue` attribute and stopped before `ReceiveMessage`;
it performed no queue mutation. The corrected preflight confirmed the
standard queue names and counts before the single redrive.

## 3. Automatic processing and read-only verification

After the successful send and source deletion, read-only polling ran for up
to ten minutes. The WorkItem reached `RUNNING`, but the end-to-end did not
complete:

| Check | Observed result |
| --- | --- |
| WorkItem | `RUNNING`, attempt `0`; no result/error/completion timestamp |
| Order | remains `PENDING`; `processing` absent |
| Owner GET | HTTP **200**, but status `PENDING`, no processing/result |
| Dispatch source / DLQ | 0 visible / 0 in-flight; DLQ 0 |
| Work queue | 0 visible / 0 in-flight |
| Work DLQ | 1 (pre-existing; untouched) |
| Result queue / DLQ | 0 / 0 |

At the 12:35:45Z read-only snapshot the WorkItem was still `RUNNING`, created
at `12:21:26Z`, last updated `12:21:36Z`, with no result or error. The Owner
GET succeeded but did not return a completed result.

CloudWatch reads found two workId-correlated INFO events in
`/aws/lambda/ris-dev2-dev-agent`, including an analysis marker; no correlated
events were found in the analysis Lambda or Mays-Orders result-consumer log
groups. No correlated ERROR, WARNING, exception or timeout marker was found
in the sampled agent events. This is insufficient to prove completed
Analysis output, a signed `ORDER_RESULT`, result-consumer processing, or
`processing.status=COMPLETED`.

## 4. Protected state and limits

- Old order `ord_676668fe5ab468284ed7fcf2` remains PENDING.
- Damaged WorkItem `work-eb1185ecc14c889a` remains only `workId` +
  `enqueuedAt`.
- Work-DLQ had 1 message in the final count snapshot; no message was read,
  redriven or cleaned.
- No new order, data correction, cleanup, grant, Terraform apply or main
  merge. No second redrive or manual worker/result invocation.
- Terraform state remained Serial 75, same Lineage and S3 VersionId
  `oacaI13gBig4EZiLdlTGuGHb_WB6ksmQ` at the final snapshot.

## 5. Decision

**BLOCKED — PARTIALLY VERIFIED.** The one approved DLQ message matched,
was sent once to the regular dispatch queue, and its source receipt was
deleted only after successful send. Automatic processing persisted a
WorkItem and moved it to `RUNNING`, but the work did not complete within the
observation window. The Owner GET returned HTTP 200 with the still-PENDING
order and no result. No further retry or recovery action was performed.
