# RIS-R08-DEV2 — Cross-Team Findings

| ID | Severity | Component | Reproduction | Expected | Actual | Owner | Next step |
|---|---|---|---|---|---|---|---|
| F-15-01 | High | RIS Backend/Auth | Synthetic user; valid auth; call metrics | JWT + tenant/partner context reaches route | `401 Unauthorized`, `no-store, private`; access token lacks tenant claim | RIS Backend + Auth | define and verify access-token tenant claim contract |
| F-15-02 | High | RIS Backend/Partner binding | Call partner routes without credential | bounded auth error and approved binding | No approved RIS partner/API credential; CRUD blocked | RIS Backend/Security | provide tenant-scoped RIS admin binding |
| F-15-03 | Medium | API/Jobsearch Frontend | Inspect API metadata | agreed browser integration path | API Gateway `CorsConfiguration=null` | Shared API/Auth | choose BFF or explicit CORS contract |
| F-15-04 | Medium | Health presentation | `GET https://d3axlsioawbq92.cloudfront.net/health` | public health response | CloudFront/S3 returned `403 AccessDenied`; distribution deployed | RIS Infrastructure | investigate OAC/public-health contract; no fix applied |
| F-15-05 | High | Privacy E2E | Attempt application/erasure flow | synthetic lifecycle complete | not executed; no synthetic application data existed | RIS Backend/Security | separate approved CRUD/erasure run |
| F-15-06 | Medium | Recovery | inspect ledger/PITR/restore | ledger writes and restore evidence | PITR live; ledger empty/disabled; restore not executed | RIS Infrastructure/Privacy | separate staging restore plan |

## Classification

* **IMPLEMENTED:** Terraform PITR/ledger infrastructure, disabled bindings,
  Lambda and metrics route.
* **VERIFIED LIVE DEV2:** Apply, state serial 27, PITR 35 days, ledger ACTIVE,
  IAM, Lambda ACTIVE/SUCCESSFUL, API route, queue mapping, synthetic auth and
  cleanup.
* **BLOCKED:** Application CRUD, pagination, metrics success, partner binding,
  SQS retry/replay, public erasure, inspect/export and restore.
* **NOT TESTED:** mutating application data and queue messages by design.
* **PRODUCTION APPROVED:** no.
