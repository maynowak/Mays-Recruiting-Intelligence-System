# AGENTS.md — Mays Recruiting Intelligence System

Use executable configuration and scripts over prose when they disagree. Do not
assume an AWS account, profile, workspace, backend, or resource ID: verify the
installation context before any AWS-backed Terraform command.

## Sources of truth

- `README.md`: supported installer workflow and current project status.
- `docs/architecture/SYSTEM-ARCHITECTURE.md` and `RUNTIME-PATH.md`: runtime wiring.
- `docs/api/API-STANDARD.md`: routes, authentication, and error contract.
- `terraform/`, `installer/`, `lambda/`, and tests are authoritative for behavior.
- `docs/reports/` contains historical evidence; it does not override code/config.

## Repository boundaries

- `terraform/`: root infrastructure and modules for API Gateway, Lambda,
  DynamoDB, SQS, IAM, monitoring, documents, health, and Orders wiring.
- `lambda/`: runtime handlers and deterministic deployment bundles.
- `agents/`: registry/discovery/eligibility/selection, runtime body, and domain
  agents; `dummy-a`/`dummy-b` are development-only.
- `installer/`: CLI, backend/workspace isolation, project overlays, and the
  Mays-Orders module builder.
- `tests/`: Python tests; `installer/projects/` is an ignored external clone area.

Mays-Orders is a separate system boundary. RIS integrates through `OrdersPort`
and generated Terraform outputs; do not inspect or mutate the external stack
as if it were RIS infrastructure.

## Required workflow

- Python runtime and Lambda Terraform defaults are Python `3.14`.
- Build bundles before planning: `python lambda/build_zip.py --bundle all`.
  The agent bundle is `terraform/lambda.zip`; the reader bundle is
  `lambda/dist/orders-reader.zip`. Bundles are deterministic and exclude
  caches, bytecode, tests, and repository metadata.
- Preferred installer commands are:
  `python -m installer.ris --project-name <p> --environment dev --profile <profile> preflight|validate|package|plan|apply|install|state`.
- The safe lifecycle is `package -> plan -> apply`; `install` orchestrates
  phases. Installer dry-run is the default; mutating operations require
  `--yes`, and live AWS deploy additionally requires the explicit AWS-operation
  gate used by the installer.
- `project_name` is the Terraform workspace identity verbatim; it is never
  replaced by `environment`. Backend bucket, region, key, and lock table must
  be supplied explicitly—never invent defaults for a live run.
- For local Terraform checks use:
  `terraform init -backend=false`, `terraform validate`, and
  `terraform fmt -check -recursive`. Do not run backend migration or state
  operations merely to validate configuration.

## Mays-Orders generated module

- The preferred integration path is the builder, not unfinished
  `installer.ris install --through` orchestration:
  `python -m installer.build_mays_orders_module --project-name <p> --force`.
- Use `--check` for a non-build verification and `--clean` only when the
  generated module should be removed and rebuilt.
- `terraform/modules/mays_orders/` is generated and ignored. Never hand-edit
  it; rebuild it from the pinned upstream source.
- The builder enforces component naming `<project>-mays-orders`, patches the
  plan-known SQS IAM gate, and runs Terraform formatting/validation.
- External clone pins are recorded in
  `installer/mays-orders-clone.pinned.json` and
  `installer/mays-jobsearch-clone.pinned.json`; update pins only deliberately
  and re-run validation/plan comparison.

## Terraform/provider safety

- The active root provider contract is declared in `terraform/main.tf` and
  recorded in `terraform/.terraform.lock.hcl`. Use regular `terraform init` to
  reconcile the lockfile; do not add an unused provider or use `init -upgrade`
  just to make an old saved plan load.
- A saved plan is tied to its exact configuration, dependency selections,
  workspace, and state. Verify its SHA-256 and all guards before applying; a
  new plan always needs a new review/approval.
- Never use `-target`, `-replace`, `-destroy`, `-refresh=false`, or `-lock=false`
  to bypass an unexpected plan. Treat deletes, replacements, protected-resource
  actions, and unexplained drift as stop conditions.
- Keep `orders_lifecycle=disabled` unless explicitly authorized. Do not enable
  privacy, erasure, freeze, upload-cutover, or other global execution flags as
  a side effect of an unrelated change.

## Testing and packaging

- Focused Python test: `python -m pytest tests/<test_file>.py -q` or a node such
  as `python -m pytest tests/test_p20_api_contract_consistency.py -q`.
- Full Python suite: `python -m pytest tests/ -q`; it requires dependencies from
  `requirements.txt`, including `moto` for AWS mocks.
- `./scripts/parallel_tests.sh static` runs the repository regression checks;
  `./scripts/parallel_tests.sh ris-dev` runs the live installation verifier.
  These scripts default to `AWS_PROFILE=mayaws` and `/tmp/tfS3`; override them
  deliberately for another installation and inspect the target before running.
- API/auth changes must update the handler, `docs/api/API-STANDARD.md`, and
  the corresponding contract tests. Cognito JWT authentication and the
  `custom:tenant_id` tenant boundary must not be bypassed.

## AWS and runtime guardrails

- Before live operations verify STS account, region, profile, workspace,
  backend state key, state lineage/serial, and the protected-resource baseline.
- Do not mutate Cognito, CloudFront/OAC, Route53/DNS, ACM, JWT/OAuth
  configuration, or foreign/shared resources without an explicit scope that
  names those changes. Never destroy resources merely because they are absent
  from a local checkout.
- Runtime flow is API Gateway/Cognito JWT → Lambda → WorkItem/SQS/DLQ →
  ecosystem selection → domain agent → DynamoDB. Work items use conditional
  idempotent writes; preserve tenant/user ownership checks and do not add new
  `UserProfile` fields without updating the contract.
- Documents use presigned URLs and tenant/user-scoped keys; do not put PII in
  object keys or commit secrets/config credentials.
- Production auth is isolated per site: `mays-job-matcher.app` uses its
  dedicated Jobsearch pool `eu-central-1_ZURSMpD2O` (client
  `5hb3f6dj5ialg77jf4blur9g6g`, custom domain `auth.mays-job-matcher.app`), not
  the RIS kernel pool. Never migrate, replace, detach, or re-point a production
  site's pool, client, or domain as a side effect of an upgrade; that requires
  an explicit scope naming the site and the target pool.
