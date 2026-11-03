# RIS-APPLICATION-E2E-04F — Regression & Final Readiness

**Result:** **READ-ONLY REGRESSION PASS / POSITIVE E2E BLOCKED**

## Infrastructure regression

No Terraform plan, apply, state mutation, Cognito mutation, CloudFront/DNS/ACM
change, or pipeline action was performed.

| Check | Result | Evidence |
|---|---|---|
| RIS health | PASS | CloudFront health page returned HTTP `200` |
| Agent Lambda | PASS | `Active`, `LastUpdateStatus=Successful` |
| ApplicationV1 API | PASS | 9 routes present; JWT authorizer `9i4w8r` |
| ApplicationV1 table | PASS | `ris-dev2-dev-applications` `ACTIVE` |
| ApplicationV1 GSI | PASS | `gsi-owner` `ACTIVE` |
| API authorizer | PASS | JWT type; external issuer `eu-central-1_ojbmoiYGM`; one configured audience |
| Existing profile/CV route surface | PASS | Existing route metadata remains present; no route mutation performed |
| CloudWatch errors | PASS | 0 matching `ERROR`/`Error`/`Exception` events in agent log group during the last 24 hours |
| CloudFront `E1IZKHFPZ5X7SN` | PASS | `Deployed`, enabled, same observed ETag `E23ZP02F085DFQ` and one origin |
| CloudFront OAC | PASS | Existing OAC/origin configuration observed unchanged from 03L baseline |
| Cognito reference | PASS | Authorizer still references the external Cognito issuer; no Cognito mutation |
| Route53 / DNS | READ-ONLY BASELINE | No hosted zones visible in the Foundation account; no DNS action performed |
| ACM | READ-ONLY BASELINE | No certificates visible in `eu-central-1` of the Foundation account; no ACM action performed |
| State lineage | PASS | `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, serial `24` |
| Execution flags | PASS | Privacy/erasure/freeze/cutover flags remain disabled |

The account boundary was verified as AWS account `262370457690`, profile
`default`, region `eu-central-1`. The external Cognito identity is not treated
as a resource of that Foundation account.

## Final readiness matrix

| Bereich | Ergebnis |
|---|---|
| Identity Discovery | BLOCKED — no authorized synthetic identity/credential |
| Positive JWT-/Partner-Auth | BLOCKED |
| Negative Auth | PASS — prior 03L baseline 27/27 expected `401`; no new positive auth run |
| ApplicationV1 CRUD | BLOCKED |
| Status und Versionierung | BLOCKED |
| Idempotenz | BLOCKED |
| Export | BLOCKED |
| Cross-Identity-Isolation | BLOCKED — second identity required |
| Privacy Inspect/Export | BLOCKED |
| Erasure AWS E2E | BLOCKED |
| Synthetisches Cleanup | NOT APPLICABLE — no data created |
| Protected Infrastructure | UNCHANGED |
| Terraform-State | UNCHANGED — serial `24`, lineage unchanged |
| Jobsearch Integration | NOT IN SCOPE |
| DSGVO-Produktionsfreigabe | NOT GRANTED |

## Required next authorization

To resume 04B–04E, provide an explicitly authorized synthetic Cognito test
identity and a separately authorized active partner credential, plus a second
authorized identity for complete isolation coverage. Values must be supplied
through a secure approved handoff; no token or secret should be placed in the
repository or report.

```text
POSITIVE AUTH E2E BLOCKED — TEST IDENTITY REQUIRED
```
