# RIS-DEV2-TEST-IDENTITY-04B — Synthetic Users

**Run ID:** `RIS-DEV2-04-20261103T111714Z`

## Result

**PASS — ONE ISOLATED SYNTHETIC USER**

## User

- Pool: `eu-central-1_K3dkdSipZ`
- Username: `ris-dev2-e2e-04-111714`
- Email: `ris-dev2-e2e-04-111714@example.invalid`
- Synthetic tenant: `ris-dev2-e2e-111714`
- Status: `CONFIRMED`
- Enabled: `true`
- Cognito groups: none

The user was created through the existing Cognito Admin API in account
`262370457690` with `MessageAction=SUPPRESS`, then given a temporary generated
password through the Admin API and made permanent for the controlled test. The
password was generated in memory, stored only in a restricted temporary local
handoff file, never printed, and is not included in Git, Terraform, reports or
the audit log.

No existing user, pool, client, OAuth setting or group was modified. No
production or real-person email address was used. The temporary password file
will be deleted after the PKCE attempt and cleanup.

## Scope boundary

This user is not an RIS administrator and has no `admins` or `Staff` group.
Partner/APIProfile/Credential provisioning remains blocked by the missing
principal-bound `tools/ris_admin` authorization mapping documented in 04A.
