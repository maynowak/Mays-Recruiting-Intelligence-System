# RIS-R08-G2C-5 — CONSOLIDATED RIS-DEV2 UPGRADE CONSTRUCTION & READINESS

**Status:** CONSTRUCTION DOCUMENTED / PLAN BLOCKED / APPLY NOT AUTHORIZED

## 1. Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`.
- Actual HEAD at this work: `438decf238828b3662e8c0e72a14951cc6ce3ae9`.
- User-provided earlier HEAD `4175e801` is historical; it is not the current
  checkout baseline.
- Target account/profile/region: `262370457690` / `default` / `eu-central-1`.
- Target project: `ris-dev2`, environment `dev`.
- State: `env:/ris-dev2/dev/terraform.tfstate` in
  `ris-dev2-tf-state-dev`; lock table `ris-dev2-tf-lock`.
- 39 pre-existing untracked files preserved.
- No AWS mutation, Terraform plan/apply/destroy, state mutation, import,
  workspace creation, Lambda invocation or deployment was performed.

## 2. Upgrade scope matrix

| Area | Local code/report status | AWS/deployed status | Upgrade boundary |
|---|---|---|---|
| Foundation/provider/backend | IMPLEMENTED / VERIFIED-LOCAL | AWS backend readable; current managed state empty | No backend/state migration |
| Cognito/Identity | IMPLEMENTED / VERIFIED-LOCAL | `ris-dev2` current pool not found; baseline unresolved | Never recreate/adopt protected identity in this gate |
| API Gateway/authorizers | IMPLEMENTED / VERIFIED-LOCAL | No current `ris-dev2` API found | No plan until state ownership restored |
| Lambda/agent runtime | IMPLEMENTED / VERIFIED-LOCAL | No current `ris-dev2` functions found | Bundles may be rebuilt offline only |
| DynamoDB | IMPLEMENTED / VERIFIED-LOCAL | Only lock table found; PITR disabled | No data table creation against empty state |
| SQS | IMPLEMENTED / VERIFIED-LOCAL | No current `ris-dev2` queues found | Orders/runtime lifecycle separate |
| Documents/S3 | IMPLEMENTED / VERIFIED-LOCAL | Only backend bucket found; versioning on, tag absent | No bucket adoption or mutation |
| Partner profiles R01–R07 | VERIFIED-LOCAL | Not deployed/verified for current `ris-dev2` | Local-only until ownership is recovered |
| Jobsearch-v1 contracts | VERIFIED-LOCAL | External identity/resources UNKNOWN | Protected external identity; no replacement |
| Privacy/Erasure R08 | IMPLEMENTED / VERIFIED-LOCAL, flags false | Not deployed for current `ris-dev2` | No activation, receipt, freeze, cutover or S3 execution |
| Mays-Orders-AWS | IMPLEMENTED / VERIFIED-LOCAL | No current `ris-dev2` Orders resources found | No implicit Orders install/reinstall |
| Monitoring/CloudTrail | IMPLEMENTED / VERIFIED-LOCAL | No current `ris-dev2` trail found | No audit resource adoption |
| Installer/CI | IMPLEMENTED / VERIFIED-LOCAL with known failures | No installer execution | Explicit identity/state guard required |

`AWS-VERIFIED`/`DEPLOYED` is not assigned to current `ris-dev2` runtime
components because the current state is empty and the targeted live inventory
is empty. Historical run evidence is retained but not promoted to current
ownership.

## 3. Actual Phase-A evidence

The read-only account guard passed. The state bucket and lock table were
readable. The latest State object is serial 17 with zero resources; versions
2–15 contain historical installations and versions 16–17 are empty teardown
states. Historical protected IDs were checked and returned not-found or
ambiguous results. No historical version was restored.

The current target inventory found:

- S3: only `ris-dev2-tf-state-dev`; versioning enabled; no Project tag
  (`NoSuchTagSet`);
- DynamoDB: only `ris-dev2-tf-lock`, ACTIVE, 2 items, PITR disabled;
- Lambda, IAM roles, API Gateway, SQS, Cognito, CloudFront and CloudTrail:
  no `ris-dev2` resources found;
- CloudFront/OAC/Cognito historical IDs: no current matches;
- ACM and Route 53: no Terraform-owned references in retained state history.

This is an ownership/recovery blocker, not evidence that protected external
Jobsearch infrastructure may be recreated.

## 4. Safest construction decision

### Variant A — in-place upgrade

**BLOCKED.** It requires an authoritative non-empty State and a single live
protected-resource baseline. Neither exists. Reusing a historical State
version, importing by name, or planning against serial 17 would violate the
safe-upgrade rules.

### Variant B — isolated RIS foundation with external Jobsearch identity

**CONSTRUCTION-RECOMMENDED, NOT IMPLEMENTED/NOT DEPLOYABLE YET.** This is the
only safe architecture if the original `ris-dev2` ownership cannot be
recovered, but it requires an explicit new project/state identity and a code
change before any plan. It must not be named `ris-dev2` while the old identity
is unresolved, and it must not create or adopt protected Jobsearch resources.

The required construction changes are:

1. Make Cognito ownership explicit: `manage_cognito=false` plus external pool,
   issuer, client and domain inputs; conditionally omit the local Cognito
   module and prevent client/domain creation.
2. Make API authorizers consume the external issuer/pool/client contract
   without creating a replacement pool, domain or client.
3. Make Mays-Orders lifecycle explicit (`orders_enabled` or external output
   handoff); do not unconditionally instantiate `module.mays_orders` or its
   embedded Cognito.
4. Add external table/queue/API/authorizer inputs for `orders_reader`, with
   ARN/name validation and no ownership/adoption behavior.
5. Scope IAM to supplied external ARNs and the new RIS foundation ARNs; no
   wildcard or implicit cross-project permissions.
6. Add explicit project overlay and backend/state tuple for the isolated
   project; preserve `ris-dev` and `ris-dev2` defaults and state paths.
7. Keep all privacy/erasure/receipt/freeze/cutover/S3 execution flags false.
8. Add static tests proving no Cognito, CloudFront, DNS, ACM or Orders resource
   is declared when external-identity mode is selected.

These are design requirements, not changes performed in this task. A separate
implementation/change review is required.

## 5. Phase-B plan gate

No Terraform plan was run. A plan against current serial 17 would be a new
installation from Terraform's perspective and could recreate protected
resources. A future plan is allowed only after:

- authoritative state ownership is restored by an approved procedure, or the
  isolated external-identity construction is implemented and reviewed;
- protected Jobsearch/Cognito/CloudFront/ACM/DNS IDs and ownership are proven;
- no state migration/import workaround is used;
- the full plan is saved outside Git and reviewed for creates, updates,
  deletes, replacements, IAM, Orders and cost impact;
- protected resources have zero changes and all flags remain false.

## 6. Offline verification at this HEAD

| Check | Actual result | Classification |
|---|---|---|
| Selected Python `py_compile` | PASS | offline-ready |
| Terraform `fmt -check` | PASS | offline-ready |
| Terraform `validate` | PASS, existing provider deprecation warnings | offline-ready |
| R08 focused suite | 58 passed | offline evidence |
| Partner-profile/CV suite | 345 passed | offline evidence |
| Privacy suite | 79 passed, 6 skipped | activation/release blocker for skipped capabilities |
| API/OpenAPI subset | 73 passed, 1 failed, 252 subtests | planned privacy routes blocker |
| Installer/pinning subset | 91 passed, 4 failed | deployment-blocking local fixture/STS/pinning blockers |
| Builder suite | timed out at 300s after partial output | deployment-blocking, not PASS |
| Full repository suite | not run as a release claim | no fabricated aggregate |

Known failures were not skipped: installer dry-run Orders pin enforcement,
mocked STS output, project-pinning path expectations, and OpenAPI routes
`/v1/partner/me/privacy/export` and `/inspect` without source declarations.

## 7. Phase-E AWS readiness

**AWS Preflight: BLOCKED for upgrade execution.** The account guard and
read-only access work, but the state/ownership criteria fail. The evidence is
sufficient to prevent unsafe action, not sufficient to authorize a plan.

## 8. Phase F/G/H gates

- Controlled Terraform plan: **BLOCKED / NOT RUN**.
- Apply: **NOT AUTHORIZED**.
- Deployment acceptance: prepare only after a separately approved plan.
- `ris-dev` handoff: independent baseline required; no `ris-dev2` result is
  transferable as resource ownership.
- Productive erasure/cutover/receipt activation: prohibited.
