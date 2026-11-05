# RIS-R08-DEV2-12F — Synthetic E2E Contract

Future DEV2 E2E execution requires dedicated synthetic subjects, an isolated
tenant/partner scope, verified JWT issuer/audience and no real user or
application data. Every application, WorkItem, document/object, queue
message, retry/DLQ item and ledger reference must carry a unique test-run ID
and ownership manifest.

Cleanup must be idempotent and scope-limited: delete only manifest-owned
records, remove versioned synthetic S3 objects, reconcile retries/DLQ without
purging shared queues, and retain explicitly required ledger/audit evidence.
Before sign-off, record zero owned data objects and an approved explanation
for every retained audit row. Permissions and expected cost require separate
approval. Cognito pool/clients and shared infrastructure are not changed by
this contract.

No identities, test data, queue messages or cleanup actions were created or
executed in Phase 12.

Status: **DESIGNED / NOT READY FOR EXECUTION**.
