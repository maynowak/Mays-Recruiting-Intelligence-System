> **RIS documentation copy.** Operator-account production decision update.
> No plan/apply, deployment, env, notice or data mutation was performed.

# JM-RIS-STORAGE-ONE-SHOT-05-REPORT

## Result

`BLOCKED`

**Operator decision update:** the target is the existing
`www.mays-job-matcher.app` production website and the existing operator
account. No new Cognito test account will be created. A copied local browser
profile had no active session (only the language preference); therefore the
verified operator `iss`/`sub` is still unavailable. The operator must log in
through the regular production login or provide the verified identity.

**Blockers:**

1. **No operator/legal approval and no real `legalApprovalRef`** for the
   ApplicationV1 consent text. The text is a candidate; notice `1.0` remains
   `DRAFT`. No agent may approve it.
2. **No verified operator identity** (`iss`/`sub`) for
   `RIS_TEST_USER_ALLOWLIST` and `CONSENT_PILOT_ALLOWLIST`. The copied browser
   profile was not logged in; no new Cognito user may be created under the
   corrected decision.
3. **No final saved Terraform plan** can be produced without that identity.
4. **No bundled operator GO** `GO JM-RIS-STORAGE-ONE-SHOT-05 APPLY + DEPLOY + E2E`.

No Terraform plan/apply, deployment, Vercel change, notice change, Cognito
mutation, push or merge was performed. No live write test was executed.

## 1. Completed local work

| Item | Value |
| --- | --- |
| Jobsearch branch | `feature/jm-ris-storage-activation-01` |
| Jobsearch head | `47f73c4` |
| RIS branch | `feature/jm-ris-storage-activation-01` |
| RIS head | `aefae0f` |
| Consent text version | `application-storage-consent-2026-11-07-v2` |
| Consent text SHA-256 | `232cc8206261b5d14f7a269f63a58320f76eea435a65f7e039b25c62d26da0ca` |
| RIS notice | `application-storage/1.0`, `DRAFT`, `legalApprovalRef=null` |
| Mapping | v2 ↔ RIS `1.0`: proposed, **none approved** |

The v2 text now explicitly includes:

- Bewerbungsstatus
- Statusänderungen
- Statusverlauf

All other statements remain unchanged. The old v1 text/hash is retained only as
historical/superseded and must not be configured.

### Tests completed

```text
Jobsearch: 15/15 UI/text, 44/44 BFF/config, build PASS, diff-check PASS
RIS:       56/56 focused consent/mapping/terraform tests, fmt PASS
```

The full text is in:

- `src/lib/applicationStorageConsent.ts`
- `docs/reports/APPLICATION-STORAGE-1.0-APPROVAL-PACKET.md` (Candidate D v2)

## 2. RIS-DEV preflight (already verified read-only)

- Account `240571105849` via `AWS_PROFILE=mayaws`.
- Lambda `ris-dev-dev-agent`, Active.
- `APPLICATIONS_TABLE=ris-dev-dev-applications`.
- `CONSENTS_TABLE=ris-dev-dev-consents`.
- `APPLICATION_CONSENT_ENFORCED=false`.
- `PARTNER_SURFACE_ENABLED=true`.
- `CONSENT_NOTICE_STATE_ENFORCED` absent.
- `CONSENT_PILOT_ALLOWLIST` absent.
- Partner edge `c7e9pdwe78` (`ris-dev-jobsearch-api`) and kernel `g6901and25`
  both target the same Lambda.
- Consent table TTL disabled; Applications TTL enabled on `expiresAt`, but the
  repository does not write it.
- Terraform state serial 42, 249 resources; no state mutation.
- Bundle hashes: agent `a18f6abb87379d6f05f46e9ceedc64416e226e93f3f9e764ab14ec88f1205255`,
  reader `e405858718101db34a8d5c1237e36d41a47b7dceb8e0ebff8b01bd86d1c366e5`.
- Existing Cognito/CloudFront/API/table resources are present; only a separate
  plan can prove no replacement. No plan was created because the allowlist
  identity is missing.

## 3. Exactly required to unblock

### A. Operator/legal approval

The operator/legal reviewer must explicitly confirm:

- the full v2 text and SHA-256;
- purpose `application-storage` and RIS notice `1.0`;
- actual retention/erasure rules;
- Art. 9 assessment for free-text cover letters/notes/contact;
- controller/processor roles, recipients/transfers;
- a real `legalApprovalRef` (record ID, owner, date, approving body).

Then the notice must become `APPROVED`/`ACTIVE` with that reference. No agent
may set it.

### B. Verified operator identity

Use the existing operator account. The operator must log in through the
regular production login and provide the verified `issuer` + `sub` (no email as
identity, no password/token disclosure), or allow the Commander to read the
`iss`/`sub` from that logged-in browser session.

The same exact `<issuer>|<sub>` must be configured in:

- Jobsearch `RIS_TEST_USER_ALLOWLIST`
- RIS `CONSENT_PILOT_ALLOWLIST`.

No new Cognito test user and no real third-party identity may be used. The
final plan cannot be generated with a placeholder.

### C. Final bundled GO

After the plan is generated and reviewed, the exact string is required:

```text
GO JM-RIS-STORAGE-ONE-SHOT-05 APPLY + DEPLOY + E2E
```

## 4. Execution sequence after unblock

1. Approve v2 text and set `legalApprovalRef`; notice `1.0` → `APPROVED`/`ACTIVE`.
2. Verify the existing operator account; record its exact issuer + sub.
3. Build deterministic Lambda bundle; create saved Terraform plan with
   `CONSENT_PILOT_ALLOWLIST=<issuer>|<sub>`.
4. Present exact plan (resource list, change count, plan hash) and bundled GO.
5. Apply the saved plan; verify Lambda code hash/status and unchanged partner
   edge.
6. Configure Jobsearch preview with v2 text/hash/state and test allowlist.
7. Run E2E: login, full text, grant, create, reload, logout/login, update,
   export, withdraw, `403 CONSENT_REQUIRED`, read/export/delete, cleanup.
8. Only after E2E: Jobsearch PR/merge and production deployment, with production
   flags restricted to the approved test audience; no general rollout.
9. Production verification and rollback if needed.

## 5. Safety state

- Notice `application-storage/1.0`: `DRAFT`.
- `APPLICATION_CONSENT_ENFORCED=false`.
- `CONSENT_NOTICE_STATE_ENFORCED` not live.
- `CONSENT_PILOT_ALLOWLIST` not live.
- No live Cognito, Vercel, Lambda, Terraform or data mutation.
- No push/merge/deploy/apply.
- No live persistence claim.

## 6. Final status

`BLOCKED — OPERATOR/LEGAL TEXT APPROVAL, LEGAL APPROVAL REFERENCE, AND VERIFIED OPERATOR IDENTITY REQUIRED`
