# RIS-R08-DEV2-10G — Safety and Costs

## Safety decision

No additional resource cost was incurred by this discovery beyond read-only
AWS API calls and local Terraform/provider execution. No precise future price
is asserted here because traffic, storage, retention and region-specific
pricing inputs were not provided.

Potential cost categories requiring an owner estimate before E2E include:

- DynamoDB provisioned/on-demand capacity and transaction throughput;
- PITR and backup storage;
- SQS requests, retention and DLQ redrive;
- Lambda duration/invocations and CloudWatch logs/alarms;
- S3 versioning, retained delete markers and restore storage;
- API Gateway requests and Cognito test identities.

## Risk decision

Deployment is **BLOCKED** until the lock anomaly and unrelated health-Lambda
updates are resolved. PITR-disabled state prevents restore/reconciliation
acceptance. Existing Cognito, CloudFront, DNS and ACM resources are protected
by the reviewed plan's zero-change result; that protection must be rechecked on
the final approved plan.

## Safe cutover contract

1. Verify account/profile/region/backend/workspace and protected IDs again.
2. Resolve lock ownership and obtain a normally locked plan.
3. Require zero protected-resource actions and no unrelated health updates.
4. Approve the exact plan hash and change list.
5. Apply only with a separate authorization; keep privacy flags false.
6. Run read-only smoke tests, then separately approved synthetic mutation tests.
7. Capture cleanup, CloudWatch, API, Lambda, SQS, IAM and DynamoDB evidence.
8. Stop immediately on any protected-ID change, unexpected replacement,
   state drift, authorization failure or data-leak signal.

Unknown pricing and unverified restore costs remain explicit unknowns.
