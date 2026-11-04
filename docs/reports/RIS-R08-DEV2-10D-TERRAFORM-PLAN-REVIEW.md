# RIS-R08-DEV2-10D — Terraform Plan Review

## Commands and evidence

- `terraform init -backend=false`, `terraform validate`: PASS with provider
  deprecation warnings;
- `terraform fmt -check -recursive`: PASS;
- verified backend initialization against bucket `ris-dev2-tf-state-dev`, key
  `dev/terraform.tfstate`, prefix `env:`, workspace `ris-dev2` and lock table
  `ris-dev2-tf-lock`;
- diagnostic read-only plan used `-lock=false` because the lock table contains
  two conflicting lock-ID records;
- plan format Terraform 1.2 / Terraform 1.17.0;
- no plan file was committed; temporary plan was removed.

## Change summary

| Action | Count |
|---|---:|
| CREATE | 1 |
| UPDATE in place | 4 |
| DELETE | 0 |
| REPLACE | 0 |

Planned resources:

1. CREATE API route `GET /v1/partner/me/applications/metrics`;
2. UPDATE health publisher Lambda artifact path;
3. UPDATE health writer Lambda artifact path;
4. UPDATE agent Lambda code hash;
5. UPDATE agent WorkItems IAM policy: add `dynamodb:TransactWriteItems` and
   correct the malformed index ARN.

No Cognito, CloudFront, OAC, DNS, ACM, existing API replacement, table
replacement, queue replacement, event-source replacement or IAM trust-policy
change appeared in the plan.

## Decision

The plan is technically readable but **not approved for Apply**. The two
health-Lambda artifact updates are unrelated to the R08 runtime change and
must be eliminated or explicitly approved. A normally locked plan must also be
reproduced after the duplicate/legacy lock records are resolved by an
authorized owner. No lock cleanup was attempted.
