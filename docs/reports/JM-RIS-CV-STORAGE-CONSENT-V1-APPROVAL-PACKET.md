# JM-RIS-CV-STORAGE-INTEGRATION-01 — CV Consent v1 Approval Packet

## Status

`AWAITING OPERATOR APPROVAL OF THE FINAL CV CONSENT TEXT`

No new text version was created. No Terraform apply, AWS mutation, push,
merge or production deployment was performed.

## 1. Exact text

| Field | Value |
| --- | --- |
| Version | `cv-storage-consent-2026-11-08-v1` |
| SHA-256 | `2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036` |
| RIS notice | `cv-storage/1.0` |
| Current notice state | `DRAFT` |
| Current `legalApprovalRef` | `null` |
| Privacy policy reference | `/datenschutz`, version `1.1`, 2026-11-07 |
| Purpose | `cv-storage` (separate from `application-storage`) |

Canonical text (paragraphs joined by a blank line; this is the exact text
hashed above):

Ich willige ein, dass der RIS-Speicherdienst meinen hochgeladenen Lebenslauf als PDF-Datei sowie die zugehörigen Dokumentmetadaten (Dateiname, Dateigröße, Inhaltstyp, Prüfsumme, Speicherstatus) dauerhaft in meinem angemeldeten Konto speichert, damit ich ihn später abrufen, herunterladen, für Bewerbungen auswählen und löschen kann.

Die Datei wird verschlüsselt in der bestehenden RIS-/AWS-Infrastruktur gespeichert. Die Speicherung erfolgt getrennt von einer KI-Verarbeitung; beim Speichern wird keine KI-Anfrage ausgelöst und es werden keine CV-Inhalte an KI-Anbieter übermittelt.

Ich willige ausdrücklich nach Art. 9 Abs. 2 lit. a DSGVO ein, dass besondere Kategorien personenbezogener Daten, die in dem von mir hochgeladenen Lebenslauf enthalten sind, gespeichert werden, soweit ich diese Angaben selbst bereitstelle. Das betrifft insbesondere Gesundheitsdaten, Angaben zu religiösen oder weltanschaulichen Überzeugungen, die Gewerkschaftszugehörigkeit, politische Meinungen, das Sexualleben und die sexuelle Orientierung, biometrische Daten, genetische Daten sowie Angaben zur rassischen oder ethnischen Herkunft. Diese ausdrückliche Einwilligung ist freiwillig, erfordert keine Zuordnung zu einer bestimmten Kategorie und keine Offenlegung, ob solche Daten überhaupt vorliegen, und kann jederzeit mit Wirkung für die Zukunft widerrufen werden; sie ist nicht Voraussetzung für die übrigen Lebenslauf-Funktionen. Eine automatische Kategorisierung oder Ableitung von Geschlecht, Geschlechtsidentität oder sexueller Orientierung findet nicht statt.

Ich kann diese Einwilligung jederzeit mit Wirkung für die Zukunft widerrufen. Der Widerruf blockiert neue Uploads und Änderungen; bereits gespeicherte Lebensläufe bleiben im Rahmen der bestehenden Rechte lesbar, herunterladbar und löschbar. Der Widerruf ist nicht automatisch eine sofortige physische Löschung.

Gespeicherte Lebensläufe bleiben bestehen, bis ich sie lösche. Sicherungen, Protokolle und gesetzliche Aufbewahrungspflichten können eine Löschung verzögern oder begrenzen.

Diese Einwilligung gilt ergänzend zu den Datenschutzhinweisen unter /datenschutz (Datenschutzrichtlinie Version 1.1 vom 7. November 2026) und ersetzt diese nicht.

## 2. Purpose mapping

| Layer | Value |
| --- | --- |
| Jobsearch client | `CV_STORAGE_CONSENT_PURPOSE = "cv-storage"` |
| Jobsearch BFF route | `/api/ris/cv-consents` forces `purpose=cv-storage`; browser cannot choose another purpose |
| Jobsearch BFF config | `risCvConsentConfig()` uses `CV_CONSENT_PURPOSE = "cv-storage"` and the CV text mapping |
| Jobsearch BFF text | `CV_CONSENT_TEXT_VERSION = cv-storage-consent-2026-11-08-v1`, SHA-256 `2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036` |
| RIS purpose | `CONSENT_PURPOSES["cv-storage"] = frozenset({"1.0"})` |
| RIS notice | `NOTICE_REGISTRY["cv-storage"]["1.0"]` |
| RIS external text | `EXTERNAL_NOTICE_REFS["cv-storage"]["cv-storage-consent-2026-11-08-v1"]` with the same hash |
| RIS Art. 9 proof | `ART9_EXTERNAL_TEXTS[("cv-storage", "cv-storage-consent-2026-11-08-v1")]` with the same hash |

ApplicationV1 `application-storage` and its approved v4 text are unchanged.

## 3. Server-side CV gate

Implemented in `lambda/handler.py`:

- `CONSENT_PILOT_ALLOWLIST` is the existing scoped pilot identity set. When it
  is non-empty, a non-listed identity receives
  `403 CV_STORAGE_PILOT_NOT_ALLOWED` for durable CV writes. The confirmed
  operator identity is:
  `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ZURSMpD2O|2344d8d2-f0e1-70a4-a1ff-1b7a6c843558`.
- `CV_STORAGE_CONSENT_ENFORCED` defaults to `false`. When enabled, CV
  create/upload/complete/update require a `GRANTED` `cv-storage` record; a
  missing/withdrawn consent returns `403 CV_STORAGE_CONSENT_REQUIRED`.
- List/Get/Download/Delete are not blocked by the CV write gate, so a
  withdrawal does not trap existing data.
- Search-profile writes are a separate profile domain and are not part of this
  CV document gate.
- Jobsearch additionally enforces its existing server-only
  `RIS_TEST_USER_ALLOWLIST`; no issuer/sub allowlist is in the browser bundle.
- No global CV flag is enabled by this packet; enabling is a separate plan and
  release action.

Route-level tests cover: non-pilot denial; pilot consent-required denial;
allowed pilot with consent; blocked create/upload/patch; allowed
list/get/delete.

## 4. RIS baseline failure comparison

The six RIS full-suite failures were reproduced on the unchanged baseline
commit `1d951b2` in a separate detached worktree with the same test command.
Both baseline and current branch produce the same six failures:

- `test_composite_lifecycle.py::...::test_global_flags_precede_command`
- `test_composite_lifecycle.py::...::test_extra_args_after_command`
- `test_composite_lifecycle.py::...::test_full_output_not_truncated`
- `test_g2c7d_plan_input_contract.py::test_plan_contract_uses_external_identity_and_explicit_orders_modes`
- `test_health_plane_integration.py::...::test_entitlement_denial_is_not_a_degradation`
- `test_platform_handlers.py::...::test_execute_agent`

They are pre-existing and outside the CV/consent change surface; no
CV-related regression was found. Current focused RIS CV/consent/API tests:
**134 PASS**.

## 5. CORS / IAM review

The only infrastructure additions are:

1. `module.documents.aws_s3_bucket_cors_configuration.documents` — private
   bucket CORS for exactly `https://www.mays-job-matcher.app`, methods
   `PUT/GET/HEAD`, headers `*`, exposed `ETag`, max age 900s. No public bucket
   access and no bucket-policy widening.
2. `module.lambda.aws_lambda_function.agent` — new CV gate code plus
   `CV_STORAGE_CONSENT_ENFORCED` env (current pre-approval plan shows `false`).

With the explicit
`mays_orders_lambda_execution_boundary=arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`,
the Mays-Orders worker permissions boundary is NO-OP. Without that variable,
the plan proposes an out-of-scope boundary removal and must not be applied.

Pre-approval technical plan (not the final activation plan):

- `/tmp/opencode/ris-cv-storage-01-preapproval.tfplan`
- SHA-256 `5986eadd20e6a4c93a9016a889cec73abd40727da0fd6c0c3a53965c62c145e0`
- state serial `43`, lineage `9cec61e5-c036-1ad5-6ae4-8b48a50122a4`
- **1 add, 1 change, 0 destroy**.

After text approval, the final plan will additionally set the actual CV gate
to `true`; it will be regenerated and presented with its own SHA-256.

## 6. Planned Vercel Production configuration

Only after approval and a separate release GO:

```text
RIS_CV_STORAGE_ENABLED=true
RIS_CV_CONSENT_NOTICE_VERSION=1.0
RIS_CV_CONSENT_TEXT_VERSION=cv-storage-consent-2026-11-08-v1
RIS_CV_CONSENT_TEXT_SHA256=2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036
RIS_CV_CONSENT_TEXT_STATE=APPROVED
VITE_RIS_CV_STORAGE_ENABLED=true
```

No values are set or deployed by this packet. `RIS_TEST_USER_ALLOWLIST` stays
restricted to the confirmed operator identity.

## 7. Rollback plan

- Disable `VITE_RIS_CV_STORAGE_ENABLED` and redeploy the previous known-good
  Jobsearch frontend.
- Disable `RIS_CV_STORAGE_ENABLED` to stop new CV BFF access; disable the RIS
  CV gate in a separately reviewed plan if required.
- Do not delete CV documents or consent history as part of rollback; existing
  list/get/download/delete behavior remains available.
- No ApplicationV1 or Mays-Orders rollback is required.

## 8. Approval requested

Please approve explicitly:

1. the exact text above as `cv-storage-consent-2026-11-08-v1` with SHA-256
   `2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036`;
2. the RIS notice `cv-storage/1.0` state `APPROVED` or `ACTIVE`;
3. the `legalApprovalRef` value, approval date and approval body.

After that approval I will prepare the RIS notice with the real reference,
regenerate the final Terraform plan with the actual CV gate enabled, and
present the final plan SHA-256, Vercel configuration and rollback plan. No
apply, push, merge or deployment will occur without the next explicit GO.
