# RIS-DEV2-AUTH-06G3 — Terraform Code Deployment Plan

## Result

```text
PASS — EXACT LAMBDA CODE-ONLY PLAN
```

No Terraform apply, Lambda mutation, alias change or other AWS write was
performed.

## Read-only preflight

- AWS account: `262370457690`;
- region: `eu-central-1`;
- workspace: `ris-dev2`;
- state lineage: `a0bd361d-5cd1-a207-a8c0-e6888f0be082`;
- state serial: `25`;
- Lambda: `ris-dev2-dev-agent`;
- Lambda ARN: `arn:aws:lambda:eu-central-1:262370457690:function:ris-dev2-dev-agent`;
- current Lambda revision: `f3719946-b052-48a5-bd62-750ffc54dcab`;
- current deployed `CodeSha256`: `Ra5SwfPMRV8OXdH2RILragK77noxF6Jg1YvSC4HFTDg=`;
- current runtime/handler: `python3.14` / `handler.lambda_handler`.

## Saved plan

The plan was generated with the existing Terraform configuration, S3 backend,
`ris-dev2` workspace and normal state refresh. Health Lambda inputs were bound
to the already existing deployed artifacts so they cannot appear as incidental
filename changes.

```text
Path: C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-auth-06g.tfplan
SHA-256: 7cfcbf7ba2a5986e9529224890b68b81bf32ce3fb9e96ef47ed82cfe5e570a8e
JSON inspection SHA-256: a441f4282fb628804d3339f54b98d66f94e9aeeaa37b70f9445a936154999c56
Terraform: 1.17.0
```

The binary plan is external to the repository and is not committed.

## Resource action scope

```text
Create:  0
Update:  1
Delete:  0
Replace: 0
```

The sole non-no-op resource is:

```text
module.lambda.aws_lambda_function.agent — update in-place
```

The inspected attribute diff is:

- `source_code_hash`: deployed hash -> `8mMDIqaIf++GBVImT2xvvrTh6JhazH2+YS6Ztt6o1hM=`;
- `last_modified`: computed by AWS after the code update.

No environment, IAM, layer, runtime, handler, API Gateway, Cognito,
DynamoDB, CloudFront, DNS, ACM, Health Lambda or other protected-resource
change is planned.

## Deployment artifact

```text
Artifact: terraform/lambda.zip
SHA-256: f2630322a6887fef860552264f6c6fbeb4e1e8985acc7dbe612e99b6dea8d613
Terraform source_code_hash Base64: 8mMDIqaIf++GBVImT2xvvrTh6JhazH2+YS6Ztt6o1hM=
```

The artifact is the validated G2 candidate and contains the dispatcher fix.

## Decision

The Terraform scope gate passes. This report authorizes preparation only; the
workflow stops before Apply as required.
