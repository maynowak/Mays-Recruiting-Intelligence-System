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

Two independent RIS installations exist side by side in the same account (240571105849, eu-central-1). Never cross-wire them.

- **`mays-ris` (dev, legacy)** — the `mays-ris-dev-*` resource family (`aboqolpm0f` API, `mays-ris-dev-agent`, `mays-ris-dev-work-queue`, `mays-ris-dev-work-items`, `mays-ris-dev-documents`). Workspace `mays-ris`, state key `env:/mays-ris/terraform.tfstate` on `s3://mays-ris-tf-state-dev`.
- **`ris-development` (permanent dev, current)** — the `ris-development-*` / `ris-development-dev-*` family. Workspace `ris-development`, state key `env:/ris-development/terraform.tfstate` on the same bucket. `project_name=ris-development`, `environment=dev`, RIS pool `ris-development-dev-users` (`eu-central-1_7QCp09XEZ`), API `https://klklimekab.execute-api.eu-central-1.amazonaws.com` (ID `klklimekab`).
- Local runs: `TF_DATA_DIR=/tmp/tfris-development AWS_PROFILE=mayaws`. Full-series verifier: `./scripts/parallel_tests.sh ris-development` (static: `./scripts/parallel_tests.sh static`).

## Architecture specifics

Entry points:
- Kernel API GW `klklimekab` stage `$default` + orders API `vdtv5in694` (both for `ris-development`). ALL kernel routes require JWT (incl. `/health` → 401 unauthenticated; verified live 2026-10-19, per `docs/api/API-STANDARD.md` Z.62).
- Worker Lambda `ris-development-dev-agent`, SQS batch 5, Visibility 300s. Queue `ris-development-dev-work-queue`, DLQ `ris-development-dev-dlq` after 3 attempts.
- WorkItem persisted to `ris-development-dev-work-items` before execution with conditional write `attribute_not_exists`. Mandatory fields: `workId`, `type`, `tenantId`, `idempotencyKey`.
- Idempotency: duplicate `workId` with COMPLETED → no new run.
- Ecosystem selects agents via Registry/Discovery/Eligibility/Selection. Worker knows no agents.
- Domain agents live in `agents/`: `reference`, `ats`, `jobsearch`, `orders-function`, `dummy-a/b` DEV only.
- DynamoDB tables (kernel): work-items, jobsearches, user-profile, agent-catalog, entitlements, agent-state. PAY_PER_REQUEST.
- Documents: bucket `ris-development-dev-documents`, keys `tenant/{t}/users/{sub}/documents/{uuid}`, presigned URLs only, no PII in keys.

Orders integration:
- Component naming is `project_name-mays-orders` verbatim (`ris-development-mays-orders`), not `project_name-orders`.
- Render: `terraform/main.tf` `module "mays_orders"` + `project_name = "${var.project_name}-mays-orders"`; generated module in `terraform/modules/mays_orders/` (build artifact, gitignored).
- Live resources: table `ris-development-mays-orders`, queue `ris-development-mays-orders-orders-queue`, Lambdas `ris-development-mays-orders-handler` / `-sqs-worker` (python3.14), API `ris-development-mays-orders-api` (`vdtv5in694`), pool `ris-development-mays-orders-users` (`eu-central-1_f53oRl4jy`), client `ris-development-mays-orders-client`. Old `ris-development-orders-*` names are gone.
- Builder: `python -m installer.build_mays_orders_module --project-name <p> [--force|--check|--clean]`. Clones `mays-order-aws` into `installer/projects/mays_orders`, runs `module_builder build --preset orders-service`, then `patch_iam_sqs_gate()` applies `count = var.sqs_enabled ? 1 : 0` (plan-known) while `resources = [var.sqs_queue_arn]` stays the ARN. Raises on any unpatched `count` line containing `sqs_queue_arn`. `sqs_enabled` defaults `false` in the IAM module; root passes `sqs_enabled = true`.
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
- Jobsearch login must use the RIS pool `ris-development-dev-users`, not the orders module's embedded pool.
- Preserve foreign resources in the shared account (e.g. e2e CloudFront `E1R3BHTJNMC6XW`) — never destroy what you did not create.
- Do not add new fields to UserProfile; firstName/lastName already v1.

## What changes what

- Changing agent selection logic → `agents/ecosystem/*`
- Changing runtime flow → `lambda/handler.py` + `agents/runtime/pipeline.py`
- Changing infra → Terraform modules, then `python -m installer.ris ... package plan apply`
- Changing API contract → `lambda/handler.py` + `docs/api/API-STANDARD.md` + `tests/test_p20_api_contract_consistency.py`

If docs conflict with config/scripts, trust executable source.
