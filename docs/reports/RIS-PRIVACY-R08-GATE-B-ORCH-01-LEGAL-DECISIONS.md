# RIS-PRIVACY-R08-GATE-B-ORCH-01 — Legal Decision Package

This is a technical decision package for Privacy/Legal review. It contains no
legal approval and does not determine a GDPR legal basis.

| Entscheidung | Verarbeitung | Rechtsgrundlagen-Kandidat | Alternative | Risiko | Rechtliche Freigabe | Status |
|---|---|---|---|---|---|---|
| P-01 | Konto/Profilverwaltung | Art. 6(1)(b) or (f), factual assessment required | Minimize account fields | Over-retention/incorrect basis | None | REVIEW REQUIRED |
| P-02 | CV storage and metadata | Art. 6(1)(b) candidate or separate Art. 6(1)(a); Art. 9 assessment | No durable storage / session-only | Special-category data and purpose drift | None | BLOCKED |
| P-03 | Application/status/follow-up | Art. 6(1)(b) candidate; (f) only where justified | Minimize timeline/metrics | Indirect profiling and retention | None | REVIEW REQUIRED |
| P-04 | Privacy receipts | Art. 6(1)(c), (f) or (b) candidate depending on duty | Minimize/delete evidence | Unapproved indefinite retention | None | BLOCKED |
| P-05 | Access/export | Art. 15/20 obligation where applicable; service/security basis | Scoped metadata export | Incomplete categories/third-party data | None | OPEN |
| P-06 | Erasure | Art. 17 obligation where applicable | Legal hold/retention exception | False physical-purge claim | None | BLOCKED |
| P-07 | Consent events | Art. 7 only if valid consent flow exists | Contract/legal obligation where applicable | Receipt proves action, not validity | None | REVIEW REQUIRED |
| P-08 | Processing information | Art. 13/14 duties | Publish versioned notice | Missing purpose/recipient/retention disclosure | None | REVIEW REQUIRED |
| P-09 | Processor boundary | Art. 28/DPA for AWS, Jobsearch, AI providers and Orders where applicable | Reduce providers | Role/transfer ambiguity | None | REVIEW REQUIRED |
| P-10 | Records and security | Art. 30, 32 | Formal registers and controls | Accountability gap | None | REVIEW REQUIRED |
| P-11 | DPIA screening | Art. 35 | Restrict profiling/CV processing | Special-category/profiling risk | None | REVIEW REQUIRED |
| P-12 | Backup/PITR | Recovery necessity versus erasure | Restore only after ledger reconciliation | Resurrection of deleted subjects | None | BLOCKED |

The repository's processing-purpose, transparency, retention and inventory
documents remain the source package. Candidate bases and durations must not be
converted into implementation or release approval without Privacy/Legal signoff.
