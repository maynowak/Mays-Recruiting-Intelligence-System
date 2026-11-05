# RIS-DEV2-OPERATOR-AUTHORIZATION-20 — Recheck

## Result

**BLOCKED before Phase 17 mutation.**

The supplied authorization file exists and contains the exact verified STS
principal, `admin` role and synthetic DEV2 tenant, but the existing RIS
authorization contract rejects it on this Windows host.

## Read-only verification

```text
AWS profile: default
Account: 262370457690
Region: eu-central-1
STS principal: arn:aws:iam::262370457690:user/devnemo
Authorization file: %USERPROFILE%\.ris\admin-authorization-dev2.json
Mapped role: admin
Mapped tenant: ris-dev2-e2e-20261105
```

The file ACL was inspected and reduced to the invoking Windows user only:

```text
DESKTOP-N2812AA\DCI-Student:(F)
```

No SYSTEM, Administrators or inherited ACE remains. The file content was not
changed.

## Blocking cause

`tools/ris_admin/credentials.py:90-93` rejects when the POSIX mode reports
group/other write bits. On this Windows/Python runtime, `os.stat()` reports
`0o666` even after the Windows ACL is owner-only and after `chmod 600`.
Therefore `resolve_admin_authorization()` raises:

```text
authorization file is group/other writable; refusing to DEV2 synthetic partner test
```

This is a platform-compatibility failure in the existing guard, not an AWS
identity failure and not a missing operator mapping. The guard was not bypassed
and no authorization file was fabricated.

## Mutation status

No Partner, APIProfile, Credential, test identity or application data was
created. No credential secret was generated. No Cognito, CloudFront, DNS,
Terraform or `ris-dev` operation occurred. The discovered DEV2 DynamoDB table
names were read-only inspected only.

## Required next action

Before Phase 17 can proceed, the existing authorization guard needs a reviewed
Windows ACL-aware permission check (with focused security tests), or the
operator must run the unchanged contract in a POSIX environment where the
owner-only mode is observable. This requires a deliberate code/workflow
decision; it must not be bypassed by weakening the check or setting a flag.
