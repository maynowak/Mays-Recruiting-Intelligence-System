# RIS-DEV2-AUTH-06 — Abschlussbericht

## Final decision

```text
RIS-DEV2-AUTH-06 — DEPLOYMENT BLOCKED
```

The ApplicationV1 dispatcher fix is packaged and locally functionally
validated. The deployed `ris-dev2-dev-agent` package is demonstrably different
and still contains the old dispatcher reference. No AWS write was executed.

## Decision matrix

| Gate | Status | Evidence |
|---|---|---|
| Repository-/Fix-Baseline | PASS | `f876c26` fix verified; subsequent reports committed cleanly |
| AWS Account Guard | PASS | account `262370457690`, profile `default`, region `eu-central-1` |
| Terraform State Guard | PASS | serial `25`, expected lineage unchanged |
| Lambda Deployment Ownership | VERIFIED | Terraform `filename` + `filebase64sha256` owns code |
| Reproducible Packaging | PASS | official `build_zip.py --bundle all`; 76-entry artifact |
| Artefakt-Hash | VERIFIED | local SHA-256 `f2630322…d613`; Base64 recorded in 06C |
| Dispatcher-Tests | PASS | functional auth/application tests and ZIP import smoke pass |
| Auth-/Application-Regression | PASS | 177 tests, 304 subtests |
| Recovery-Artefakt | AVAILABLE | read-only prior ZIP matches deployed `CodeSha256` |
| Deployment-Differenz | VERIFIED | deployed hash differs; prior ZIP contains old dispatcher call |
| Protected Infrastructure | UNCHANGED | no AWS write, Terraform apply, alias or config mutation |
| AWS Code Deployment | NOT EXECUTED | explicitly outside authorization |

## Blocking causes

1. This prompt explicitly stops before every AWS write operation.
2. The complete selected offline packaging run had one Windows path-copy
   failure (`181 passed, 1 failed, 2 skipped, 304 subtests`), so the strict
   offline regression gate is not fully green. The functional suite itself
   passed (`177 tests, 304 subtests`), and the remaining packaging tests passed
   when excluding that environment-sensitive case.
3. A future deployment must use Terraform's existing ownership path, an exact
   reviewed plan, the artifact digest, and a fresh Lambda `RevisionId` check.

## Artifacts and recovery

- Release artifact: `terraform/lambda.zip`;
- release SHA-256: `f2630322a6887fef860552264f6c6fbeb4e1e8985acc7dbe612e99b6dea8d613`;
- previous deployed recovery ZIP: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-auth-06-previous-lambda.zip`;
- previous deployed SHA-256: `45ae52c1f3cc455f0e5dd1f64482eb6a02bbee7a3117a260d58bd20b81c54c38`;
- previous revision: `f3719946-b052-48a5-bd62-750ffc54dcab`.

Neither ZIP is committed. No rollback was performed. A later release requires
separate explicit authorization naming the Lambda ARN, artifact hash, reviewed
Terraform plan and revision guard.
