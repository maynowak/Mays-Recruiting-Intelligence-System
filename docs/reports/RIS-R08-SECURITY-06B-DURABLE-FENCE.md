# RIS-R08-SECURITY-06B — Durable Fence Review

The review found and corrected the fence lookup key bug (`fenceKey` versus the
WorkItems primary key `workId`). Admission now rejects missing subject/tenant,
uses canonical JSON scope encoding, carries partner/issuer fields when
available, and activates both base and scoped fences for context-backed
erasure. Existing RUNNING rows are checked, and a final fence/attempt
transaction occurs immediately before execution. Result/failure persistence is
also status/attempt conditional.

Remaining BLOCKER: public `/me/erasure` does not invoke the existing
ApplicationV1 erasure executor, so complete cross-domain erasure is not proven.
External agent/SQS atomicity remains explicitly out of scope.
