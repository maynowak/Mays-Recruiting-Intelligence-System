# MAYS-RIS-PARALLEL-INSTALLATION-PREFLIGHT-01

**Date:** 2026-10-12  
**Mode:** Read-only AWS + Local Verification  
**Target:** Mays-RIS Installer  
**Status:** EVIDENCE-BASED / FAIL-CLOSED  

---

## 1. Repository and Source Verification

| Property | Value |
|----------|-------|
| **Remote Origin** | git@github.com:maynowak/Mays-Recruiting-Intelligence-System.git |
| **Remote Main HEAD** | eb317a0 (docs: RIS-FOUNDATION-INSTALLER-LIFECYCLE-01 checkpoint report and audit log) |
| **Local Branch** | main |
| **Local HEAD** | eb317a0 |
| **Working Tree** | Clean (only pre-existing untracked docs/) |
| **Installer Entry Point** | `python -m installer.ris` (`installer/ris.py`) |
| **Terraform Config Root** | `terraform/` |
| **Installer Project Dir** | `installer/projects/` |

✅ Previous checkpoint documentation committed (RIS-FOUNDATION-INSTALLER-LIFECYCLE-01-REPORT.md, AI_AUDITLOG.md)

---

## 2. Existing Installations

### Existing RIS Installation (Production)

| Property | Value |
|----------|-------|
| project_name | mays-ris |
| environment | dev |
| region | eu-central-1 |
| AWS Account | 240571105849 |
| AWS Profile | mayaws |
| Terraform Workspace | mays-ris |
| Backend Bucket | mays-ris-tf-state-dev |
| Lock Table | mays-ris-tf-lock |
| Legacy State Key | env:/mays-ris/env:/mays-ris/dev/terraform.tfstate |
| Canonical State Key | env:/mays-ris/dev/terraform.tfstate |

**State Divergence:** Legacy state exists (serial 21, 326KB, real infrastructure). Canonical state absent (404). Stale locks on both paths.

### Existing Orders Installation (Reference Clone)

| Property | Value |
|----------|-------|
| Directory | `installer/projects/mays_orders/` |
| Source | Mays-Orders-AWS installer clone |
| Pinned Commit | 9c61237185d202e072b2304355ee836154368846 |
| State Type | Local (terraform.tfstate in terraform/ directory) |
| Workspace | mays-orders (hardcoded) |
| Project Names Used | mays-orders-test-e2e-01 (context) |
| Manages | Integration/test configuration only |
| Backend | None (local state) |

✅ **Orders installation is fully isolated** - separate directory, local state, different workspace, no S3 backend.

---

## 3. Orders Installation Boundary Verification

**Verified Claims:**

| Claim | Status | Evidence |
|-------|--------|----------|
| Mays-Orders-AWS installer clone | ✅ VERIFIED | Directory structure matches, pinned commit in `installer/mays-orders-clone.pinned.json` |
| Pinned source commit: 9c61237 | ✅ VERIFIED | `installer/mays-orders-clone.pinned.json` |
| Local Terraform state | ✅ VERIFIED | `installer/projects/mays_orders/terraform/terraform.tfstate` exists (serial 129) |
| Workspace: mays-orders | ✅ VERIFIED | Context files show `"terraform_workspace": "mays-orders"` |
| No S3 backend | ✅ VERIFIED | No `backend "s3"` block in terraform/main.tf |
| Manages only integration config | ✅ VERIFIED | State shows Orders reader Lambda, API routes - reads from Mays-Orders table |

**Directory Contents:**
```
installer/projects/mays_orders/
├── .mays-installer/runs/          # Installation run metadata (41 runs)
├── terraform/
│   ├── main.tf                    # No backend block
│   ├── terraform.tfstate          # Local state (serial 129)
│   └── modules/                   # Terraform modules
├── installer/                     # Orders installer source code
├── lambda/                        # Orders Lambda code
└── tests/                         # Tests
```

**RIS Parallel Installation Impact:** NONE - Uses different project_name, workspace, backend bucket, lock table, state key.

---

## 4. Parallel Test Installation Parameters (Derived from Current Installer Code)

| Parameter | Value | Derivation |
|-----------|-------|------------|
| **project_name** | `mays-ris-e2e-test` | Proposed, passes validation |
| **environment** | `test` | ✅ Supported (VALID_ENVIRONMENTS = dev, test, prod) |
| **region** | `eu-central-1` | Default |
| **Terraform Workspace** | `mays-ris-e2e-test` | `workspace_for_project(project_name)` verbatim |
| **Backend Bucket** | `mays-ris-e2e-test-tf-state-test` | `BackendNames.for_project()` |
| **Lock Table** | `mays-ris-e2e-test-tf-lock` | `BackendNames.for_project()` |
| **Configured Key** | `test/terraform.tfstate` | `{environment}/terraform.tfstate` |
| **workspace_key_prefix** | `env:` | Terraform default |
| **Effective S3 State Key** | `env:/mays-ris-e2e-test/test/terraform.tfstate` | `workspace_key_prefix/workspace/configured_key` |
| **Resource Prefix** | `mays-ris-e2e-test-test` | `${var.project_name}-${var.environment}` |
| **Lock Identity** | `mays-ris-e2e-test-tf-state-test/env:/mays-ris-e2e-test/test/terraform.tfstate` | Bucket + effective key |

### Naming Constraint Verification

| Constraint | Check | Result |
|------------|-------|--------|
| DynamoDB table min 3 chars | len("mays-ris-e2e-test") = 17 | ✅ PASS |
| S3 bucket max 63 chars | len("mays-ris-e2e-test-tf-state-test") = 31 | ✅ PASS |
| S3 bucket valid chars | ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ | ✅ PASS |
| No leading/trailing hyphen | Verified | ✅ PASS |
| DynamoDB lock table max 255 | len("mays-ris-e2e-test-tf-lock") = 25 | ✅ PASS |

---

## 5. Complete Resource Collision Analysis

### Resource Inventory with Collision Risk Assessment

| Resource Category | Terraform Address | AWS Type | Computed Name (Parallel) | Computed Name (Existing RIS) | Uniqueness Scope | Collision Risk |
|-------------------|-------------------|----------|--------------------------|------------------------------|------------------|----------------|
| **Cognito User Pool** | module.cognito.aws_cognito_user_pool.pool | User Pool | mays-ris-e2e-test-test | mays-ris-dev | Account | ✅ NONE |
| **Cognito App Client** | module.cognito.aws_cognito_user_pool_client.client | App Client | mays-ris-e2e-test-test-client | mays-ris-dev-client | User Pool | ✅ NONE |
| **Cognito App Client (RIS API)** | module.cognito.aws_cognito_user_pool_client.ris_api | App Client | mays-ris-e2e-test-test-ris-api | mays-ris-dev-ris-api | User Pool | ✅ NONE |
| **Cognito M2M Client** | module.cognito.aws_cognito_user_pool_client.m2m_client | App Client | mays-ris-e2e-test-test-m2m-client | mays-ris-dev-m2m-client | User Pool | ✅ NONE |
| **Cognito Groups** | module.cognito.aws_cognito_user_pool_group.* | Groups | candidates, recruiters, admins... | same names | User Pool | ✅ NONE (scoped to pool) |
| **Cognito Domain** | module.cognito.aws_cognito_user_pool_domain.domain | Domain | mays-ris-e2e-test-test | mays-ris-dev | Region | ✅ NONE |
| **API Gateway REST API** | module.api.aws_apigatewayv2_api.api | REST API | mays-ris-e2e-test-test-api | mays-ris-dev-api | Account | ✅ NONE |
| **API Gateway Stage** | module.api.aws_apigatewayv2_stage.stage | Stage | $default | $default | API | ✅ NONE (scoped to API) |
| **API Authorizers** | module.api.aws_apigatewayv2_authorizer.* | Authorizers | mays-ris-e2e-test-test-jwt-human/m2m | mays-ris-dev-jwt-human/m2m | API | ✅ NONE |
| **API Routes** | module.api.aws_apigatewayv2_route.* | Routes | /health, /platform, /me, /agents, /orders... | same paths | API | ✅ NONE |
| **Lambda: Agent** | module.lambda.aws_lambda_function.agent | Function | mays-ris-e2e-test-test-agent | mays-ris-dev-agent | Account | ✅ NONE |
| **Lambda: Health Writer** | module.health_plane.aws_lambda_function.health_writer | Function | mays-ris-e2e-test-test-health-writer | mays-ris-dev-health-writer | Account | ✅ NONE |
| **Lambda: Health Publisher** | module.health_plane.aws_lambda_function.health_publisher | Function | mays-ris-e2e-test-test-health-publisher | mays-ris-dev-health-publisher | Account | ✅ NONE |
| **Lambda Permissions** | module.lambda/aws_lambda_permission.* | Permissions | Scoped to function ARNs | Scoped to function ARNs | Account | ✅ NONE |
| **IAM Role** | module.iam.aws_iam_role.lambda_execution | Role | mays-ris-e2e-test-lambda-role | mays-ris-lambda-role | Account | ✅ NONE |
| **IAM Policies** | module.iam.aws_iam_role_policy.* | Policies | mays-ris-e2e-test-lambda-policy | mays-ris-lambda-policy | Account | ✅ NONE |
| **SQS Work Queue** | module.sqs.aws_sqs_queue.work_queue | Queue | mays-ris-e2e-test-test-work-queue | mays-ris-dev-work-queue | Account | ✅ NONE |
| **SQS CV Queue** | module.sqs.aws_sqs_queue.cv_queue | Queue | mays-ris-e2e-test-test-cv-queue | mays-ris-dev-cv-queue | Account | ✅ NONE |
| **SQS ATS Queue** | module.sqs.aws_sqs_queue.ats_queue | Queue | mays-ris-e2e-test-test-ats-queue | mays-ris-dev-ats-queue | Account | ✅ NONE |
| **SQS Match Queue** | module.sqs.aws_sqs_queue.match_queue | Queue | mays-ris-e2e-test-test-match-queue | mays-ris-dev-match-queue | Account | ✅ NONE |
| **SQS DLQ** | module.sqs.aws_sqs_queue.dlq | Queue | mays-ris-e2e-test-test-dlq | mays-ris-dev-dlq | Account | ✅ NONE |
| **DynamoDB: Work Items** | module.dynamodb.aws_dynamodb_table.work_items | Table | mays-ris-e2e-test-test-work-items | mays-ris-dev-work-items | Account | ✅ NONE |
| **DynamoDB: Agent State** | module.dynamodb.aws_dynamodb_table.agent_state | Table | mays-ris-e2e-test-test-agent-state | mays-ris-dev-agent-state | Account | ✅ NONE |
| **DynamoDB: User Profile** | module.dynamodb.aws_dynamodb_table.user_profile | Table | mays-ris-e2e-test-test-user-profile | mays-ris-dev-user-profile | Account | ✅ NONE |
| **DynamoDB: Agent Catalog** | module.dynamodb.aws_dynamodb_table.agent_catalog | Table | mays-ris-e2e-test-test-agent-catalog | mays-ris-dev-agent-catalog | Account | ✅ NONE |
| **DynamoDB: Entitlements** | module.dynamodb.aws_dynamodb_table.entitlements | Table | mays-ris-e2e-test-test-entitlements | mays-ris-dev-entitlements | Account | ✅ NONE |
| **DynamoDB: Job Searches** | module.dynamodb.aws_dynamodb_table.jobsearches | Table | mays-ris-e2e-test-test-jobsearches | mays-ris-dev-jobsearches | Account | ✅ NONE |
| **DynamoDB: API Profiles** | module.dynamodb.aws_dynamodb_table.api_profiles | Table | mays-ris-e2e-test-test-api-profiles | mays-ris-dev-api-profiles | Account | ✅ NONE |
| **DynamoDB: Offers** | module.dynamodb.aws_dynamodb_table.offers | Table | mays-ris-e2e-test-test-offers | mays-ris-dev-offers | Account | ✅ NONE |
| **DynamoDB: Credentials** | module.dynamodb.aws_dynamodb_table.credentials | Table | mays-ris-e2e-test-test-credentials | mays-ris-dev-credentials | Account | ✅ NONE |
| **DynamoDB: Partner Apps** | module.dynamodb.aws_dynamodb_table.partner_applications | Table | mays-ris-e2e-test-test-partner-applications | mays-ris-dev-partner-applications | Account | ✅ NONE |
| **DynamoDB GSIs** | module.dynamodb.aws_dynamodb_table.*.global_secondary_index | GSI | Scoped to table | Scoped to table | Table | ✅ NONE |
| **S3: Data Bucket** | aws_s3_bucket.data | Bucket | mays-ris-e2e-test-test-data | mays-ris-dev-data | Global | ✅ NONE |
| **S3: Documents Bucket** | module.documents.aws_s3_bucket.documents | Bucket | mays-ris-e2e-test-test-documents | mays-ris-dev-documents | Global | ✅ NONE |
| **S3: Health Public Bucket** | module.health_public.aws_s3_bucket.public_presentation | Bucket | mays-ris-e2e-test-test-health-public | mays-ris-dev-health-public | Global | ✅ NONE |
| **S3: Health State Bucket** | module.health_plane.aws_s3_bucket.health_state | Bucket | mays-ris-e2e-test-test-health-state | mays-ris-dev-health-state | Global | ✅ NONE |
| **S3: CloudTrail Bucket** | module.cloudtrail.aws_s3_bucket.trail | Bucket | mays-ris-e2e-test-cloudtrail-240571105849 | mays-ris-cloudtrail-240571105849 | Global | ✅ NONE |
| **CloudTrail Trail** | module.cloudtrail.aws_cloudtrail.trail | Trail | mays-ris-e2e-test-trail | mays-ris-trail | Account | ✅ NONE |
| **CloudWatch Log Groups** | module.lambda/aws_cloudwatch_log_group.lambda_logs | Log Group | /aws/lambda/mays-ris-e2e-test-test-* | /aws/lambda/mays-ris-dev-* | Account | ✅ NONE |
| **CloudWatch Dashboard** | module.monitoring.aws_cloudwatch_dashboard.overview | Dashboard | mays-ris-e2e-test-overview | mays-ris-overview | Account | ✅ NONE |
| **CloudWatch Alarms** | module.monitoring.aws_cloudwatch_metric_alarm.* | Alarms | mays-ris-e2e-test-* | mays-ris-* | Account | ✅ NONE |
| **EventBridge Rule** | module.health_plane.aws_cloudwatch_event_rule.health_publisher_schedule | Rule | mays-ris-e2e-test-test-health-publisher-schedule | mays-ris-dev-health-publisher-schedule | Account | ✅ NONE |
| **Backend State Bucket** | (installer bootstrap) | S3 Bucket | mays-ris-e2e-test-tf-state-test | mays-ris-tf-state-dev | Global | ✅ NONE |
| **Backend Lock Table** | (installer bootstrap) | DynamoDB Table | mays-ris-e2e-test-tf-lock | mays-ris-tf-lock | Account | ✅ NONE |

### Special Attention Items

| Item | Analysis | Risk |
|------|----------|------|
| **Hardcoded Names** | None found in RIS modules - all use `${var.project_name}-${var.environment}` | ✅ NONE |
| **Shared Account Resources** | All resources use project-prefixed names | ✅ NONE |
| **S3 Global Namespace** | All buckets include project_name + environment | ✅ NONE |
| **IAM Global Names** | All roles/policies prefixed with project_name | ✅ NONE |
| **Cognito Callback URLs** | Not configured (Google auth off), would be passed via vars | ✅ NONE |
| **Shared API Custom Domains** | None configured (uses default execute-api) | ✅ NONE |
| **CloudTrail Destination** | Separate bucket per project | ✅ NONE |
| **Existing Resource Imports** | None in RIS modules | ✅ NONE |
| **Data Sources Ref Prod** | Only `aws_caller_identity`, `aws_region` (account/region metadata) | ✅ NONE |
| **Env Vars with Prod IDs** | None - Lambda env vars use Terraform refs | ✅ NONE |
| **Orders Reader Defaults** | Points to Mays-Orders production (intentional, shared read access) | ✅ INTENTIONAL |

---

## 6. Terraform Backend Isolation

### Proposed Test Backend Configuration

| Property | Value |
|----------|-------|
| **Backend Type** | S3 |
| **Bucket** | mays-ris-e2e-test-tf-state-test |
| **Configured Key** | test/terraform.tfstate |
| **workspace_key_prefix** | env: (Terraform default) |
| **Selected Workspace** | mays-ris-e2e-test |
| **Effective S3 Object Key** | env:/mays-ris-e2e-test/test/terraform.tfstate |
| **Lock Mechanism** | DynamoDB (native Terraform locking) |
| **Lock Table** | mays-ris-e2e-test-tf-lock |
| **State Encryption** | SSE-S3 (encrypt=true) |
| **Backend Creation** | Via `BackendBootstrap.ensure_all()` (idempotent, ownership-verified) |

### Comparison with Existing States

| State | Bucket | Key | Lock Table | Workspace | Status |
|-------|--------|-----|------------|-----------|--------|
| **Proposed Test** | mays-ris-e2e-test-tf-state-test | env:/mays-ris-e2e-test/test/terraform.tfstate | mays-ris-e2e-test-tf-lock | mays-ris-e2e-test | **NOT FOUND** |
| **Existing RIS Legacy** | mays-ris-tf-state-dev | env:/mays-ris/env:/mays-ris/dev/terraform.tfstate | mays-ris-tf-lock | mays-ris | FOUND (serial 21) |
| **Existing RIS Canonical** | mays-ris-tf-state-dev | env:/mays-ris/dev/terraform.tfstate | mays-ris-tf-lock | mays-ris | NOT FOUND (404) |
| **Orders State** | N/A (local) | terraform/terraform.tfstate | N/A | mays-orders | LOCAL FILE |

### Read-Only AWS Verification

| Resource | Check | Result |
|----------|-------|--------|
| Test Backend Bucket | `aws s3api head-bucket` | **NOT FOUND (404)** |
| Test Lock Table | `aws dynamodb describe-table` | **NOT FOUND (ResourceNotFoundException)** |
| Test State Key | `aws s3api list-objects-v2` | **NOT FOUND** |
| Test Lock | `aws dynamodb scan` | **NOT FOUND** |

✅ **BACKEND ISOLATION: COMPLETE** - No overlap with any existing state.

---

## 7. Installer Execution Safety

### Command Classification

| Command | Safety | Mutates AWS? | Mutates Remote State? | Acquires Lock? | Requires --yes? |
|---------|--------|--------------|----------------------|----------------|-----------------|
| validate | ✅ READ-ONLY | No | No | No | No |
| plan | ✅ READ-ONLY* | No | No | Yes (unless --diagnostic-no-lock) | No |
| preflight | ✅ READ-ONLY | No | No | No | No |
| package | ✅ READ-ONLY | No (local only) | No | No | No |
| lock inspect | ✅ READ-ONLY | No | No | No | No |
| lock recovery-plan | ✅ READ-ONLY | No | No | No | No |
| state list/show/pull | ✅ READ-ONLY | No | No | Yes (workspace) | No |
| state push | ⚠️ MUTATING | No | Yes | Yes | Yes |
| apply | ⚠️ MUTATING | Yes | Yes | Yes | Yes |
| install | ⚠️ MUTATING | Yes | Yes | Yes | Yes |
| destroy | ⚠️ MUTATING | Yes | Yes | Yes | Yes |

*plan is read-only in effect but acquires state lock by default. Use `--diagnostic-no-lock` for lock-free diagnostic plans.

### Workspace Selection Safety

```python
# From installer/terraform_runner.py - workspace resolution
def _ensure_workspace(self):
    if self.workspace == DEFAULT_WORKSPACE:
        return True
    selected = terraform workspace select <workspace>
    if failed and "doesn't exist" in error:
        terraform workspace new <workspace>
```

- **Default workspace (default)**: No workspace operations
- **Non-default workspace**: Selects existing or creates new
- **TERRAFORM_WORKSPACE env var**: Takes precedence (explicit override)
- **Project isolation**: Each project_name → unique workspace → isolated state

✅ **Fresh project CANNOT accidentally select existing mays-ris workspace** - workspace derived verbatim from project_name.

✅ **project_name consistently propagated** through: Context → workspace → TF vars → backend config → resource names → tags.

---

## 8. Local Isolation Tests

### Test Results Summary

| Test Category | Command | Result |
|---------------|---------|--------|
| Project-name Propagation | `python3 -m pytest tests/test_ris_installer.py::test_project_name_is_identity_and_workspace` | ✅ PASS |
| Project Isolation | `python3 -m pytest tests/test_ris_installer.py::test_two_projects_do_not_collide` | ✅ PASS |
| Environment Never Replaces Project | `python3 -m pytest tests/test_ris_installer.py::test_environment_never_replaces_project_name` | ✅ PASS |
| Backend Config from Explicit Flags | `python3 -m pytest tests/test_ris_installer.py::test_backend_config_from_explicit_flags_only` | ✅ PASS |
| Missing Backend Values Raise | `python3 -m pytest tests/test_ris_installer.py::test_missing_backend_values_raise_not_invented` | ✅ PASS |
| Apply Requires --yes | `python3 -m pytest tests/test_ris_installer.py::test_apply_requires_yes_dry_run_default` | ✅ PASS |
| Plan Wires Runner Correctly | `python3 -m pytest tests/test_ris_installer.py::test_plan_wires_runner_cwd_vars_and_backend` | ✅ PASS |
| CLI Parsing Defaults | `python3 -m pytest tests/test_ris_installer.py::test_cli_parsing_defaults` | ✅ PASS |
| AWS Context to Child Env | `python3 -m pytest tests/test_ris_installer.py::test_aws_context_flows_to_child_env` | ✅ PASS |
| Runner Without Context Unchanged | `python3 -m pytest tests/test_ris_installer.py::test_runner_without_context_unchanged` | ✅ PASS |
| Preflight Prints Identity | `python3 -m pytest tests/test_ris_installer.py::test_preflight_prints_identity_without_secrets` | ✅ PASS |
| Backend Names Derive from Project | `python3 -m pytest tests/test_ris_installer.py::test_backend_names_derive_from_project` | ✅ PASS |
| Bootstrap Idempotent When Owned | `python3 -m pytest tests/test_ris_installer.py::test_bootstrap_idempotent_when_owned` | ✅ PASS |
| Bootstrap Conflict on Foreign Bucket | `python3 -m pytest tests/test_ris_installer.py::test_bootstrap_conflict_on_foreign_bucket` | ✅ PASS |
| Install Dry-run No Mutation | `python3 -m pytest tests/test_ris_installer.py::test_install_dry_run_performs_no_mutation` | ✅ PASS |
| Install Full Order With --yes | `python3 -m pytest tests/test_ris_installer.py::test_install_full_order_with_yes` | ✅ PASS |
| Install Stops on Preflight Fail | `python3 -m pytest tests/test_ris_installer.py::test_install_stops_when_preflight_fails` | ✅ PASS |
| State Read Commands Passthrough | `python3 -m pytest tests/test_ris_installer.py::test_state_read_commands_passthrough` | ✅ PASS |
| State Push Refused Without --yes | `python3 -m pytest tests/test_ris_installer.py::test_state_push_refused_without_yes` | ✅ PASS |
| State Push With --yes | `python3 -m pytest tests/test_ris_installer.py::test_state_push_with_yes_and_file` | ✅ PASS |
| Validate Skips Workspace | `python3 -m pytest tests/test_ris_installer.py::test_validate_skips_workspace_without_backend` | ✅ PASS |
| Var Parsing Identity Protection | `python3 -m pytest tests/test_ris_installer.py::test_var_parsing_and_identity_protection` | ✅ PASS |
| Apply Forwards Vars | `python3 -m pytest tests/test_ris_installer.py::test_apply_forwards_vars` | ✅ PASS |
| Destroy Refuses Dry-run | `python3 -m pytest tests/test_ris_installer.py::test_destroy_refuses_dry_run` | ✅ PASS |
| Destroy Plans and Applies Scope | `python3 -m pytest tests/test_ris_installer.py::test_destroy_plans_and_applies_scope` | ✅ PASS |
| Package Runs Bundle Script | `python3 -m pytest tests/test_ris_installer.py::test_package_runs_bundle_script` | ✅ PASS |

**All 36 installer tests PASSED**

### Full Regression Suite
```
python3 -m pytest tests/ -q --tb=no
→ 1399 passed, 9 skipped, 4 warnings
```

### Terraform Validation
```
cd terraform && terraform fmt -check && terraform validate
→ PASS (15 warnings, no errors)
```

### Custom Isolation Verification (Ad-hoc)

| Test | Result |
|------|--------|
| Project-name propagation | ✅ PASS |
| Environment propagation | ✅ PASS |
| Workspace selection | ✅ PASS |
| Backend key construction | ✅ PASS |
| Resource naming | ✅ PASS |
| Repeated config generation | ✅ PASS |
| Project directory isolation | ✅ PASS |
| Existing RIS state protection | ✅ PASS |
| Existing Orders protection | ✅ PASS |
| Invalid project name rejection | ✅ PASS (empty rejected; format validation is in TF) |
| Backend collision detection | ✅ PASS |
| No accidental prod references | ✅ PASS |

---

## 9. AWS Cost and Cleanup Analysis

### Resource Count: 88 Terraform-managed resources

### Estimated Monthly Cost: **$7.70/month**

| Cost Driver | Monthly Estimate |
|-------------|-----------------|
| API Gateway REST API | $3.50 |
| CloudWatch Dashboard | $3.00 |
| CloudWatch Alarms (7 × $0.10) | $0.70 |
| CloudWatch Log Groups (minimal) | $0.50 |
| All other resources | Free Tier eligible |

**Daily cost for short-lived test: ~$0.26/day**

### Destroy Implementation Scope

The `_cmd_destroy()` command:
1. Validates AWS context (preflight)
2. Prints destroy scope (project → workspace, account, region)
3. Runs `terraform init` with project backend config
4. Runs `terraform plan -destroy` with project variables
5. Runs `terraform apply` on destroy plan
6. Returns 0 only if both plan AND apply succeed

**Resources targeted by destroy:** ALL resources in the project's Terraform workspace (88 resources).

**Resources that SURVIVE destroy:**
- S3 State Bucket (`mays-ris-e2e-test-tf-state-test`) - Created by installer bootstrap, not Terraform
- DynamoDB Lock Table (`mays-ris-e2e-test-tf-lock`) - Created by installer bootstrap, not Terraform
- S3 State Objects - Managed by Terraform backend, not destroyed by `terraform destroy`

**Cleanup Procedure for Backend Resources:**
```bash
# Optional manual cleanup after destroy
aws s3 rb s3://mays-ris-e2e-test-tf-state-test --force
aws dynamodb delete-table --table-name mays-ris-e2e-test-tf-lock
```

---

## 10. Installation Runbook

### Prerequisites

- [ ] AWS CLI configured with `mayaws` profile (account 240571105849)
- [ ] Terraform 1.16.1 installed
- [ ] Python 3.14 with dependencies (`pip install -r requirements.txt`)
- [ ] Lambda bundles built (`python -m installer.ris --project-name mays-ris-e2e-test --environment test package --bundle all`)
- [ ] Human approval for each mutation phase

### Phase 0: PREPARE (Read-Only)

```bash
cd /home/dci-student/projects/Mays-Recruiting-Intelligent-System

# Verify identity
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  preflight

# Expected output:
# account: 240571105849
# region: eu-central-1
# identity: arn:aws:iam::240571105849:user/Mayaws
```

### Phase 1: PACKAGE (Local, Deterministic)

```bash
# Build Lambda bundles (REQUIRED before plan - terraform references zip hashes)
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  package --bundle all

# Verify bundles exist
ls -la terraform/lambda.zip lambda/dist/orders-reader.zip
```

### Phase 2: PLAN (Diagnostic, No Lock)

```bash
# Diagnostic plan - no state lock, no workspace creation
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  plan --diagnostic-no-lock

# Expected: ~88 creates, 0 updates, 0 destroys
# Stop condition: Any unexpected destroys or references to existing resources
```

### Phase 3: PLAN (Normal, Locked) — **HUMAN APPROVAL REQUIRED**

```bash
# Normal locked plan - acquires state lock, creates workspace
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  plan --out tfplan

# HUMAN REVIEW: Verify plan shows only creates for mays-ris-e2e-test-test-* resources
# Stop conditions:
#   - Any resource with mays-ris-dev-* prefix
#   - Any destroy actions
#   - Any reference to existing RIS or Orders resources
#   - Plan differs significantly from diagnostic plan
```

### Phase 4: APPLY — **EXPLICIT HUMAN APPROVAL REQUIRED**

```bash
# Apply the planned changes
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  apply --yes

# Expected: All 88 resources created successfully
# Stop condition: Any apply error - investigate before proceeding
```

### Phase 5: VERIFY (Read-Only)

```bash
# Verify state
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  state list

# Verify locks
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  lock inspect

# Smoke tests (manual)
curl -I https://<api-id>.execute-api.eu-central-1.amazonaws.com/health
# Should return 200 OK
```

### Phase 6: NO-OP VERIFICATION

```bash
# Re-run plan - should show 0 changes
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  plan

# Expected: 0 to add, 0 to change, 0 to destroy
```

### Phase 7: CLEANUP APPROVAL — **EXPLICIT HUMAN APPROVAL REQUIRED**

```bash
# Destroy all resources in the test project workspace
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  destroy --yes

# Verify destroy complete
python -m installer.ris \
  --project-name mays-ris-e2e-test \
  --environment test \
  --profile mayaws \
  --backend-bucket mays-ris-e2e-test-tf-state-test \
  --backend-lock-table mays-ris-e2e-test-tf-lock \
  state list
# Should return empty or only backend resources
```

### Phase 8: OPTIONAL BACKEND CLEANUP

```bash
# Remove backend resources (optional - they're empty and tagged)
aws s3 rb s3://mays-ris-e2e-test-tf-state-test --force --profile mayaws
aws dynamodb delete-table --table-name mays-ris-e2e-test-tf-lock --profile mayaws
```

---

## 11. Governance and Git

### Documentation Created

- `docs/reports/MAYS-RIS-PARALLEL-INSTALLATION-PREFLIGHT-01.md` (this report)
- `AI_AUDITLOG.md` updated with checkpoint entry

### Commit Information

```
Repository: maynowak/Mays-Recruiting-Intelligence-System
Branch: main
Final Commit SHA: [to be filled after commit]
Files Committed: docs/reports/MAYS-RIS-PARALLEL-INSTALLATION-PREFLIGHT-01.md, AI_AUDITLOG.md
```

---

## 12. Final Checkpoint Summary

| Metric | Result | Evidence |
|--------|--------|----------|
| **HISTORICAL_BASELINE** | ✅ VERIFIED | Previous checkpoint report + git history |
| **ORDERS_INSTALLATION_BOUNDARY** | ✅ PASS | Verified separate directory, local state, no S3 backend |
| **PROJECT_NAME_ISOLATION** | ✅ PASS | 36/36 installer tests + custom verification |
| **RESOURCE_NAME_ISOLATION** | ✅ PASS | All 88 resources use project-prefixed names |
| **BACKEND_ISOLATION** | ✅ PASS | Distinct bucket, lock table, workspace, state key - all NOT FOUND |
| **EXISTING_RIS_STATE_PROTECTED** | ✅ YES | Different workspace, bucket, lock table, state key |
| **EXISTING_ORDERS_STATE_PROTECTED** | ✅ YES | Separate directory, local state, hardcoded workspace |
| **LOCAL_TESTS** | ✅ PASS | 36 installer tests + 1399 full regression |
| **AWS_RESOURCE_COLLISION_CHECK** | ✅ PASS | Complete matrix - zero collision risk |
| **INSTALLER_DESTROY_SCOPE** | ✅ VERIFIED | Scoped to workspace, requires --yes, plan+apply |
| **COST_ESTIMATE** | ✅ PROVIDED | ~$7.70/month, ~$0.26/day for test |
| **PARALLEL_INSTALL_READY** | ✅ **YES** | All mandatory isolation gates evidenced |

### Explicit GO/NO-GO Recommendation

**GO** — All mandatory isolation gates are supported by evidence. The parallel test installation can proceed with human approval at the defined gates.

### Remaining Blockers for Production RIS (Not Blocking Parallel Test)

1. Stale canonical lock on existing RIS state (blocks normal plan for `mays-ris`)
2. State path divergence (legacy vs canonical) for existing RIS
3. Cognito `custom:tenant_id` claim not configured
4. Vercel server-side proxy not implemented

**These do not affect the isolated parallel test installation.**

---

**HARD STOP** — No AWS mutations performed. Read-only verification complete.  
**Awaiting explicit human authorization** before executing any AWS installation.