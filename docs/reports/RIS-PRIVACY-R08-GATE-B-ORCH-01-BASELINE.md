# RIS-PRIVACY-R08-GATE-B-ORCH-01 — Baseline

## Preflight

- Repository: `Mays-Recruiting-Intelligence-System`
- Branch: `feature/ris-privacy-r08-gate-b-orchestration-01`
- Start HEAD: `b490824694005e5a51d51cc1d6062525dab9d933`
- `origin/main`: `b490824694005e5a51d51cc1d6062525dab9d933`
- Working tree: clean
- New branch: created directly from current `origin/main`
- AWS/Terraform Apply/Destroy/deployment: not performed
- Mays-Jobsearch and Mays-Orders: read-only; no files changed

## Scope

This branch reconciles R08 evidence and performs only one bounded local code
hardening: ApplicationV1 responses now return `Cache-Control: no-store,
private`. No productive privacy flag, receipt journal, erasure worker, SQS,
IAM, PITR or storage behavior was activated or changed.

## Evidence rule

Historical live reports establish only the environment and date they recorded.
Local tests establish code/test-double behavior. Neither is treated as current
`ris-dev` or production evidence without a new authorized live run.

## Gate B decision at baseline

**NO-GO for Apply.** Legal bases, retention, PITR/restore reconciliation,
receipt policy, productive erasure, current live infrastructure and RG-11
SQS/DLQ erasure safety remain unresolved.
