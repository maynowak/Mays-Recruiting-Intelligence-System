# RIS-R08-PR-08B — Security Traceability

| Finding | Risk | Fix | Code evidence | Negative test | Retest | Status |
|---|---|---|---|---|---|---|
| FIX-01 | WorkItem resurrection | durable fence + atomic admission | `subject_fence.py`, `pipeline.py` | replay/missing-row tests | SECURITY-06/07 | PASS local |
| FIX-02 | stale in-flight worker | final fence/attempt transaction + CAS result writes | `pipeline.py` | inflight fence test | SECURITY-06 | PASS local |
| FIX-03/04 | duplicate retry/terminal replay | conditional retry and terminal states | `pipeline.py` | worker retry suite | SECURITY-06 | PASS local |
| FIX-05 | incomplete ApplicationV1 resume | IN_PROGRESS/version/cursor semantics | `application_repository.py` | application suite | SECURITY-07 | PASS local |
| FIX-06 | public reduced erasure scope | synthetic completion opt-in only | `privacy_document_erasure.py` | C1B tests | SECURITY-06/07 | PASS local |
| FIX-07/RG-09 | cached PII responses | centralized no-store boundary | `lambda/handler.py` | cache/API tests | SECURITY-06/07 | PASS local |
| 07-HIGH | public erasure omitted Applications | existing executor wired into route | `handler.py`, `privacy_erasure.py` | public route/page/failure tests | independent 7-pass retest | PASS local |

Open live gates remain RG-09 legal, RG-10 PITR/restore/ledger, RG-11
SQS/DLQ/redrive, and productive R08-C erasure activation.
