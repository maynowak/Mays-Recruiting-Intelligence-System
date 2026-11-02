# R08-E2E-G1 — LOCAL TEST ENVIRONMENT & INTEGRATION

**Status:** LOCAL INTEGRATION VERIFIED / AWS E2E BLOCKED

## Scope and safety

- Baseline: `e03f9faec0a3d2e0c97bd2de69debf4a4ddda90e`
- Python 3.14.10 was installed user-locally; no global Python package change
- Project-local `.venv` was created
- Java 17.0.21 was extracted under the temporary OpenCode directory only
- DynamoDB Local used dummy credentials and in-memory storage
- No AWS calls, deployments, Terraform applies, productive S3 operations,
  erasure activation or receipt activation were performed
- Jobsearch and Orders were not changed
- The 39 pre-existing untracked files and `terraform/ris-dev2.tfvars` were
  preserved

## Environment

| Component | Result |
|---|---|
| Python | 3.14.10 PASS |
| Project venv | `.venv` PASS |
| pytest | 9.2.0 PASS |
| boto3/botocore | 1.43.123 PASS |
| moto | 5.2.5 PASS |
| requests/urllib3 | installed and importable PASS |
| Java | OpenJDK/Zulu 17.0.21 PASS |
| DynamoDB Local | downloaded and started on local port 18000 |
| Credentials | dummy `local-r08` values only |
| `types-all>=2024.1.0` | unavailable on configured package index; not required for executed runtime/test suites |

The first `requirements.txt` installation was intentionally not claimed as a
complete install because the index exposes only `types-all==1.0.0`. The
runtime/test and development packages required for this gate were then
installed explicitly in `.venv`; no global package installation was used.

## Collection comparison

| Run | Result |
|---|---|
| Before G1 restoration | 2,121 collected, 27 collection errors under Python 3.15 with missing dependencies |
| After G1 restoration | 2,360 collected, 16 collection errors |

The remaining 16 errors are confined to the generated separate package tree
`installer/projects/mays_order_builder/**`. They are package-path/import setup
errors (`cognito_backup`, `installer.core`, `installer.cli`, `installer.terraform`,
`index`, `errors`, `state_machine`, `module_builder`, `delete_seed_orders`,
etc.). No RIS production source was changed to mask or reclassify them.

## DynamoDB Local integration

Command:

```text
RIS_TEST_DYNAMODB_ENDPOINT=http://127.0.0.1:18000
pytest tests/integration/test_partner_profile_dynamodb_local.py -q
```

Result: **39 passed in 6.57s**.

The test suite created and removed only generated `ris-r07g0-*` tables. An
initial run supplied `RIS_TEST_TABLE_PREFIX=ris-r07g0-`, which is invalid for
the harness because that variable expects a complete table name. The variable
was removed; the harness then generated valid isolated names automatically.
No source correction was required.

### Listener qualification

DynamoDB Local's current distribution does not support `-bind` or `-host`.
Its listener reported `::` while the SDK endpoint and harness were explicitly
`http://127.0.0.1:18000`. The process was used only for this local run and was
force-stopped immediately afterward; port 18000 is now inactive. This remains
a local-environment hardening note for any future run that requires a verified
OS-level loopback-only listener.

## C1A/C1B/C0F and privacy regression

Command scope:

```text
tests/test_r08_c1a_profile_only_erasure.py
tests/test_r08_c1b_document_erasure_integration.py
tests/test_r08_c0f_s3_erasure.py
tests/test_privacy_erasure_contract.py
tests/test_privacy_erasure_repository.py
tests/test_privacy_erasure_security.py
tests/test_privacy_receipt_contract.py
tests/test_privacy_receipt_journal.py
tests/test_partner_privacy_inspection.py
```

Result: **125 passed in 0.43s**.

These are synthetic/local tests. They do not activate the receipt journal in
production, call AWS, delete real S3 objects, or perform productive erasure.

## Remaining blockers

G1 does not resolve the previously documented AWS/IAM or policy blockers:

- UserProfile IAM still lacks the required guarded delete/transaction rights.
- Version-aware S3 permissions (`ListBucketVersions`,
  `DeleteObjectVersion`) remain unresolved.
- Distributed S3 fencing and historical upload-ticket cutover evidence remain
  open.
- Quiescence and all G5 categories remain release prerequisites.
- Durable operation/phase repositories are not provisioned and wired for AWS.
- Object Lock/legal-hold evidence is absent.
- Retention/privacy policy remains `REVIEW_REQUIRED`.
- PITR/backup/restore reconciliation evidence is not established.
- Receipt journal and erasure activation remain disabled.
- The separate Builder package/import tree still prevents a clean monorepo
  collection.
- `types-all>=2024.1.0` remains unavailable from the configured index.

## G2 readiness decision

- **Local G1 environment:** PASS for the RIS DynamoDB integration and targeted
  erasure/privacy regression.
- **Full clean repository collection:** BLOCKED by 16 Builder-only import
  errors.
- **E2E-G2 non-production AWS execution:** **NOT READY**. It requires explicit
  infrastructure/IAM, fencing, upload cutover, quiescence, retention,
  backup/restore and approval evidence first.
- **Production erasure:** BLOCKED.

## Cleanup and git result

DynamoDB Local was stopped and no listener remains on port 18000. Temporary
Java/DynamoDB artifacts are outside the repository. Git tracked changes are
limited to this report; the 39 pre-existing untracked files remain untouched.

The intended commit is:

```text
test(ris): verify local test environment and integration
```
