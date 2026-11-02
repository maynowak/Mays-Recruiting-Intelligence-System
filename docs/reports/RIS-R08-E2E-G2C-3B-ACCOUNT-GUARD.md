# R08-E2E-G2C-3B — AWS ACCOUNT GUARD

**Status:** BLOCKED — ACCOUNT MISMATCH

## Guard scope

- RIS branch: `feature/ris-partner-profile-persistence-v1`.
- Starting HEAD: `8954c21c2d98b87bb07ef939e9e89b10d4f9eac4`.
- Target project: `ris-dev-pf`.
- Expected account: `240571105849`.
- Expected region: `eu-central-1`.
- User-authorized operation: one read-only STS `GetCallerIdentity` call.
- No Terraform, remote-state, resource discovery, mutation, invocation or
  deployment was performed.

## Local profile

The only local AWS profile is `[default]`. The user confirmed that this
profile should be used for the guard. No credentials or tokens were printed or
changed.

## STS result

The single allowed read-only STS call returned:

| Check | Result |
|---|---|
| Profile | `default` |
| Account | `262370457690` |
| Principal | `arn:aws:iam::262370457690:user/devnemo` |
| Region | `eu-central-1` |
| Account guard | **FAIL** — expected `240571105849` |
| Region guard | **PASS** |

The account mismatch caused immediate termination. No further AWS API call was
made in this gate.

## Decision

**Account Prüfung: BLOCKED.** The available `default` profile is valid for
`eu-central-1` but belongs to account `262370457690`, not the RIS account.

**Read-only Resource Discovery: BLOCKED.** No S3, DynamoDB, Lambda, IAM,
Cognito, API Gateway, SQS, CloudTrail, state or lock query was executed.

**Terraform Plan/Deployment: NOT AUTHORIZED.** `ris-dev` and `mays-ris` were
not accessed or changed; `ris-dev-pf` was not created or adopted.

## Required next step

An authorized credential/profile for account `240571105849` must be provided
before retrying the same guard. The next operation must again be only:

```text
STS GetCallerIdentity
```

and must pass both account `240571105849` and region `eu-central-1` before any
resource discovery is considered.

## Commit intent

```text
docs(ris): record aws account guard result
```
