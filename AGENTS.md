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

## Architecture specifics

Entry points:
- API GW `aboqolpm0f` stage `$default`, 9 routes: `/health /platform /me /me/profile /agents` + orders routes. `/health` is only unauthenticated.
- Worker Lambda `mays-ris-dev-agent`, SQS batch 5, Visibility 300s. Queue `mays-ris-dev-work-queue`, DLQ `mays-ris-dev-dlq` after 3 attempts.
- WorkItem persisted to `mays-ris-dev-work-items` before execution with conditional write `attribute_not_exists`. Mandatory fields: `workId`, `type`, `tenantId`, `idempotencyKey`.
- Idempotency: duplicate `workId` with COMPLETED → no new run.
- Ecosystem selects agents via Registry/Discovery/Eligibility/Selection. Worker knows no agents.
- Domain agents live in `agents/`: `reference`, `ats`, `jobsearch`, `orders-function`, `dummy-a/b` DEV only.
- DynamoDB tables: work-items, jobsearches, user-profile, agent-catalog, entitlements, agent-state. PAY_PER_REQUEST.
- Documents: bucket `mays-ris-dev-documents`, keys `tenant/{t}/users/{sub}/documents/{uuid}`, presigned URLs only, no PII in keys.

Orders integration:
- `OrdersPort` with `submit_order/get_order_status/can_handle`.
- POST never blindly retried: `safe_to_retry: False`. Server-side idempotency key is OPEN.

Observability:
- CloudTrail `mays-ris-trail` multi-region, separate S3 from TF state.
- CloudWatch dashboard `mays-ris-overview`, DLQ alarms live.

## Monorepo boundaries

- `installer/` — RIS installer CLI, project pinning, backend bootstrap.
- `terraform/` — modules api/lambda/dynamodb/sqs/iam. Project isolation via S3 backend + workspace.
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
- Do not add new fields to UserProfile; firstName/lastName already v1.

## What changes what

- Changing agent selection logic → `agents/ecosystem/*`
- Changing runtime flow → `lambda/handler.py` + `agents/runtime/pipeline.py`
- Changing infra → Terraform modules, then `python -m installer.ris ... package plan apply`
- Changing API contract → `lambda/handler.py` + `docs/api/API-STANDARD.md` + `tests/test_p20_api_contract_consistency.py`

If docs conflict with config/scripts, trust executable source.
