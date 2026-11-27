# RIS-DEV2 Worker Controlled Apply — 19H

**Result: COMPLETE.** The explicitly approved 19G5 saved plan was applied
exactly once. Read-only verification passed. **Stop before 20A — Live Canary
Preflight.** No automatic continuation is authorized.

## Approved plan and apply

- AWS account/region: `262370457690` / `eu-central-1`; workspace: `ris-dev2`.
- Feature branch source HEAD at apply: `d89042bab32ad1e012b0b260c829bac64948c2f5`.
- Saved plan:
  `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-worker-19g5.tfplan`
- Approved plan SHA-256:
  `d78c0fcfaee991c774895c583604f0ea270dee600f59af7e37c9cf1e804985c3`.
- Worker bundle SHA-256:
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
- Terraform apply was invoked exactly once on that saved plan and exited 0:
  **0 added, 2 changed, 0 destroyed**. The only changed addresses were
  `module.lambda.aws_lambda_function.agent` and
  `module.agent_transport[0].aws_lambda_function.dispatch_ingress`.
- No replan, retry, rollback, Lambda invocation, order creation, redrive, or
  recovery was performed.

## Read-only post-apply verification

Both target Lambdas now report the approved package `CodeSha256`
`UHvBfbny7gky5C3gOaUIqz8B47srVRDqefLlT5WzpY0=` (the base64 SHA-256 of the
approved Worker ZIP), `State=Active`, and `LastUpdateStatus=Successful`.
Their runtime settings, environment variables, and ownership tags matched the
pre-apply snapshot.

Analysis (`ris-dev2-dev-analysis`) and Orders-Reader
(`ris-dev2-dev-orders-reader`) retained their pre-apply code hashes and
complete environment/configuration; both remain Active with successful last
updates. Analysis still has `ANALYSIS_SYNTHETIC_MODE=true`. There were no
unexpected State inventory/resource changes.

The backend State retained lineage
`a0bd361d-5cd1-a207-a8c0-e6888f0be082`; serial advanced from `75` to `76`.
S3 VersionId advanced from `oacaI13gBig4EZiLdlTGuGHb_WB6ksmQ` to
`M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T`. The only State resource addresses changed
were the two approved Lambda functions. Their code-related State fields
(`source_code_hash`, `code_sha256`, `source_code_size`, and `last_modified`)
reflect the successful code updates.

Non-sensitive machine-readable verification is in
`docs/reports/evidence/19H/post-apply-verification.json`; environment values
are not included, only unchanged indicators and SHA-256 fingerprints.

The pre-existing unstaged
`docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json` remained the
only worktree change and was not touched.

## Final gates

| Gate | Result |
|---|---|
| `PREFLIGHT` | PASS — account, region, HEAD, workspace, backend, State and live resources verified |
| `APPROVED_PLAN_HASH` | PASS — exact 19G5 plan SHA-256 verified immediately before apply |
| `CONTROLLED_APPLY` | PASS — one invocation, exit 0 |
| `APPLY_SCOPE` | PASS — 0 Add / 2 Change / 0 Destroy; only the approved Worker and Ingress |
| `AGENT_CODE_HASH` | PASS — approved Worker bundle hash |
| `DISPATCH_CODE_HASH` | PASS — approved Worker bundle hash |
| `ANALYSIS_UNCHANGED` | PASS — code/configuration/environment unchanged |
| `ORDERS_READER_UNCHANGED` | PASS — code/configuration/environment unchanged |
| `MODE_UNCHANGED` | PASS — Analysis synthetic mode remains `true`; environments unchanged |
| `STATE_VERIFICATION` | PASS — serial 75 → 76, lineage unchanged, new S3 VersionId recorded |
| `LIVE_INVOCATIONS` | 0 |
| `NEW_ORDERS` | 0 |
| `REDRIVES` | 0 |
| `APPLY_COUNT` | 1 |

**STOP before 20A — Live Canary Preflight. No automatic continuation.**
