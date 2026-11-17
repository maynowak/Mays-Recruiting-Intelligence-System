# XREPO-JM-RIS-CONSENT-FINAL-01

**Status:** `B — XREPO CONTRACT VERIFIED / AUTH E2E BLOCKED`  
**Scope:** Mays Jobsearch ↔ Mays RIS / limited-beta application storage and CV storage consent  
**No new Production deployment, Main merge, Terraform apply, AWS change or real applicant data.**

## 1. Gemeinsamer Systemstatus

| Komponente | Stand |
|---|---|
| Jobsearch Main | `92ca1fc690adcb1c6db3b392f710b3456c324e04` |
| Jobsearch Production Build | `92ca1fc` |
| Jobsearch Deployments | `dpl_F9wqvv56CutqLxQpQcbMFYFLNVze` (matcher), `dpl_GARYDrYPdJJP1AFPg7UnG22ujTk6` (jobsearch) |
| RIS Code-Main | `00363977ede1417c4992933b2639ac442a70a4b0` |
| RIS Docs-Main | `b193b716a508ac6835185b76e6a3173dc7c740c4` |
| RIS State | serial `80`, lineage `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| RIS Live Agent | `ris-dev-dev-agent`, code `cQFmaERVhZ0cjrqcio/kzaD5ZJB71kS0sa7vB4vJbdU=` |
| RIS Agent Bundle | `application-storage/1.0 = APPROVED`, `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` |
| RIS Post-Apply Plan | no changes, SHA-256 `30c4a15c4acd1e1d3c2bbec7e40b282deeb6143daa1cda73496ef2c2703cce86` |

## 2. Datenfluss und Vertragsprüfung

```text
Jobsearch StorageConsentLive
  -> src/lib/risConsentApi.ts
  -> GET/POST /api/ris/consents
  -> Jobsearch BFF api/_lib/ris/consentsHandler.mjs
  -> RIS /v1/partner/me/consents
  -> RIS ConsentRepository / consents table
  -> GET /api/ris/consents (reload)
```

Bestätigte Vertragspunkte:

- Jobsearch sendet bei ApplicationV1 nur `purpose=application-storage`,
  `specialCategoriesConsent=true` und den server-owned Notice-Kontext.
- Der BFF verlangt `noticeState` `APPROVED`/`ACTIVE`,
  `noticeApproved=true` und `acceptedForNewGrant=true`.
- Der BFF verlangt zusätzlich die separat konfigurierte Textversion und den
  SHA-256-Hash; Version `application-storage-consent-2026-11-07-v4` und Hash
  `8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7`
  stimmen mit der kanonischen Fassung überein.
- RIS Main enthält `application-storage/1.0 = APPROVED` mit
  `legalApprovalRef=JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` und dem
  v4-Textmapping.
- Der BFF liefert `grantAllowed=true` nur bei erfüllten Notice- und
  Textbedingungen; der Client setzt keine Freigabe selbst.
- `specialCategoriesConsent` wird im POST-Body übertragen und von RIS
  serverseitig validiert. Fehlt sie, bleibt der Vorgang gesperrt.
- Nach erfolgreichem POST übernimmt die UI die Serverantwort; nach Reload wird
  der Status erneut über `GET /api/ris/consents` geladen. Eine bereits erteilte
  Art.-9-Einwilligung wird checked/disabled dargestellt.
- Widerruf setzt die lokale Art.-9-Bestätigung zurück; Regrant verlangt eine
  neue ausdrückliche Checkbox-Bestätigung.
- CV-Speicherung nutzt den separaten Purpose `cv-storage` und die separate
  Route `/api/ris/cv-consents`; ApplicationV1- und CV-Consent sind getrennt.
- Fehlercodes werden im BFF/Client fail-closed behandelt: `401`, `403`,
  `409 notice_not_active`/verwandte Notice-Codes, `422`, `503` und
  `consent_disabled`/`missing_config`.

## 3. Vorhandene technische Nachweise

Aus den bereits abgeschlossenen Arbeiten:

- RIS Consent-Fix: gemerged und auf `ris-dev` angewendet; Apply
  `0 added / 8 changed / 0 destroyed`; Post-Apply-Plan ohne Änderungen.
- RIS Agent-Bundle enthält die APPROVED-Notice; Live-Lambda-Code stimmt mit dem
  ausgerollten Bundle überein.
- Jobsearch UX-03 ist in Production auf Build `92ca1fc`; öffentliche Routen
  `/`, `/profil`, `/profil?tab=settings`, `/profil?tab=cv`, `/datenschutz`,
  `/impressum` liefern `200`, ohne Console-/Page-Fehler.
- Jobsearch-Bundle enthält die neuen Meldungen „Einwilligung wird geprüft …“,
  „Anmeldung abgelaufen“, „Bitte setze die Checkbox“,
  „CV-Speicherfreigabe wird geprüft …“ und „nicht mehr vorhanden“.
- Unauthentifizierter Consent-API-Smoke: matcher `401`, jobsearch separate
  Deployment `503 consent_disabled`; kein unerwarteter 5xx.
- CV-404: persistente PDF-Metadaten und PDF-Dokument sind getrennte Zustände;
  der 404 wird nicht-destruktiv behandelt, die Liste wird aktualisiert, es wird
  nicht gelöscht oder migriert.

## 4. Testergebnisse

Jobsearch (aktueller Main / bereits verifiziert):

```text
Fokussiert Consent/CV: 32 PASS
RIS Consent API:       40 PASS
Serielle Gesamtsuite:  1952 PASS / 11 skipped
Build:                 PASS
```

RIS (aktueller Main / bereits verifiziert):

```text
Fokussiert Consent:    27 PASS
Serielle Gesamtsuite:  2629 PASS / 104 skipped / 5 bekannte Baseline-Fehler
Terraform:             fmt/validate PASS; Post-Apply-Plan clean
```

Die RIS-Baseline-Fehler sind unabhängig vom Consent-Vertrag und wurden bereits
auf sauberem `origin/main` reproduziert.

## 5. Verbleibender Blocker

**AUTH E2E BLOCKED.**

Es ist keine gültige autorisierte Limited-Beta-Testsession bzw. kein
Access-Token für die bereits vorgesehene synthetische Testidentität verfügbar.
Konkret fehlt:

- ein gültiger Cognito-Access-Token einer synthetischen Identität, die in der
  serverseitigen Jobsearch-`RIS_TEST_USER_ALLOWLIST` (`iss|sub`) freigegeben ist
  und von der RIS-Partneroberfläche akzeptiert wird.

Nicht ausgeführt und nicht behauptet:

- ApplicationV1-Grant im angemeldeten Live-Konto
- Reload-/Withdraw-/Regrant-Live-E2E
- CV-Grant und CV-PDF-404 mit angemeldeten synthetischen Daten

Es wurden keine Authentifizierungs- oder Consent-Gates umgangen, keine
Testidentität eigenmächtig angelegt und keine echten Bewerbungsdaten verändert
oder protokolliert.

## 6. Bekannte behobene Probleme

- RIS `application-storage/1.0` war auf Main `DRAFT`; die bestehende
  Limited-Beta-Freigabe wurde wiederhergestellt und ausgerollt.
- Jobsearch zeigte keinen verlässlichen Prüf-/Erfolgsstatus und keine
  handlungsorientierten Fehler; UX-03 behebt dies.
- Jobsearch zeigte eine bereits erteilte Art.-9-Einwilligung nach Reload nicht
  korrekt an; der Serverstatus wird nun übernommen.
- CV-404 wird als nicht-destruktiver, verständlicher Zustand behandelt.
- Der CV-Speichervertrag bleibt vom ApplicationV1-Vertrag getrennt.

## 7. Nächste Operator-Aktion

Eine bereits autorisierte synthetische Testsession bzw. ein gültiger Token für
die vorhandene Allowlist-Identität bereitstellen. Danach kann der separate
synthetische Live-E2E einmalig ausgeführt werden:

1. ApplicationV1 Grant → Success-Meldung
2. Reload → `GRANTED` + Art.-9-Proof
3. Withdraw → `WITHDRAWN`
4. Regrant nur nach neuer Checkbox-Bestätigung
5. CV Grant separat → `GRANTED`
6. CV-PDF-404 mit synthetischen Metadaten → nicht-destruktiver Fehler

Keine erneute allgemeine manuelle Button-Aufforderung; erforderlich ist
ausschließlich die fehlende autorisierte Testsession.

## 8. Freigabegrenzen

- Kein neuer Production-Deploy.
- Kein Main-Merge der Docs-Branches.
- Kein Terraform Apply.
- Keine RIS-/AWS-/Cognito-/CloudFront-/DNS-Änderung.
- Keine echten Bewerberdaten.
