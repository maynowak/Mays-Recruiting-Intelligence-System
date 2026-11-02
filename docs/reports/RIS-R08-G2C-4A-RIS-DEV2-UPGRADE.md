# R08-G2C-4A — RIS-DEV2 SAFE UPGRADE & REHEARSAL

**Status:** PHASE A COMPLETE / PHASE B BLOCKED BEFORE PLAN

## Scope and safety boundary

- Repository branch: `feature/ris-partner-profile-persistence-v1`.
- Local starting HEAD: `4175e8017f31c61f7f39c749cd21971e32c41c00`.
- Target: only the Modi test-account installation `ris-dev2`.
- Account guard: `262370457690`.
- Region: `eu-central-1`.
- Profile: explicitly `default` for this authorized read-only rehearsal.
- `ris-dev`, `mays-ris`, `ris-dev-pf` and foreign resources were not targeted.
- No apply, destroy, import, state mutation, workspace creation, resource
  replacement, Lambda invocation or deployment was performed.
- No `-target`, `-replace`, `state rm` or import workaround was used.
- The 39 pre-existing untracked files were preserved.

## Phase A — identity and backend evidence

### Account guard

The explicit read-only STS guard passed for the requested Modi test account:

```text
account  = 262370457690
region   = eu-central-1
principal = arn:aws:iam::262370457690:user/devnemo
profile  = default
```

No credentials or tokens were recorded.

### State and lock

The read-only backend check used the historically documented `ris-dev2`
backend tuple:

| Item | Observed result |
|---|---|
| S3 backend bucket | `ris-dev2-tf-state-dev` exists and was readable |
| State key | `env:/ris-dev2/dev/terraform.tfstate` |
| Current state object | exists; metadata-only checks passed |
| Current state serial | `17` |
| Current state resources | **0** |
| State lineage | present |
| Lock table | `ris-dev2-tf-lock` exists, status `ACTIVE` |
| State object versions | multiple historical versions exist |

The current object is an empty post-destroy-style state, not a usable managed
resource inventory. Historical object versions contain larger state snapshots,
but selecting or restoring one would be a state mutation/migration decision
and was not attempted.

### Historical resource evidence

Local evidence records a previous isolated `ris-dev2` run in this account,
including a live Cognito pool, CloudFront health distribution, OAC and runtime
resources. The cleanup evidence later records zero runtime resources and only
the backend bucket/lock table remaining. Historical IDs are therefore not
current ownership evidence.

The historical records also disagree on protected Cognito identifiers (for
example `eu-central-1_uhvqKPR7G` and `eu-central-1_TGra2zmvu`) and associated
CloudFront/OAC observations. Because the current state contains no resources,
there is no authoritative Terraform association for selecting one baseline.

**Protected baseline conclusion:** CloudFront distribution, Cognito pool,
Cognito clients/domain, CloudFront OAC, certificates and DNS cannot be
confirmed as one coherent current `ris-dev2` installation from the available
state. They must not be adopted, replaced or destroyed.

## Phase A — required resource/security checks

The state gate stopped resource adoption checks after proving the current state
was empty. The following live evidence remains uncollected for the current
resource set:

- CloudFront distribution status/configuration, OAC and aliases;
- Cognito pool, clients, domain and dependent CloudFront distribution;
- ACM certificate status and DNS record ownership;
- DynamoDB table schemas, PITR and backups;
- Lambda roles, inline/attached policies and function configuration;
- S3 versioning, encryption, public-access blocks, Object Lock and denies;
- API Gateway routes/authorizers and Orders bindings;
- CloudTrail trail status and audit bucket policy.

The empty state is a blocker before these can be classified as Terraform-owned
upgrade resources. Reading arbitrary resources to find something to adopt would
violate the safe-upgrade boundary.

## Phase B — plan readiness

No Terraform plan was run. This is intentional and required by the hard stop:

1. Current state has zero managed resources.
2. Protected resource IDs are not uniquely established.
3. Historical state versions are not a substitute for an approved state
   recovery/migration.
4. A plan against the empty current state could propose a new installation or
   destructive ownership conflict rather than an upgrade.

The safe plan gate therefore cannot prove the required invariants:

- CloudFront distribution unchanged;
- Cognito pool ID unchanged;
- Cognito clients/domain/OAC/certificate/DNS unchanged;
- no deletes or replacements;
- no foreign `ris-dev`, `mays-ris` or `ris-dev-pf` changes.

### Explicit plan blockers

**BLOCKER B1 — State ownership:** restore/reconcile the authoritative `ris-dev2`
state through a separately approved state procedure. Do not copy a historical
object, remove locks or import resources in this gate.

**BLOCKER B2 — Protected baseline:** provide one verified, current baseline
mapping of Cognito pool/client/domain and CloudFront/OAC/certificate/DNS
resources to `ris-dev2`.

**BLOCKER B3 — Current inventory:** after B1/B2, collect read-only live
descriptions and ownership tags for the complete state resource set.

**BLOCKER B4 — Code readiness:** only then build the current Lambda bundles,
run backend-bound validation against the reconciled workspace and produce a
saved plan outside the repository. The plan must be reviewed in full.

## Expected upgrade review, once unblocked

The reviewed plan must list every create/update/delete/replace and classify
cost and rollback impact. It must contain no delete or replace for protected
CloudFront/Cognito/OAC/certificate/DNS resources, and no unrelated project
family. New G2B tables/policies and Lambda environment wiring must be checked
individually; all privacy/erasure flags must remain `false`.

No plan artifact, state body or sensitive output was committed.

## Phase C status

Phase C is not authorized and was not started. No apply can be considered
until a complete plan report is separately approved. `ris-dev2` is not to be
recreated under the same name while state ownership is unresolved.

## Verification record

| Check | Result |
|---|---|
| Account/region guard | **PASS**, account `262370457690`, region `eu-central-1` |
| State key/backend read-only check | **PASS**, object and lock table readable |
| Current state resource inventory | **BLOCKED**, 0 resources |
| Protected resource identity | **BLOCKED**, conflicting historical evidence |
| Terraform plan | **NOT RUN** |
| Apply/destroy/import/state mutation | **NOT RUN** |
| `ris-dev`/`mays-ris`/`ris-dev-pf` changes | **NONE** |

## Decision

**Phase A:** BLOCKED for safe upgrade completion because the current State is
empty and protected ownership is ambiguous.

**Phase B:** BLOCKED before Terraform plan. No plan or upgrade is authorized.

**Phase C:** NOT AUTHORIZED.

## Commit intent

```text
docs(ris): document ris-dev2 safe upgrade rehearsal blocker
```
