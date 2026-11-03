# RIS-DEV2-AUTH-06E — Deployment and Recovery Plan

## Decision

```text
DEPLOYMENT BLOCKED — NO DEPLOYMENT AUTHORIZATION
```

This phase prepared the release plan only. No `aws lambda update-function-code`,
Terraform plan/apply, alias mutation, API Gateway deployment, rollback or other
AWS write was executed.

## Release scope

The intended later change is limited to the Terraform-managed agent Lambda:

- function: `ris-dev2-dev-agent`;
- ARN: `arn:aws:lambda:eu-central-1:262370457690:function:ris-dev2-dev-agent`;
- artifact: `terraform/lambda.zip`;
- runtime/handler: `python3.14` / `handler.lambda_handler`.

The release must not change environment variables, IAM, API Gateway,
authorizers, DynamoDB, S3, Cognito, CloudFront, DNS or ACM. No alias strategy
exists today; only `$LATEST` was discovered. A later release must preserve
that architecture unless separately approved.

## Safe execution sequence for a future approval

1. Re-verify profile, account, region, state lineage/serial and protected
   resource baseline.
2. Rebuild with `python lambda/build_zip.py --bundle agent` and verify the
   approved SHA-256/Base64 digest.
3. Re-read the Lambda `RevisionId` immediately before any operation and stop if
   it differs from the recorded value.
4. Run the existing Terraform package/plan workflow in read-only review mode;
   accept only a code-hash/function-code change for this function. Any IAM,
   environment, API, database, identity, replacement or destroy action is a
   stop condition.
5. Obtain separate explicit approval naming the exact artifact digest, Lambda
   ARN, Terraform plan and revision guard.
6. Apply only through the existing Terraform owner workflow. Do not substitute
   a direct Lambda API update.
7. Re-read configuration, revision, code hash and status, then execute the
   documented smoke tests. No automatic retry after an ambiguous result.

## Recovery evidence

The current deployed package was downloaded read-only to:

```text
C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-auth-06-previous-lambda.zip
```

It matches the discovered Lambda `CodeSha256` and revision:

- SHA-256 hex: `45ae52c1f3cc455f0e5dd1f64482eb6a02bbee7a3117a260d58bd20b81c54c38`;
- Lambda-compatible Base64: `Ra5SwfPMRV8OXdH2RILragK77noxF6Jg1YvSC4HFTDg=`;
- revision: `f3719946-b052-48a5-bd62-750ffc54dcab`.

The recovery ZIP is not committed. A rollback would require a separate
decision, a new reviewed Terraform plan using that exact source artifact, and
the same revision/concurrency checks. Restoring Lambda code does not undo data,
identity or infrastructure changes.

## Post-release smoke plan

After a separately approved release, verify Lambda `Active/Successful`, Health
HTTP 200, negative JWT 401, valid JWT without partner credential as the
controlled contract error (not dispatcher 500), unchanged authorizers/pool/
CloudFront, active DynamoDB tables/GSI, and absence of unexpected Lambda
errors. A new secure test JWT is required for the positive partner-boundary
smoke; none is retained here.
