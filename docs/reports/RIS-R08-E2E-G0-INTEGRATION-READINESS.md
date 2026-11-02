# R08-E2E-G0 — INTEGRATION & DEPLOYMENT READINESS

**Status:** READINESS BASELINE COMPLETE / REAL E2E BLOCKED

## Baseline

- HEAD: `12495ea80b0cd71d7089271e7ee579bb6722890e`
- C1B-1 local acceptance: synthetic USER/CV E2E GO
- No code, Terraform, AWS, installation or deployment changes in this gate
- 39 pre-existing untracked files preserved

## Test environment findings

| Component | Finding | Impact |
|---|---|---|
| Python | `3.15.0` only; project requires 3.14 | **BLOCKED** — no approved 3.14 runtime |
| pytest | `9.2.0` available | usable for dependency-free tests |
| boto3/botocore | not installed | DynamoDB Local and installer tests blocked |
| moto | not installed | AWS-shaped mock tests unavailable |
| requests/urllib3 | not installed | HTTP/installer tests blocked |
| Java | not installed | DynamoDB Local JAR cannot start |
| Docker | not installed | no isolated DynamoDB/LocalStack fallback |
| AWS CLI | not installed | no live smoke path; no live call attempted |
| DynamoDB Local | JAR/lib absent; port 18000 not listening | local transaction integration blocked |
| Builder imports | generated `installer/projects/mays_order_builder` exists, but its tests are a separate package tree and fail collection from the RIS root due missing package-path/dependency setup | full root collection blocked |
| virtual environments | no usable venv detected; only system Python 3.15 | isolated reproducible run unavailable |

No dependency was installed. The repository's `requirements.txt` declares the
missing packages, but that is not evidence of availability.

### Observed collection result

`py -m pytest -q --collect-only` collected 2,121 tests but stopped with **27
collection errors**, including missing `boto3`, `requests`, `urllib3`, and
Builder package imports. This is recorded as a blocker, not a pass.

## Terraform/IAM read-only assessment

### Existing positive bindings

- Partner profile policy includes `GetItem`, `PutItem`, `UpdateItem`,
  `DeleteItem`, `Query` and `TransactWriteItems` on the partner-profile table
  and indexes.
- Partner-profile Terraform table has `gsi-user` and `gsi-parent`.
- Documents bucket has versioning, SSE-S3 and public-access blocking.
- Privacy receipt table is provisioned with a subject GSI.
- `terraform validate` succeeds with existing deprecation warnings.

### Blocking gaps

1. **UserProfile delete authorization:** the Lambda platform policy has no
   `dynamodb:DeleteItem` or `dynamodb:TransactWriteItems` for the UserProfile
   table, although the guarded UserProfile delete requires both.
2. **Version-aware S3 erasure authorization:** the documents policy grants
   `s3:ListBucket`, `s3:GetObject`, `s3:PutObject` and `s3:DeleteObject`, but not
   `s3:ListBucketVersions` or `s3:DeleteObjectVersion`.
3. **Durable erasure stores are not provisioned/wired:** no Terraform table or
   Lambda environment binding was found for `ERASURE_OPERATION_TABLE` or the
   C0F S3 phase repository. The operation/phase repositories therefore remain
   fail-closed unless separately approved and configured.
4. **S3 Object Lock/legal hold evidence:** no documents-bucket Object Lock or
   legal-hold verification is present in Terraform. Versioning is not Object
   Lock.
5. **PITR/backup evidence:** no `point_in_time_recovery`, AWS Backup binding or
   restore reconciliation is present in this Terraform tree. The privacy
   contract explicitly keeps backup/PITR claims separate from active deletion.
6. **Activation flags:** Terraform explicitly sets
   `PRIVACY_RECEIPT_JOURNAL_ENABLED = "false"`; erasure operation, phase,
   execution, freeze and upload-ledger flags are not deployed as approved
   environment bindings. Enabling them ad hoc would not establish policy or
   fencing readiness.

`terraform fmt -check -recursive` reports the existing ignored/local
`terraform/ris-dev2.tfvars`; no Terraform file was changed by this gate.

## Consolidated production blockers

| Priority | Blocker | Required evidence |
|---|---|---|
| P0 | Distributed S3 fencing | stale-worker protection at the S3 request boundary, not only DynamoDB CAS |
| P0 | Historical upload tickets | complete issuer/path inventory, unknown-ticket resolution and cutover evidence |
| P0 | Quiescence | active freeze, blocked issuance, zero active actions, complete version/delete-marker inventory |
| P0 | S3 IAM/Object Lock | version-list/delete permissions, bucket policy, legal hold and Object Lock verification |
| P0 | UserProfile/G5 IAM | guarded UserProfile delete and all operation/phase transactions authorized |
| P0 | Open G5 categories | credentials, API profiles, work items, system records, Cognito and other required phases explicitly resolved |
| P1 | Retention/privacy approval | approved periods and legal holds; no invented TTL or receipt retention |
| P1 | Durable operation/checkpoint stores | provisioned tables, conditional writes, crash/resume and restore tests |
| P1 | Backup/PITR/restore | PITR/backup configuration, deletion ledger and restore reconciliation evidence |
| P1 | Receipt journal | R08-A2 approval, retention policy and controlled activation; remains disabled now |

## Prioritized E2E test matrix

| Test | Prerequisite | Expected evidence | Release criterion |
|---|---|---|---|
| Python/import baseline | approved Python 3.14 venv and locked dependencies | `pip check`, import manifest | all declared runtime/test imports resolve |
| DynamoDB Local hierarchy | loopback DynamoDB Local, isolated `ris-r07g0-*` names | table creation, GSI queries, transaction logs | USER/CV hierarchy and conditional conflicts pass |
| Operation/checkpoint CAS | approved operation/phase tables | version/CAS/replay records | stale worker cannot advance checkpoint |
| Write freeze | guarded test tables and verified context | freeze condition checks on every mutation | foreign/stale/freeze-loss mutations fail closed |
| S3 fake version/delete-marker | fenced fake adapter | explicit version deletes plus empty re-inventory | metadata release only after verification |
| S3-compatible non-production | approved bucket, versioning, IAM, Object Lock evidence | CloudTrail/IAM/list/delete evidence | no stale-worker or late-upload gap remains unaddressed |
| Upload cutover/quiescence | all issuers known and legacy population resolved | ticket inventory, action count, freeze and lease evidence | quiescence lease acquisition is justified |
| Full USER E2E | all G5 categories and retention decision | operation/checkpoint/receipt evidence | only then may full operation complete |
| Full CV E2E | CV scope authorization and unrelated-CV fixture | scope-isolation evidence | unrelated users/CVs unchanged |
| Failure/resume | kill/restart at each external action boundary | retry phase and idempotent replay evidence | no false completion or lost reference |
| Backup restore | approved PITR/backup and deletion-ledger procedure | restore reconciliation report | erased subject cannot be resurrected |

## Smallest safe next executable step

After explicit environment approval, the smallest safe step is **local-only
dependency and DynamoDB-Local restoration**, not AWS execution:

1. install/select Python 3.14;
2. create an isolated project venv;
3. install `requirements.txt` in that venv;
4. obtain an approved DynamoDB Local distribution and Java 17+;
5. start it only on `127.0.0.1:18000` with an isolated `ris-r07g0-*`
   namespace; and
6. run `tests/integration/test_partner_profile_dynamodb_local.py` plus the
   C1A/C1B suites with `RIS_TEST_DYNAMODB_ENDPOINT` explicitly set.

Do not enable erasure persistence, receipt writes, S3 execution or any AWS
endpoint in that step. The next step after that local gate requires separate
approval for IAM/table/bucket changes and non-production AWS evidence.

## Gate decision

- **Integration readiness:** **BLOCKED** — environment and infrastructure
  prerequisites are not complete.
- **Next executable E2E step:** approved Python 3.14 + isolated dependencies +
  loopback DynamoDB Local only.
- **Real AWS E2E:** **BLOCKED**.
- **Production:** **BLOCKED**.
