# RIS-SCV-AWS-LIVE-BASELINE-RECONCILIATION-08

**Status:** `RIS-SCV-AWS-LIVE-BASELINE-RECONCILIATION-08 — LOCAL VERIFIED / G4 REPLAN APPROVAL PENDING`

**Date:** 2026-11-14

**Task:** `MAYS-SCV-RC3-001`

**Mode:** local code reconciliation, tests and documentation. No AWS mutation, no new AWS plan.

## 1. Git baselines

| Ref | HEAD | Use |
|---|---|---|
| RIS `origin/main` | `df3c0329f399daa7ff0f9f0bbb71bb2a017140f9` | current main/XRepo |
| RIS `release/structured-cv-rc1` | `4bfd08f7a3afa82cf788fc8da505d9cbae6b91b1` | unchanged baseline |
| Live `ris-dev` state | serial `61`, lineage `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` | G4-07 evidence |
| New release branch | `release/structured-cv-rc2-reconciled` | `ee0905a09c69a0cad1734fac326506b1db440392` |

`release/structured-cv-rc1` was not modified. No main mutation, merge into main, force-push or
rebase of RC1 occurred.

## 2. Origin of the live deviations

The rejected G4 plan was generated from RC1 plus a generated Orders module. RC1 did not contain
the later live-baseline line. The functions were reconstructed from the verified
`feature/jm-ris-cv-storage-integration-01` history:

| Live function | Origin commit | Deployment evidence | RC1 plan |
|---|---|---|---|
| Partner erasure route | `451c12e` | `MAYS-P3-FINAL`: live `POST /v1/partner/me/erasure`, API `c7e9pdwe78` | DELETE |
| Documents CORS + consent flags | `216e061` | live state serial 61; CORS exact one-origin rule; CV/search consent gates | DELETE CORS / REMOVE flags |
| Notice-state flag | `81634d8` | current runtime env | REMOVE |
| Scoped pilot allowlist | `37503a9` | current runtime env (value intentionally not in Git) | REMOVE |
| Search-profile consent flag | `fc32aad` | current runtime env | REMOVE |
| `ConditionCheckItem` | `48a55c1` | live partner-profile policy | REMOVE |
| Orders boundary root wiring | `197fb1c` | live Orders worker role has boundary | REMOVE (config default null) |
| Health schedule 15 min | `74e766c` | applied RIS health schedule report | 5 min |
| Structured CV routes/GSI | RC1 `4bfd08f` | not live | CREATE/UPDATE |

`main` is not the complete live infrastructure definition: the live baseline exists on the
deployed feature line and in the state, while RC1 carried the Structured-CV delta. RC2 merges
both lines instead of recreating values from unconfirmed state inspection.

## 3. Restored Terraform definitions

- Partner edge route list again includes `POST /v1/partner/me/erasure`; it uses the existing
  partner API and JWT authorizer, not a parallel route.
- Documents module again defines `aws_s3_bucket_cors_configuration.documents` with the existing
  single approved origin `https://www.mays-job-matcher.app`, methods `PUT/GET/HEAD`, exposed
  `ETag`, max age 900; no origin wildcard.
- Agent Lambda environment again includes:
  `CONSENT_NOTICE_STATE_ENFORCED`, `CONSENT_PILOT_ALLOWLIST`,
  `CV_STORAGE_CONSENT_ENFORCED`, `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`.
  The pilot allowlist value remains outside Git and must be supplied from protected operator
  configuration at plan time.
- Partner-profile policy again includes `dynamodb:ConditionCheckItem`.
- Orders module call again accepts `lambda_execution_boundary`; `ris-dev` project config supplies
  the existing `Mays-Orders-Lambda-Execution-Boundary` ARN. The repository does not hardcode it in
  root `main.tf`/`variables.tf`.
- Health publisher schedule is `rate(15 minutes)`, preserving live behavior.
- Structured-CV remains default-off: `STRUCTURED_CV_PROFILE_ENABLED=false`; six routes and
  `gsi-structured-owner` remain defined.

`terraform/modules/lambda/main.tf` now combines the four live consent controls with the
Structured-CV flag. `terraform/main.tf` passes all five inputs. The consent contract keeps all
four purposes, including separate `cv-storage`, `search-profile-storage` and DRAFT
`cv-builder-profile-storage`.

## 4. Security effect

- No consent gate was weakened; the scoped proof validation and the structured-CV DRAFT
  fail-closed check are both retained.
- No IAM wildcard was added.
- No permissions boundary was removed.
- No origin wildcard was introduced.
- No Cognito, CloudFront, DNS/ACM, or existing table/data deletion was introduced.
- The old plan `36632ab5…` remains rejected and is not a release basis.

## 5. Tests

| Check | Result |
|---|---|
| Focused reconciliation/consent/Structured-CV tests | **249 PASS** |
| Full RIS suite | **2634 PASS / 56 skipped / 5 failed** |
| XRepo receiver suite | **82 PASS / 4 subtests** |
| `terraform fmt -check -recursive` | PASS |
| `terraform validate` (backend=false) | PASS with deprecation warnings |
| New static baseline regression guards | PASS |
| New AWS plan | NOT EXECUTED |

The five full-suite failures are pre-existing on RC1 and reproduce identically there:

- 3 × `test_composite_lifecycle.py::TestOrchestratorArgOrdering`
- 1 × `test_health_plane_integration.py::TestPipelineEmitsHealthEvents`
- 1 × `test_platform_handlers.py::TestAgentAPI::test_execute_agent`

They are not caused by the RC2 baseline merge. No test was weakened to make the suite green.

## 6. Release diff

| Resource | Live baseline | RC1 plan | RC2 target |
|---|---|---|---|
| Erasure route | present | DELETE | retained |
| Documents CORS | present | DELETE | retained |
| Consent flags | active per live config | REMOVE | retained |
| `ConditionCheckItem` | present | REMOVE | retained |
| Orders boundary | present | REMOVE | retained via project config |
| Health schedule | 15 min | 5 min | 15 min |
| Structured-CV routes | missing | CREATE | CREATE |
| Structured-CV GSI | missing | UPDATE | UPDATE |

## 7. RC2 state

- Branch: `release/structured-cv-rc2-reconciled`
- HEAD: `ee0905a09c69a0cad1734fac326506b1db440392`
- Pushed to `origin/release/structured-cv-rc2-reconciled`.
- RC1 remains `4bfd08f7a3afa82cf788fc8da505d9cbae6b91b1`.
- RC2 has not been merged into main and has no AWS plan.

## 8. Missing or unresolved evidence

1. **Consent allowlist value:** the current live identity scope is intentionally not committed.
   A G4 replan must pass it from protected operator configuration. Without it, the plan would
   still remove `CONSENT_PILOT_ALLOWLIST`.
2. **Generated Orders module:** `terraform/modules/mays_orders` is generated/ignored. The local
   builder wrapper currently has a Windows-only Git executable path; it was not changed here.
   A replan must use the pinned generated module or a separately approved builder fix.
3. **Live CORS exactness:** the restored module default matches the serial-61 state (one origin,
   no wildcard), but no new AWS read was performed in this task.
4. **No RC2 plan:** by instruction, no AWS plan was created. The next plan must be authorized
   separately.

## 9. Risks

- RC2 is locally verified only; the actual plan delta is unknown until a new G4 run.
- A plan without the protected allowlist value would reintroduce the consent-pilot removal.
- The generated Orders module must be reproducible before G4 approval.
- The five pre-existing full-suite failures remain separate from this release work.
- No feature flag, consent notice or production route was activated.

## 10. G4 replan recommendation

**Recommendation: prepare G4 replan, do not apply.**

Before requesting the new plan:

1. Supply the live `CONSENT_PILOT_ALLOWLIST` only via protected, uncommitted operator input.
2. Build the Orders module from the pinned builder or an approved reproducible artifact.
3. Run G4 against RC2 `ee0905a`, not the rejected RC1 plan.
4. Require the new plan to contain only the six Structured-CV route creates and the
   `gsi-structured-owner` update, plus the expected agent bundle/flag update.
5. STOP on any delete/replace, any consent/IAM weakening, any CORS removal, or any unexpected
   health schedule change.

No Terraform Apply, state mutation, import, destroy, consent activation, main merge or production
deployment was performed.

**RIS-SCV-AWS-LIVE-BASELINE-RECONCILIATION-08 — LOCAL VERIFIED / G4 REPLAN APPROVAL PENDING**

XRepo task `MAYS-SCV-RC3-001` remains `IMPLEMENTING`.
