# RIS-R08-DEV2-13C — Controlled Cutover Handoff

This is a proposed sequence for a separately authorized future deployment;
this report performs no deployment.

1. Reconfirm account, profile, region, backend, workspace, state serial/
   lineage and lock/parallelism. Refuse any base LockID or unexpected state.
2. Build the deterministic bundles and validate/fmt the exact checkout.
3. Review the fresh plan hash and the ten-resource register. Do not use
   `-target` or a stale saved plan.
4. Apply only after explicit approval of the full plan. Terraform graph
   dependencies make the ledger table available before the ledger IAM policy,
   and table/IAM outputs feed the Lambda environment and module dependency.
   The metrics route is independently graphable. Terraform does not provide
   an end-to-end transactional cutover or guarantee the business sequence.
5. Read-only post-apply verification must confirm table schema/PITR status,
   IAM policy scope, Lambda environment flags/hash and route configuration.
6. Run separately authorized authenticated smoke tests, then the synthetic
   E2E contract and manifest-scoped cleanup.

The common plan is technically dependency-aware for resource references, but
an interrupted apply can leave infrastructure partially changed. Rollback is
not an automatic restore: it requires a fresh reviewed plan and explicit
handling of PITR, ledger rows, Lambda code and route state.

Existing SQS event-source mapping is unchanged. Old or already-visible queue
messages may therefore reach the updated Lambda after a code update. No live
queue age, retry, DLQ or redrive evidence exists; queue baseline/drain and
stale-message behavior require a separate gate. Privacy/erasure/freeze and
ledger runtime flags remain disabled.

Status: **CUTOVER DESIGNED / NOT AUTHORIZED**.
