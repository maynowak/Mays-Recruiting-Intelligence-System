# RIS-R08-G2C-7D-1 — Live Resource Discovery

**Status:** LIVE DISCOVERY VERIFIED / PROTECTED IDENTITY MAPPING BLOCKED

## Guard

| Field | Observed |
|---|---|
| AWS profile | `default` |
| Account | `262370457690` — STS guard PASS |
| Region | `eu-central-1` |
| Principal | `arn:aws:iam::262370457690:user/devnemo` |
| Discovery time | 2026-11-02 UTC |
| AWS operation class | read-only |

No profile fallback was used.

## Target backend and current RIS inventory

| Resource | Live evidence | Ownership conclusion |
|---|---|---|
| S3 state bucket | `ris-dev2-tf-state-dev`, `eu-central-1`, versioning enabled | backend only; no application ownership inferred |
| State key | `env:/ris-dev2/dev/terraform.tfstate`, current object present | current State remains serial 17 / zero resources per prior evidence |
| State versions | 17 object versions, no delete marker; current version unchanged | historical evidence only |
| Lock table | `ris-dev2-tf-lock`, ACTIVE, 2 items, PITR DISABLED | backend lock only |
| RIS DynamoDB | no application table with `ris-dev2` prefix | no current RIS data ownership |
| Lambda | no `ris-dev2` functions | no current runtime ownership |
| API Gateway | no `ris-dev2` APIs | no current API/authorizer ownership |
| SQS | no `ris-dev2` queues | no current queue ownership |
| IAM | no `ris-dev2` roles | no current runtime-role ownership |
| CloudTrail | no `ris-dev2` trail | no current audit-trail ownership |

Names were used only to find candidates. Absence/presence by name was not
treated as proof of Terraform ownership.

## Protected Jobsearch/Auth discovery

### Public endpoint evidence

Repository configuration and retained reports identify:

- `mays-job-matcher.app` and `www.mays-job-matcher.app` as public Jobsearch
  endpoints;
- `auth.mays-job-matcher.app` as the historical/custom authentication domain.

Current DNS resolution returned:

| Host | Observation |
|---|---|
| apex | `216.198.79.1` |
| `www` | `216.198.79.1` |
| `auth` | CNAME `dsv3el0c1dn2.cloudfront.net` |
| auth OIDC discovery | HTTPS response `404`, Cognito/CloudFront headers present |

DNS proves an external public mapping only. It does not prove the owning AWS
account, distribution ownership, Cognito pool, or Terraform state association.

### Target-account AWS evidence

Read-only searches in account `262370457690` found:

- no matching Cognito User Pool or App Client;
- no matching CloudFront distribution or OAC;
- no Route 53 hosted zone/record for the Jobsearch domain;
- no ACM certificate matching `mays-job-matcher`, `ris` or `jobsearch` in
  `eu-central-1` or `us-east-1`;
- no API Gateway authorizer that can be associated with the external domain.

Historical IDs such as pool `eu-central-1_ojbmoiYGM` and historical CloudFront
IDs are not current evidence and are not promoted to plan inputs. No users were
listed or changed.

## Protected-resource matrix

| Protected resource | Current ID/ARN | Evidence | Ownership | Allowed change |
|---|---|---|---|---|
| Jobsearch domain/DNS | public DNS only | resolver + retained config | UNKNOWN/external | none |
| CloudFront/OAC | external CNAME target only | DNS + target-account inventory | UNKNOWN, likely foreign | none |
| Cognito pool | not found in target account | target-account `list/describe` | UNKNOWN | none |
| Human client | not found | no current pool | UNKNOWN | none |
| M2M client | not found | no current pool | UNKNOWN | none |
| Cognito issuer | not verifiable; OIDC endpoint returned 404 | public endpoint only | UNKNOWN | none |
| Cognito domain/OAuth | not verifiable | public DNS + no target-account pool | UNKNOWN | none |
| ACM/TLS | no target-account matching certificate | ACM inventory | UNKNOWN/external | none |
| Route 53 | no target-account zone | Route 53 inventory | external DNS likely | none |

## Plan prerequisites

The account/backend discovery gate is **GO**. The protected identity reference
gate is **BLOCKED**. Before a future plan, an authorized owner must provide and
independently verify current pool/client IDs, issuer, OAuth contract and
CloudFront/OAC ownership. Access to another account must not be obtained by
switching profiles under this task.

No Terraform plan, import, state operation or AWS write was performed.
