# RIS-APPLICATION-DEPLOY-03F — ApplicationV1 AWS E2E

**Result:** **BLOCKED — Apply did not complete**

## Test gate

AWS E2E execution was not started because the authorized Apply failed before
resource mutation. The ApplicationV1 table and routes are absent, so CRUD,
authorization, privacy and erasure E2E tests cannot be executed truthfully.

No synthetic application data, tokens, credentials, documents or model calls
were sent to AWS.

## Matrix

| Area | Result | Reason |
|---|---|---|
| Create / Get / List | BLOCKED | ApplicationV1 table and routes not deployed |
| Update / status / history | BLOCKED | ApplicationV1 routes not deployed |
| Cover-letter versioning | BLOCKED | route/table not deployed |
| Pagination / version conflict | BLOCKED | route/table not deployed |
| Idempotent create retry | BLOCKED | route/table not deployed |
| Export / delete | BLOCKED | route/table not deployed |
| Missing/invalid JWT tests | BLOCKED | no ApplicationV1 route deployment; no auth bypass used |
| Partner/identity isolation | BLOCKED | no deployed ApplicationV1 endpoint or approved test identities |
| Privacy inspect/export | BLOCKED | ApplicationV1 persistence not installed |
| Resumable erasure E2E | BLOCKED | no deployed ApplicationV1 data; global flags remain disabled |
| Health/API regression | NOT RUN | Apply failure gate; no mutation verification run |
| CloudWatch post-deploy verification | NOT RUN | no deployment occurred |

## Read-only evidence

After the failed Apply, read-only checks found:

- state serial still `23` and lineage unchanged;
- no `ris-dev2-dev-applications` table;
- no `/v1/partner/me/applications` routes;
- Agent Lambda remained Active with successful prior update status and no
  ApplicationV1 environment binding;
- protected CloudFront remained deployed and enabled.

## Security and privacy boundary

No authentication was bypassed and no test identity was invented. No global
privacy, erasure, freeze or cutover flag was enabled. Jobsearch integration
remained out of scope.

AWS E2E can only be reconsidered after a separately authorized retry of the
exact plan succeeds and the post-Apply guards pass.

## 03H resume result

The explicitly approved resume attempt also stopped before resource mutation
with Terraform exit code `1` because the saved plan's dependency selections
did not match the current Terraform working data:

```text
Error: Inconsistent dependency lock file
```

Read-only verification again found state serial `23`, no ApplicationV1 table,
no ApplicationV1 routes and an unchanged Agent Lambda. No AWS E2E test was
started and no retry was performed.

## 03L Apply and E2E update

The separately approved 03J plan was applied successfully with exit code `0`:

```text
Apply complete! Resources: 11 added, 1 changed, 0 destroyed.
```

Read-only verification confirmed the ApplicationV1 table and GSI are ACTIVE,
all nine JWT-protected ApplicationV1 routes exist, and the agent Lambda is
Active with `LastUpdateStatus=Successful`. CloudFront remained deployed and
enabled with its prior origin/OAC configuration.

Negative authentication tests passed for all nine ApplicationV1 routes:
missing JWT, invalid JWT, and credential-without-JWT each returned `401` (27/27
expected responses). Positive CRUD, isolation and privacy tests remain
**BLOCKED** because no authorized Cognito identity and partner credential were
available. No real applicant data or authentication boundary bypass was used.
