# Privacy remediation plan (proposal; no execution authorized)

**Status:** PLANNED ONLY. This discovery task makes no runtime, Terraform, secret, queue, deployment, or sister-repository changes. Real-data processing remains NO-GO until the [acceptance gate](PRIVACY-ACCEPTANCE-GATE.md) is approved by named humans.

## Workstreams and ordering

| Order | Owner | Work item / dependency | Acceptance evidence | Existing/required tests | Status |
|---:|---|---|---|---|---|
| 0 | Privacy/Legal + product owners | Decide controller/processor roles, purposes, Article 6/9 basis, notice, retention, exception and DPIA outcome before any live remediation design. | Signed purpose/role register, notice version, retention schedule, DPIA decision | Document review; no code test substitutes | BLOCKED on human/legal decisions |
| 1 | RIS + Mays-Orders owners | Define stable opaque subject linkage and inventory every Orders write path; include RIS dispatch, retries, result callbacks and legacy orders. Depends on 0 and approved data minimization. | Synthetic end-to-end query proving every in-scope AgentOrder is discoverable; migration/backfill strategy separately approved | RIS `tests/test_agent_order_dispatch_e2e.py`; Orders `lambda/tests/test_order_service.py`, `test_result_handoff.py`; add property tests for all producers and index coverage | OPEN; pin must remain unchanged in this task |
| 2 | RIS + Orders owners | Complete inspect/export projections and all embedded personal-data fields; provide per-domain partial status and safe export format. Depends on 1. | Synthetic fixture with all data categories; export manifest/count reconciles each store; no secret/internal key leak | RIS `test_partner_privacy_inspection.py`, `test_application_privacy_contract.py`; Orders privacy service/index tests; add cross-repo contract tests | OPEN |
| 3 | RIS data/document owners | Complete resumable deletion/anonymization, child ordering, write freeze, S3 versions/markers, profile metadata, cursors/idempotency/capacity/lifecycle and Cognito boundary. Depends on 0–2. | Synthetic delete/partial/retry verification by category; never claim completed while required records remain | RIS `test_privacy_erasure_contract.py`, `test_privacy_erasure_repository.py`, `test_privacy_erasure_security.py`, `test_application_erasure.py`, partner-profile integration tests; add S3 version purge tests | OPEN |
| 4 | RIS runtime + Orders + Jobsearch | Define queue/result cancellation, terminal-result policy, DLQ inspection/redrive safeguards, log minimization and provider/cache deletion request semantics. Depends on retention and rights policy. | Synthetic stale-message/retry tests; explicit owner response for each external boundary; no live redrive in validation | RIS worker cancellation/runtime tests; Orders result-consumer tests; Jobsearch API/consent tests; add DLQ/log payload scanning with synthetic markers | OPEN |
| 5 | Platform/operations + Privacy | Approve backup/PITR lifecycle and deletion ledger; implement restore reconciliation and S3 version expiry only under separate approved change. | Authorized synthetic restore proves erased subjects do not reappear; expiry and ledger retention evidence | Existing RIS recovery/CAS/reconciliation tests; add restore rehearsal and all-version S3 assertions | OPEN; no Terraform Apply/AWS action in this plan |
| 6 | Security + service owners | Inventory/rotate/revoke internal secrets, least privilege, redaction and audit access across exact deployments. | Secret ownership/rotation evidence and negative authorization tests; no secret value in artifacts | Orders secret auth tests; RIS auth/security tests; add rotation/revocation and log-redaction tests | OPEN |
| 7 | Release owner + Privacy/Legal | Run final synthetic cross-repository acceptance, close all blockers, attach deployment SHA and human sign-offs. | All gate rows evidenced and signed; real-data decision is explicit, scoped and revocable | Existing original suites plus additional tests above and CI report | NOT AUTHORIZED |

## Proposed CI/CD privacy gate (non-approving)

1. Run existing repository-native unit/contract/security suites in isolated processes; pin exact RIS, Orders and Jobsearch SHAs. No live credentials, personal datasets, or AWS operations.
2. Run static checks for route/auth contract drift, purpose/notice registry consistency, data-category inventory links, retention configuration drift, forbidden secret/CV/token logging and missing subject index fields on every order producer.
3. Run synthetic XRepo contract tests for owner isolation, inspect/export completeness, idempotent partial erasure, queue cancellation, result handling and backup restore/no-resurrection using mocks/local emulators only.
4. Publish immutable evidence with pass/fail/skipped status, source SHA, test command, fixture provenance and limitations. A skipped or unavailable boundary is never PASS.
5. CI can block release and request review but **cannot approve legal basis, consent, real-data processing, Terraform Apply or deployment**. Required manual approvals are separate named Privacy/Legal, Security and service-owner decisions attached to the exact release SHA.

## Sequencing constraints

- Resolve lawfulness and scope before implementing deletion/retention behavior; do not infer policy from existing TTL values.
- Establish complete subject linkage before claiming inspect/export/erase completeness.
- Make operations resumable and partial before enabling cross-domain execution.
- Validate with synthetic fixtures before separately authorized live verification; any deployment/secret/queue/backup change requires its own scoped task and approval.
- Keep Mays-Orders pin `db4f9e7` unchanged unless a separately authorized upgrade task passes the full upgrade gate.
