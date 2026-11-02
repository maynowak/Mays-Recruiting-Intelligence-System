# RIS-DEV2 Protected Infrastructure Contract

**Scope:** `ris-dev2` only, account `262370457690`, region `eu-central-1`.

## Contract

The following resources are immutable from an upgrade operation unless an
explicit ownership and migration decision is approved separately:

- Jobsearch domain and its CloudFront distribution;
- Cognito user pool, app clients, domain and OAuth configuration;
- existing users and authentication contracts;
- DNS, ACM and TLS relationships;
- CloudFront OAC and bucket-policy source references;
- foreign RIS installations and Mays-Orders resources.

## Current evidence status

The authoritative current Terraform object
`s3://ris-dev2-tf-state-dev/env:/ris-dev2/dev/terraform.tfstate` is serial 17
with zero resources. Historical versions show a prior installation and staged
teardown, but the current state does not bind any protected resource.

Read-only checks against historical IDs found no current matches for the
recorded Cognito pools/clients, health CloudFront distribution or OAC. The
historical Cognito domain response was not sufficient to establish a live pool
relationship. No ACM certificate or Route 53 record is represented as a
Terraform resource in the retained state history.

Accordingly, all current ownership fields below are `UNKNOWN`, not inferred
from names:

| Resource | ID/ARN evidence | Account/region | Ownership | Allowed change |
|---|---|---|---|---|
| Jobsearch domain | no authoritative current ID | UNKNOWN | UNKNOWN | none |
| Jobsearch CloudFront | no authoritative current ID | UNKNOWN | UNKNOWN | none |
| Cognito pool | historical IDs not live | `262370457690`/`eu-central-1` historical only | UNKNOWN | none |
| Cognito clients | historical IDs not live | historical only | UNKNOWN | none |
| Cognito domain/OAuth | historical domain evidence incomplete | historical only | UNKNOWN | none |
| Users/auth contracts | no current pool binding | UNKNOWN | UNKNOWN | none |
| DNS/ACM/TLS | no Terraform-owned references | UNKNOWN | UNKNOWN | none |
| CloudFront OAC | historical ID not live | historical only | UNKNOWN | none |

## Recovery requirement

No Terraform plan may run until each protected resource has one current ID/ARN,
one owner, one evidence source and one approved Terraform ownership decision.
The evidence must include live descriptions and the state association, not just
historical names or reports.

An empty state must not be repaired by restoring an S3 object version, importing
by name, deleting locks, or creating a new resource family under `ris-dev2`.
