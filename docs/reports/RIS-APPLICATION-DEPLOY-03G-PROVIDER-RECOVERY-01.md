# RIS-APPLICATION-DEPLOY-03G — Provider Recovery 01

**Result:** **PROVIDER READY / APPLY NOT EXECUTED**

## Root cause

Terraform `1.17.0` on Windows `amd64` was compatible with the saved plan, but
the external 03C Terraform data directory contained only:

```text
hashicorp/aws/6.67.0/windows_amd64
```

The required `hashicorp/time` `0.14.2` provider binary was absent. There was
no `TF_PLUGIN_CACHE_DIR`, CLI provider mirror or Terraform CLI configuration
overriding installation. The repository lockfile did contain the exact time
provider version and checksums. The failure was therefore a missing local
provider installation, not a platform mismatch, corrupt binary or AWS/state
problem.

## Phase A diagnostics

| Check | Result |
|---|---|
| Terraform | `1.17.0` |
| Platform | Windows `amd64` |
| Repository lockfile | contains `hashicorp/time` `0.14.2`, constraint `~> 0.11` |
| 03C provider directory | AWS `6.67.0` only; time absent |
| 03D provider directory | AWS `6.67.0` only; time absent |
| Repository `.terraform/providers` | absent |
| `TF_PLUGIN_CACHE_DIR` | unset initially |
| Terraform CLI config/mirror | none found |
| Failure classification | missing provider binary in selected `TF_DATA_DIR` |

## Recovery

The repository lockfile was first fingerprinted and then restored after a
normal root `terraform init` temporarily re-selected only the providers
currently referenced by the root configuration. No `-upgrade` was used.

Provider recovery used a separate external minimal Terraform root with an
exact regular requirement:

```text
source  = "hashicorp/time"
version = "= 0.14.2"
```

The provider was installed by normal Terraform provider installation into
external directories only:

- provider root: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03g-provider-root`
- provider data: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03g-apply-tfdata`
- shared cache: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03g-plugin-cache`

Terraform reported the provider as signed and installed:

```text
Installed hashicorp/time v0.14.2 (signed by HashiCorp)
```

The actual provider executable is Windows `amd64`, exists at the dedicated
external data path, and is 18,760,840 bytes. Its binary SHA-256 is recorded
for provenance only:

`c041e0317ff779eac75a392b5ce851431ae712fedca6d4f1a97fee98e7c535e8`

## Checksum and plan verification

The external installation lock contains 14 hashes, all of which are a subset
of the repository lockfile's 15 hashes for `hashicorp/time` `0.14.2`. No
checksum was missing from the repository lockfile.

The existing saved plan was then loaded successfully with
`terraform show -json` using the recovered provider. No new plan was created.

| Check | Result |
|---|---|
| Plan file exists | PASS |
| Plan SHA-256 | MATCH — `65410136A4FB1EF720FB143F9304F8B6A54BEE026C18AA4EE8F527075F4ED196` |
| Plan Terraform version | `1.17.0` |
| Resource changes | 164 entries; 12 active |
| Resource drift | 85, unchanged |
| Plan complete/applyable metadata | `true` / `true` |
| Repository lockfile final hash | `37CF178D14C397F3C29FBCFB04D26837972614F261011363FAA2B7B0C663F71A` |
| Lockfile final Git status | unchanged |

## AWS and state consistency

Read-only verification with profile `default` confirmed:

- account `262370457690`;
- region `eu-central-1`;
- lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`;
- state serial `23`;
- workspace `ris-dev2` using the existing backend configuration.

No AWS resource was mutated. No state push, migration, import, unlock, Apply
or plan calculation was performed during recovery.

## Apply boundary

**Apply was not executed.** The recovered provider is ready for a separately
reviewed resumption of the previously failed Apply using the same saved plan.
This report does not grant or imply a second Apply authorization.
