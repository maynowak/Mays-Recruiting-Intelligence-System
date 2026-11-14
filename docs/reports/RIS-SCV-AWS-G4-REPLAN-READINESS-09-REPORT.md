# RIS-SCV-AWS-G4-REPLAN-READINESS-09

**Status:** `RIS-SCV-AWS-G4-REPLAN-09 — LOCAL READY / AWS APPROVAL PENDING`

**Date:** 2026-11-14

**Task:** `MAYS-SCV-RC3-001`

**Mode:** local release readiness only. No AWS API, state read, Terraform plan or apply.

## 1. Git baselines

| Ref | HEAD | State |
|---|---|---|
| RIS `origin/main` | `df3c0329f399daa7ff0f9f0bbb71bb2a017140f9` | unchanged |
| RIS RC1 | `4bfd08f7a3afa82cf788fc8da505d9cbae6b91b1` | unchanged |
| RC2 | `release/structured-cv-rc2-reconciled @ 6eeab5d37edc0eb8dabf284f0c5e9dc173b82751` | local verified, pushed |
| Rejected plan | `36632ab510cbef32030e111d82465aa7b2f8b65b2913181d107aa9021b79a57b` | unchanged, DO NOT APPLY |

RC2 is not merged into main. No force-push or branch rewrite occurred.

## 2. Protected plan inputs

The existing protected operator file for the live `ris-dev` values was identified locally. It
matches the live state serial 61 values for all four consent controls, including the scoped pilot
allowlist. The allowlist value is deliberately not reproduced in this report, Git, CI logs or an
unprotected Terraform artifact.

A dedicated RC2 plan-input copy was prepared at:

`/tmp/opencode/ris-scv-rc2-09/protected/ris-dev.tfvars.json`

| Property | Verified value |
|---|---|
| File mode | `0600` |
| Allowlist | present, non-empty, length 106; value withheld |
| `CONSENT_NOTICE_STATE_ENFORCED` | false (live value) |
| `CV_STORAGE_CONSENT_ENFORCED` | true (live value) |
| `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` | true (live value) |
| Orders boundary | present in protected input |
| Structured-CV flag | false |
| Project/environment/region | `ris-dev` / `dev` / `eu-central-1` |

Non-sensitive live inputs:

- Documents CORS: one origin `https://www.mays-job-matcher.app`, methods `GET`, `HEAD`, `PUT`,
  exposed header `ETag`, max age 900; no origin wildcard.
- Health publisher schedule: `rate(15 minutes)`.
- Orders boundary: `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`.
- Structured-CV stays disabled: `STRUCTURED_CV_PROFILE_ENABLED=false`.

## 3. Pinned Orders builder

The pinned builder was verified at source commit
`1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d` (`installer/mays-orders-builder.pinned.json`).

The builder wrapper had two Windows-only defects: a hardcoded
`C:\Program Files\Git\bin\git.exe` and a Windows `where`/`terraform.exe` lookup. It was corrected
to use `GIT_EXE` (default `git`) and `shutil.which("terraform")`.

Evidence:

- Builder correction commit: `17a828b`.
- Two consecutive builds at the pin produced **byte-identical module files** (excluding the
  timestamped manifest).
- Generated module manifest source: `1dbb0cb`.
- Orders Lambda artifact: SHA-256 `b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b`.
- Builder tests: cross-platform guard PASS; module `fmt`, `init -backend=false`, `validate` PASS.
- Follow-up module default alignment: `6eeab5d` (`ris-dev-mays-orders`, no `ris-dev2` default).
- No foreign module version was used.

A network fetch is still required to materialize the pinned builder clone; no AWS call is made by
the builder.

## 4. Local release check

| Check | Result |
|---|---|
| Six Structured-CV routes | present |
| `gsi-structured-owner` | present |
| Partner erasure route | present |
| Documents CORS | present, exact approved origin |
| Four consent flags | present and wired |
| `dynamodb:ConditionCheckItem` | present |
| Orders permissions boundary | present via project config |
| Health schedule | 15 minutes |
| `STRUCTURED_CV_PROFILE_ENABLED` | false |
| Focused reconciliation/consent/Structured-CV tests | **249 PASS** |
| Builder/cross-platform tests | **10 PASS** |
| Full RIS suite | **2634 PASS / 56 skipped / 5 pre-existing failures** |
| XRepo receiver suite | **82 PASS / 4 subtests** |
| Terraform `fmt -check -recursive` | PASS |
| Terraform `validate` (`-backend=false`) | PASS with deprecation warnings |
| New AWS plan | **NOT EXECUTED** |

The five full-suite failures reproduce on RC1 and were not changed:

- 3 × `test_composite_lifecycle.py::TestOrchestratorArgOrdering`
- 1 × `test_health_plane_integration.py::TestPipelineEmitsHealthEvents`
- 1 × `test_platform_handlers.py::TestAgentAPI::test_execute_agent`

No test was weakened to hide a failure.

## 5. RC2 release diff

| Resource | Live baseline | RC1 plan | RC2 target |
|---|---|---|---|
| Erasure route | present | DELETE | retained |
| Documents CORS | present | DELETE | retained |
| Consent flags | active per live config | REMOVE | retained |
| `ConditionCheckItem` | present | REMOVE | retained |
| Orders boundary | present | REMOVE | retained |
| Health schedule | 15 min | 5 min | 15 min |
| Structured-CV routes | missing | CREATE | CREATE |
| Structured-CV GSI | missing | UPDATE | UPDATE |

Additional hardening: health/reader Lambda `filename` churn is ignored so local absolute paths do
not create unintended Lambda updates; source-code hashes remain active.

## 6. Open risks

1. **No RC2 AWS plan yet.** The actual delta is unverified until a separately authorized G4 run.
2. **Protected allowlist** must be supplied from the `0600` operator file; never committed.
3. **Live state drift** must be re-read at G4; serial 61 is only the last verified baseline.
4. **Builder fetch** requires network access to the pinned repository; no foreign module version
   may be substituted.
5. The five pre-existing test failures remain separate from this release.
6. The generated Orders module is ignored by Git; the RC2 plan must build it from the pin.

## 7. G4 replan gate

**G4 replan authorization: NOT GRANTED. This task did not use the earlier RC1 G4 approval as an
RC2 approval.**

Proposed target for a separate authorization:

```text
Environment: ris-dev
Account:     240571105849
Region:      eu-central-1
Profile:     mayaws
Workspace:   ris-dev
Backend:     mays-ris-tf-state-dev
State Key:   env:/ris-dev/dev/terraform.tfstate
Lock Table:  mays-ris-tf-lock
Release:     RC2 6eeab5d
```

After explicit authorization, and only then:

1. Re-run STS identity and target checks.
2. Re-read state lineage/serial and effective backend key.
3. Validate the protected plan inputs and build the pinned Orders module.
4. Run init/validate/plan, record the new plan SHA-256.
5. Review the complete resource diff independently for G5.
6. STOP immediately on any DELETE/REPLACE, consent/IAM/CORS/route/boundary removal, schedule
   change, Cognito/CloudFront/DNS change or unexpected state drift.

## 8. Boundaries

- No Terraform apply.
- No state import, mutation or destroy.
- No AWS plan.
- No consent activation.
- No production deployment.
- No main merge.
- No XRepo `COMPLETED`; task remains `IMPLEMENTING`.

**RIS-SCV-AWS-G4-REPLAN-09 — LOCAL READY / AWS APPROVAL PENDING**

**STOP BEFORE APPLY.**
