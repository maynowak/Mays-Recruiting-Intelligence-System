# RIS-APPLICATION-DEPLOY-03I — Saved-Plan Dependency Lock Forensics

**Decision:** **REPLAN REQUIRED**

**Apply:** **NOT EXECUTED**

## 1. Executive summary

The `Inconsistent dependency lock file` error is caused by a mismatch between
the dependency selections embedded in the saved binary plan and the
dependency selections produced by the Terraform working data used for the
03H Apply attempt.

The repository lockfile at the plan commit and today is identical and contains
`hashicorp/time` `0.14.2`. However, the current Terraform root has no active
`time` provider requirement; its only configured provider is AWS. A normal
root `terraform init` therefore selected AWS only in the working data and
removed the orphaned `time` selection from that local dependency context. The
saved plan still requires the time provider to load, as proven by the 03E
missing-provider error and successful `terraform show` only after installing
time.

The exact uncommitted lock context used when the plan was created was not
captured. The binary plan and JSON output do not expose the complete internal
dependency-selection map. Therefore the original plan/apply lock consistency
cannot be safely reconstructed from verified artifacts.

## 2. Plan and state identity

| Item | Result |
|---|---|
| Branch | `feature/ris-application-persistence-v1` |
| HEAD at investigation | `e9c30a3c7f7c6199a124412c861434ffea7861ad` |
| Terraform | `1.17.0` / Windows `amd64` |
| Plan | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03c.tfplan` |
| Plan SHA-256 | `65410136A4FB1EF720FB143F9304F8B6A54BEE026C18AA4EE8F527075F4ED196` |
| Plan actions | 11 creates, 1 update, 0 deletes, 0 replacements |
| State serial | `23` |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |

The plan hash was rechecked. No plan, Apply, init, state operation or AWS
mutation was executed during this forensic phase.

## 3. Exact error evidence

### 03E

The first Apply attempt failed while loading the saved plan because the
selected 03C data directory did not contain:

```text
registry.terraform.io/hashicorp/time 0.14.2
```

### 03H

After a signed `time 0.14.2` binary was installed in a separate external
provider environment, the exact same plan failed before resource execution:

```text
Error: Inconsistent dependency lock file

The given plan file was created with a different set of external dependency
selections than the current configuration. A saved plan can be applied only
to the same configuration it was created from.

Create a new plan from the updated configuration.
```

The error names no individual provider or version. It is a dependency-selection
set mismatch, not an AWS/state error and not merely a missing executable.

## 4. Provider and lockfile inventory

### Repository root and configuration

- Terraform root: `terraform/` in the repository checkout;
- root `required_providers`: AWS `>= 6.0.0, ~> 6.0`;
- no active `hashicorp/time` provider block in the current Terraform root or
  modules;
- plan JSON provider configuration contains only AWS;
- plan JSON resource providers contain only AWS.

### Repository lockfile history

The lockfile history contains the prior committed changes:

```text
04c47d2 S06: RIS-Wrapper-Pin-And-Build
045ca91 fix(ris-development): finish -mays-orders component rename
0730acf RIS-HEALTH-PLANE PRE-DEPLOY CLEANUP
```

The lockfile at plan commit `f8deeb7` and the current lockfile are byte-identical
with SHA-256:

`37cf178d14c397f3c29fbcfb04d26837972614f261011363faa2b7b0c663f71a`

The committed time selection is:

```text
provider:   registry.terraform.io/hashicorp/time
version:    0.14.2
constraint: ~> 0.11
```

It contains 15 hashes, including both `h1` hashes and the platform `zh`
hashes. No committed lockfile change occurred after the plan commit.

### Provider environments

| Environment | Observed providers |
|---|---|
| 03C data directory | AWS `6.67.0`; time absent |
| 03D data directory | AWS `6.67.0`; time absent |
| 03G recovery cache/data | time `0.14.2` and AWS available after regular installation |
| Terraform CLI mirror/config | none configured |
| `TF_PLUGIN_CACHE_DIR` initially | unset |

The recovered time installation was signed, Windows `amd64`, 18,760,840 bytes,
and its external lock hashes were a subset of the repository lock hashes. That
proves the binary is valid; it does not prove that the saved plan's complete
dependency-selection map matches the current root's map.

## 5. Plan versus current configuration

The supported JSON representation reports:

- Terraform `1.17.0`;
- 164 resource-change entries;
- 152 no-op entries;
- 12 active entries;
- 85 drift entries;
- provider configuration: AWS only;
- `complete=true`, `applyable=true`.

The binary plan nevertheless required `hashicorp/time` to load. This indicates
that dependency information relevant to plan loading is not fully represented
by `configuration.provider_config` or resource `provider_name` in the JSON.
The exact saved-plan provider-selection map is therefore **NOT DETERMINABLE**
from supported `terraform show -json` output.

The plan was created after a remote `terraform init` had reported changes to
provider dependency selections. The subsequent local lockfile was restored
before committing the 03C report, but no immutable copy of the exact
uncommitted lockfile used at the instant of plan creation was retained. Git
can reconstruct the committed lockfile, not that transient working copy.

## 6. Root cause

1. The saved plan was created in a working context that carried a `time
   0.14.2` dependency selection, even though the current root configuration
   exposes only AWS as an active provider.
2. The first Apply environment lacked the time executable.
3. Provider recovery installed the executable but did not make the current
   root's dependency-selection set identical to the saved plan.
4. Terraform correctly rejected the exact saved plan rather than applying it
   under a different dependency context.

The failure is local Terraform plan/configuration consistency, not AWS drift,
state-lineage change, account mismatch or resource-level authorization.

## 7. Recovery assessment

### Verified recoverable components

- The committed lockfile and checksums are available.
- A signed compatible `hashicorp/time 0.14.2` binary is available externally.
- The saved plan hash is stable.
- AWS account, workspace, lineage and serial remain stable.

### Not safely recoverable

- The exact dependency-selection map embedded in the binary plan is not exposed
  by supported plan JSON.
- The transient lockfile/working context at plan creation was not preserved as
  an immutable artifact.
- A root `terraform init` naturally reselects the current root's active AWS
  dependency set and does not preserve the orphaned time selection.

Using an inferred lockfile or forcing the old plan through an altered local
runtime would be unsafe and is not authorized.

## 8. Decision and recommendation

**REPLAN REQUIRED**

The existing plan is not safely reusable because its exact dependency-selection
context cannot be reconstructed and Terraform has already rejected it under
the recovered provider environment.

Recommended next phase:

1. preserve the current state and repository unchanged;
2. create a new controlled plan from the current root and committed lockfile;
3. verify the new plan's provider/dependency context and SHA-256;
4. re-run all protected-resource and ApplicationV1 guards;
5. obtain a new, separate Apply approval for the new plan.

No new plan was created in 03I, and this report grants no Apply authorization.

## 9. Final safety status

- AWS mutation: **none**;
- State mutation: **none**;
- State serial: **23**;
- Existing plan: hash unchanged, not safely reusable;
- ApplicationV1 deployment: not installed;
- Protected infrastructure: unchanged by read-only verification;
- Apply: **NOT EXECUTED**.
