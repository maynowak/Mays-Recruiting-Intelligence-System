# RIS-R08-DEV2-10E — Migration Readiness

## Current data posture

The live Applications, WorkItems, PartnerRegistry, ErasureOperations,
PrivacyReceipts and related privacy tables are empty according to DynamoDB
table metadata, except for two seeded agent-catalog rows. Therefore no
backfill was needed or performed during this discovery.

The code stores durable subject fences in the existing WorkItems table under a
derived `erasure-fence#...` `workId`; there is no separate fence table. Existing
historical WorkItems, if introduced later, must not be mass-mutated by this
mission. The worker's fail-closed admission and final fence check are the
required compatibility mechanism.

## Required cutover order

1. Resolve the duplicate/legacy Terraform lock records under separate
   ownership approval; never delete them automatically.
2. Remove unrelated health-bundle drift from the plan or approve it separately.
3. Verify the WorkItems IAM transaction/index resources against the exact plan.
4. Keep all privacy/erasure/receipt flags disabled.
5. Deploy the agent artifact and route only under a separate Apply approval.
6. Run synthetic, isolated smoke tests before any queue or data mutation test.
7. Capture CloudWatch, API, Lambda, DynamoDB and SQS evidence.

No data migration is authorized here. A failed rollout must stop before Apply
or be rolled back only through a separately approved, reviewed plan; no
Terraform state repair, import, move or deletion is permitted.

PITR is currently disabled on the relevant tables. This is a release blocker
for restore/reconciliation evidence, not a reason to enable it in this mission.
