# RIS-APPLICATION-PERSISTENCE-01 — Deployment Readiness

**Status:** IMPLEMENTATION READY FOR REVIEW; **Terraform plan NOT AUTHORIZED**

## Scope of a future controlled plan

- Account: `262370457690`
- Profile: `default`
- Region: `eu-central-1`
- Workspace: `ris-dev2`
- Existing state must be used; no import, rebuild, migration or state push.
- `orders_lifecycle = "disabled"` must remain unchanged.

Expected intended changes are limited to the ApplicationV1 DynamoDB table,
owner GSI, Lambda IAM/env wiring, API routes/OpenAPI, and Lambda code bundle.
No plan has been generated, hashed or authorized in this development step.

## Protected resources

The future plan must machine-check Cognito/user pools and clients,
CloudFront/OAC, DNS, ACM, authorizer issuer/audiences, Orders lifecycle,
existing DynamoDB/SQS resources and data-preserving replacements. Any
protected-resource action, unplanned replacement, broad IAM expansion, or
Orders activation is a hard stop.

## Open deployment gates

1. Obtain explicit legal/privacy approval for legal basis, retention, backup
   deletion, special-category handling and DPIA decision.
2. Add the application erasure executor to the existing durable erasure
   operation schema/registry and prove resume-after-failure.
3. Run moto/DynamoDB-Local and S3-version integration evidence in an approved
   isolated environment.
4. Build the Lambda bundle, run the complete focused regression, then create a
   stored remote plan only after separate plan authorization.

No AWS mutation, remote Terraform plan, push, merge or deployment was executed.
