# RIS-DEV2-TEST-IDENTITY-01 — Design Execution Log

## Status

COMPLETE — design and boundary review only. No AWS mutation.

## Checkpoint

- Branch: `feature/ris-application-persistence-v1`
- HEAD at start: `e19b0cd322dbc4fc88bc86dd9f3bd1b3236294bb`
- AWS target: account `262370457690`, region `eu-central-1`, workspace
  `ris-dev2`
- State lineage: `a0bd361d-5cd1-a207-a8c0-e6888f0be082`
- State serial observed: `24`

## Findings

- `identity_mode` supports `managed` and `external` with fail-closed input
  validation;
- managed mode already declares the Cognito pool, Human client, M2M client,
  resource server and prefix domain;
- API JWT authorizers consume the managed issuer and corresponding audiences;
- custom domain, DNS and ACM remain disabled in the proposed DEV2 overlay;
- existing external Cognito references are not changed by the code design;
- partner bindings and credentials are outside the identity module and remain
  separately gated;
- the external-to-managed transition requires a saved-plan review for
  authorizer updates, deletes and replacements.

## Authorization boundary

No user, pool, client, role, credential, partner record, token or AWS resource
was created or changed. Apply remains blocked.

## Resume point

Add and validate the dedicated non-secret `ris-dev2` managed-identity overlay,
then produce the offline validation report and commit it separately.
