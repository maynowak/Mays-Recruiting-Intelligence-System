# RIS-DEV-CLEANUP-AND-INSTALLER-CONSOLIDATION-01

**Date:** 2026-10-08
**Status:** VERIFIED
**AWS Account:** 240571105849
**Profile:** mayaws
**Region:** eu-central-1

## Summary
Clean removal of Mays-RIS development resources and consolidation of installer with Mays-Orders orchestration.

## Actions Performed

### 1. State Discovery
* Discovered duplicate state objects in `mays-ris-tf-state-dev`
* Identified legacy state key `env:/mays-ris/terraform.tfstate`
* Identified duplicate key `env:/mays-ris/env:/mays-ris/terraform.tfstate`

### 2. Cleanup
* Removed duplicate state object
* Removed DynamoDB lock entries for legacy keys
* Deleted S3 buckets:
  * `mays-ris-cloudtrail-240571105849`
  * `mays-ris-dev-data`
  * `mays-ris-dev-documents` incl. versioning
* Deleted DynamoDB tables:
  * `mays-ris-dev-jobsearches`
  * `mays-ris-dev-agent-catalog`
  * `mays-ris-dev-entitlements`
  * `mays-ris-dev-work-items`
  * `mays-ris-dev-credentials`
  * `mays-ris-dev-api-profiles`
  * `mays-ris-dev-user-profile`
  * `mays-ris-dev-offers`
* Deleted SQS queues
* Deleted Lambda `mays-ris-dev-agent`
* Deleted API Gateway `aboqolpm0f`
* Removed Terraform state object `s3://mays-ris-tf-state-dev/env:/mays-ris/terraform.tfstate`

### 3. Installer Consolidation
* Backend key changed to explicit `env:/{project_name}/{environment}/terraform.tfstate`
* Workspace derivation verified: `project_name` verbatim
* AWS context auto-validation implemented in `installer/ris.py`
* Pin-based auto-checkout implemented in `installer/orchestrator.py`
* State discovery commands added: `state discover`, `state inventory`
* Documentation unified in `docs/installer/RIS-INSTALLER-PARAMETERS.md`

### 4. Verification
* `python -m installer.ris --project-name mays-ris --environment dev --profile mayaws --backend-bucket mays-ris-tf-state-dev --backend-region eu-central-1 --backend-lock-table mays-ris-tf-lock plan` → success
* Package build successful: `terraform/lambda.zip` deterministic
* Mays-Orders pin verified: `9c61237185d202e072b2304355ee836154368846`

## Evidence
* Execution log: `docs/reports/RIS-FRESH-CLONE-CLEAN-INSTALL-01-EXECUTION_LOG.md`
* Destroy manifest: `docs/reports/RIS-DEV-CLEAN-REINSTALL-E2E-01-DESTROY-MANIFEST.md`
* AI_AUDITLOG.md updated

## Next Steps
* Orchestrated fresh install with Mays-Orders consideration
* Apply with `--yes` after final approval
