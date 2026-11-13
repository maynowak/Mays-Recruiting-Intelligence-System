# RIS-STRUCTURED-CV-BACKEND-HARDENING-02

**Status:** `RIS-STRUCTURED-CV-BACKEND-02 — INTEGRITY & PRIVACY VERIFIED LOCAL / READY FOR BFF PLANNING`

**Date:** 2026-11-13

**Branch:** `feature/ris-structured-cv-backend-hardening-02`

**Baseline:** `9386535c616528522c1ac43b58305fcb03c5c53e`

## 1. Git basis

- Started from the required `feature/ris-structured-cv-backend-01` HEAD
  `9386535`.
- New branch created in an isolated worktree:
  `/home/dci-student/projects/mays-xrepo-orchestration/worktrees/ris-structured-cv-backend-hardening-02`.
- No main merge, deployment, AWS call, Terraform plan/apply or state access.

## 2. Review findings and corrections

### A. DynamoDB concurrency

**Cause:** `update()` performed a pre-read and only checked the version in the
request path, but the subsequent conditional `UpdateItem` was not handled. A
racing writer could make DynamoDB return `ConditionalCheckFailedException`,
which the handler would classify as a generic storage failure.

**Correction:**

- Conditional failures from `update_item` are recognized by error code and
  mapped to `StructuredCvConflict`.
- The repository re-reads only to distinguish:
  - profile gone/foreign → `404`;
  - newer version → `409 VERSION_CONFLICT`;
  - own unchanged item with a failed condition → `409` (never last-write-wins).
- Missing `If-Match` remains `428`; infrastructure errors remain `503`.
- Delete has the same race handling for its profile condition: vanished or
  foreign profile → `404`, changed version → `409`, counter condition failure
  is handled separately (below).

### B. Privacy export

**Cause:** `structuredCvProfiles` existed only in privacy inspect, not in the
general account privacy export.

**Correction:** `_privacy_export_structured_cv` collects every page through the
owner GSI and returns full profiles, including `cvData` and the complete
`importReview` sidecar (`text`, `original`, `edited`, `target`, `status`,
`applied`, page/section provenance). The existing export category set is
unchanged. A structured-CV failure produces an `UNAVAILABLE` category and marks
the overall export `PARTIAL`; it is never reported as complete.

### C. Capacity and deletion

**Cause:** Delete removed the profile and then adjusted the capacity counter in
a separate best-effort write. A failed counter write could leave a successful
delete with a stale counter.

**Correction:**

- Profile delete and `count = count - 1` now use one `TransactWriteItems`.
- The counter condition `count > 0` prevents negative capacity.
- If the counter item is missing/stale, the repository performs one bounded
  owner-index reconciliation and retries the transaction once.
- If reconciliation still fails, the operation raises
  `CAPACITY_RECONCILIATION_REQUIRED` (503); it does not claim successful
  lifecycle completion.
- A public `reconcile_capacity()` recovery operation recomputes the counter
  from the bounded owner index. It is documented as a recovery operation, not
  a concurrent write path.

**Delete contract decision:** the contract and implementation now agree on:

- first own delete → `204`;
- repeated own delete → `404`;
- foreign/unknown ID → `404`.

No tombstone is written. This deliberately avoids retaining ownership metadata
after deletion and gives the same safe response for repeated, foreign and
unknown IDs. The contract and draft OpenAPI were updated accordingly.

### D. Consent / notice safety

- `STRUCTURED_CV_PROFILE_ENABLED` remains default-off in code and Terraform.
- HTTP create/update require `GRANTED` consent **and** an approved notice with
  a non-null `legalApprovalRef`.
- The current structured-CV notice is DRAFT with `legalApprovalRef=null`, so
  the HTTP path always returns fail-closed consent rejection, even when
  `CONSENT_NOTICE_STATE_ENFORCED=false`.
- The production handler contains no test-mode environment branch. The
  partner security boundary test that forbids test-mode bypasses passes.
- The existing `ConsentRepository.grant()` legacy technical behavior still
  allows a DRAFT only when the separate local
  `STRUCTURED_CV_PROFILE_TEST_MODE=true` switch is set and notice enforcement
  is off. That switch is not wired by Terraform and is not reachable through
  the structured-CV HTTP adapter.
- No notice state was changed to APPROVED/ACTIVE. Existing consent purposes
  were not altered.

### E. Erasure and regression

- The existing `PrivacyErasure` structured-CV step remains idempotent and
  resumable across partner scopes.
- Partial deletion is reported as a failed step; `complete=true` is not
  claimed.
- Privacy inspect still returns owner-scoped metadata; privacy export now
  includes full review provenance.
- No existing category or route was removed.

## 3. Test evidence

Focused hardening tests:

```text
tests/test_structured_cv_profile.py          22 passed
tests/test_structured_cv_http.py             13 passed
tests/test_structured_cv_consent.py           3 passed
tests/test_structured_cv_privacy_export.py    2 passed
```

Additional focused checks:

- contract document tests: 8 passed;
- prior structured-CV privacy/erasure tests: passed;
- partner security boundary: passed;
- privacy inspection regression: passed.

Full RIS suite on this branch:

```text
2576 passed, 56 skipped, 19 failed, 425 subtests passed
```

Baseline at `49eb13b`:

```text
2533 passed, 56 skipped, 19 failed, 425 subtests passed
```

The same 19 pre-existing failures remain:

- 13 `test_wrapper_regression.py` wrapper/installer failures;
- 3 `test_composite_lifecycle.py` argument-ordering failures;
- 1 `test_health_plane_integration.py` health-event failure;
- 1 `test_lambda_packaging.py` missing fixture/archive failure;
- 1 `test_platform_handlers.py::TestAgentAPI::test_execute_agent` failure.

No test was removed or weakened. The hardening adds 43 net passing tests over
the contract baseline (28 from backend-01 plus 15 hardening tests).

## 4. Local infrastructure checks

- `terraform fmt -check -recursive terraform`: PASS.
- `terraform init -backend=false` + `terraform validate`: PASS with existing
  deprecation warnings.
- No plan against AWS, no apply, no state access, no AWS STS/API call.
- No Terraform lockfile change was committed.
- Draft OpenAPI YAML and `git diff --check`: PASS.
- Secret/private-data scan: no matches in changed files.

### Verification boundary

The owner GSI is queried in a local moto DynamoDB table. The installed moto
version cannot execute this table's `TransactWriteItems` shape, so transaction
condition behavior is simulated explicitly by the test fake. This is not an
AWS/DynamoDB production verification. Delete/counter atomicity, cancellation
reason handling and real GSI throughput remain to be verified after an approved
deployment.

## 5. Remaining open decisions

`REVIEW_REQUIRED` remains for:

- notice/legal approval and Art. 9 assessment;
- retention, withdrawal grace and post-withdrawal read/export policy;
- backup/PITR reconciliation and physical purge;
- capacity 20 vs. 10;
- production GSI/API Gateway activation and real DynamoDB transaction
  verification;
- BFF/UI consent and conflict UX.

No real CV data, personal data, consent grant, deployment or main integration
was created.

## 6. Commits

- `bf923bf` — concurrency and capacity hardening.
- `aeabfeb` — privacy export and consent/delete-contract hardening.
- This report and audit entry are committed immediately after the code changes.

## 7. Next gates

1. Human review of this report and privacy decision matrix.
2. BFF planning against the stable 404-after-delete, 409-conflict and
   428-missing-precondition semantics.
3. Separately approved Terraform plan containing `gsi-structured-owner` and the
   default-off flag.
4. Real DynamoDB Local or approved AWS verification of transactions and the
   owner GSI.
5. Synthetic authenticated E2E after notice/legal approval and explicit
   feature activation.
