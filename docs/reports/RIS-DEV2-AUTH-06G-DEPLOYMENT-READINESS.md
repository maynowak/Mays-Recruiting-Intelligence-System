# RIS-DEV2-AUTH-06G — Deployment Readiness

## Decision

```text
DEPLOYMENT BLOCKED — EXACT REMAINING CAUSE:
terraform fmt -check -recursive fails on the unrelated existing file
installer/projects/mays_order_builder/terraform/main.tf
```

No Terraform apply, Lambda update, alias change or other AWS mutation was
executed.

## Completed gates

- G1 Windows packaging recovery: **PASS**;
- packaging suite: **6 passed, 2 pre-existing live-contract skips**;
- functional regression suite: **177 passed, 304 subtests passed**;
- ZIP structure, handler alias, dispatcher fix and forbidden-file checks:
  **PASS**;
- Python 3.14.10 compileall: **PASS**;
- Python 3.14.10 ZIP import smoke: **PASS**;
- artifact SHA-256:
  `f2630322a6887fef860552264f6c6fbeb4e1e8985acc7dbe612e99b6dea8d613`;
- Terraform init without backend: **PASS**;
- Terraform validate: **PASS**, with existing `range_key` deprecation warnings;
- saved Terraform plan scope: **PASS**, exact Agent Lambda code-only update.

The G2 format gate is not green because the unrelated installer project file
is unformatted. That file was not modified in this work and remains outside
the requested Lambda deployment scope.

## Saved plan and state checkpoint

```text
Plan: C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-auth-06g.tfplan
Plan SHA-256: 7cfcbf7ba2a5986e9529224890b68b81bf32ce3fb9e96ef47ed82cfe5e570a8e
AWS account: 262370457690
Region: eu-central-1
Workspace: ris-dev2
State serial: 25
State lineage: a0bd361d-5cd1-a207-a8c0-e6888f0be082
```

The plan contains exactly:

```text
0 creates / 1 in-place update / 0 deletes / 0 replacements
module.lambda.aws_lambda_function.agent
```

Only `source_code_hash` changes intentionally; `last_modified` is computed by
AWS. No environment, IAM, layer, runtime, handler, API Gateway, Cognito,
DynamoDB, CloudFront, DNS, ACM or Health Lambda change is planned.

## Recovery and protected resources

The read-only previous deployed artifact is secured at:

```text
C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-auth-06-previous-lambda.zip
SHA-256: 45ae52c1f3cc455f0e5dd1f64482eb6a02bbe7a3117a260d58bd20b81c54c38
```

Its digest corresponds to the currently deployed Lambda `CodeSha256`
`Ra5SwfPMRV8OXdH2RILragK77noxF6Jg1YvSC4HFTDg=`. Recovery, if required after
an approved deployment, is a Terraform-managed code deployment of that
artifact followed by a fresh read-only plan and verification; no direct AWS
CLI code update is authorized.

Protected resources for this release are the Health Lambdas, IAM, environment
variables, layers, runtime/handler, API Gateway, Cognito, DynamoDB, CloudFront,
DNS and ACM. The saved plan leaves all of them unchanged.

## Next controlled action

1. The owner of `installer/projects/mays_order_builder/terraform/main.tf`
   must resolve or formally clear the unrelated format-gate failure.
2. Re-run the read-only account/state/Lambda preflight and regenerate the plan
   immediately before deployment.
3. If the regenerated plan remains exactly the documented one-resource scope,
   obtain explicit approval for the Terraform apply of the saved plan.
4. Apply only through Terraform; verify Lambda revision and `CodeSha256` after
   apply, then run the documented recovery/health checks.

Until step 1 is cleared and the plan is revalidated, the correct release
decision is not `READY FOR CONTROLLED APPLY`.
