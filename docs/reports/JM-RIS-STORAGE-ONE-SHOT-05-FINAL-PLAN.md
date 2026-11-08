# JM-RIS-STORAGE-ONE-SHOT-05 — FINAL PLAN & APPROVAL

## Result

`RIS-DEV TERRAFORM PLAN CLEAN — READY FOR FINAL REVIEW`

`APPROVED FOR LIMITED BETA PILOT — NOT GENERAL AVAILABILITY`

No apply, deployment, push, merge, or live write was performed.

## 1. Operator approval record

| Field | Value |
| --- | --- |
| Text | `application-storage-consent-2026-11-07-v4` |
| SHA-256 | `8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7` |
| RIS notice | `application-storage/1.0` |
| Notice state | **APPROVED** (not `ACTIVE`) |
| `legalApprovalRef` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` |
| Approval date | `2026-11-08` |
| Approval body | Betreiberin May's Job Matcher |
| Scope | Limited beta pilot; only the confirmed operator identity |
| RIS commit | `6bfb71f` |

Open and explicitly not confirmed:

- full account deletion / ApplicationV1 account erasure;
- final consent-history retention period;
- DPA/transfer review for AWS/Vercel;
- general rollout or other users.

## 2. Final Terraform plan

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-one-shot-05-v4-final.tfplan` |
| Plan SHA-256 | `d9689931cab89181ec9262407b85dd37ec107f8ae5db32d1241163a6a0a6d532` |
| Terraform | `1.16.1` |
| State | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| State serial / lineage | `42` / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Changes | **272 no-op, 1 update, 0 deletes, 0 replacements** |
| Apply | **not executed** |

### Active change

`module.lambda.aws_lambda_function.agent` — **UPDATE**

- Code hash: `783PJahGgBAGcS3cbwd7SNhc5o5RQNKplp9/RAxEEio=` →
  `xcbJ2JEI3ouo7VRXMT1nOtei7wlvQEhdTPhKNzJDA1U=`
- Env additions:
  - `CONSENT_NOTICE_STATE_ENFORCED="false"`
  - `CONSENT_PILOT_ALLOWLIST=<confirmed operator issuer|sub>`
- Global gates unchanged; notice is `APPROVED`, not `ACTIVE`.

### NO-OP confirmation

- Orders SQS Queue Policy: unchanged
- Orders Worker IAM Role / permissions boundary: unchanged
- Health Publisher / Health Writer: unchanged
- Orders Reader: unchanged
- Cognito: unchanged
- CloudFront: unchanged
- DNS/Route53: unchanged
- ACM: unchanged
- DynamoDB: unchanged
- API Gateway routes/integrations: unchanged
- Partneredge: unchanged

### Temporary module compatibility

The plan uses Mays-Orders module revision `c1dcca2`, which still contains
the deployed SQS queue policy. The IAM boundary is passed explicitly via the
new `mays_orders_lambda_execution_boundary` variable. This is a temporary
compatibility measure; F-03 (removal of the wildcard queue policy) remains a
separate remediation. The existing policy and boundary must not be changed in
this pilot.

## 3. Vercel Production configuration plan

Target: `https://www.mays-job-matcher.app`, project `maymilly/mays-job-matcher`.
No preview target, no production change yet.

Server-side (names; secret values never printed):

```text
RIS_API_BASE_URL
RIS_PARTNER_CREDENTIAL
RIS_COGNITO_ISSUER
RIS_COGNITO_CLIENT_ID
RIS_APPLICATION_STORAGE_ENABLED=true
RIS_CONSENT_SERVICE_ENABLED=true
RIS_CONSENT_NOTICE_VERSION=1.0
RIS_CONSENT_TEXT_VERSION=application-storage-consent-2026-11-07-v4
RIS_CONSENT_TEXT_SHA256=8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7
RIS_CONSENT_TEXT_STATE=APPROVED
RIS_TEST_USER_ALLOWLIST=<confirmed operator issuer|sub>
```

Frontend:

```text
VITE_RIS_APPLICATION_STORAGE_ENABLED=true
VITE_RIS_CONSENT_UI_ENABLED=true
```

The existing per-user capability gate prevents non-allowlisted accounts from
entering remote mode; they remain in session mode. No preview is used as the
release target.

## 4. Exact apply/deploy/E2E sequence

1. Apply the saved plan `d9689931…` exactly; no new plan, no target/replace.
2. Verify Lambda `ris-dev-dev-agent` State=Active, code hash
   `xcbJ2JEI3ouo7VRXMT1nOtei7wlvQEhdTPhKNzJDA1U=`, env has the confirmed
   `CONSENT_PILOT_ALLOWLIST`, and global gates remain false.
3. Verify consent/application routes and partner edge; run negative
   non-allowlisted check.
4. Jobsearch: run final focused tests, create regular PR, verify CodeQL/Vercel
   checks, merge to `main` (merge commit).
5. Confirm production Vercel deployments of both projects are READY at the
   merge SHA.
6. Set production Vercel env to the values above (secrets are set through the
   approved secret process; no values in reports). Do not enable any general
   rollout.
7. Deploy/redeploy production with the approved commit and env.
8. Verify `www.mays-job-matcher.app`, login, privacy v1.1, consent UI, and
   non-allowlisted session behavior.
9. E2E with the confirmed operator account and synthetic data:
   load full v4 text and hash; explicit Art. 9 checkbox; grant `GRANTED`;
   create application; verify RIS `applicationId`/`ownerId`; reload; close
   browser; new session/login; reload application; update; export; withdraw;
   new write `403 CONSENT_REQUIRED`; read/export/delete; delete; verify absent.
10. Cleanup synthetic data; record actual HTTP/browser/RIS evidence and
    deployment IDs.

## 5. Rollback plan

- No apply has occurred; current state is unchanged.
- After a future apply: restore Lambda code hash
  `783PJahGgBAGcS3cbwd7SNhc5o5RQNKplp9/RAxEEio=`, remove the pilot allowlist,
  keep global gates false.
- Disable production `VITE_RIS_APPLICATION_STORAGE_ENABLED` and redeploy the
  previous known-good Jobsearch commit; users return to session mode.
- Do not delete existing applications or consent records; keep data available
  for export/deletion.
- Do not change Orders SQS policy or IAM boundary during rollback.

## 6. Final approval gate

Required exact GO:

```text
GO JM-RIS-STORAGE-ONE-SHOT-05 APPLY + DEPLOY + E2E
```

No apply, merge, or deployment before this GO. Consent v4 is approved for the
limited pilot, but general availability remains explicitly excluded.
