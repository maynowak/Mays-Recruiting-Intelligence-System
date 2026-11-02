# R08-E2E-G2C-3A — AWS ACCOUNT & PROFILE RECONCILIATION

**Status:** LOCAL PROFILE ANALYSIS COMPLETE / AWS ACCESS BLOCKED

## Baseline and boundary

- Branch: `feature/ris-partner-profile-persistence-v1`.
- Starting HEAD: `1c47cd5ef874260b9ce411df4d54879b1bc4afe7`.
- Expected account: `240571105849`.
- Test project: `ris-dev-pf`.
- Region: `eu-central-1`.
- No AWS/STS calls were made for this reconciliation.
- No credentials were read, created, copied, changed or printed.
- No Terraform, installer, state, resource or global configuration was
  changed. The 39 untracked files were preserved.

## Local configuration findings

### Environment overrides

The local process environment contains no AWS-related variables, including no:

- `AWS_PROFILE`;
- `AWS_DEFAULT_PROFILE`;
- `AWS_REGION` or `AWS_DEFAULT_REGION`;
- `AWS_CONFIG_FILE`; or
- `AWS_SHARED_CREDENTIALS_FILE`.

No AWS-related executable directory was present in `PATH` during the previous
AWS gate, which is why the AWS CLI was unavailable.

### Shared AWS files

The default file locations exist:

```text
%USERPROFILE%\.aws\config
%USERPROFILE%\.aws\credentials
```

Only the profile section `[default]` is present in either file. The config
contains the non-secret setting `region = eu-central-1` and `output = json`.
There is no `[mayaws]` section. Credential values and all secret-bearing
lines were intentionally not read or displayed.

### Why `mayaws` is missing

`mayaws` is a repository/documentation convention, not a locally provisioned
profile. It appears in `AGENTS.md`, deployment context, README examples and
historical deployment reports as the expected operator profile for account
`240571105849`; it is not created by Terraform or by the RIS installer. The
installer accepts an optional explicit profile name and passes it to AWS CLI,
but it does not create credentials or profile sections.

The local `default` profile is therefore the only available credential-chain
candidate. G2C-3 already verified via read-only STS that it resolves to account
`262370457690` and principal `arn:aws:iam::262370457690:user/devnemo`, which is
not the RIS account. That historical live result is retained as evidence; no
new AWS call was made here.

## Credential and SDK precedence

`installer/identity_context.py` defines the relevant behavior:

1. An explicit installer `--profile` wins.
2. Otherwise `AWS_PROFILE` is used if present.
3. Otherwise the SDK/AWS CLI default chain is used.
4. Region precedence is explicit argument, then `AWS_REGION`, then the
   repository default `eu-central-1`.

The installer validates identity through read-only STS when invoked, but its
current `AwsExecutionContext` records the returned account; it does not itself
enforce the repository's expected account `240571105849`. Therefore an
external hard account guard is required before any Terraform or installer
operation for this RIS gate.

## Required manual setup

An authorized operator must configure the RIS account profile outside this
repository, using the organization's approved credential method. The setup
must create or expose a profile named `mayaws` (or another explicitly approved
name) that resolves to account `240571105849` in `eu-central-1`.

Acceptable mechanisms may include the organization's SSO/login flow, an
approved role/profile chain, or another managed credential provider. Do not
place access keys, session tokens, credential-process output, or secrets in
the repository, report, `.tfvars` files or shell history.

No profile setup was performed by this task. The global `[default]` profile was
not overwritten.

## Required hard account guard

After the approved profile is configured, but before any Terraform or
installer command, run this read-only guard in a controlled shell. It must
fail closed and must not be replaced by a region-only check:

```powershell
$expectedAccount = '240571105849'
$expectedRegion = 'eu-central-1'
$profile = 'mayaws'
$identity = aws sts get-caller-identity --profile $profile --output json | ConvertFrom-Json
$region = aws configure get region --profile $profile
if ($identity.Account -ne $expectedAccount) { throw "AWS account mismatch: $($identity.Account)" }
if ($region -ne $expectedRegion) { throw "AWS region mismatch: $region" }
Write-Output "AWS identity guard PASS: account=$($identity.Account), region=$region, principal=$($identity.Arn)"
```

The principal ARN may be recorded as non-secret evidence, but credentials and
tokens must not be recorded. A successful guard is a prerequisite for the
later `ris-dev-pf` read-only discovery, not authorization for plan/apply.

For later commands, use explicit identity rather than ambient defaults, for
example:

```powershell
$env:AWS_PROFILE = 'mayaws'
$env:AWS_REGION = 'eu-central-1'
python -m installer.ris --project-name ris-dev-pf --environment dev --profile mayaws --region eu-central-1 preflight
```

This command is preparation only and must not be run until the account guard,
AWS read-only authorization and command-specific approval are satisfied. The
G2C-3B discovery should use the same explicit profile/account tuple.

## Required G2C-3B prerequisites

Before retrying AWS discovery:

1. `mayaws` exists locally and is backed by an approved credential source.
2. The hard guard returns account `240571105849` and region `eu-central-1`.
3. The caller has only the approved read permissions for identity, backend,
   state metadata, locks and target resource inventory; no mutation is needed.
4. The exact `ris-dev-pf` tuple is used:
   `workspace=ris-dev-pf`, state
   `env:/ris-dev-pf/dev/terraform.tfstate`, and project-derived names.
5. Any account/profile mismatch stops the process before S3, DynamoDB, Lambda,
   IAM, Cognito, API Gateway, SQS or CloudTrail queries.
6. Terraform plan remains separately unauthorized until the complete
   read-only evidence is reviewed.

## Decision

**G2C-3B Readiness: BLOCKED.** The expected `mayaws` profile and account
`240571105849` are not locally available. The only configured default profile
was previously proven to resolve to a different account. No global default was
changed and no AWS call was made in this task.

## Commit intent

```text
docs(ris): reconcile aws profile before readonly discovery
```
