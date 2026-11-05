# RIS-R08-DEV2-ADMIN-BOOTSTRAP-19

## Status

**Security fix complete. Operator authorization and DEV2 provisioning remain
open.**

No AWS mutation, Cognito change, Registry write, API Profile, Credential,
ApplicationV1 record, Terraform operation, Jobsearch change, push or merge was
performed.

## 19A — Partner provisioning security fix

Implemented in `tools/ris_admin/cli.py`:

* non-dry-run `partner create` now resolves the actor through the existing
  `_actor()` and `resolve_admin_authorization()` trust-anchor path;
* `--tenantId` was removed from `partner create`;
* tenant is taken only from the authorized actor mapping;
* the referenced APIProfile must be visible, `ACTIVE`, and tenant-equal before
  Registry mutation;
* missing/unmapped/invalid authorization fails before DynamoDB access;
* `partner deactivate` now also requires the trust anchor.

Implemented in `agents/ecosystem/partner_registry.py`:

* deactivation accepts an optional expected tenant;
* when supplied by the guarded CLI, DynamoDB requires
  `attribute_exists(applicationId) AND tenantId = :t`;
* the existing client reservation remains preserved.

The APIProfile, Credential issuance, hashing, secure output and revocation
contracts were not replaced or weakened.

## Tests and dry-runs

Relevant tests:

```text
49 passed
```

This includes the new Partner CLI security tests, existing CLI/APIProfile tests
and Partner Registry atomicity tests. New coverage includes:

* removed tenant override;
* missing authorization;
* unmapped principal;
* foreign APIProfile tenant;
* authorized tenant propagation to Registry create;
* authorized tenant propagation to Registry deactivation.

Dry-runs for Partner create, APIProfile create and Credential issue completed
with explicit no-mutation output. No secret was generated.

## 19B — Trust-anchor contract and operator template

The existing file is a local JSON mapping consumed by
`tools/ris_admin/credentials.py:64-122`:

```json
{
  "principals": {
    "arn:aws:iam::<ACCOUNT>:user/<PRINCIPAL>": {
      "role": "admin",
      "tenantId": "<APPROVED_SYNTHETIC_TENANT>"
    }
  }
}
```

The exact current STS principal previously verified for this session is:

```text
arn:aws:iam::262370457690:user/devnemo
```

The file is valid only when supplied out-of-band by the RIS owner/security
authority and then locally verified as owner-only, not group/other writable,
owned by the invoking user, valid JSON, exactly principal-mapped, role-valid and
tenant-scoped. The repository has no signer, issuer registry, expiry, nonce or
replay protection for this file. The file therefore cannot be self-created or
treated as approval based on its contents alone.

The file does not encode environment/account explicitly. The approval must
bind these out-of-band:

```text
AWS account: 262370457690
Region: eu-central-1
Environment/workspace: ris-dev2
Principal: arn:aws:iam::262370457690:user/devnemo
Role: <approved role; admin required for profile activation>
Tenant: <operator-assigned synthetic tenant>
Scope: one temporary Partner, APIProfile, Credential, Metrics/ApplicationV1 E2E
Expiry: <short-lived expiry>
Cleanup: revoke credential, deactivate/remove only self-created test records
```

This is a template only. It is not an authorization file and has not been
written to disk.

## 19C — Freigabe status

**Not granted.** No valid `RIS_ADMIN_AUTHORIZATION_FILE` is configured and no
independent owner/security approval was supplied. AWS IAM access alone is not
RIS application authorization. Gate B remains NO-GO.

The following condition remains before 19D:

1. An authorized operator supplies the approved local mapping through the
   existing out-of-band process.
2. The operator confirms the exact tenant, expiry and DEV2-only scope.
3. The operator uses the now-guarded Partner CLI path with the same trust
   anchor; direct DynamoDB writes remain prohibited.

## 19D — Provisioning and E2E

Not executed because the authorization gate is not satisfied.

| Gate | Status |
|---|---|
| Test Partner Provisioning | BLOCKED — no approved trust anchor |
| Credential Authentication | BLOCKED — no credential issued |
| JWT + Partner Binding | BLOCKED — no binding exists |
| Metrics | BLOCKED — prerequisite absent |
| ApplicationV1 | BLOCKED — prerequisite absent |
| Credential Revocation | BLOCKED — no credential exists |
| Cleanup | PASS — no-op; no resources created |
| Cognito Changes | NONE |
| Jobsearch Changes | NONE |
| Gate B | NO-GO |
| Production | BLOCKED |

## Jobsearch follow-up after approval

Jobsearch still needs a server-side BFF using the existing credential contract:

* keep `RIS_API_KEY`/credential server-side only;
* forward the Cognito access JWT and `X-Api-Credential` from the BFF;
* use the live `/v1/partner/me/applications` routes and cursor/version
  semantics;
* never send the credential to the browser or log it;
* keep local drafts until explicit transfer confirmation and server success;
* handle RIS unavailable/401/403/409/503 without fabricated persistence;
* run the real synthetic E2E only after the approved binding exists.

Jobsearch/Vercel key presence and BFF deployment remain **NOT VERIFIED**.

## Commits

```text
811d519 fix: guard partner provisioning with admin trust anchor
4fb4bdb fix: enforce tenant scope on partner cleanup
```
