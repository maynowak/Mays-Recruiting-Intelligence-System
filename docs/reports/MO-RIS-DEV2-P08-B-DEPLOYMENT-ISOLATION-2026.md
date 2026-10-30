# PROMPT 08-B — RIS-DEV2 DEPLOYMENT ISOLATION & SECURITY RECONCILIATION

**Status:** CONDITIONAL

## 1. Task and scope

- Task: PROMPT 08-B
- Topic: Deployment Isolation & Security Reconciliation
- RIS project: `ris-dev2`
- MO component: `ris-dev2-mays-orders`
- Status: CONDITIONAL
- No AWS live execution
- No AWS plan, apply, or destroy executed

## 2. Identity and state isolation

Existing and new resources must remain separate at every layer:

- Existing RIS: `ris-dev`
- New RIS: `ris-dev2`
- Existing MO component: `ris-dev-mays-orders`
- New MO component: `ris-dev2-mays-orders`
- Terraform workspace: `ris-dev2`
- AWS region: `eu-central-1`
- AWS profile: `mayaws` — documented only; live profile/account identity not confirmed

Backend, state key, and workspace prefix are derived from the actually present repository configuration. Any value not live-confirmed is labeled EXPECTED rather than VERIFIED. Existing `ris-dev` state and resources remain out of scope and must not be modified.

## 3. F-01 — IAM worker boundary

From the pinned MO source, `lambda_execution_boundary` is a string containing an account-specific IAM ARN default, not a Boolean flag.

- Contract: account-specific IAM permissions-boundary ARN string
- Portability of the builder across AWS accounts: NOT VERIFIED
- Status: OPEN

The boundary ARN and its applicability to the target account must be confirmed before any deployment approval.

## 4. F-03 — SQS queue policy

The MO SQS resource policy has the following characteristics:

- `Principal = "*"`
- Actions: `SendMessage`, `ReceiveMessage`, `DeleteMessage`, `GetQueueAttributes`
- Resource: `aws_sqs_queue.orders.arn`
- No restrictive Conditions present

Status: DEPLOYMENT BLOCKER.

No synthetic or malformed SQS ARNs are used in this documentation. The policy must be corrected or an explicitly documented, account-specific security exception must be approved before deployment.

## 5. F-04 / F-05 — API and authentication

- RIS API and MO API are statically separated.
- Cognito pools and JWT configuration are documented as statically configured.
- Status: STATIC VERIFIED / LIVE NOT VERIFIED

No live AWS API, authorizer, user-pool, or account linkage verification was performed.

## 6. Further findings

- F-02 Component contract: LOCAL VERIFIED
- F-06 Terraform formatting: LOCAL VERIFIED
- S07-01 Manifest provenance: OPEN
- S07-02 Duplicate of F-03
- S07-03 Terraform versions: compatible
- S07-04 Vendor tag: retained
- S07-05 Terraform default: overwritten by installer

## 7. Plan-readiness decision

Status: CONDITIONAL.

No AWS plan or deployment approval is granted by this document. The documented local evidence does not establish AWS readiness.

## 8. Evidence

Referenced existing artifacts and commits:

- `docs/reports/MO-RIS-DEV2-P08-A-AWS-PLAN-READINESS-2026.md`
- `docs/reports/MO-RIS-DEV2-S04-MO-CONTRACT-FIX-2026.md`
- `docs/reports/MO-RIS-DEV2-S05-RIS-ROOT-VALIDATE-2026.md`
- `docs/reports/S06_RIS-Wrapper-Pin-And-Build-2026.md`
- `docs/reports/MO-RIS-DEV2-S07-DEPENDENCY-CONSOLIDATION-2026.md`
- `docs/reports/S07-CHECKPOINT-RECONCILIATION-2026.md`
- `docs/reports/MO-RIS-DEV2-S08-WRAPPER-REPAIR-2026.md`
- `docs/AI_AUDITLOG.md`
- Commit `d8b8d110a884ff3994dc7db1a71af05d11608486` — AWS plan readiness report checkpoint
- Commit `d19563ced45dc231dc13902d51cf561359445877` — AI audit-log documentation checkpoint
- Commits `0c2bd4b`, `ca26b0e`, `5e8d944` — previously recorded wrapper and local validation checkpoints

Original dedicated evidence that is not preserved is marked NOT AVAILABLE. No results are invented.
