# RIS-DEV2-AUTH-05D — Bootstrap Readiness

## Decision

```text
BLOCKED — NO VERIFIED ISSUER OR DEV2 AUTHORIZATION GRANT
```

No bootstrap component was implemented. Creating or self-signing an
`RIS_ADMIN_AUTHORIZATION_FILE` would turn a local file into self-authorization
and violate the existing trust-anchor model.

## Offline checks

The existing authorization implementation was inspected and its focused
negative checks were run:

- no file: denied;
- missing file: denied;
- unmapped principal: denied;
- missing role: denied;
- missing tenant scope: denied;
- unparsable policy: denied;
- unsafe writable policy: denied;
- AWS identity alone: denied;
- CLI has no actor-role override: verified.

Result: **10 passed, 39 deselected** in the focused authorization subset.

The broader credential issuance tests were not used as a readiness claim in
this Windows environment because their owner-only temporary-directory ACL
assumptions are incompatible with the runner's default ACLs. No production
code was changed to weaken those checks.

## Readiness gates

| Gate | Result | Reason |
|---|---|---|
| Authorization issuer | BLOCKED | No independently supplied RIS owner/security approval |
| Account binding | PARTIAL | Exact ARN binds account indirectly; no explicit account field |
| Environment binding | BLOCKED | File has no environment field; DEV2 scope must be approved out-of-band |
| Principal binding | READY in code / BLOCKED in DEV2 | Current ARN has no mapping |
| Expiry/replay protection | BLOCKED | Local policy has no expiry, nonce or signed replay protection |
| Scope escalation | BLOCKED | Partner CLI path needs shared trust-anchor guard review |
| Credential protection | READY in existing adapter | Owner-only destination, one-time secret, revocation lifecycle |
| Cleanup/revocation | READY by contract | Existing revoke path; no live credential exists for this run |

## Required next action

An authorized RIS owner must provide a tenant-scoped DEV2 approval and, before
any mutation, the partner CLI must be brought under the same trust-anchor
authorization as APIProfile/Credential operations. Then a separate approved
run may create only the synthetic PartnerApplication, APIProfile and
Credential, validate them, execute the ApplicationV1 E2E, and revoke/clean up.

Until those gates are met, no AWS mutation or partner provisioning is
authorized.
