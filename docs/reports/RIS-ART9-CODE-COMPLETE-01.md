# RIS-ART9-CODE-COMPLETE-01 — ART. 9 CODE CLOSURE

**Status: ART. 9 CODE COMPLETE / DEPLOYMENT PENDING**

- RIS original Art. 9 work: `fd02722` on `origin/main` (restored from the
  cv-storage integration line)
- Gate-03 enforcement addition: `e370567`
- Jobsearch BFF Art. 9 enforcement: present on Jobsearch main `c63911f`
- No code change in this closure. No deployment, plan/apply, AWS mutation or
  main merge.

## 1. What was already complete

The original Art. 9 proof work is not new. It exists on:

- `feature/jm-ris-cv-storage-integration-01`
- `release/structured-cv-rc2-reconciled`

Relevant commits:

| Commit | Purpose |
| --- | --- |
| `2301aee` | store and validate ApplicationV1 Art. 9 consent proof |
| `3ed915b` | require the Art. 9 text for special-category consent |
| `994954c` | v4 Art. 9 text including `sex_life` |
| `6bfb71f` | v4 operator approval for the limited beta pilot |
| `fd02722` | restore proof and profile purposes on main |

`fd02722` is an ancestor of `origin/main`. It already contains:

- `validate_consent_proof`;
- explicit `specialCategoriesConsent` + category subset validation;
- purpose-specific external text and pinned SHA-256;
- fail-closed error codes;
- proof persistence in the consent row and append-only event;
- legacy-row read/withdraw behavior;
- re-grant/`RECONSENT_REQUIRED` behavior.

## 2. What Gate 03 added

`e370567` did **not** reimplement the original contract. Its
`consent_contract.py` change is limited to:

```python
SPECIAL_CATEGORY_REQUIRED_PURPOSES = frozenset({"cv-storage"})

if purpose in SPECIAL_CATEGORY_REQUIRED_PURPOSES and not consent:
    raise ConsentContractError(
        "SPECIAL_CATEGORIES_REQUIRED",
        f"{purpose} requires explicit special-category consent")
```

plus negative tests and documentation. That closed the one remaining gap:
RIS now **requires** the already-existing proof for new `cv-storage` grants.

## 3. Verification

RIS focused Art. 9 / consent suites:

```text
tests/test_consent_special_categories.py
tests/test_consent_notice_catalog_contract.py
tests/test_consent_notice_lifecycle.py
tests/test_consent_e2e_joint.py
tests/test_cv_storage_consent_gate.py
84 passed
```

Jobsearch BFF / UI Art. 9 suites:

```text
tests/api/ris-consents.test.mjs
src/components/StorageConsentLive.test.tsx
src/lib/usePersistentCvStorage.test.tsx
9 files, 156 tests passed
```

Original Art. 9 code remains intact; the Gate-03 change is additive.

## 4. Not done (deployment only)

The current live RIS Lambda `UCdPXzMRdBFnnPQyIj6C53YMfqg5qAm8PW8Gy3sk/Cs=`
predates the Art. 9 enforcement addition. Therefore:

- Code on the integration branches is complete.
- Live behavior does not yet enforce the new `cv-storage` requirement.
- Deployment is pending because the RIS Terraform plan is blocked by the
  Mays-Orders module contract and a fresh authorized plan has not been made.
- Privacy/Legal confirmation of the Art. 9 legal basis and consent retention
  remains a release gate.

## 5. Decision

Art. 9 is **code-complete**. No further Art. 9 code work is required for the
current contract.

Remaining work is deployment/release governance only:

1. reconcile the RIS Orders module/pin so a plan is possible;
2. authorize and review a plan with 0 delete / 0 replace and no enforcement
   weakening;
3. obtain Privacy/Legal sign-off;
4. apply and run a synthetic live E2E;
5. no main merge or production rollout without those approvals.

**ART. 9 CODE COMPLETE / DEPLOYMENT PENDING**
