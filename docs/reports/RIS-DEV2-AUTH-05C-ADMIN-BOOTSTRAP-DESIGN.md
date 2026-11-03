# RIS-DEV2-AUTH-05C — DEV2 Admin Bootstrap Design

## Decision

```text
DESIGN COMPLETE / BOOTSTRAP NOT AUTHORIZED
```

No authorization file, partner, APIProfile or Credential was created.

## Existing trust anchor

The existing `tools/ris_admin` APIProfile, Credential and Offer adapters use
`resolve_admin_authorization()` in
`tools/ris_admin/credentials.py`. The actual contract is:

```json
{
  "principals": {
    "arn:aws:iam::<account>:user/<principal>": {
      "role": "admin|staff|owner",
      "tenantId": "<tenant-scope>"
    }
  }
}
```

The caller ARN is obtained from STS `GetCallerIdentity`; it is not a CLI flag.
The file must exist, be readable, be owned by the invoking user, and not be
group/other writable. The exact ARN must be mapped, the role must be one of
`admin`, `staff`, or `owner`, and `tenantId` is mandatory. Missing, malformed,
unowned, writable, unmapped or incomplete policy fails closed.

## Issuance and scope

The authorization document must be issued out-of-band by the RIS owner or
security authority responsible for DEV2. The repository does not implement a
signer, issuer registry, expiry, nonce, replay counter, or cryptographic
signature for this local file. Therefore a file cannot be self-created by the
current operator and its provenance cannot be inferred from JSON contents.

For a valid DEV2 approval, the approver must independently verify:

- AWS account `262370457690` and region `eu-central-1`;
- the exact STS principal ARN;
- environment `ris-dev2`;
- one synthetic tenant and one dedicated synthetic partner;
- minimal ApplicationV1/APIProfile/Credential scope;
- no Agent entitlement and no other environment scope;
- expiration, revocation and cleanup instructions.

The file alone currently carries principal, role and tenant, but not an
explicit account/environment field. Account binding is indirect through the
exact ARN and STS identity. Environment binding must therefore be enforced by
the approving operator and by the selected `ris-dev2` CLI configuration.

## Existing operations to reuse

1. Create/activate APIProfile through `tools/ris_admin/apiprofiles.py`, which
   maps the approved actor to the existing domain actor and never accepts a
   tenant override.
2. Issue and later revoke the opaque Credential through
   `tools/ris_admin/credentials.py`; the raw secret is output once only to a
   prechecked owner-only destination.
3. Create and validate the PartnerApplication through the existing registry
   lifecycle, binding Cognito client, APIProfile and tenant.
4. Verify active status, tenant/owner consistency, expiry and revocation before
   the HTTP E2E run.

The Cognito user is not an RIS administrator and must not be placed in an
`admins` group merely to bootstrap a partner.

## Important implementation gap

The current `tools/ris_admin/cli.py` Partner subcommands include direct
registry operations and expose `--tenantId` on `partner create`, while the
shared `_actor()` trust-anchor path is wired later for APIProfile/Credential/
Offer operations. This is not sufficient evidence of a safe admin bootstrap.
It must be reviewed and guarded by the same trust anchor before any partner
mutation is authorized. No mutation was attempted through that path.

## Current DEV2 outcome

For `arn:aws:iam::262370457690:user/devnemo`, no matching authorization file is
configured. Consequently the regular bootstrap remains blocked and no
alternative authorization architecture is proposed.
