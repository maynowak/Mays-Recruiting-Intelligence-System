# RIS-DEV2-FIX-16B-APPLY-17

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `3d0e96557ca330c9fdf16c94f1937d3ce00c3ca7`
**AWS:** `262370457690` / `eu-central-1` / Workspace `ris-dev2`
**Status:** **FIX 16B APPLIED — LIVE VERIFIED**

## 1. Preflight (PASS)

- STS account `262370457690`, CLI region `eu-central-1`, workspace
  `ris-dev2`.
- Backend metadata: bucket `ris-dev2-tf-state-dev`, region `eu-central-1`,
  workspace key `env:/ris-dev2/dev/terraform.tfstate`, lock table
  `ris-dev2-tf-lock`.
- State before apply: serial **74**, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`.
- S3 VersionId before apply:
  `d24K7fWhqup_DQtI_PNDl85DoML9fpE.`.
- Lock table was active/available; consistent read of the exact backend lock
  key returned no active lock.
- Saved plan SHA-256 matched the approval:
  `43ca49436dac5f0e0f23bcf2c0e4171c034e7f9f380947dbfb8cdf8e9c0af6bf`.
- Plan actions: **0 Add / 3 Change / 0 Destroy / 0 Replace**, only agent,
  dispatch-ingress and analysis Lambda code hashes. Bundle hashes matched;
  `ANALYSIS_SYNTHETIC_MODE=true`; no drift.

## 2. Apply (exactly once)

Command executed exactly once:

```text
terraform apply -auto-approve -no-color C:\tmp\ris-dev2-transaction-client-fix-16b.tfplan
```

Terraform result: **Apply complete! Resources: 0 added, 3 changed,
0 destroyed.** No retry, re-plan, or rollback.

## 3. Live Lambda verification (read-only)

| Function | State | LastUpdateStatus | Live CodeSha256 | Plan match |
| --- | --- | --- | --- | --- |
| `ris-dev2-dev-agent` | Active | Successful | `jsUKYUCNKO+yuF/2yDsF3Q7mB1ubRgge8W1kl5PMY4M=` | yes |
| `ris-dev2-dev-agent-dispatch-ingress` | Active | Successful | `jsUKYUCNKO+yuF/2yDsF3Q7mB1ubRgge8W1kl5PMY4M=` | yes |
| `ris-dev2-dev-analysis` | Active | Successful | `J2tORCAnIWfdMsWQ1tur7UAIckpwkeTYZQTVRE/iaxA=` | yes |

Analysis environment reports `ANALYSIS_SYNTHETIC_MODE=true`. The saved plan
contained only the three Lambda `source_code_hash` and `last_modified`
changes; it contained no IAM, Cognito, environment, queue, API or other
resource changes.

## 4. State after apply

| Field | Value |
| --- | --- |
| Serial | **75** |
| Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` (unchanged) |
| S3 VersionId | `oacaI13gBig4EZiLdlTGuGHb_WB6ksmQ` |
| S3 LastModified | `2026-11-26T11:04:58+00:00` |

## 5. Protected Orders / WorkItems / queues (read-only)

| Resource | Observed state |
| --- | --- |
| Old order `ord_676668fe5ab468284ed7fcf2` | PENDING; untouched |
| Old WorkItem `work-eb1185ecc14c889a` | still only `workId` + `enqueuedAt` |
| Second order `ord_a566f415ef9d77720cd97cd4` | PENDING; dispatch SENT; no processing |
| Its WorkItem `work-2c26e835ee8fee7c` | absent |
| Dispatch queue | 0 visible / 0 in-flight |
| Dispatch DLQ | 1 |
| Work queue | 0 visible / 0 in-flight |
| Work DLQ | 1 |
| Results queue / DLQ | 0 / 0 |

No queue message was received or modified. No redrive or order was made.

## 6. Completion and limits

**FIX 16B APPLIED — LIVE VERIFIED.** All three Lambda updates succeeded and
live hashes match the approved plan. Terraform reported no deployment error.

No redrive, new order, data correction, cleanup, grant, further apply or
main merge. Stop after live verification as instructed.
