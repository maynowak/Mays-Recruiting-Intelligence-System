# RIS-DEV2-TEST-IDENTITY-03 — Controlled Apply

**Result:** **APPLY PASS**

## Guarded execution

- Profile/account/region: `default` / `262370457690` / `eu-central-1`
- Workspace: `ris-dev2`
- State serial before: `24`
- State lineage: `a0bd361d-5cd1-a207-a8c0-e6888f0be082`
- Plan: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-managed-identity-02.tfplan`
- SHA-256: `35EE37C10CF190A0DD1A80714734C2DD9A567CF191186693B9952B9C2ED64CE6`

After all guards passed, exactly one saved-plan apply was run in the original
Terraform workdir with no replan, retry, `-target`, `-replace` or rollback.

## Apply result

```text
Exit code: 0
Apply complete! Resources: 10 added, 1 changed, 0 destroyed.
```

The only update was the existing Human JWT authorizer. No delete or replacement
occurred. The deprecated backend parameter warning was non-fatal and unrelated
to the approved resource actions.

## Created identity

- Pool: `eu-central-1_K3dkdSipZ` (`ris-dev2-dev-users`)
- Human client: `21j28p71vogg0m41tcue0ib3l4` (`ris-dev2-dev-client`)
- Issuer: `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ`
- Prefix domain: `ris-dev2-dev`
- Seven planned groups

The client is public and no client secret is present. No user, token, partner
binding, APIProfile or credential was created.

## State result

- State serial: `24` → `25`
- State lineage unchanged: `a0bd361d-5cd1-a207-a8c0-e6888f0be082`
- Expected Cognito resources are present;
- managed M2M client/resource server are absent;
- consumed plan status: **APPLIED — DO NOT REAPPLY**.

The old `ris-dev2-managed-identity-01.tfplan` remains **SUPERSEDED — DO NOT
APPLY**.
