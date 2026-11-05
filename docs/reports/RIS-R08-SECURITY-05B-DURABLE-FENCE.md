# RIS-R08-SECURITY-05B — Durable Fence

Implemented locally in `agents/runtime/subject_fence.py`. The fence is a
write-once item in the existing WorkItems table, keyed by a SHA-256 digest of
tenant, user, partner application, and issuer context. It contains only
identity/context, schema/state, and operation ID; no CV, prompt, token, or
credential payload is stored. There is no TTL or automatic release path.

Erasure writes the fence before cancellation. Missing, corrupt, or unavailable
fence infrastructure fails closed. No AWS resource was created or mutated.
