# PROMPT 08-A — RIS-DEV2 AWS PLAN READINESS

**Status:** CONDITIONAL

## Scope and decision

This document records AWS plan-readiness for the `ris-dev2` integration only. It is a documentation checkpoint; no AWS plan, apply, destroy, or deployment was executed as part of Prompt 08-A.

## Project identity

- RIS project: `ris-dev2`
- MO component: `ris-dev2-mays-orders`
- Terraform workspace: `ris-dev2`
- AWS region: `eu-central-1`
- Documented AWS profile: `mayaws` (live profile and account identity not confirmed)
- Existing `ris-dev` resources and state remain strictly out of scope and must not be changed.

## Local integration evidence

The following results are recorded from existing project documentation and are not re-executed by this report:

- MO builder run: **REPORTED successful**.
- Terraform module gates (`fmt`, `init`, `validate`): **REPORTED PASS**.
- RIS-root integration gates (`fmt`, `init`, `validate`): **REPORTED PASS**.
- Wrapper regression suite: **REPORTED PASS** (49 tests reported in prior project records).
- No AWS live validation was performed for Prompt 08-A. Local results do not prove AWS account, permissions, backend, state, or resource availability.

Where original command output is not preserved in a dedicated evidence artifact, the result is labeled **REPORTED** rather than independently verified. Missing original evidence is **NOT AVAILABLE**.

## AWS plan prerequisites

Before any plan can be considered reviewable or any deployment can be approved, all of the following must be confirmed explicitly:

1. Resolve the `mayaws` profile to the intended AWS account and confirm the account ID.
2. Confirm the region is `eu-central-1` and that credentials have the required read-only planning permissions.
3. Verify backend configuration and state isolation for workspace `ris-dev2`.
4. Verify that the state and resource namespace are separate from existing `ris-dev` resources.
5. Provide and review all required Terraform variables, including the component-specific ARNs, IDs, URLs, and security parameters.
6. Review any proposed changes for accidental replacement or modification of existing resources.
7. Keep apply disabled unless a separate, explicit deployment authorization is issued.

## Required Terraform variables

The plan operator must provide the repository-defined required variables for the `ris-dev2` / `ris-dev2-mays-orders` integration, including the relevant AWS, API, authentication, queue, worker, and boundary inputs. Values must be reviewed for account, region, ARN/ID, and environment consistency before planning. No variable values are asserted here as live-confirmed.

## Open security findings

- **F-01 — Worker IAM boundary: OPEN.** The worker IAM configuration depends on a kontospezifisches (account-specific) permissions-boundary ARN/default. The boundary ARN and its applicability must be confirmed for the target account; portability is not established.
- **F-03 — SQS resource policy: DEPLOYMENT BLOCKER.** The policy uses `Principal = "*"` without restrictive Conditions. This remains unresolved and prevents deployment approval until the policy is corrected or an explicitly accepted, account-specific security exception is documented.
- **F-04/F-05 — API/Cognito contracts: STATIC VERIFIED only.** Local/static contract evidence is recorded, but live AWS API, authorizer, user-pool, and account linkage are not verified.

## Evidence and provenance

Relevant existing records include:

- `docs/reports/MO-RIS-DEV2-S04-MO-CONTRACT-FIX-2026.md`
- `docs/reports/MO-RIS-DEV2-S05-RIS-ROOT-VALIDATE-2026.md`
- `docs/reports/S06_RIS-Wrapper-Pin-And-Build-2026.md`
- `docs/reports/MO-RIS-DEV2-S07-DEPENDENCY-CONSOLIDATION-2026.md`
- `docs/reports/S07-CHECKPOINT-RECONCILIATION-2026.md`
- `docs/reports/MO-RIS-DEV2-S08-WRAPPER-REPAIR-2026.md`
- `docs/AI_AUDITLOG.md`
- Commit `d19563ced45dc231dc13902d51cf561359445877` — AI audit-log documentation checkpoint.
- Commits `0c2bd4b`, `ca26b0e`, and `5e8d944` — previously recorded wrapper and local validation checkpoints.

Original dedicated evidence for some later command runs is **NOT AVAILABLE**; corresponding claims remain **REPORTED** and are not upgraded to independently verified evidence by this document.

## Release decision

**CONDITIONAL — NOT READY FOR AWS PLAN APPROVAL OR DEPLOYMENT.**

The documented local integration evidence is insufficient to establish AWS readiness. Do not run an AWS plan, apply, or destroy under this checkpoint until AWS identity, backend/workspace isolation, required variables, and the open F-01/F-03 findings have been addressed and independently evidenced.
