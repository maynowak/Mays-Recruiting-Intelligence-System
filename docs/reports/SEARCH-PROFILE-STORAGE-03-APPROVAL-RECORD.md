# SEARCH-PROFILE-STORAGE-03 — Notice Approval Record

**Status:** `NOTICE APPROVED FOR LIMITED PILOT — NOT YET DEPLOYED`  
**Approval date:** `2026-11-08`  
**Approving body:** Betreiberin May’s Job Matcher

## 1. Approval evidence

The operator confirmed the final text and the separate notice with:

```text
CONFIRM SEARCH-PROFILE-TEXT v2
75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6
CONFIRM PRIVACY-POLICY v1.2

APPROVE NOTICE search-profile-storage/1.0
Ref: JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08
Date: <tatsächliches Freigabedatum>
Body: <tatsächliche Freigabestelle>

GO NOTICE APPROVAL
```

The date and body placeholders were completed from the confirmation date and
the existing operator identity used in the prior approved limited-pilot record
(`JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`): **2026-11-08** /
**Betreiberin May’s Job Matcher**. No earlier date was chosen and no third-party
approval body was invented.

## 2. Approved object

| Field | Value |
| --- | --- |
| Purpose | `search-profile-storage` |
| RIS notice | `search-profile-storage/1.0` |
| Notice state | **`APPROVED`** |
| `legalApprovalRef` | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` |
| Consent text | `search-profile-storage-consent-2026-11-08-v2` |
| SHA-256 | `75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6` |
| Privacy policy | v1.2, 2026-11-08 |
| Scope | limited synthetic/operator pilot; no general rollout |

## 3. What the approval does not mean

- No general user enablement.
- No production deployment by itself.
- No apply of a Terraform plan.
- No erasure redesign for P3.
- No change to ApplicationV1 or CV-storage notices.

## 4. Apply gate

The new plan after the notice change is:

```text
/tmp/opencode/ris-dev-search-profile-04.tfplan
SHA-256: d6cfcda99a73dacf6ed44f111c42f719f8c401dcea6d7edb82caf9bfd1e2576a
State serial: 46
Changes: 0 CREATE / 1 UPDATE / 0 DELETE / 0 REPLACE
Only change: module.lambda.aws_lambda_function.agent
```

A separate explicit **GO APPLY** for this exact hash is still required. No
apply or deployment was performed.
