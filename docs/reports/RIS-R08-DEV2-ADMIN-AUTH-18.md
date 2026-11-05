# RIS-R08-DEV2-ADMIN-AUTH-18

## Decision

**BLOCKED — no valid DEV2 admin authorization proof exists.**

No authorization file, signature, approval, admin identity, AWS resource,
credential, Registry entry or API Profile was created or changed.

## Where the authorization is checked

The contract is implemented in:

```text
tools/ris_admin/credentials.py:64-122
tools/ris_admin/cli.py:355-379
```

`cli.py` obtains the exact caller ARN from STS `GetCallerIdentity`; it does not
accept a CLI actor override. It passes the explicit `--authorization-file` or
the `RIS_ADMIN_AUTHORIZATION_FILE` environment variable to
`resolve_admin_authorization()`.

`resolve_admin_authorization()` fails closed when:

* the path is missing or does not exist;
* the file is unreadable or invalid JSON;
* the file is group/other writable;
* the file is not owned by the invoking user;
* the exact STS principal ARN is not mapped;
* the role is not `admin`, `staff` or `owner`; or
* `tenantId` is missing.

There is no default role, default tenant, flag override, signature bypass or
AWS-IAM-Administrator fallback.

## Required file format

The existing contract is a local JSON mapping:

```json
{
  "principals": {
    "arn:aws:iam::<account>:user/<principal>": {
      "role": "admin",
      "tenantId": "<approved-dev2-synthetic-tenant>"
    }
  }
}
```

For this session the exact STS principal is:

```text
arn:aws:iam::262370457690:user/devnemo
```

The file must be owner-only (`0600` equivalent), owned by the invoking local
user, and stored outside Git. The repository does **not** implement a signer,
issuer registry, expiry, nonce or replay protection for this file. Therefore
its legitimacy comes from the out-of-band RIS owner/security approval, not from
JSON contents alone.

The file itself contains no explicit account or environment field. The approver
must bind the approval out-of-band to account `262370457690`, region
`eu-central-1`, workspace `ris-dev2`, the exact STS ARN, one synthetic tenant,
and the short-lived test scope.

## Existing proof assessment

| Evidence source | Result |
|---|---|
| `RIS_ADMIN_AUTHORIZATION_FILE` environment variable | Not configured |
| Repository/user candidate paths | No matching valid file found in prior verified preflight |
| Exact principal mapping | Not available |
| Independent DEV2 owner/security approval | Not supplied |
| Historical examples | Documentation only; not an authorization grant |
| AWS/Cognito state | Read-only; no auth or resource mutation |

The current principal is not authorized merely because it can call AWS or has
IAM permissions. The previous bootstrap report explicitly records that
AdministratorAccess is not RIS application authorization.

## Legitimate issuance process

The existing reports define the following process; it is not an instruction to
self-create the file:

1. A RIS owner/security authority independently approves the exact principal,
   DEV2 account/region, synthetic tenant, short-lived partner scope, expiry,
   revocation and cleanup plan.
2. That authority supplies the local owner-only mapping through an approved
   out-of-band channel.
3. The operator stores it at a local path such as
   `~/.config/ris/ris-admin-auth.json`, outside Git, and sets
   `RIS_ADMIN_AUTHORIZATION_FILE` to that path.
4. The operator verifies the file permissions, exact ARN and tenant scope
   locally; no contents or secrets enter reports.
5. The existing APIProfile/Credential lifecycle is used: create `PENDING`,
   activate through the admin-only transition, issue the expiring credential
   to a secure one-time output file, then revoke and clean up.

Important open security condition: the existing `partner create` CLI subcommand
currently exposes direct Registry arguments without calling the shared
`_actor()` trust-anchor path. Existing security reports identify this as a
known implementation gap. It must not be used for Phase 17 until the authorized
operator provides an approved, trust-anchor-guarded Registry procedure. Direct
DynamoDB writes are prohibited.

## Concrete authorization request

The following request is prepared for the authorized RIS operator; it is not an
authorization file and has not been written to disk:

```text
Please approve a temporary RIS application-admin mapping for:

AWS account:       262370457690
Region:            eu-central-1
Environment:       ris-dev2
STS principal:     arn:aws:iam::262370457690:user/devnemo
Requested role:    admin (required for profile activation and controlled test provisioning)
Tenant:            <operator-assigned synthetic DEV2 tenant>
Partner:           one temporary synthetic partner only
Scope:             APIProfile + temporary Credential + Partner Registry binding
Test data:         synthetic ApplicationV1 only
Expiry:            short-lived, explicitly specified by approver
Cleanup:           revoke credential first, then remove only self-created test records
Additional gate:   provide a trust-anchor-guarded Partner Registry procedure;
                  do not use the current unguarded partner CLI path
```

The operator must return the approved tenant identifier, expiry and the
approved secure local delivery path. No tenant was invented here.

## Dry-run recheck

With no authorization file and no mutation, the existing CLI dry-runs were
rerun successfully for APIProfile creation, credential issue and credential
revocation. Each returned `dryRun: true` and explicitly reported no mutation.

The focused authorization tests remain the previously recorded **10 passed, 39
deselected**. The broader credential test run in this Windows environment was
not treated as a security pass: **43 passed, 21 failed**, due to the documented
Windows temporary-directory ACL/symlink assumptions. No production check was
weakened.

## Next concrete step for Phase 17

After the RIS owner supplies the approved mapping and a guarded Registry
procedure:

1. set the local environment variable only in the operator shell;
2. run CLI dry-runs and inspect the resolved account/principal/tenant guards;
3. create and activate one synthetic API Profile;
4. create the Partner Registry binding through the approved guarded path;
5. issue a short-lived credential to an owner-only destination;
6. run the bounded synthetic DEV2 E2E;
7. revoke the credential and remove only the self-created records;
8. verify zero active test resources and commit the evidence report.

Until then, Phase 17 remains blocked and Gate B remains NO-GO.
