# RIS-ANALYSIS-CANARY-10B — Controlled AWS Apply · Synthetic Canary

**Date:** 2026-11-20
**Status:** **HYBRID SYNTHETIC E2E VERIFIED** (component: **AWS PARSER RUNTIME
VERIFIED**). **FULL RIS ANALYSIS AGENT LIVE VERIFIED: not claimed** — there is
no deployed analysis Lambda and no real-user data approval.
**Operator approval:** granted for exactly plan
`e64a6272ac212dce54123c2b9533d42175f85ccc8d34ec2b6e26c3b39d15e676`
(17/2/0), including the two documented in-place updates.
**Safety:** synthetic data only; no main merge, no production deployment, no
PURGE, no Cognito/CloudFront/DNS change, no entitlement/catalog/consent grant,
no agent activation.

---

## 1. Approved plan and artifact

| Item | Value |
|---|---|
| Plan file | `C:/Users/DCI-Student/AppData/Local/Temp/opencode/rc10b/plan.out` |
| Plan SHA-256 (approved & applied) | `e64a6272ac212dce54123c2b9533d42175f85ccc8d34ec2b6e26c3b39d15e676` |
| Plan JSON SHA-256 | `66a954763dae6662974bdc7338a7d69f59b76102773fa4b8d75330976a8c9f31` |
| Artifact SHA-256 | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` |
| Artifact size / files | 17 937 176 bytes / 412 |
| Expected / preflight counts | 17 add / 2 change / 0 destroy / 0 replace |
| Guard before apply | `NO_SHARED_DESTROY` |

The saved plan was re-hashed and re-rendered to JSON immediately before apply;
both values matched the approval. No new plan was substituted.

## 2. AWS target and state

| Item | Before apply | After apply |
|---|---|---|
| Account | `262370457690` | unchanged |
| Caller | `arn:aws:iam::262370457690:user/devnemo` | unchanged |
| Region | `eu-central-1` | unchanged |
| Backend | `ris-dev2-tf-state-dev` / `dev/terraform.tfstate` | unchanged |
| Lock table | `ris-dev2-tf-lock` | unchanged |
| Workspace | `ris-dev2` | unchanged |
| State serial | **64** | **67** |
| Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` | unchanged |
| State resources | 266 | 283 (+17) |

## 3. Terraform apply result

Command: `terraform apply -input=false -auto-approve <approved plan>` in the
existing workspace, locking enabled, no targets, no replacements, no extra
variables, no parallel operation.

```
Apply complete! Resources: 17 added, 2 changed, 0 destroyed.
```

Full Terraform summary: `%TEMP%/opencode/rc10b/apply.log`.

### Created (17)

Analysis runtime: `analysis` role, `analysis` policy, `jobs` bucket, Public
Access Block, SSE configuration, lifecycle configuration, analysis log group,
`parser` role, `parser_logs` policy, parser log group, parser Lambda,
`analysis_invoke_parser` policy, `parser_invoke_analysis` permission.

Transport/documents: `orders_agent_dispatch` policy, `agent_transport.order_result`
policy, `lambda.order_result_transport` policy, documents CORS configuration.

### Changed (2, in place)

| Resource | Verified effect |
|---|---|
| `module.agent_transport[0].aws_iam_role_policy.dispatch_ingress` | WorkItems statement now also allows `table/ris-dev2-dev-work-items/index/*`; same four actions; nothing removed |
| `module.mays_orders[0].module.lambda.aws_lambda_function.handler` | Env now includes `ORDER_DISPATCH_QUEUE_URL`; all previous values unchanged, including both Cognito references |

No destroy and no replacement occurred. No Cognito, CloudFront, Route53 or ACM
resource appears in the state change set.

## 4. Parser Lambda live verification

| Property | Observed |
|---|---|
| Function | `ris-dev2-dev-analysis-parser` |
| State / last update | `Active` / `Successful` |
| Runtime / architecture | `nodejs22.x` / `arm64` |
| Memory / timeout | 512 MB / 15 s |
| Handler | `lambda/ris_parser_handler.handler` |
| Role | `ris-dev2-dev-analysis-parser` |
| Code SHA-256 (Lambda base64) | `+3Qfsl580pIypDpjE3puKoyg6UjMLv32dkuHeRGfMBo=` = artifact hex `fb741fb2…f301a` |
| Code size | 17 937 176 bytes |
| Function URL | **none** (`ResourceNotFoundException`) |
| Permission | `AllowAnalysisRuntimeInvoke`, principal `arn:aws:iam::262370457690:role/ris-dev2-dev-analysis`, action `lambda:InvokeFunction` |

IAM:

- Analysis role policy: logs, `s3:GetObject` on `ris-dev2-dev-documents/tenant/*`,
  `Put/Get/DeleteObject` on `ris-dev2-dev-analysis-jobs/jobs/*`.
- Invoke policy: `lambda:InvokeFunction` on the parser function only.
- Parser role policy: `CreateLogStream`/`PutLogEvents` on its own log group.
- Parser trust: `lambda.amazonaws.com` only.

**Caveat:** the analysis role is not attached to a deployed compute component
(its trust allows Lambda only, and no function uses it). The invoke permission
was verified by IAM/Lambda configuration; the live invocations below ran under
the operator identity.

## 5. Hybrid synthetic E2E

Local `AnalysisOrchestrator` with `NodeParser(mode="lambda")` against the real
`ris-dev2-dev-analysis-parser`. Synthetic fixtures only
(`synthetic-canary-cv.pdf`, SHA-256 `70e4076f…`; `synthetic-job.json`,
SHA-256 `26c320d7…`).

| Case | Result |
|---|---|
| CV-only (PDF via Lambda) | `CVParserResultBody` 1.0; tags `Python, AWS, Terraform, Docker, Linux, SQL, MSc Computer Science` |
| Job-only | `JobParserResultBody` 1.0; 15 tags |
| ATS-only | `ATSAnalysisResultBody` **2.0**; 8 tags |
| Comparison | `ComparisonResultBody` 1.0; required 83.3 %, preferred 0 %, overall 76.9 % |
| Full analysis | all four bodies correct |
| CV-PDF | pageCount 1, textLength 273, document SHA = fixture SHA |
| Idempotent replay | `idempotent=true`, all four bodies identical |
| Invalid capability | controlled `ParserInputError` (`invalid_input`) |
| Parser timeout | real invoke with 0.01 s client timeout → `ParserUnavailable` (`parser_unavailable`); no unhandled error |
| Cross-tenant CV | `cv_access_denied` |
| Missing entitlement | `entitlement_denied` |
| Missing consent | `consent_required` |
| Expired jobRef | `job_ref_expired` |
| Oversize job text | `job_text_too_large` |

The adapter now enforces `connect_timeout`/`read_timeout` with zero SDK retries
(`agents/parsers/lambda_adapter.py`), covered by a unit test.

## 6. Job S3 and cleanup

Real bucket `ris-dev2-dev-analysis-jobs`, synthetic objects only:

| Check | Evidence |
|---|---|
| Put / get | 74-byte object read back identically; `job_` opaque ref |
| SSE | `ServerSideEncryption = AES256` |
| Metadata | tenant, user, sha256, expires-at, max-expires-at |
| TTL | default **7200 s**, hard max **14400 s** |
| Cross-tenant | object not found (key includes tenant/user) |
| Oversize | > 1 MiB rejected with `JobTooLarge` |
| 2 h / 4 h expiry | controlled clock: `JobExpired` after 2 h + 1 s and after 4 h + 1 s |
| Explicit delete | object deleted, subsequent get `JobNotFound` |
| Cleanup | `cleanup_expired` removed only the object past max-expiry (1 removed); fresh object kept |
| Final state | 0 objects under `jobs/` |

**Not claimed:** physical deletion within 4 h. Access is refused server-side
after 2 h/4 h; the bucket lifecycle is 1 day and is only a backup. A physical
4-hour deletion was not verified.

## 7. CloudWatch and regression checks

| Check | Result |
|---|---|
| Parser `Errors` metric (last 2 h) | 0 |
| Parser invocations | 17 |
| Log content | only START/END/REPORT; no `JVBERi`, `CANARY APPLICANT` or synthetic job marker in logs |
| Analysis log group | 0 events, retention 14 d |
| Parser log group | retention 14 d |
| `ris-dev2-dev-agent` | Active / Successful, unchanged (LastModified 2026-11-18) |
| `ris-dev2-dev-orders-reader` | Active / Successful, unchanged |
| `ris-dev2-dev-agent-dispatch-ingress` | Active / Successful, unchanged |
| `ris-dev2-mays-orders-handler` | Active / Successful; env update as approved |
| Shared queues/secrets/tables | no delete, no replacement |

## 8. Post-apply plan and drift

Fresh read-only plan with the same variables after apply:

| Item | Value |
|---|---|
| Changes | **0** (no drift) |
| Guard | `NO_SHARED_DESTROY` |
| Plan SHA-256 | `46a1e563ca16f64ff46d576b6d5f5118c0f7f6da27dfd59b21422bd8e6839150` |
| Plan JSON SHA-256 | `ae63207417bb37eb6ad148dd3b2b20112be68fdf4bd2a1dafac5b4b1c36e9af2` |

This plan is evidence only and was **not** applied.

## 9. Privacy / entitlement state after the canary

| Item | State |
|---|---|
| `analysis-processing` v1.0 | **DRAFT**, no legal approval ref |
| Entitlements (`ris-internal-analysis`, `analysis-agent`) | **PENDING_APPROVAL**, no grants |
| Catalog | **ABSENT**, no seed |
| Agent activation | **false** |
| Real CV/job data | none processed |
| Synthetic objects | removed; bucket empty |
| PURGE | not executed |

## 10. Remaining blockers

1. Legal/operator approval of the `analysis-processing` notice (real data).
2. Entitlement grant and catalog decision; agent activation.
3. A deployed compute component using the analysis role (no analysis Lambda).
4. Live authenticated canary identity/token for an end-to-end agent test.
5. Lambda's own 15 s timeout was not exercised (only a client-side timeout);
   a controlled slow path would need a separate test hook.

## 11. Tests, auditlog and commits

| Check | Result |
|---|---|
| Focused RIS regression | 254 passed + 13 subtests (see auditlog) |
| Jobsearch parser CLI + handler | 4 passed |
| Preflight manifest test | 7 passed |
| Post-apply plan | 0 changes, guard pass |

Reports: this file, `RIS-ANALYSIS-CANARY-10B-PREFLIGHT.md`,
`analysis-canary-10b-plan-manifest.json`.
