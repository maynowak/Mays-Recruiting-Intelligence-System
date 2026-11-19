# XREPO-JM-RIS-CONSENT-LIVE-E2E-02

**Status:** `C — PRODUCT DEFECT CONFIRMED / FIX PREPARED / LIVE DEPLOYMENT NOT AUTHORIZED`
**Scope:** Jobsearch ↔ RIS limited-beta application-storage and CV-storage consent  
**No Main merge, new Production deployment, Terraform apply, AWS/Cognito/CloudFront/DNS change or real applicant data.**

## 1. Ergebnis

Der authentifizierte Live-Lauf konnte nach der Operator-Anmeldung ausgeführt
werden. Er hat zwei echte RIS-Vertragsfehler bestätigt:

1. **ApplicationV1:** Grant, Reload und Status funktionieren, aber der
   Art.-9-/Text-Nachweis wird nicht gespeichert. Nach Reload meldet der BFF
   `specialCategoriesConsent=false`, `externalTextVersion=null`,
   `externalTextSha256=null`; die UI zeigt „Art.-9-Einwilligung: nicht
   erteilt“.
2. **CV-/Search-Profile-Consent:** `GET /api/ris/cv-consents` und
   `GET /api/ris/search-profile-consents` liefern `404 UNKNOWN_PURPOSE`.
   Der aktuelle RIS-Main-Code kennt nur `application-storage`.

Der Live-CV-Teil ist damit **nicht** durchführbar; ein CV-Grant, Upload,
Reload, Download oder eine CV-404-Prüfung wurde nicht behauptet. Die
Jobsearch-UI und der XRepo-Transport sind nicht die Ursache.

## 2. Ausgangsstand

| Komponente | Stand |
|---|---|
| Jobsearch Main / Production | `92ca1fc690adcb1c6db3b392f710b3456c324e04` |
| Jobsearch Build | `92ca1fc` |
| Jobsearch Deployments | `dpl_F9wqvv56CutqLxQpQcbMFYFLNVze`, `dpl_GARYDrYPdJJP1AFPg7UnG22ujTk6` |
| RIS Code-Main | `00363977ede1417c4992933b2639ac442a70a4b0` |
| RIS Docs-Main | `b193b716a508ac6835185b76e6a3173dc7c740c4` |
| RIS State | serial `80`, lineage `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| RIS Live Agent | `ris-dev-dev-agent`, Code `cQFmaERVhZ0cjrqcio/kzaD5ZJB71kS0sa7vB4vJbdU=` |
| RIS Post-Apply Plan | no changes, SHA-256 `30c4a15c…` |

## 3. Authentifizierung

Die vorhandene, bereits allowlistete Pilot-Session wurde nach der
Operator-Anmeldung über den normalen Cognito-Refresh-Flow im Browser erneuert.
Es wurden keine Tokenwerte, Credentials, Profil-E-Mails oder Subject-Werte
ausgegeben oder gespeichert.

Der BFF akzeptierte die Session:

```text
GET /api/ris/consents
HTTP 200
grantAllowed=true
noticeState=APPROVED
textState=APPROVED
consent.status=GRANTED
```

Damit war die Identität für die serverseitige `RIS_TEST_USER_ALLOWLIST` und
die RIS-Partnerautorisierung gültig. Es gab keine Auth-Umgehung und keine
neue Testidentität.

## 4. Live-E2E ApplicationV1

Ausgeführt über die sichtbare Produktions-UI (`/profil?tab=settings`) und den
BFF:

- Application-Consent wurde einmal widerrufen.
- Art.-9-Checkbox wurde gesetzt.
- Grant wurde erneut ausgeführt.
- Sichtbare Bestätigung:
  „Die Einwilligung zur dauerhaften Speicherung wurde gespeichert.
  Status: erteilt.“
- Reload und anschließender BFF-GET:

```text
HTTP 200
consent.status=GRANTED
grantAllowed=true
noticeState=APPROVED
consent.specialCategoriesConsent=false
consent.specialCategories=[]
consent.externalTextVersion=null
consent.externalTextSha256=null
UI: "Art.-9-Einwilligung: nicht erteilt"
```

**Bewertung:** Grant und Statuspersistenz funktionieren; der
Art.-9-/Text-Nachweis geht verloren. Das ist ein RIS-Backend-Vertragsfehler,
kein Browser-/UI-Fehler. Der finale Consent-Status blieb `GRANTED`; es wurden
keine Bewerberdaten angelegt oder verändert.

## 5. Live-E2E CV / Search Profile

```text
GET /api/ris/cv-consents
HTTP 404
code=UNKNOWN_PURPOSE

GET /api/ris/search-profile-consents
HTTP 404
code=UNKNOWN_PURPOSE
```

Der BFF leitet die getrennten Zwecke korrekt an RIS weiter. RIS-Main/Live
akzeptiert sie jedoch nicht. Dadurch sind CV-Consent und Suchprofil-Consent
in Produktion nicht erreichbar; CV-Grant/Upload/Download/404 konnten nicht
ausgeführt werden.

Zusätzlicher Code-Befund: Die aktuellen RIS-Main-Routen für manuelle
Suchprofile, ATS-Profile und CV-Writes verwenden keinen der vorhandenen
Consent-Gates. Der Live-Stand ist daher nicht nur funktional unvollständig,
sondern auch ein Privacy-Regress gegenüber dem zuvor verifizierten
Pilotstand. Keine realen Nutzerdaten wurden dabei verändert.

## 6. Ursache

Der aktuelle RIS-Main-Code enthält nur den Application-Vertrag:

- `jobsearch/consent_contract.py`: `CONSENT_PURPOSES` enthält nur
  `application-storage`; `cv-storage` und `search-profile-storage` fehlen.
- `jobsearch/consent_repository.py`: Grant/Status speichern keine
  `specialCategoriesConsent`, `specialCategories`, `externalTextVersion`
  oder `externalTextSha256`.
- `lambda/handler.py`: Der Consent-POST reicht die Nachweisfelder nicht an
  das Repository weiter; CV-/Search-Routen nutzen den allgemeinen
  Storage-Guard ohne Consent-Prüfung.

Der zuvor verifizierte Pilotstand (`451c12e`) enthielt diese Bestandteile.
Der Release-05-Apply aus RIS-Main hat den Live-Lambda-Code damit auf einen
älteren, unvollständigen Consent-Vertrag zurückgesetzt. Es liegt **kein**
XRepo-Protokollfehler und **keine** Jobsearch-BFF-Abweichung vor.

## 7. Vorbereiteter Fix

Lokaler RIS-Branch, nicht in Main gemergt und nicht deployt:

| Feld | Wert |
|---|---|
| Branch | `fix/xrepo-ris-consent-contract-02` |
| Commit | `fd02722` |
| Pull Request | RIS #15 |
| Basis | `origin/main` `b193b71` |
| Geänderte Bereiche | `jobsearch/consent_contract.py`, `jobsearch/consent_repository.py`, `lambda/handler.py`, Consent-/Profile-Tests |
| Nicht geändert | Terraform, AWS, Cognito, API Gateway, Consent-Aktivierung, Deployment |

Der Fix stellt den bekannten, zuvor live verifizierten Consent-Vertrag wieder
her:

- ApplicationV1-Art.-9-Nachweis inklusive Textversion und SHA-256 wird
  validiert, gespeichert und im Status zurückgegeben.
- `cv-storage` und `search-profile-storage` sind wieder gültige, getrennte
  Zwecke mit den bestehenden genehmigten Notices.
- CV-, manuelle Suchprofil- und ATS-Writes besitzen wieder die zugehörigen
  Consent-Gates; Reads/Delete bleiben bei Widerruf möglich.
- Der BFF-Vertrag bleibt unverändert; keine neuen Credentials, Scopes oder
  Infrastrukturvariablen.

Tests:

```text
RIS fokussiert (Consent, CV, Search, Profile): 232 PASS
RIS vollständig: 2823 PASS / 104 skipped / 19 bekannte Baseline-Fehler
Clean-Main-Baseline b193b71: 2746 PASS / 104 skipped / 19 identische Fehler
Jobsearch BFF/Consent/UI-Libs: 53 PASS
```

Die 19 Restfehler sind identisch zur Clean-Main-Baseline (Wrapper-/Terraform-,
Composite-, Health-, Packaging- und Platform-Handler-Tests) und wurden durch
den Fix nicht verursacht. Es wurden keine Terraform- oder AWS-Änderungen
vorgenommen.

## 8. Betriebsstatus und nächste Gates

Bis zu einem separat freigegebenen RIS-Deployment bleibt Produktion
eingeschränkt:

- ApplicationV1: Grant/Status vorhanden, Art.-9-/Text-Nachweis **nicht**
  belastbar; keine Aussage „Art.-9-Nachweis persistiert“.
- CV-/Search-Profile: Consent-APIs `404`; keine Nutzung für reale Nutzer.
- Keine allgemeine Freigabe, kein Main-Merge, kein neues Deployment.

Nächste Schritte:

1. Review des Branches `fix/xrepo-ris-consent-contract-02` (`fd02722`).
2. Separates RIS-Deployment-Gate mit expliziter Freigabe; dabei bestehende
   Env-/Terraform-Schalter prüfen, ohne sie in diesem Branch zu ändern.
3. Danach Live-E2E erneut ausführen: ApplicationV1 Art.-9-Proof,
   Withdraw/Regrant, CV-Grant, synthetischer PDF-Upload/Reload/Download/404,
   Cleanup.
4. Erst danach Status auf `A` setzen.

## 9. Evidenz / Reproduktion

- Live-UI: `/profil?tab=settings`, Application-Consent-Abschnitt.
- Live-BFF: `GET /api/ris/consents`, `GET /api/ris/cv-consents`,
  `GET /api/ris/search-profile-consents`.
- Fix-Tests: `python3 -m pytest -q` im Branch-Worktree.
- Keine Tokens, Access-/Refresh-Token, E-Mails oder Subject-Werte in Report,
  Logs oder Auditlog.
- Keine realen Bewerberdaten; der Application-Consent wurde einmal
  zurückgesetzt und wieder erteilt, finaler Status `GRANTED`.

Kein Main-Merge, kein neues Deployment, kein Terraform/AWS/Cognito/
CloudFront/DNS-Eingriff.
