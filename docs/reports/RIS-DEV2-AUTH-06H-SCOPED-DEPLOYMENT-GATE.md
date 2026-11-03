# RIS-DEV2-AUTH-06H — Scoped Deployment Gate

## Final decision

```text
READY FOR CONTROLLED APPLY
```

This is a readiness decision only. No Terraform apply, Lambda update, alias
change or other AWS mutation was executed.

## Gate evidence

- verified active RIS root: `terraform/`;
- scoped `terraform fmt -check -recursive`: **PASS**;
- scoped `terraform init -backend=false`: **PASS**;
- scoped `terraform validate`: **PASS**, with existing DynamoDB deprecation
  warnings only;
- no active RIS dependency on
  `installer/projects/mays_order_builder/terraform/main.tf`;
- identity/API regression: **59 passed, 304 subtests passed**;
- full RIS functional selection: **177 passed, 304 subtests passed**;
- packaging: **6 passed, 2 skipped**;
- packaging skips explicitly require unavailable `mayaws` credentials for live
  checks; deterministic local packaging checks all pass;
- artifact SHA-256 matches the required value:
  `f2630322a6887fef860552264f6c6fbeb4e1e8985acc7dbe612e99b6dea8d613`;
- saved plan SHA-256 matches the required value:
  `7cfcbf7ba2a5986e9529224890b68b81bf32ce3fb9e96ef47ed82cfe5e570a8e`;
- state serial: `25`;
- state lineage: `a0bd361d-5cd1-a207-a8c0-e6888f0be082`;
- recovery artifact exists and was hash-verified.

## Authorized scope for a future controlled apply

The existing saved plan contains exactly:

```text
0 creates / 1 in-place update / 0 deletes / 0 replacements
module.lambda.aws_lambda_function.agent
```

The only intended change is the Lambda `source_code_hash`; the computed
`last_modified` is expected. No environment, IAM, layer, runtime, handler,
API Gateway, Cognito, DynamoDB, CloudFront, DNS, ACM, Health Lambda or other
protected-resource change is authorized.

The global format command may still report the unrelated ignored builder-clone
file, but that file is outside the verified RIS root and does not block this
scoped RIS deployment gate.

## Next action

After explicit deployment approval, execute only the existing saved Terraform
plan through the verified `ris-dev2` backend/workspace. Reconfirm the account,
region, state serial/lineage and plan hash immediately before apply, then
verify the Lambda revision and `CodeSha256`. Do not use a direct AWS Lambda
code update or create a replacement plan without a new review.
