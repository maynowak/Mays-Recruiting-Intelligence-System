# RIS-R08-DEV2-13D — Synthetic E2E Approval Matrix

No identity, message or test data was created in this review.

| Test | Required resources | Synthetic identity | Cleanup | Risk | Separate approval |
|---|---|---|---|---|---|
| Auth/JWT authorizer | existing external Cognito/API | dedicated subject, tenant, partner, issuer and audience | revoke/delete only owned subject artifacts | auth/config boundary | required |
| ApplicationV1 CRUD/pagination | API, Applications table | same run-scoped synthetic subject | manifest-owned rows only | data leakage/pagination | required |
| Tenant/partner/issuer isolation | API, WorkItems/Application context | at least two isolated synthetic scopes | verify zero cross-scope artifacts | authorization failure | required |
| SQS retry/DLQ/redrive | existing queues/DLQs | run-scoped message envelope | no shared-queue purge; owned messages only | stale/foreign messages | required |
| Subject fence/resurrection | WorkItems, ledger, erasure contracts | synthetic erased subject | preserve approved ledger evidence | reactivation | required |
| Public erasure | `/me/erasure`, related stores | synthetic subject only | idempotent owned cleanup | partial erasure | required |
| Inspect/export/no-store | API and privacy contracts | synthetic subject only | remove generated export artifacts | PII/cache leakage | required |
| CloudWatch/error evidence | logs/alarms | run ID correlation | retain operational evidence | cost/noise | required |
| Restore test | separate STAGING restore and ledger | synthetic dataset only | staging teardown after evidence | restore/promotion | separate later gate |

The contract requires a unique run ID and ownership manifest on every object,
versioned S3 cleanup, bounded DLQ handling and evidence for retained ledger or
audit rows. Missing identity authorization or ambiguous cleanup is a hard
blocker, not an assumed prerequisite.

Status: **DESIGNED / NOT READY FOR EXECUTION**.
