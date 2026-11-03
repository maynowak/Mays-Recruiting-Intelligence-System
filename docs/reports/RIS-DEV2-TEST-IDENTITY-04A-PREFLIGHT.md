# RIS-DEV2-TEST-IDENTITY-04A — Preflight

**Run ID:** `RIS-DEV2-04-20261103T111714Z`

## Result

**ENVIRONMENT GUARD PASS / RIS PARTNER PROVISIONING BLOCKED**

## Repository and AWS baseline

- Repository: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1`
- Branch: `feature/ris-application-persistence-v1`
- Starting HEAD: `3b7a6ea89db05e61d563dae6fee2c5ec13299e6a`
- Working tree: clean
- AWS profile/account/region: `default` / `262370457690` / `eu-central-1`
- Terraform workspace: `ris-dev2`
- State serial/lineage: `25` / `a0bd361d-5cd1-a207-a8c0-e6888f0be082`
- Cognito pool: `eu-central-1_K3dkdSipZ`
- Human client: `21j28p71vogg0m41tcue0ib3l4`
- Human authorizer: new pool issuer and Human audience verified
- M2M authorizer: external issuer/audience unchanged

No Terraform operation was run. The applied identity plan was not reused.

## Provisioning-contract finding

The repository's existing `tools/ris_admin` implementation is the authorized
RIS path for PartnerApplication, APIProfile and Credential operations. It fails
closed unless:

1. the current STS principal is known;
2. a local authorization JSON mapping exists;
3. the mapping is owner-only and not group/other writable;
4. the exact principal maps to an allowed role and tenant.

The current principal is:

```text
arn:aws:iam::262370457690:user/devnemo
```

No `RIS_ADMIN_AUTHORIZATION_FILE` is configured and no matching authorization
file was found in the repository/user candidate paths. Historical admin or
cross-account reports are evidence only, not an authorization grant.

There is no deployed public PartnerApplication admin route. Direct DynamoDB
writes would bypass the RIS authorization contract and are forbidden.

Therefore:

```text
RIS PARTNER PROVISIONING BLOCKED
```

No PartnerApplication, APIProfile, Credential, entitlement or DynamoDB item
was created.

## Allowed continuation

The Cognito-only synthetic-user and PKCE checks may continue independently if
the current AWS principal has the required Cognito Admin API permissions. The
ApplicationV1 positive E2E, partner binding and credential-dependent phases
remain blocked until an authorized RIS provisioning path is supplied.
