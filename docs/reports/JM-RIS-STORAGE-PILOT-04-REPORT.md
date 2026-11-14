> **RIS documentation copy.** Read-only preflight and approval-packet update.
> No plan/apply, deployment, env, notice-state or live write was performed.

# JM-RIS-STORAGE-PILOT-04-REPORT

## Result

`CONSENT TEXT READY FOR OPERATOR REVIEW`

`RIS-DEV DEPLOYMENT PREFLIGHT READY`

No live activation, no Terraform plan/apply, no RIS/Vercel deployment, no
production flag change, no notice-state change, and no live write test was
performed.

## 1. Baseline

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Branch | `feature/jm-ris-storage-activation-01` | `feature/jm-ris-storage-activation-01` |
| Current head | `26e6edd` | `23c4890` |
| Consent code | `2b4b520`, `115ea57` | `37503a9` |
| Auditlog | `ef370d0`, `26e6edd` | `50b18f5`, `7032e82`, `23c4890` |

The privacy policy v1.1 remains unchanged. No new persistence or pilot
infrastructure was created.

## 2. Complete consent text

**Text version:** `application-storage-consent-2026-11-07-v1`

**SHA-256:** `2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953`

**State:** `DRAFT` candidate; not approved. No `legalApprovalRef`.

**RIS notice:** `application-storage/1.0`, currently `DRAFT`.

**Mapping:** proposed text ↔ RIS `1.0`; **none approved**.

Exact canonical text (`paragraphs.join("\n\n")`):

> Ich willige ein, dass der RIS-Speicherdienst meine Bewerbungsdaten im nachfolgend beschriebenen Umfang dauerhaft speichert, damit ich sie später abrufen, bearbeiten, exportieren und löschen kann. Diese Einwilligung gilt ergänzend zu den Datenschutzhinweisen unter /datenschutz (Datenschutzrichtlinie Version 1.1 vom 7. November 2026) und ersetzt diese nicht.
>
> Gespeichert werden: meine Bewerbungen mit Stellenbezug (jobId, Titel, Unternehmen, Ort, Quelle und URL), meine Anschreiben und Anschreiben-Versionen, der Dokumentstatus, Verweise auf ausgewählte CV- und Suchprofile sowie Bewerbungsdatum und -kanal, Kontaktangaben, Notizen, Gehaltsvorstellung und -angebot, Wiedervorlagen und Verlaufsereignisse (Feedback, Interview, Notizen).
>
> Nicht gespeichert werden durch diese Einwilligung: PDF-Dateien, im Browser ausgelesene CV-Texte, KI-Prompts oder Provider-Nutzlasten. Verweise auf CV- und Suchprofile verweisen nur auf die jeweilige Ressource und enthalten keine Dokumentkopie.
>
> Der Zweck der Speicherung ist ausschließlich der spätere Abruf, die Änderung, der Export und die Löschung der ausgewählten Bewerbungsdaten durch mich.
>
> RIS ist der Speicherdienst; die Daten liegen in der bestehenden RIS-/AWS-Infrastruktur. Diese Einwilligung betrifft keine KI-Analyse und keine Übermittlung an KI- oder sonstige Provider. Eine Einwilligung in eine KI-Verarbeitung ist nicht Teil dieser Erklärung und wird durch sie nicht erteilt.
>
> Mit dieser Einwilligung wird die dauerhafte Speicherung der genannten Daten für mein angemeldetes Konto freigeschaltet. Ohne diese Einwilligung bleiben die abhängigen Speicherfunktionen gesperrt.
>
> Ich kann diese Einwilligung jederzeit mit Wirkung für die Zukunft widerrufen. Der Widerruf blockiert neue abhängige Schreibzugriffe. Bereits gespeicherte Daten bleiben im Rahmen der bestehenden Rechte lesbar, exportierbar und löschbar; der Widerruf ist nicht automatisch eine sofortige physische Löschung.
>
> Für ApplicationV1 ist derzeit keine pauschale Aufbewahrungsfrist freigegeben. Gespeicherte Bewerbungen bleiben bestehen, bis ich sie lösche. Sicherungen, Protokolle und gesetzliche Aufbewahrungspflichten können eine Löschung verzögern oder begrenzen.

### Comparison with ApplicationV1 fields

| Text phrase | ApplicationV1 field |
| --- | --- |
| Bewerbungen mit Stellenbezug | `job.jobId/title/companyName/location/source/originalUrl` |
| Anschreiben / Anschreiben-Versionen | `documents.coverLetterDraft`, `documents.coverLetterVersions` |
| Dokumentstatus | `documents.documentStatus` |
| CV-/Suchprofil-Verweise | `documents.cvReference`, `profileRef`, `cvRef` |
| Bewerbungsdatum/-kanal | `applicationDate`, `applicationChannel` |
| Kontaktangaben | `contact` |
| Notizen | `notes`, `history` notes |
| Gehaltsvorstellung/-angebot | `salary` |
| Wiedervorlagen | `followUp` |
| Verlaufsereignisse | `history` |
| Status/Statusverlauf | covered by "meine Bewerbungen" / "Verlaufsereignisse"; explicit naming is a wording decision for the operator |

The text does **not** claim that PDFs, raw CV text, AI prompts or provider
payloads are stored. Those are not part of ApplicationV1.

### Updated approval packet

`docs/reports/APPLICATION-STORAGE-1.0-APPROVAL-PACKET.md` was updated with:

- Candidate D (this complete text, version, hash, DRAFT state);
- the field-mapping table above;
- the corrected finding: a complete candidate exists, but no approval,
  `legalApprovalRef`, or RIS `1.0` mapping exists;
- updated baselines and unchanged open legal decisions.

Programmatic check: all 8 paragraphs match the source file verbatim.

## 3. RIS-DEV preflight (read-only, `AWS_PROFILE=mayaws`)

Account: `240571105849` (`arn:aws:iam::240571105849:user/Mayaws`).

### Lambda

| Item | Value |
| --- | --- |
| Function | `ris-dev-dev-agent` |
| State | Active |
| LastModified | `2026-11-06T17:57:25Z` |
| CodeSha256 | `783PJahGgBAGcS3cbwd7SNhc5o5RQNKplp9/RAxEEio=` |
| `APPLICATIONS_TABLE` | `ris-dev-dev-applications` |
| `CONSENTS_TABLE` | `ris-dev-dev-consents` |
| `APPLICATION_CONSENT_ENFORCED` | `false` |
| `PARTNER_SURFACE_ENABLED` | `true` |
| `CONSENT_NOTICE_STATE_ENFORCED` | absent |
| `CONSENT_PILOT_ALLOWLIST` | absent |

The new code (`37503a9`) and the scoped allowlist are **not deployed**.

### API Gateway / partner edge

| Item | Value |
| --- | --- |
| Partner edge | `c7e9pdwe78` = `ris-dev-jobsearch-api` |
| Kernel API | `g6901and25` = `ris-dev-dev-api` |
| Partner integration | `ardaws:lambda:...:function:ris-dev-dev-agent` (same Lambda) |
| Kernel integration | same `ris-dev-dev-agent` plus orders reader |
| Stage | `$default`, AutoDeploy true |
| CORS origins | `www.mays-job-matcher.app`, `mays-job-matcher.vercel.app`, localhost |
| Consent routes | present on partner edge (GET/POST/withdraw/history) |
| Application routes | present on partner edge (list/get/create/patch/status/history/cover-letter/export/delete/metrics) |

The partner edge and kernel API share the same RIS-DEV Lambda. A global gate
change would affect both; the scoped allowlist is therefore mandatory.

### Tables

| Table | Status | TTL |
| --- | --- | --- |
| `ris-dev-dev-consents` | ACTIVE | DISABLED |
| `ris-dev-dev-applications` | ACTIVE | ENABLED on `expiresAt` |

The application repository does not write `expiresAt`; there is no automatic
application expiry. The consent table has no TTL.

Reported `ItemCount` was 0 for both tables (not a strong consistency proof, but
no test data was added).

### Partner configuration

| Row | Status |
| --- | --- |
| `applicationId=mays-jobsearch`, `tenantId=mays-jobsearch` | ACTIVE |
| reserved client for Jobsearch pool `5hb3...` | RESERVED |
| `ris-dev-e2e-20261105` | INACTIVE |
| another reserved client | RESERVED |

No secret values were printed.

### Terraform state

| Item | Value |
| --- | --- |
| Backend object | `s3://mays-ris-tf-state-dev/env:/ris-dev/dev/terraform.tfstate` |
| VersionId | `wVw.GTLeSJ6IN7WXS02qrQSU2xiguw8x` |
| Serial / lineage | `42` / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Resource count | 249 |
| Lambda | 6 |
| API Gateway | 3 |
| API routes | 79 |
| DynamoDB tables | 20 |
| Cognito pools / clients | 2 / 3 |
| CloudFront distributions | 1 |
| Route53 records / ACM certs | 0 / 0 |

The state contains the existing `ris-dev-dev-agent`, `ris-dev-jobsearch-api`,
both consent/application tables and the existing Cognito/CloudFront resources.
No state mutation, plan or apply was performed.

### Bundle preflight

Deterministic build:

```text
agent bundle: terraform/lambda.zip
  sha256 a18f6abb87379d6f05f46e9ceedc64416e226e93f3f9e764ab14ec88f1205255
  83 files, 281295 bytes

reader bundle: lambda/dist/orders-reader.zip
  sha256 e405858718101db34a8d5c1237e36d41a47b7dceb8e0ebff8b01bd86d1c366e5
  1 file, 4321 bytes
```

A second build produced the same hashes. Bundles are gitignored and were not
committed.

## 4. Deployment impact analysis

### Shared Lambda

`ris-dev-dev-agent` is the integration target for both:

- `ris-dev-jobsearch-api` (`c7e9pdwe78`) — partner edge with production Jobsearch
  CORS origins and `mays-jobsearch` partner registry row; and
- `ris-dev-dev-api` — kernel API.

Therefore any deployment changes the runtime for both surfaces. The new code
keeps global gates false and applies additional gates only to identities in
`CONSENT_PILOT_ALLOWLIST`. Non-pilot identities keep the previous behavior.

### Is the pilot sufficiently isolated?

**Conditionally yes, after a reviewed deployment and exact allowlist.** The
code enforces:

- global `APPLICATION_CONSENT_ENFORCED=false` **or** exact
  `issuer|sub` pilot match for write gating;
- global `CONSENT_NOTICE_STATE_ENFORCED=false` **or** exact pilot match for new
  grant notice enforcement;
- empty/unset/malformed allowlist = no pilot identity;
- exact issuer + sub matching, no wildcard;
- non-listed identities unchanged.

**Technical gap before live E2E:** the deployed Lambda has neither the new code
nor `CONSENT_PILOT_ALLOWLIST`. A reviewed deployment/bundle and env update are
required. The test identity must be dedicated and identical in
`RIS_TEST_USER_ALLOWLIST` (Jobsearch) and `CONSENT_PILOT_ALLOWLIST` (RIS).

### Protected resources

The local change adds only:

- Terraform variables `consent_notice_state_enforced` and
  `consent_pilot_allowlist` (default false/empty);
- Lambda env entries `CONSENT_NOTICE_STATE_ENFORCED` and
  `CONSENT_PILOT_ALLOWLIST`.

No Cognito, CloudFront, DNS, ACM, API Gateway route, table, or S3 resource
change is part of the local diff. A Terraform plan is not authorized in this
task, so **0 replacements/updates outside the Lambda env must still be confirmed
by the separate plan review**.

## 5. Activation order (after separate approvals)

1. Operator/legal approval of the complete text and hash.
2. Set a real `legalApprovalRef`; approve the text mapping.
3. Set RIS `application-storage/1.0` to `APPROVED` or `ACTIVE`; update the
   external ref mapping only after the documented decision.
4. Build the deterministic Lambda bundle; create a new Terraform plan.
5. Review plan: Lambda code/env update only; 0 Cognito/CloudFront/DNS/ACM/
   table/API replacements; protected resources unchanged.
6. Apply RIS-DEV plan with:
   - `CONSENT_PILOT_ALLOWLIST=<issuer>|<synthetic sub>`
   - `APPLICATION_CONSENT_ENFORCED=false`
   - `CONSENT_NOTICE_STATE_ENFORCED=false`
   - `PARTNER_SURFACE_ENABLED=true`.
7. Deploy/configure the Jobsearch preview with:
   - RIS base URL/credential/issuer/client;
   - `RIS_APPLICATION_STORAGE_ENABLED=true`,
     `RIS_CONSENT_SERVICE_ENABLED=true`;
   - `RIS_CONSENT_NOTICE_VERSION=1.0`;
   - `RIS_CONSENT_TEXT_VERSION=application-storage-consent-2026-11-07-v1`;
   - `RIS_CONSENT_TEXT_SHA256=2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953`;
   - `RIS_CONSENT_TEXT_STATE=APPROVED` only after text approval;
   - matching `RIS_TEST_USER_ALLOWLIST`;
   - `VITE_RIS_CONSENT_UI_ENABLED=true`,
     `VITE_RIS_APPLICATION_STORAGE_ENABLED=true` (preview only).
8. Verify non-allowlisted identity → 403; production flags untouched.
9. Login as synthetic user; load/show full text, version, hash.
10. Grant; create synthetic application; require RIS `applicationId`/`ownerId`.
11. Reload; application still present.
12. Logout/login; application still present.
13. Update; version increments.
14. Export; verify content.
15. Withdraw; new write → 403 `CONSENT_REQUIRED`.
16. Read/export/delete still available.
17. Delete; verify not retrievable.
18. Clean synthetic rows/user; record evidence and deployment IDs.

## 6. Next approvals required

1. **Text/legal:** approve the exact text/version/hash; provide
   `legalApprovalRef`; decide the explicit status/statusHistory wording.
2. **Privacy:** Art. 9 assessment for free-text cover letters/notes/contact;
   controller/processor roles; recipients/transfers; ApplicationV1 retention
   and erasure.
3. **RIS-DEV plan/apply:** reviewed plan for the Lambda bundle/env update and
   `CONSENT_PILOT_ALLOWLIST`; no global flags.
4. **Jobsearch preview:** approved preview env, test audience, and preview
   deployment.
5. **Test identity:** dedicated synthetic `<issuer>|<sub>` used in both
   allowlists.
6. **Live E2E:** separate GO; no real applicant data.

## 7. Status

`CONSENT TEXT READY FOR OPERATOR REVIEW`

`RIS-DEV DEPLOYMENT PREFLIGHT READY`

No live activation without explicit GO.
