# RIS-R08-G2C-5 — UPGRADE READINESS MATRIX

## Gate summary

| Gate | Status | Evidence / blocker |
|---|---|---|
| Git baseline | PASS | Actual HEAD `438decf`; 39 untracked preserved |
| Account/region guard | PASS | `262370457690` / `eu-central-1` / `default` |
| Backend access | PASS | Bucket/key readable; lock table ACTIVE |
| Current managed State | BLOCKED | Serial 17, 0 resources |
| State ownership | BLOCKED | Historical teardown; no current resource mapping |
| Protected infrastructure | BLOCKED | Historical IDs not live; domain/ACM/DNS incomplete |
| In-place upgrade | BLOCKED | Cannot prove ownership or protected baseline |
| External-identity construction | DESIGN READY | Requires reviewed code change before plan |
| Offline Python/format/validate | PASS | See construction report |
| API contract | BLOCKED | 2 planned privacy routes lack source declarations |
| Installer/builder | BLOCKED | 4 installer failures; builder timeout |
| AWS read-only inventory | PASS/BLOCKED | Inventory read-only; upgrade criteria fail |
| Terraform plan | BLOCKED / NOT RUN | Correct safety behavior |
| Apply | NOT AUTHORIZED | Separate approval required |

## Protected-resource matrix

| Protected area | Current evidence | Ownership | Allowed change |
|---|---|---|---|
| Jobsearch domain | No current ris-dev2 mapping; historical external references conflict | UNKNOWN | None until live ID/ARN/owner proof |
| Jobsearch CloudFront | No current ris-dev2 mapping | UNKNOWN | None |
| Cognito pool | Historical pools not found; current State empty | UNKNOWN | No create/adopt/replace |
| Cognito clients | Historical clients not found | UNKNOWN | No client recreation |
| Cognito domain/OAuth | Domain response not authoritative; no current State address | UNKNOWN | No domain/OAuth change |
| Users/auth contracts | No current pool association | UNKNOWN | No user migration or pool replacement |
| DNS/ACM/TLS | No Terraform-owned references in retained state | UNKNOWN | No DNS/certificate change |
| CloudFront OAC | Historical OAC not found | UNKNOWN | No recreate/adopt |
| Other installations | Outside scope | MUST REMAIN FOREIGN | No reads/mutations |

## Classification of remaining failures

| Finding | Class | Required action |
|---|---|---|
| Empty current State | deployment-blocking | approved state recovery or isolated design |
| Historical ID conflicts | deployment-blocking | one authoritative protected baseline |
| Lock table PITR disabled | deployment/recovery blocker | approved backup/PITR decision |
| Backend bucket untagged | ownership blocker | owner evidence; no adoption by name |
| OpenAPI privacy routes | functional-activation blocker | implement source or revise contract decision |
| 39 DynamoDB Local skips in historical baseline | deployment verification blocker | approved local endpoint and rerun |
| Installer pin/STS/path failures | deployment-blocking | repair fixture/tool contract, rerun |
| Builder timeout | deployment-blocking | reproduce under approved builder fixture |
| Privacy flags false | safe by default | remain false |

## Plan approval checklist

- [ ] Explicit account/profile/region guard repeated.
- [ ] State lineage and complete resource inventory proven.
- [ ] Protected IDs/ARNs match live resources.
- [ ] No foreign project addresses in plan.
- [ ] No protected deletes/replacements.
- [ ] No state migration/import/`-target`/`-replace`/`state rm`.
- [ ] No implicit Orders or Cognito installation.
- [ ] All privacy/erasure flags false.
- [ ] Plan artifact and hash stored outside Git.
- [ ] Separate written apply approval.
