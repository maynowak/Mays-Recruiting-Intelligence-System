# RIS-R08-G2C-7D-2A — External Identity Resolution

**Status:** REPOSITORY DISCOVERY VERIFIED / PUBLIC JWKS PARTIAL /
OWNERSHIP AND CURRENT DEPLOYMENT CONFLICT / G2C-7D-3 BLOCKED

## 1. Baseline and guard

- Branch: `feature/ris-partner-profile-persistence-v1`
- Starting HEAD: `1ff80c2d010b4547f385d083232bdbeaa0b8e880`
- AWS profile: `default`
- Account guard: `262370457690` PASS
- Region: `eu-central-1`
- Principal: `arn:aws:iam::262370457690:user/devnemo`
- No AWS mutation, token issuance, login, user operation, plan or state
  operation was performed.

## 2. Repository and Jobsearch discovery

### RIS configuration

The G2C-6 implementation requires in external mode:

- Cognito pool ID and pool ARN;
- complete HTTPS Cognito issuer;
- human app client ID;
- M2M app client ID;
- optional informational OAuth domain.

The API module creates two JWT authorizers. The human authorizer audience is
the human client; the machine authorizer audience is the M2M client and the
machine route requires `ris-api/m2m/execute`. The issuer is passed explicitly
to both authorizers. Lambda consumes API Gateway-verified claims (`iss`, `aud`,
`client_id`, `token_use`, `scope`) and binds partner credentials through the
registry; it does not independently invent an issuer or client identity.

The local checkout contains no `installer/projects/mays_jobsearch` clone or
current Jobsearch deployment configuration. Repository overlays and reports
are evidence sources only, not current deployment proof.

### Historical/configuration values

The latest retained OAuth audit (2026-10-21) records, in a different account
(`240571105849`), the following values:

| Field | Historical value | Evidence quality |
|---|---|---|
| Pool | `eu-central-1_ojbmoiYGM` / `ris-dev-dev-users` | HISTORICAL ONLY |
| Human client | `7ldhihlpdgsgcl3puvu4oi7ksv` | HISTORICAL ONLY |
| M2M client | `82ji073smu1b3fsvj96sonso` | HISTORICAL ONLY |
| Issuer | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM` | HISTORICAL ONLY |
| OAuth/custom domain | `auth.mays-job-matcher.app` | HISTORICAL/CONFLICT |
| Historical Cognito CloudFront | `d1xd3gat3vr3ss.cloudfront.net` | HISTORICAL ONLY |
| M2M scope | `ris-api/m2m:execute` | CONFIG/HISTORICAL |

Older reports contain additional pool/client values and are not treated as
current.

## 3. Public OIDC/DNS verification

Read-only public checks produced:

| Check | Result | Interpretation |
|---|---|---|
| `auth.mays-job-matcher.app` DNS | CNAME `dsv3el0c1dn2.cloudfront.net` | current external DNS observation |
| Custom-domain OIDC discovery | HTTP 404 | no usable public discovery metadata |
| Custom-domain JWKS | HTTP 404 | no usable custom-domain JWKS |
| Historical pool JWKS URL | JSON JWKS, 2 public keys | public keyset exists for historical pool ID; does not prove current Jobsearch use/ownership |
| Historical prefix discovery | HTTP 404 | no usable discovery metadata at that hostname |
| TLS | HTTPS response with Cognito/CloudFront headers on custom domain | endpoint is externally served, ownership unresolved |

The current DNS target `dsv3el0c1dn2.cloudfront.net` conflicts with the
historical Cognito CloudFront target `d1xd3gat3vr3ss.cloudfront.net`. The 404
must not be interpreted as proof that the pool is absent; it does mean the
public custom-domain contract is not currently verifiable.

No tokens, credentials, login attempts or mutating OAuth requests were used.

## 4. Target-account AWS verification

Read-only target-account searches found no Cognito pool, client, CloudFront
distribution, OAC, Route 53 zone/record or ACM certificate matching the
historical/configuration candidates. Explicit `describe-user-pool` checks in
account `262370457690` returned `NOT_FOUND` for:

- `eu-central-1_ojbmoiYGM`;
- `eu-central-1_7QCp09XEZ` (older historical candidate).

No other AWS profile or account was queried. This does not prove deletion or
nonexistence in the owning external account.

## 5. Identity contract matrix

| Field | Value | Evidence | Status |
|---|---|---|---|
| Identity AWS account | likely external; exact account not authorized/verified | target-account absence + historical reports | UNKNOWN |
| Identity region | `eu-central-1` | pool IDs/issuer/JWKS | CONFIG/PUBLIC PARTIAL |
| Pool ID | `eu-central-1_ojbmoiYGM` candidate | historical reports + public JWKS | HISTORICAL ONLY |
| Pool ARN | not currently verified | no target-account pool; no owning-account access | UNKNOWN |
| Human client | `7ldhihlpdgsgcl3puvu4oi7ksv` candidate | historical audit/config reports | HISTORICAL ONLY |
| M2M client | `82ji073smu1b3fsvj96sonso` candidate | historical audit report | HISTORICAL ONLY |
| JWT issuer | historical regional issuer above | historical reports + matching public JWKS URL | HISTORICAL ONLY |
| OAuth domain | `auth.mays-job-matcher.app` candidate | DNS + historical reports | CONFLICT |
| Current CloudFront | `dsv3el0c1dn2.cloudfront.net` DNS target | public DNS | UNKNOWN/external |
| Historical CloudFront | `d1xd3gat3vr3ss.cloudfront.net` | historical external-account audit | HISTORICAL ONLY |
| Domain/TLS ownership | external DNS/CloudFront evidence only | DNS, HTTP, target-account absence | UNKNOWN |

## 6. M2M decision

**M2M REQUIRED for the current RIS implementation.** The Terraform API module
always declares the machine JWT authorizer and the machine execution route
requires the `ris-api/m2m/execute` scope. The external variables also fail
closed when the M2M client ID is missing. `orders_lifecycle=disabled` does not
remove this kernel API dependency.

The candidate M2M ID is not authorized as a plan input because it is only
historical. No M2M client will be created automatically.

## 7. RIS compatibility

The implementation is structurally compatible if the owning team supplies a
single consistent current tuple:

```text
pool_id + pool_arn + issuer + human_client_id + m2m_client_id
```

The issuer must be the regional pool issuer, not the CloudFront/custom-domain
hostname. Human and M2M audiences remain distinct; M2M requires
`ris-api/m2m/execute`. No Cognito resource is managed in external mode.

One follow-up code issue is identified: the offline G2C-7C preflight currently
validates an external pool ARN against the target account ID. If the protected
pool is in another account, that validator needs a reviewed cross-account
identity-account field before it can accept the real tuple. This is a separate
implementation task; no identity resource or validation bypass was introduced
here.

## 8. Required evidence and decision

The owning Jobsearch/AWS team must provide, through an authorized read-only
channel:

1. current pool ID/ARN and owning account;
2. current human and M2M client IDs;
3. current issuer and OAuth domain;
4. current client OAuth flows/scopes/callbacks;
5. CloudFront/OAC ownership mapping;
6. confirmation that these values correspond to the currently deployed
   Jobsearch version.

Until then:

- Identity Repository Discovery: **VERIFIED**
- Public OIDC verification: **PARTIAL/BLOCKED**
- Cognito ownership: **BLOCKED**
- Human client contract: **BLOCKED**
- M2M requirement: **REQUIRED, reference unresolved**
- RIS external compatibility: **STRUCTURAL GO / INPUT BLOCKED**
- G2C-7D-3 Terraform plan: **BLOCKED / NOT AUTHORIZED**
- Apply: **NOT AUTHORIZED**

## 9. Offline verification

- G2C-6/G2C-7 identity, bootstrap and plan-contract tests: **15 passed**.
- `py_compile installer/bootstrap_preflight.py`: **PASS**.
- Terraform `fmt -check`: **PASS**.
- Terraform `validate`: **BLOCKED** in the final protected checkout because
  the pre-existing deletion of `terraform/modules/mays_orders/variables.tf`
  is preserved; the generated module then lacks its input declarations. A
  prior local builder run validated the complete generated artifact, but the
  deleted tracked file was not left restored.
