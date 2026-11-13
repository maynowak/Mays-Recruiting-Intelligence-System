# RIS AWS G4 Decision Template — Structured CV

**Status:** TEMPLATE ONLY — **NO AWS DISCOVERY OR PLAN**

## Approval fields (must be supplied by Release Owner)

| Field | Value |
|---|---|
| AWS account id | [INTERNAL — NOT SUPPLIED] |
| Account alias | [INTERNAL — NOT SUPPLIED] |
| Region | [TO CONFIRM — do not assume] |
| Terraform workspace | [TO CONFIRM] |
| Backend bucket/key | [TO CONFIRM] |
| Lock table | [TO CONFIRM] |
| State lineage | [AFTER AUTHORIZED DISCOVERY] |
| State serial | [AFTER AUTHORIZED DISCOVERY] |
| Protected-resource baseline | [TO CONFIRM] |
| Authorized operator/profile | [TO CONFIRM] |
| Change window | [TO CONFIRM] |
| G4 plan approval | [NOT GIVEN] |
| G6 apply approval | [NOT GIVEN] |

## Allowed G4 plan scope (proposal)

- add `gsi-structured-owner` to the existing partner-profile table;
- add the six explicit Structured-CV API Gateway routes prepared in
  `feature/ris-structured-cv-api-routes-01`;
- add/confirm default-off `STRUCTURED_CV_PROFILE_ENABLED` Lambda environment;
- no Cognito/CloudFront/DNS or consent activation.

## Expected resource changes (to be verified, not assumed)

- **Update** partner-profile DynamoDB table with one GSI; no new table.
- **Update** API Gateway with six routes and JWT authorizer references.
- **Update** agent Lambda environment/package for the new handler module.
- **No** IAM widening expected because partner-profile IAM already grants
  table/index actions.
- **No** data backfill; existing items without `ownerKey` remain outside the
  sparse GSI.

## Required plan evidence

- saved plan path and SHA-256;
- state serial/lineage before/after;
- full create/update/delete/replace inventory;
- protected-resource comparison;
- IAM/route diff;
- cost/throughput note for GSI;
- rollback/recovery plan;
- independent reviewer sign-off.

## Rollback/recovery proposal

1. Keep prior Lambda bundle and API route baseline.
2. If the feature is unsafe, keep flag OFF and revert route/Lambda changes via
   a reviewed plan.
3. GSI removal is a destructive schema action; do not assume it is safe.
4. Never restore backups without deletion-ledger reconciliation.
5. Escalate any unexpected delete/replace/protected-resource change.

## Current state

No account, region, workspace, state or plan was read or created. This document
is a fill-in template only.
