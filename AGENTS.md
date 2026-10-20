# AGENTS.md — Mays Recruiting Intelligence System

Compact working notes for OpenCode agents. Verify against code/config before acting.

## Project identity

- Agent-Runtime-Plattform AWS eu-central-1. SQS → Worker → Ecosystem → Agent Body → Domain Agents → DynamoDB.
- External boundary: Mays-Orders via OrdersPort → RealMaysOrdersAdapter → HTTP. No access to MO infra.
- Python 3.14 only. No compiled deps in Lambda. Package <50MB unzipped.
- No secrets in repo. Config via env vars only. JWT auth via Cognito, tenant isolation via `custom:tenant_id` claim.

## Canonical sources

Trust executable sources over prose. Canonical docs:
- `docs/architecture/SYSTEM-ARCHITECTURE.md` — overall system, terms, status
- `docs/architecture/RUNTIME-PATH.md` — step-by-step runtime detail
- `docs/api/API-STANDARD.md` — live routes, auth, error codes
- `docs/roadmap/ROADMAP.md`
- `README.md` — installer usage and current status

Older docs like `docs/CURRENT-ARCHITECTURE.md` are history.

## Key commands

Installer / Terraform:
- `python -m installer.ris --project-name mays-ris --environment dev --profile <profile> {validate,plan,apply,preflight,install,state}`
- Dry-run is default. Mutating commands need `--yes`: apply, destroy, state push.
- Workspace = `project_name` verbatim, never environment.
- Backend values must be explicit; no defaults invented.
- Contract: `package → plan → apply`. Lambda bundles are built via `lambda/build_zip.py --bundle all` before plan, otherwise `terraform plan` fails (lambda.zip missing is OPEN).

Terraform local checks:
- `terraform init -backend=false && terraform validate && terraform fmt -check`
- CI only validates Terraform; no pytest, no linter in CI.

Tests:
- `python -m pytest tests/ -q`
- Requires moto for local AWS mocks. Requirements in `requirements.txt`.
- Known baseline issues: 5 pre-existing test defects, collection errors under `installer/projects/mays_orders/**` (separate project, ignore). Suite reported 321 passed (4 deselected, 1 collection).

Lambda packaging:
- `python lambda/build_zip.py --bundle agent|reader|all`
- Deterministic build, excludes `__pycache__`, `.git`, `.pytest_cache`, byte-code.
- Bundles: agent → `terraform/lambda.zip`, reader → `lambda/dist/orders-reader.zip`.

## Deployments

Account 240571105849, eu-central-1. The permanent dev installation is `ris-dev`; the legacy `mays-ris` and the earlier `ris-development` stack no longer exist (both destroyed). Never cross-wire against foreign families.

- **`ris-dev` (permanent dev, current)** — the `ris-dev-*` / `ris-dev-dev-*` family. Workspace `ris-dev`, state key `env:/ris-dev/dev/terraform.tfstate` on `s3://mays-ris-tf-state-dev`. `project_name=ris-dev`, `environment=dev`, RIS pool `ris-dev-dev-users` (`eu-central-1_ojbmoiYGM`), kernel API `ris-dev-dev-api` (`g6901and25`), orders API `ris-dev-mays-orders-api` (`zf8tc0k2r2`), orders pool `ris-dev-mays-orders-users` (`eu-central-1_cmJWXujnb`).
- **API/Lambda IDs and pool IDs are per-install random** — a rebuild issues new IDs. Never hardcode them; resolve from live state/outputs.
- **Name-length rationale.** `ris-dev` (7 chars) was chosen so `ris-dev-mays-orders` (19) satisfies *both* the always-on CloudTrail-bucket limit (project max 39) *and* the stricter Cognito-backup limit (project max 23). The previous `ris-development` (27) only passed with `enable_cognito_backup=false`.
- **Destructive rename is a delete+create**, not in-place: new workspace, new state, all-new resource names. Treat as a rebuild.
- Local runs: `TF_DATA_DIR=/tmp/tfris-dev AWS_PROFILE=mayaws`. Full-series verifier: `./scripts/parallel_tests.sh ris-dev` (static: `./scripts/parallel_tests.sh static`).

## Architecture specifics

Entry points:
- Kernel API GW `ris-dev-dev-api` (`g6901and25`) stage `$default` + orders API `ris-dev-mays-orders-api` (`zf8tc0k2r2`). ALL kernel routes require JWT (incl. `/health` → 401 unauthenticated; verified live 2026-10-20, per `docs/api/API-STANDARD.md` Z.62).
- Worker Lambda `ris-dev-dev-agent`, SQS batch 5, Visibility 300s. Queue `ris-dev-dev-work-queue`, DLQ `ris-dev-dev-dlq` after 3 attempts.
- WorkItem persisted to `ris-dev-dev-work-items` before execution with conditional write `attribute_not_exists`. Mandatory fields: `workId`, `type`, `tenantId`, `idempotencyKey`.
- Idempotency: duplicate `workId` with COMPLETED → no new run.
- Ecosystem selects agents via Registry/Discovery/Eligibility/Selection. Worker knows no agents.
- Domain agents live in `agents/`: `reference`, `ats`, `jobsearch`, `orders-function`, `dummy-a/b` DEV only.
- DynamoDB tables (kernel): work-items, jobsearches, user-profile, agent-catalog, entitlements, agent-state. PAY_PER_REQUEST.
- Documents: bucket `ris-dev-dev-documents`, keys `tenant/{t}/users/{sub}/documents/{uuid}`, presigned URLs only, no PII in keys.

Orders integration:
- Component naming is `project_name-mays-orders` verbatim (`ris-dev-mays-orders`), not `project_name-orders`.
- Render: `terraform/main.tf` `module "mays_orders"` + `project_name = "${var.project_name}-mays-orders"`; generated module in `terraform/modules/mays_orders/` (build artifact, gitignored).
- Live resources: table `ris-dev-mays-orders`, queue `ris-dev-mays-orders-orders-queue`, Lambdas `ris-dev-mays-orders-handler` / `-sqs-worker` (python3.14), API `ris-dev-mays-orders-api` (`zf8tc0k2r2`), pool `ris-dev-mays-orders-users` (`eu-central-1_cmJWXujnb`), client `ris-dev-mays-orders-client`.
- Builder: `python -m installer.build_mays_orders_module --project-name <p> [--force|--check|--clean]`. Clones `mays-order-aws` into `installer/projects/mays_order_builder`, runs `module_builder build --preset orders-service`, then `patch_iam_sqs_gate()` applies `count = var.sqs_enabled ? 1 : 0` (plan-known) while `resources = [var.sqs_queue_arn]` stays the ARN. Raises on any unpatched `count` line containing `sqs_queue_arn`. `sqs_enabled` defaults `false` in the IAM module; root passes `sqs_enabled = true`.
- **Preferred integration path.** Do not wait on `installer.ris install --through` (WIP, `stop_through` not yet consumed). The module builder decouples RIS and Mays-Orders, pulls MO `main` per build, and lets both develop in parallel.
- `--clean` deletes the generated module; the next build recreates it. The module is never committed.
- `OrdersPort` with `submit_order/get_order_status/can_handle`.
- POST never blindly retried: `safe_to_retry: False`. Server-side idempotency key is OPEN.

Observability:
- CloudTrail `mays-ris-trail` multi-region, separate S3 from TF state.
- CloudWatch dashboard `mays-ris-overview`, DLQ alarms live.

## Monorepo boundaries

- `installer/` — RIS installer CLI, project pinning, backend bootstrap, `build_mays_orders_module` wrapper.
- `terraform/` — modules api/lambda/dynamodb/sqs/iam/monitoring + `modules/mays_orders` (generated). Project isolation via S3 backend + workspace.
- `lambda/` — handlers, build script.
- `agents/` — agent body, ecosystem, domain agents.
- `jobsearch/`, `lambda/`, `tests/` — separate concerns.

Pinning:
- `installer/mays-orders-clone.pinned.json` @9c61237
- `installer/mays-jobsearch-clone.pinned.json` @3cd58b81
- Verify drift via installer verify.

## Quirks / gotchas

- Installer `install` does phased preflight→bootstrap→init→validate→plan→apply. Without `--yes` it stops at plan.
- `state push` requires `--yes` and `--state-file`.
- Google Federation is configured but standard OFF, not live verified. No Google login UX yet.
- Profile boundary: Cognito Identity ≠ Application Profile. Google login creates no profile until explicit POST `/me/profile`.
- SQS `*` policy and missing DLQ on Mays-Orders side are documented external OPENs.
- API Machine route `POST /v1/m2m/agents/{agentId}/execute` requires JWT + header `X-Api-Credential`.
- No formatter/linter config in repo; quality checks are `py_compile` + `pytest` + `terraform fmt`.
- Do not treat `dummy-a/b` as production agents.
- `terraform/modules/mays_orders/` is generated; regenerate with the builder after `--clean` or a fresh clone. Never hand-edit it.
- Jobsearch login must use the RIS pool `ris-dev-dev-users`, not the orders module's embedded pool.
- Preserve foreign resources in the shared account (e.g. e2e CloudFront `E1R3BHTJNMC6XW`) — never destroy what you did not create.
- Do not add new fields to UserProfile; firstName/lastName already v1.

## What changes what

- Changing agent selection logic → `agents/ecosystem/*`
- Changing runtime flow → `lambda/handler.py` + `agents/runtime/pipeline.py`
- Changing infra → Terraform modules, then `python -m installer.ris ... package plan apply`
- Changing API contract → `lambda/handler.py` + `docs/api/API-STANDARD.md` + `tests/test_p20_api_contract_consistency.py`

If docs conflict with config/scripts, trust executable source.
