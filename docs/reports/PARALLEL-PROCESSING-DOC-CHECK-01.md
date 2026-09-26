PARALLEL-PROCESSING-DOC-CHECK-01

Repository: maynowak/mays-order-aws
Remote: git@github.com:maynowak/mays-order-aws.git
Analyzed commit: 9c61237185d202e072b2304355ee836154368846 (origin/main, verified
equal to `git ls-remote` HEAD; shallow single-branch clone to /tmp/opencode,
working tree clean, no local files used as source)

Status: YELLOW

Parallel Deployment: DEFINED and TESTED, but canonical lifecycle/architecture
docs lag behind execution logs. Mechanism: one Terraform workspace per
`project_name` (auto-selected; `InstallationContext` defaults workspace to
project_name and exports `TERRAFORM_WORKSPACE`; `TerraformRunner` selects/
creates it before each command). Proven: `mays-orders` + `mays-order-par`
deployed side-by-side (37 resources each), tested simultaneously, destroyed
independently with zero cross-impact (09-01 GREEN, 09-02 GREEN). Fix for prior
state collision documented in 09-04 (GREEN). Doc gap flagged in 09-05 (YELLOW):
INSTALLER-LIFECYCLE H2 section + architecture docs do not yet name workspace
isolation — still true at analyzed commit (no "workspace" in H2 section;
only env-table default at line 774).

Deployment Identity: `DeploymentId = <account>:<project>:<environment>`
(e.g. `240571105849:mays-orders:development`), version explicitly excluded
(upgrade = same deployment). Plus plan identity
`<project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>.tfplan`
with hardened discovery, destroy isolation scoped to DeploymentId, ownership
classes OWNED/FOREIGN/AMBIGUOUS/UNMANAGED, canonical AWS tags
(Project/Environment/DeploymentId + version/governance/system).
Source: INSTALLER-H2-DEPLOYMENT-IDENTITY.md (COMPLETED, 125/125 tests).

State Isolation: per-workspace Terraform state (workspace name = project_name).
S3 backend-key-per-project is an OPEN QUESTION only (09-01 Q2 + recommendation
4) — no decision, no backend-key strategy documented (grep over md/tf/py: no
`workspace_key_prefix` or equivalent). Relying on workspaces is the tested
practice; stronger S3-level isolation is undecied.

Resource Isolation: `${var.project_name}-*` naming across API/Lambda/SQS/
Cognito/CloudWatch/CloudTrail (terraform/README.md naming tables, e.g.
`mays-orders-api` → `mays-order-par-api` on rename); DynamoDB tables are bare
project names (`mays-orders`, `mays-order-par` side-by-side, 09-02 evidence);
tag-based ownership (Project/Environment/DeploymentId) with destroy guard
(`is_destroyable_by`, ambiguous never silently adopted); policy gate derives
project from resource tags (09-02 fix for hardcoded `mays-orders`).

DynamoDB Naming: YES, part of isolation. Tables per project (bare
`<project_name>`); single-table design per `var.project_name`
(terraform/README.md:119). No cross-project table sharing documented.

Runtime Parallel Processing: documented at scaling/idempotency level, no
explicit concurrency tuning. Lambda auto-scales (stateless, 1000 concurrent
default per region); API Gateway auto-scales; DynamoDB on-demand adaptive;
GSI1 `LIST`-partition hot-partition note with sharding documented as
non-critical at target volumes. Correctness under concurrency: idempotent
handlers (no double-create on retry), conditional writes (409
CONFLICTED_UPDATE), `version` attribute for optimistic locking (reserved),
SQS worker E2E-tested (`test_sqs_message_processed` PASSED, incl. parallel
project run). No BatchSize/reserved-concurrency/FIFO config documented
(grep: no hits) — defaults apply, not a gap per docs' target volumes.

Existing Documentation (read, targeted — no full inventory):
- docs/reports/INSTALLER-H2-DEPLOYMENT-IDENTITY.md (identity/tags/isolation)
- docs/INSTALLER-LIFECYCLE.md (D0-D8, H1/H2, D8 pipeline; §§415-490, 677ff)
- docs/reports/09-01-PARALLEL-PROJECT-TEST-EXECUTION_LOG.md (GREEN test)
- docs/reports/09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG.md (GREEN upgrade)
- docs/reports/09-04-UPGRADE-PARALLEL-DEPLOYMENT-FIX-EXECUTION_LOG.md (GREEN fix)
- docs/reports/09-05-DOCUMENTATION-REVIEW-EXECUTION_LOG.md (YELLOW doc lag)
- terraform/README.md (naming tables, state migration notes, T013 identity)
- reliability/consistency-and-failure-handling.md (§§1-3: idempotency, scaling)
- database/dynamodb-design.md, docs/phase2-async-order-ingest.md (scanned)

Contradictions: NONE blocking. Progression is consistent: 09-01 risk
(no auto-propagation of --project-name) → fixed in 09-02 (auto-inject) →
hardened in 09-04 (workspace auto-select). Doku-Aussagen ("IMPLEMENTED")
refer to file existence, never contradict wiring evidence. R10 chain
(project_name → workspace → isolated state → DeploymentId → DynamoDB naming)
holds with one nuance: DeploymentId carries no workspace dimension, but
workspace == project_name makes it 1:1 — consistent, not contradictory.

Missing Definition:
1. Workspace isolation in canonical docs (INSTALLER-LIFECYCLE H2,
   architecture) — recommended by 09-05, still open at analyzed commit.
2. S3 backend-key-per-project decision (09-01 open question, no owner).
3. Test parameterization per PROJECT_NAME (09-01 open question; tests hard-code
   `mays-orders`).
4. No explicit concurrency config (defaults undocumented — acceptable, noted).

Conclusion: Do NOT redefine. The source of truth exists and is tested
(H2 identity + GREEN parallel-test/upgrade/fix logs). Confirm it and close the
three doc gaps above (workspace note, backend-key decision, test
parameterization). R10 stays GREEN — no Terraform repair needed on this side.

// Answers to the 11 ticket questions: (1) workspace-per-project_name,
tested GREEN; (2) DeploymentId account:project:environment (+ plan identity
per operation); (3) project_name = central naming/identity lever, workspace
name, state separator; (4) environment = identity dimension, case-insensitive;
(5) DeploymentId = canonical instance id, version excluded; (6) Terraform
workspaces (S3-key strategy open); (7) ${project_name}-* naming + tags +
ownership/destroy guards + tag-derived policy gate; (8) yes, bare
project-name tables; (9) yes — SQS worker + auto-scaling Lambda + idempotent
handlers; (10) idempotency, conditional writes, optimistic-locking `version`
(reserved), E2E-tested; (11) no contradictions, one nuance (no workspace
dimension in DeploymentId, 1:1 via project_name).

// Method: Git-only (clone of remote main @ exact SHA to /tmp; sibling
/Mays-Orders-AWS/* dirs and zips explicitly NOT used). No Terraform plan/
apply/destroy, no infra mutation, no new architecture.
