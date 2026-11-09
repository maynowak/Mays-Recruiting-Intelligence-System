# RIS-HEALTH-PUBLISHER-SCHEDULE-15MIN-01 — Report

**Result:** `APPLIED / VERIFIED — RIS-DEV`  
**Classification:** GREEN  
**Date:** 2026-11-09 (plan 08:36:03Z, apply 08:36:34Z)  
**Branch / HEAD:** `feature/jm-ris-cv-storage-integration-01` / `74e766c`  
**Worktree:** `/home/dci-student/projects/mays-xrepo-orchestration/worktrees/ris-cv-storage-01`

## 1. Scope

Only `module.health_plane.aws_cloudwatch_event_rule.health_publisher_schedule`.
No Lambda code, IAM, API Gateway, data, Cognito, CloudFront, DNS/ACM or
Mays-Orders change; no product code.

## 2. Context

| Field | Value |
| --- | --- |
| AWS account | `240571105849` |
| Profile / region | `mayaws` / `eu-central-1` |
| Terraform | `1.16.1`, AWS provider `6.67.0` |
| Workspace | `ris-dev` |
| Backend | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| State lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| State serial | `54` before, `55` after |
| State resources | `250` |
| Live rule | `ris-dev-dev-health-publisher-schedule` |
| Live target | `ris-dev-dev-health-publisher` |
| Rule state | `ENABLED` |

## 3. Change

`terraform/modules/health_plane/main.tf:160`

```diff
-  schedule_expression = "rate(5 minutes)"
+  schedule_expression = "rate(15 minutes)"
```

Commit `74e766c` (`chore(health): reduce publisher schedule to 15 minutes`),
files: `terraform/modules/health_plane/main.tf`, `docs/AI_AUDITLOG.md`.

## 4. Plan

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-health-15min.tfplan` |
| SHA-256 | `f8b02fb00ab9e95cae57c91cc361eb24f650edded411440bdfcee33c436b64b8` |
| Timestamp | `2026-11-09T08:36:03Z` |
| Result | 0 add / 1 change / 0 destroy |
| Only change | `module.health_plane.aws_cloudwatch_event_rule.health_publisher_schedule` |
| Plan JSON | 273 no-op + 1 update; no output changes |
| Log | `/tmp/opencode/health-15min-plan.log` |

## 5. Apply

| Field | Value |
| --- | --- |
| Apply log | `/tmp/opencode/health-15min-apply.log` |
| Applied | `2026-11-09T08:36:34Z` (CloudTrail `PutRule`) |
| Result | `Apply complete! Resources: 0 added, 1 changed, 0 destroyed.` |
| State serial | `54 → 55` |
| State object | `LastModified=2026-11-09T08:36:37Z` |
| CloudTrail | one `PutRule`, Terraform provider; no other mutating API |
| Forbidden flags | none observed (`-target`, `-replace`, `-destroy`, `-refresh=false`, `-lock=false`) |

## 6. Verification commands

```bash
AWS_PROFILE=mayaws aws events describe-rule \
  --name ris-dev-dev-health-publisher-schedule --region eu-central-1
# ScheduleExpression: rate(15 minutes); State: ENABLED

AWS_PROFILE=mayaws aws s3 cp \
  's3://mays-ris-tf-state-dev/env:/ris-dev/dev/terraform.tfstate' - \
  --region eu-central-1
# serial 55; lineage 9cec61e5-c036-1ad5-6ae4-8b48a50122a4; 250 resources

AWS_PROFILE=mayaws aws cloudtrail lookup-events \
  --region eu-central-1 --start-time 2026-11-09T08:35:00Z \
  --end-time 2026-11-09T08:38:00Z \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutRule
# 1 event, 08:36:34Z, requestParameters.scheduleExpression=rate(15 minutes)
```

## 7. Invocation impact

- Pre-change `AWS/Lambda Invocations`: 12/hour (288/day).
- Expected at the 15-minute rate: 4/hour (96/day).
- At audit time no full post-change hour had elapsed; re-check a full hour after
  `08:36Z` if a measured post-change number is required.

## 8. Checks

- `terraform fmt -check -diff terraform/modules/health_plane/main.tf`: PASS.
- `terraform -chdir=terraform validate`: PASS; only pre-existing deprecation
  warnings.
- No Lambda bundle rebuild required (no Lambda change).
- No product tests required for a schedule-only change.

## 9. Git / hygiene

- `git status --short --branch`: clean before the report commit.
- Commit `74e766c` is local only; no push, merge, PR or deployment.
- Files changed: `terraform/modules/health_plane/main.tf`,
  `docs/AI_AUDITLOG.md`.

## 10. Risks / open

- Post-change invocation count not yet measured for a full hour.
- No alarm/health behavior change; the health publisher continues at one
  third of the previous frequency.

## Evidence

- `/tmp/opencode/ris-dev-health-15min.tfplan`
- `/tmp/opencode/health-15min-plan.log`
- `/tmp/opencode/health-15min-apply.log`
- `/tmp/opencode/health-15min-state.json`
- `/tmp/opencode/status-final-state.json`
