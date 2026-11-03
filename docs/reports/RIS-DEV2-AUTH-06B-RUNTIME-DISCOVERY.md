# RIS-DEV2-AUTH-06B — Lambda Runtime Discovery

## Environment guard

Read-only verification passed:

- AWS profile: `default`;
- account: `262370457690`;
- region: `eu-central-1`;
- Terraform state serial: `25`;
- Terraform state lineage: `a0bd361d-5cd1-a207-a8c0-e6888f0be082`.

## Runtime

The Terraform state output and Lambda discovery identify the function as:

- name: `ris-dev2-dev-agent`;
- ARN: `arn:aws:lambda:eu-central-1:262370457690:function:ris-dev2-dev-agent`;
- runtime: `python3.14`;
- architecture: `x86_64`;
- package type: `Zip`;
- handler: `handler.lambda_handler`;
- layers: none;
- state: `Active`;
- last update status: `Successful`;
- revision ID: `f3719946-b052-48a5-bd62-750ffc54dcab`;
- last modified: `2026-11-03T09:14:49.000+0000`;
- code signing configuration: none reported.

The function has only `$LATEST` in the read-only version listing and no Lambda
aliases. No version or alias mutation was attempted.

The current AWS `CodeSha256` is recorded as an opaque comparison value in the
execution evidence, not as a secret. It differs from the newly built local
artifact hash, so the deployed package cannot be assumed to contain the
dispatcher fix.

## Ownership

Terraform module `terraform/modules/lambda/main.tf` declares the function,
sets `filename = var.lambda_config.filename`, and computes
`source_code_hash = filebase64sha256(var.lambda_config.filename)`. The root
default is `lambda.zip`, while the repository's deterministic lifecycle maps
the agent bundle to `terraform/lambda.zip`.

Therefore code ownership is **Terraform-managed**, using the existing
`lambda/build_zip.py --bundle agent|all` packaging procedure. The CI workflow
also deploys through Terraform rather than a direct Lambda update. A direct
`aws lambda update-function-code` would bypass the source-of-truth workflow
and is not authorized here.

## Result

```text
RUNTIME DISCOVERY PASS / DEPLOYMENT METHOD VERIFIED / NO UPDATE EXECUTED
```

Environment variables were not printed; no secrets were included in this
report.
