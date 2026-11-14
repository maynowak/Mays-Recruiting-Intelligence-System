> **RIS documentation copy.** The Jobsearch text/display implementation was
> performed in `maynowak/mays-jobsearch`; this copy records the RIS scoped
> pilot, mapping, tests and the exact RIS-DEV E2E prerequisites. No apply,
> deployment, env or notice-state change was performed.

# JM-RIS-STORAGE-PILOT-03-REPORT

## Result

`APPLICATION STORAGE READY FOR RIS-DEV E2E`

**Status detail:** the implementation, text, mapping, scoped activation and
local tests are ready. The first real RIS-DEV E2E has **not** been executed.
It still requires the operator/legal approval of the text and notice, a reviewed
RIS-DEV deployment with the new Lambda bundle and pilot allowlist, and the
Jobsearch preview configuration. No push, merge, deployment, Terraform apply,
live Lambda env change, production Vercel change, or notice approval was
performed.

## 1. Baseline

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Branch | `feature/jm-ris-storage-activation-01` | `feature/jm-ris-storage-activation-01` |
| Start head | `5daa99a` | `8e6578b` |
| New implementation | `2b4b520`, `115ea57` | `37503a9` |
| Auditlog commits | `ef370d0` | `50b18f5` |
| Main branch | unchanged | unchanged |
| Push/merge/deploy | none | none |

The existing privacy policy v1.1 was not changed. No new persistence
architecture and no new RIS workspace were created.

## 2. Actual RIS-DEV configuration

Read-only checks used the required `mayaws` profile. No secrets were read or
printed.

| Item | Observed value |
| --- | --- |
| AWS account | `240571105849` (`arn:aws:iam::240571105849:user/Mayaws`) |
| RIS-DEV Lambda | `ris-dev-dev-agent`, Active |
| `CONSENTS_TABLE` | `ris-dev-dev-consents` |
| `APPLICATION_CONSENT_ENFORCED` | `false` |
| `PARTNER_SURFACE_ENABLED` | `true` |
| `CONSENT_NOTICE_STATE_ENFORCED` | absent in the deployed Lambda env |
| Partner edge API | `c7e9pdwe78` = `ris-dev-jobsearch-api` |
| Kernel API | `g6901and25` = `ris-dev-dev-api` |
| Jobsearch edge | same RIS-DEV runtime can serve the Jobsearch partner edge |

The Jobsearch partner edge and other RIS-DEV clients must not be globally
switched. The pilot therefore uses a scoped identity allowlist, not a global
gate flip.

## 3. Complete ApplicationV1 consent text

**Text version:** `application-storage-consent-2026-11-07-v1`

**SHA-256:** `2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953`

**State:** `DRAFT` candidate; not approved. The operator/legal reviewer must
approve this exact text before `RIS_CONSENT_TEXT_STATE=APPROVED` and a RIS
notice approval may be used.

The exact canonical text (`paragraphs.join("\n\n")`) is:

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

The text invents no legal basis, retention period, recipient/transfer
statement, or approval claim. Art. 9 assessment for free-text cover letters,
notes and contact data remains an open legal decision.

## 4. Version mapping and lifecycle

| Field | Value |
| --- | --- |
| RIS purpose | `application-storage` |
| RIS notice version | `1.0` |
| RIS notice state | `DRAFT` |
| `legalApprovalRef` | `null` |
| Jobsearch text version | `application-storage-consent-2026-11-07-v1` |
| Jobsearch text SHA-256 | `2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953` |
| Jobsearch text state | `DRAFT` candidate |
| Proposed mapping | text ↔ RIS `1.0`; **requires operator approval** |
| RIS external ref | known as `mays-jobsearch` draft, `noticeVersion: null`, hash pinned |

RIS does not accept the Jobsearch text identifier as a `noticeVersion`. The
external reference is visible in the partner catalogue but remains
non-equivalent until a documented operator decision sets the legal approval
reference and the mapping.

## 5. Technical changes

### Jobsearch

Commit `2b4b520`:

- new `src/lib/applicationStorageConsent.ts` with the complete text, canonical
  version, paragraphs, and SHA-256;
- new `api/_lib/ris/consentText.mjs` with the server-side text identity;
- `risConsentConfig` reads `RIS_CONSENT_TEXT_VERSION`,
  `RIS_CONSENT_TEXT_SHA256`, `RIS_CONSENT_TEXT_STATE`;
- GET returns `textVersion`, `textHash`, `textState`, `textMapped`,
  `textApproved`, `textReason`;
- `grantAllowed` requires the approved notice **and** the approved text
  mapping; POST grant re-checks both before writing;
- `StorageConsentLive` renders the full declaration before the button, shows
  version/SHA-256/status, and blocks the button unless the server mapping
  matches and is approved.

Commit `115ea57`:

- the server text state is the authoritative displayed status;
- the client constant is only labelled as a text candidate when the server has
  not approved it;
- no contradictory `DRAFT` label remains when the server reports `APPROVED`.

### RIS

Commit `37503a9`:

- new `CONSENT_PILOT_ALLOWLIST` (`<issuer>|<sub>`, comma/newline separated);
  empty/unset/malformed = no pilot identity;
- effective write gate = global `APPLICATION_CONSENT_ENFORCED=true` **or**
  pilot identity;
- effective notice gate = global `CONSENT_NOTICE_STATE_ENFORCED=true` **or**
  pilot identity;
- `ConsentRepository.grant(..., enforce_notice_state=...)` applies state
  enforcement only to new/regranted grants; idempotent repeats and withdrawal
  keep their behavior;
- Terraform root/module variable `consent_pilot_allowlist` default `""`, env
  `CONSENT_PILOT_ALLOWLIST`; all other gates stay default false/empty;
- `EXTERNAL_NOTICE_REFS` registers the Jobsearch text version/hash as a known
  DRAFT reference with `noticeVersion: None`;
- mapping document:
  `docs/reports/APPLICATION-STORAGE-1.0-NOTICE-MAPPING.md`.

The existing `ris-dev` Lambda and partner edge are **not** modified by this
task. The scoped activation only affects an explicitly listed synthetic
identity after a separate deployment/GO.

## 6. Tests

### Jobsearch

Final focused tests:

```text
npx vitest run tests/api/ris-consents.test.mjs tests/api/ris-routing.test.mjs tests/api/ris-config-separation.test.mjs
→ 3 files passed, 55/55 tests

npx vitest run src/components/StorageConsentLive.test.tsx src/lib/storageConsent.test.ts
→ 2 files passed, 14/14 tests

npm run build
→ PASS

node --check api/**/*.mjs
→ PASS

git diff --check
→ PASS
```

Full suite:

```text
run 1: 1572 passed, 2 failed, 5 skipped (2 transient ManualSearchProfiles failures)
isolated ManualSearchProfiles: 8/8 PASS
run 2: 1574 passed, 5 skipped (152 files)
```

The two transient failures are not in the consent/application code; the
integration file passes isolated. The second full run is clean.

### RIS

```text
PYTHONPATH=/tmp/opencode/pydeps python3 -m pytest \
  tests/test_consent_pilot_allowlist.py \
  tests/test_consent_active_notice_pilot.py \
  tests/test_consent_notice_catalog_contract.py \
  tests/test_consent_notice_state_enforcement_terraform.py \
  tests/test_consent_e2e_joint.py tests/test_consent_gate.py -q
→ 69 passed

wider scoped/contract set
→ 84 passed / 124 passed
```

Terraform:

```text
terraform fmt -check -recursive → PASS
terraform init -backend=false + validate (temporary copy) → Success
27 pre-existing hash_key warnings only
```

No plan, apply, deployment or AWS mutation.

## 7. Agent sessions and reviews

| Step | Agent | Session | Result |
| --- | --- | --- | --- |
| Jobsearch consent text/display | Jobsearch | `ses_e49a66ef3ffeCeeSQhQhNwNnqs` | `2b4b520`, `115ea57` |
| RIS scoped pilot/mapping | RIS | `ses_e49a08eb7ffe8RltsM98S9VTQq` | `37503a9` |
| RIS reviews Jobsearch | RIS | same RIS session | **PASS** |
| Jobsearch reviews RIS | Jobsearch | same Jobsearch session | **PASS** |
| Auditlog entries | both agents | same sessions | `ef370d0` / `50b18f5` |

Cross-review confirmed:

- Jobsearch text is complete, versioned, hashed, and contains no invented legal
  approval or retention period.
- Jobsearch BFF fails closed on missing/mismatched/`DRAFT` text or notice.
- RIS scoped allowlist gates only the listed synthetic identity; non-pilot
  identities keep global behavior.
- RIS mapping remains DRAFT and non-equivalent; no `legalApprovalRef` invented.
- No unauthorized env, secret, Terraform apply, deployment or push.

## 8. Impact on the existing partner edge

- `APPLICATION_CONSENT_ENFORCED` stays `false`.
- `CONSENT_NOTICE_STATE_ENFORCED` stays `false`.
- `PARTNER_SURFACE_ENABLED` stays `true`, unchanged.
- Only a matching `CONSENT_PILOT_ALLOWLIST` identity gets the effective gates.
- Non-listed identities keep the pre-existing behavior exactly.
- The RIS-DEV Lambda env, partner edge, Cognito, CloudFront, DNS, ACM and
  Terraform state are not changed by this task.

The allowlist is identity-scoped (`issuer|sub`), not partner/tenant-scoped. It
must contain only a dedicated synthetic test identity, never a real user.

## 9. Required operator/legal decisions

1. Approve the exact text version/hash above.
2. Provide the real `legalApprovalRef` (record ID, owner, date, approving body).
3. Set RIS `application-storage/1.0` to `APPROVED` or `ACTIVE` with that ref.
4. Complete the Art. 9 assessment for free-text cover letters, notes and
   contact data.
5. Confirm controller/processor roles, recipients/transfers and the
   ApplicationV1 retention/erasure rule.
6. Approve the synthetic test identity and the matching allowlist values.
7. Approve the RIS-DEV Lambda bundle/deployment and the `CONSENT_PILOT_ALLOWLIST`
   env change (separate plan/apply GO).
8. Approve the Jobsearch preview env and the preview URL/test audience.

## 10. Exact first RIS-DEV E2E flow (after separate GO)

1. Operator approves the text/hash and RIS notice `1.0`; sets
   `legalApprovalRef` and `APPROVED`/`ACTIVE`; rebuilds the Lambda bundle.
2. RIS-DEV plan/apply sets:
   - `CONSENT_PILOT_ALLOWLIST=<issuer>|<synthetic sub>`
   - `APPLICATION_CONSENT_ENFORCED=false`
   - `CONSENT_NOTICE_STATE_ENFORCED=false`
   - `PARTNER_SURFACE_ENABLED=true`
   - notice `application-storage/1.0` approved/active with legal ref.
3. Jobsearch preview env sets:
   - `RIS_API_BASE_URL`, `RIS_PARTNER_CREDENTIAL` (secret, name only),
     `RIS_COGNITO_ISSUER`, `RIS_COGNITO_CLIENT_ID`;
   - `RIS_CONSENT_SERVICE_ENABLED=true`, `RIS_APPLICATION_STORAGE_ENABLED=true`;
   - `RIS_CONSENT_NOTICE_VERSION=1.0`;
   - `RIS_CONSENT_TEXT_VERSION=application-storage-consent-2026-11-07-v1`;
   - `RIS_CONSENT_TEXT_SHA256=2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953`;
   - `RIS_CONSENT_TEXT_STATE=APPROVED` only after text approval;
   - `RIS_TEST_USER_ALLOWLIST=<issuer>|<synthetic sub>` (must equal RIS
     `CONSENT_PILOT_ALLOWLIST`);
   - `VITE_RIS_CONSENT_UI_ENABLED=true`,
     `VITE_RIS_APPLICATION_STORAGE_ENABLED=true` (preview only).
4. Login as the synthetic test user.
5. Open the consent UI; verify the full text, version, SHA-256 and privacy link
   are shown.
6. Verify a non-allowlisted identity receives `403`, with no RIS write.
7. Grant `application-storage/1.0`; verify `GRANTED`.
8. Create a synthetic application; require a RIS `applicationId` and `ownerId`;
   the UI must not show a local-only success.
9. Reload the browser; the application must still be present.
10. Logout/login; the application must still be present.
11. Update it; verify the version increments.
12. Export it; verify the exported application contains the record.
13. Withdraw consent.
14. Attempt a new write; require `403 CONSENT_REQUIRED`.
15. Read and export the existing application; it must remain available.
16. Delete it; verify it is no longer retrievable.
17. Remove synthetic consent/test-user data; record counts, IDs, timestamps,
    HTTP statuses and deployment IDs.
18. Keep global gates false; the scoped allowlist remains the only pilot
    activation.

A mock test is not accepted as live persistence evidence. The live E2E is not
run in this task.

## 11. Rollback

1. Remove the preview `VITE_RIS_APPLICATION_STORAGE_ENABLED` or set it `false`;
   the UI returns to session mode.
2. Set/keep `CONSENT_PILOT_ALLOWLIST` empty, or revert the RIS-DEV deployment
   to the previous known-good Lambda; do not flip global flags.
3. If the text/notice approval is withdrawn, restore notice `1.0` to `DRAFT`;
   existing grants remain valid, new grants blocked.
4. Keep pilot data for export/delete; delete only synthetic rows.
5. Revert the Jobsearch preview to the previous known-good image.
6. Remove only the synthetic test identity/rows; do not touch production users
   or the shared partner edge.

## 12. Final status

`APPLICATION STORAGE READY FOR RIS-DEV E2E`

**Pending:** operator/legal text and notice approval, RIS-DEV bundle/deployment
with `CONSENT_PILOT_ALLOWLIST`, Jobsearch preview env, and the separate live
E2E GO.

No live persistence was claimed or executed. No production activation occurred.
