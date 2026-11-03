# RIS-APPLICATION-DEPLOY-03H — Authorized Apply Resume

**Result:** **FAIL before resource mutation; no retry performed**

## Pre-Apply guards

All requested guards passed before the Apply attempt:

- branch: `feature/ris-application-persistence-v1`;
- HEAD: `70a615356062f37b15eff119e05c659bec088fc3`;
- worktree clean;
- AWS profile `default`, account `262370457690`, region `eu-central-1`;
- workspace `ris-dev2`;
- backend bucket/key/lock matched the approved values;
- state lineage matched `a0bd361d-5cd1-a207-a8c0-e6888f0be082`;
- state serial was `23`;
- plan SHA-256 matched:
  `65410136A4FB1EF720FB143F9304F8B6A54BEE026C18AA4EE8F527075F4ED196`;
- `hashicorp/time` `0.14.2` was available for Windows `amd64`;
- `terraform show -json` succeeded;
- active plan actions were 11 creates, 1 update, 0 deletes and 0 replacements;
- no protected resource was an active plan action.

## Apply result

Terraform was invoked with only the approved binary plan and the recovered
03G Terraform data/provider configuration. It stopped before resource
execution with exit code **1**:

```text
Error: Inconsistent dependency lock file

The given plan file was created with a different set of external dependency
selections than the current configuration. A saved plan can be applied only
to the same configuration it was created from.
```

No new plan was created. No retry, `-upgrade`, target, replace, destroy,
force-unlock, import or state repair was performed.

## Read-only post-failure state

- State serial remains `23`.
- State lineage remains unchanged.
- State SHA-256 remains
  `2476b37a32bfb1208ae38d3b932a6a4be569fbff6673538eeb1ee35f30a32840`.
- `ris-dev2-dev-applications` does not exist.
- ApplicationV1 API routes do not exist.
- Agent Lambda remains Active with its prior successful update status, prior
  code hash and no `APPLICATIONS_TABLE` environment variable.
- CloudFront `E1IZKHFPZ5X7SN` remains deployed and enabled.

The evidence indicates that the Apply failed during plan/dependency
compatibility validation and performed no resource mutation.

## Status

| Item | Result |
|---|---|
| Pre-Apply guards | PASS |
| Plan hash | MATCH |
| Terraform Apply | FAIL |
| Actual creates | 0 |
| Actual updates | 0 |
| Deletes/replacements | 0 / 0 |
| State serial | 23, unchanged |
| Protected infrastructure | UNCHANGED by read-only verification |
| ApplicationV1 deployment | NOT INSTALLED |
| Retry | NOT RUN |

The approved plan remains unused. A further attempt requires a new explicit
authorization after the dependency-selection mismatch is resolved.
