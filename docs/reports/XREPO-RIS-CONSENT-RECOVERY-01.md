# XREPO-RIS-CONSENT-RECOVERY-01

**Status:** `A — FIX VERIFIED LOCAL / PRODUCTION ACTIVATION PENDING`  
**Live E2E:** **NOT EXECUTED** — no valid authorized test identity/token was available.  
**No production, AWS, Terraform or main change.**

## 1. Ausgangslage

Betroffen ist die dauerhafte Speicherung von ApplicationV1 über RIS.
Der Datenfluss wurde read-only verfolgt:

```text
Jobsearch StorageConsentLive
  -> src/lib/risConsentApi.ts
  -> GET/POST /api/ris/consents
  -> Jobsearch BFF api/_lib/ris/consentsHandler.mjs
  -> RIS GET/POST /v1/partner/me/consents
  -> RIS ConsentRepository / consents table
```

Die Jobsearch-Produktionskonfiguration ist aktiv:

- `RIS_CONSENT_SERVICE_ENABLED` aktiv
- `RIS_CONSENT_TEXT_VERSION = application-storage-consent-2026-11-07-v4`
- `RIS_CONSENT_TEXT_SHA256 = 8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7`
- `RIS_CONSENT_TEXT_STATE = APPROVED`
- `VITE_RIS_CONSENT_UI_ENABLED = true`
- unauthenticated `GET /api/ris/consents` auf `www.mays-job-matcher.app`
  antwortet mit `401 unauthenticated`, nicht mit `503`.
- `mays-jobsearch.vercel.app` hat die Consent-UI/BFF separat deaktiviert und
  ist für diesen Test nicht die richtige Domain.

## 2. Bestätigte Ursache

Auf dem aktuellen RIS-`origin/main` (`ae08267`) steht die
`application-storage/1.0`-Notice auf:

```text
noticeState: DRAFT
noticeApproved: false
legalApprovalRef: null
```

Mit der produktiven Enforcement-Annahme
`CONSENT_NOTICE_STATE_ENFORCED=true` liefert RIS damit:

```text
noticeVersion: 1.0
noticeState: DRAFT
noticeApproved: false
acceptedForNewGrant: false
legalApprovalRef: null
```

Der Jobsearch-BFF verlangt für einen Grant genau:

- `noticeState` ist `APPROVED` oder `ACTIVE`
- `noticeApproved === true`
- `acceptedForNewGrant === true`

Deshalb setzt der BFF in `GET /api/ris/consents` korrekt
`grantAllowed=false`; die UI disabled „Speicherung zustimmen“ und zeigt
`noticeReason=notice_not_active`. Ein POST würde vor dem Schreiben mit
`409 notice_not_active` abgelehnt.

Die v4-Textprüfung ist dagegen bereits korrekt: Version und SHA-256 passen
zwischen Jobsearch-Client, BFF und Produktionskonfiguration.

### Ursache der Abweichung

Der nachweislich funktionierende Pilotstand liegt in
`feature/jm-ris-cv-storage-integration-01` / `451c12e` und enthält:

```text
application-storage/1.0 -> APPROVED
legalApprovalRef -> JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08
application-storage-consent-2026-11-07-v4 -> application-storage/1.0
```

Dieser bereits dokumentierte Operator-Approval-Commit `6bfb71f` wurde nie in
`origin/main` integriert. `origin/main` ist deshalb mit dem aktuell
erwarteten Jobsearch-BFF-Vertrag nicht kompatibel. Die Änderung ist **keine
neue Rechtsfreigabe**, sondern die Wiederherstellung des bereits dokumentierten
Limited-Beta-Pilotstands.

## 3. Minimaler Fix

Betroffenes Repository: **`maynowak/Mays-Recruiting-Intelligence-System`**.

In `jobsearch/consent_contract.py`:

1. `application-storage/1.0` wieder auf `APPROVED` setzen.
2. Den bestehenden `legalApprovalRef`
   `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` erhalten.
3. Den v4-Text (`application-storage-consent-2026-11-07-v4`) wieder
   explizit auf RIS `1.0` abbilden.

Nicht geändert:

- keine Deaktivierung des Consent-Gates
- kein künstliches `grantAllowed=true`
- keine neue Notice-Version
- kein neuer legaler Freigabevermerk
- keine Änderung an `CONSENT_NOTICE_STATE_ENFORCED`
- keine Änderung an `APPLICATION_CONSENT_ENFORCED`
- kein AWS-/Terraform-/Cognito-/CloudFront-Eingriff
- keine Jobsearch-Produktänderung

Der Jobsearch-BFF bleibt bewusst fail-closed. Eine RIS-Notice, die nicht
freigegeben ist, darf auch weiterhin nicht durch den BFF „freigeschaltet“
werden.

## 4. Testergebnisse

RIS, fokussiert:

```text
python3 -m pytest \
  tests/test_consent_notice_lifecycle.py \
  tests/test_consent_e2e_joint.py \
  tests/test_consent_repository.py \
  tests/test_consent_gate.py -q
# 27 passed
```

RIS, gesamte Suite:

```text
python3 -m pytest tests/ -q
# 2620 passed, 104 skipped, 6 failed
```

Die 6 Fehler sind auf dem unveränderten `origin/main` reproduzierbar:

- `test_composite_lifecycle` (3)
- `test_health_plane_integration` (1)
- `test_lambda_packaging` (1)
- `test_platform_handlers` (1)

Sie sind nicht durch den Consent-Fix verursacht.

Jobsearch, fokussiert (keine Produktänderung):

```text
npx vitest run \
  tests/api/ris-consents.test.mjs \
  src/components/StorageConsentLive.test.tsx \
  src/components/StorageConsentSection.active.test.tsx \
  src/lib/storageConsent.test.ts
# 63 passed
```

Jobsearch Build war auf dem aktuellen `main` bereits PASS; es wurde kein
Jobsearch-Produktcode geändert.

## 5. Live-Nachweisstatus

Der authentifizierte Live-GET/POST konnte **nicht** ausgeführt werden:

- vorhandener Operator-Session-Refresh-Token: `invalid_grant`
- keine gültige Testidentität/kein gültiger Test-Token im Arbeitsbereich
- keine Passwörter, Tokens oder Consent-Historien wurden protokolliert

Damit ist die Live-Ursache nicht als „production verified“ beansprucht. Die
statische Repo-/Konfigurations-Evidenz ist vollständig, aber der konkrete
Live-Katalog muss nach Bereitstellung einer autorisierten Testidentität
verifiziert werden.

## 6. Erforderliche Freigaben

1. **RIS Lambda-Deployment** des Fixes (Plan/Apply nach separater Freigabe).
2. **Produktions-Smoke** mit einer autorisierten Testidentität:
   `GET /api/ris/consents` muss `noticeState=APPROVED`,
   `grantAllowed=true` liefern; anschließend POST/GRANTED/Reload/Withdraw/
   Regrant prüfen.
3. Keine allgemeine Freigabe für neue Benutzer; der bestehende Limited-Beta-
   Pilot bleibt bestehen.
4. Jobsearch-Deployment ist für diesen Fix nicht erforderlich, sofern der
   aktuelle BFF/Env-Stand unverändert bleibt.

## 7. Offene Risiken

- Ohne Live-Test ist nicht ausgeschlossen, dass zusätzlich eine
  Allowlist-, Env- oder RIS-Erreichbarkeitsstörung besteht.
- `CONSENT_NOTICE_STATE_ENFORCED=true` bleibt vorausgesetzt; der Fix allein
  ändert keine Laufzeitflags.
- Die Freigabe ist ausdrücklich auf den begrenzten Pilot beschränkt; keine
  allgemeine Rechtsfreigabe und kein allgemeiner Rollout.
- Es wurden keine echten Bewerber- oder Consent-Daten verwendet.
