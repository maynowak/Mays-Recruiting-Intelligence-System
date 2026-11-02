# RIS Existing Installation Upgrade Runbook

**Purpose:** controlled, non-destructive upgrade of an existing RIS
installation after its authoritative Terraform state and protected resource
baseline have been proven.

This runbook is a procedure template. It does not authorize an apply. The
`ris-dev2` rehearsal stopped before plan because its current state was empty;
that failure must be resolved before applying this procedure to `ris-dev`.

## 1. Preconditions

1. Obtain written approval naming the exact project, environment, account,
   region, profile, backend bucket, lock table and state key.
2. Run an explicit STS account/region guard. Abort on any mismatch.
3. Confirm the exact workspace and effective state path; do not infer them from
   a default or a historical report.
4. Confirm the current state contains the expected resource inventory and has
   an authoritative lineage. An empty, foreign, duplicated or ambiguous state
   is a hard stop.
5. Record protected baselines for Cognito pool ID, clients, domain and
   dependent CloudFront distribution; health CloudFront distribution and OAC;
   ACM certificate; DNS aliases; API IDs and critical Lambda IDs.
6. Read-only verify ownership, status, versioning, encryption, PITR/backups,
   IAM and CloudTrail. Do not adopt resources based on names alone.
7. Build Lambda artifacts using the repository package contract. Keep plan and
   state artifacts outside Git and outside the report.
8. Confirm all privacy, receipt, freeze, upload-ledger, cutover and S3
   execution flags remain `false`.

## 2. Identity and state commands

Use explicit values supplied by the approved deployment record. Never use
ambient profiles or a fallback account.

```text
STS GetCallerIdentity with the approved profile
Terraform workspace must equal project_name
Backend key input must equal <environment>/terraform.tfstate
workspace_key_prefix must equal env:
Effective state must equal env:/<project>/<environment>/terraform.tfstate
```

For the `ris-dev2` rehearsal the expected tuple was:

```text
project   = ris-dev2
environment = dev
account   = 262370457690
region    = eu-central-1
state     = env:/ris-dev2/dev/terraform.tfstate
```

For the later permanent installation, substitute the approved `ris-dev` tuple;
never share state, workspace, plan or resource operations between projects.

## 3. Protected-resource baseline

Before planning, collect read-only evidence and store it outside the repo:

| Area | Required immutable comparison |
|---|---|
| Cognito | pool ID, pool ARN, clients, domain, issuer |
| Cognito CloudFront | distribution ID, status, aliases and target |
| Health CloudFront | distribution ID, enabled/status, aliases and origins |
| CloudFront OAC | OAC ID, origin association and bucket policy source ARN |
| ACM/DNS | certificate ARN/status and approved DNS records |
| API | API ID, routes, stages and authorizers |
| Lambda | function names, versions/code hashes and execution roles |
| DynamoDB | table names/key schemas, PITR and backups |
| S3 | bucket owner/tags, versioning, encryption, PAB, Object Lock/denies |
| Audit | CloudTrail name/status, trail bucket and policy |

If any protected ID differs from the approved baseline, stop. Do not let
Terraform replace the resource to make the plan pass.

## 4. Plan procedure

1. Use a separate Terraform data directory and a temporary plan path outside
   the repository.
2. Initialize only against the verified existing backend/workspace. Do not
   initialize a new backend or create a workspace when state is unresolved.
3. Run validation and produce one saved plan with explicit identity values.
4. Render a machine-readable plan summary outside Git.
5. Review every `create`, `update`, `delete` and `replace` action.
6. Reject any plan containing protected-resource delete/replace, foreign
   project names, backend changes, unexpected state migration, or activation
   flag changes.
7. Review IAM changes resource-by-resource and confirm least privilege.
8. Review expected costs: Lambda/API requests, DynamoDB on-demand/PITR,
   S3 versions/logs, CloudWatch, CloudTrail and Cognito.
9. Submit the complete plan report for separate approval. There is no implicit
   transition from plan approval to apply.

Do not use `-target`, `-replace`, `terraform state rm`, import or manual state
editing to suppress a safety finding.

## 5. Apply gate and post-upgrade checks

Apply is permitted only after explicit approval of the exact saved plan,
identity tuple and plan hash. Re-run the account guard and confirm the state
lock immediately before apply. Apply only that plan.

Afterward, read-only verify:

1. Cognito pool ID and protected clients/domain are unchanged.
2. CloudFront IDs/status and OAC are unchanged.
3. ACM certificate and DNS mapping are unchanged.
4. No unexpected deletes/replacements occurred.
5. Lambda/API/DynamoDB/SQS/Orders/monitoring smoke tests are non-destructive.
6. All privacy/erasure flags remain `false`.
7. CloudTrail and logs contain expected deployment evidence.
8. State serial/resource inventory matches the applied plan.

Any mismatch is a stop condition. Do not destroy/recreate or repair state
ad hoc; preserve evidence and escalate with recovery options.

## 6. Recovery and migration rules

- Empty or ambiguous state requires an approved state recovery/migration plan.
- Historical state versions are evidence, not automatic restore candidates.
- Never delete a state version or lock to unblock a plan without explicit
  approval and a backup/evidence record.
- Resource import is a separate change with ownership proof and approval; it is
  not a workaround for an unsafe upgrade.
- Keep `ris-dev`, `ris-dev2`, `ris-dev-pf` and any Orders component in separate
  workspaces, state paths and plan artifacts.

## 7. Evidence checklist

Record outside Git:

- account guard output (account/region/principal only);
- backend/state metadata and state serial/resource count;
- protected-resource baseline and post-upgrade comparison;
- full plan summary and plan hash;
- IAM, backup/PITR, S3 and CloudTrail checks;
- smoke-test results;
- cost estimate and rollback/recovery decision;
- operator approvals and timestamps.

Never commit credentials, state bodies, plan files, Lambda environment values
or secret configuration.
