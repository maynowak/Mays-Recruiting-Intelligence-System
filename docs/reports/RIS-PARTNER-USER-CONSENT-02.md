# RIS-PARTNER-USER-CONSENT-02 — Consent Service Deployment & Jobsearch Integration

- **Datum:** 2026-11-06
- **Modus:** Integration + Plan; **kein Apply**
- **Ergebnis:** **DEPLOYED / VERIFIED LIVE (Consent-Flow) — ApplicationV1-Gate PENDING**

---

## 1. Baseline

| Repo | Stand |
|---|---|
| RIS | `main` @ `b923f9b` (Consent-Lifecycle-Fix), Tree sauber außer geschützter fremder Datei |
| Jobsearch | `main` @ `f59aa4b` (Consent-BFF/UI-Anbindung) |
| RIS-Plan alt | `94a8086d…` — **ungültig** (Bundle nach Fix neu gebaut) |
| RIS-Plan neu | **`2a9e5aa8b42730ee71fd0bf67e26aa4e296bbe756f70a338d97f32965023cf7e`** |

---

## 2. Vorhandene Jobsearch-Einwilligung (wiederverwendet)

| Aspekt | Befund |
|---|---|
| UI | `StorageConsentSection` (Vorbereitungsmodus), `ConsentGate`, `CvConsentGate` |
| Vertrag | `src/lib/storageConsent.ts` (Purpose-/Status-Modell, Server-Backend als „nicht verfügbar" markiert) |
| Textversion | `2026-11-04-draft-1` |
| Speicherung bisher | keine serverseitige; `consentSource: "simulated"` |
| BFF | `api/ris/applications.mjs` + `_lib/ris/*` (Auth/JWKS/Credential) |

Keine neue UI gebaut: Die bestehende Sektion wurde um einen optionalen Live-Block erweitert.

---

## 3. Jobsearch-Integration (commit `f59aa4b`)

| Datei | Änderung |
|---|---|
| `api/ris/consents.mjs` | BFF: Status, Grant, Withdraw, History; nutzt bestehende RIS-Auth/Client |
| `api/_lib/ris/config.mjs` | `risConsentConfig()`; **Server besitzt** `RIS_CONSENT_NOTICE_VERSION` |
| `src/lib/risConsentApi.ts` | Browser-Client ohne Credential/Version |
| `src/components/StorageConsentLive.tsx` | Status/Grant/Withdraw/History |
| `StorageConsentSection.tsx` | Live-Block nur bei `VITE_RIS_CONSENT_UI_ENABLED=true` |
| `tests/api/ris-consents.test.mjs` | 7 Tests (401, Status, Version serverseitig, kein Client-Version-Override, Withdraw, unbekannter Zweck) |

Wichtig: Ein Client kann **keine** `noticeVersion` erfinden; der BFF setzt die serverseitig konfigurierte Version. Ohne Mapping antwortet er `503 notice_version_not_mapped`.

Tests: **40 passed** (Consent-BFF, Applications-BFF, bestehende UI) · `npm run build` PASS.

---

## 4. Notice-Version-Lifecycle (RIS `b923f9b`)

Der frühere Zustand „1.0 ist akzeptiert" war eine harte Annahme. Jetzt:

| Zustand | Bedeutung |
|---|---|
| `DRAFT` | Text existiert, keine rechtliche Freigabe (`application-storage/1.0`) |
| `APPROVED` | rechtlich freigegeben |
| `ACTIVE` | für neue Grants akzeptiert |
| `SUPERSEDED` | ersetzt; bestehende Grants bleiben gültig |

- `CONSENT_NOTICE_STATE_ENFORCED` (Default `false`) erlaubt synthetische Läufe; bei `true` erzeugen nicht-ACTIVE Versionen `422 NOTICE_NOT_ACTIVE`.
- Bestehende Grants überleben `SUPERSEDED`; Widerruf bleibt immer möglich; keine Rückdatierung.
- `GET /consents` liefert additiv `catalog`, `externalRefs`, `noticeState`.
- Consent-Routen sind im kanonischen OpenAPI dokumentiert (3 Contract-Tests dadurch grün).

**Konsequenz:** Der Jobsearch-Text (`2026-11-04-draft-1`) ist **nicht** automatisch `1.0`. Eine Zuordnung ist eine rechtliche Entscheidung.

---

## 5. Neue API / Auth

Bestehender Partnerzugang unverändert: Gateway `c7e9pdwe78`, Pool `ZURSMpD2O`, Client `5hb3…`, Partner `mays-jobsearch` ACTIVE. RIS prüft weiterhin JWT + Credential + Partner + Profil + Tenant + `iss|sub`.

Keine Änderung an Cognito, Login-Domain, CloudFront, DNS, ACM.

---

## 6. Terraform-Plan (nicht angewendet)

| Aktion | Anzahl |
|---|---:|
| CREATE | **10** (Consent-Tabelle, 8 Routen, IAM-Policy) |
| UPDATE | **1** (Lambda-Env `CONSENTS_TABLE`, `APPLICATION_CONSENT_ENFORCED=false`) |
| DELETE / REPLACE | 0 / 0 |
| Geschützt | 0 Änderungen |

SHA-256: **`2a9e5aa8b42730ee71fd0bf67e26aa4e296bbe756f70a338d97f32965023cf7e`**

Der zuvor freigegebene Plan `94a8086d…` ist durch den Bundle-Neubau überholt.

---

## 7. Enforcement / Rollout

- `APPLICATION_CONSENT_ENFORCED` bleibt `false` (Integrationsphase).
- Zielzustand `true` erfordert: Jobsearch-Consent-UI aktiv, Textversion ACTIVE, alle aktiven Partner abgedeckt, neuer Plan + Freigabe.
- Gate deckt 5 Schreibpfade; Lesen/Export/Delete bleiben frei.

---

## 8. E2E-Status

| Test | Status |
|---|---|
| Status/Grant/Withdraw/History lokal (RIS-Repo, 8-Schritte-E2E aus `b923f9b`) | **PASS** |
| Jobsearch-BFF-Consent-Tests | **PASS (7)** |
| Live-E2E über Jobsearch-UI → BFF → RIS | **BLOCKED** |

Blocker: (a) Consent-Infrastruktur nicht deployt (kein Apply), (b) `noticeVersion` nicht ACTIVE, (c) UI-Flag `VITE_RIS_CONSENT_UI_ENABLED` nicht gesetzt.

---

## 9. Datenschutz

Keine JWTs/Keys/CV-Inhalte in Consent-Daten; Identität serverseitig. Widerruf löscht keine bestehenden Bewerbungen. Offene Folgearbeiten: Consent in Inspect/Export/Erasure, Aufbewahrung, Erklärungstext-Freigabe.

---

## 10. Ergebnisübersicht

| Bereich | Status |
|---|---|
| RIS-Consent-Infrastruktur | **BLOCKED** (Apply-Freigabe für neuen Plan) |
| RIS-Consent-Endpunkte | **BLOCKED** (nicht deployt) |
| Jobsearch-Consent-UI wiederverwendet | **VERIFIED LOCAL** |
| Jobsearch-BFF-Anbindung | **VERIFIED LOCAL** (7 Tests) |
| Grant/Withdraw/History | **PASS (lokal)** |
| ApplicationV1-Gate | **PENDING** (Enforcement false) |
| Synthetischer E2E | **BLOCKED** |
| Datenschutz-Folgearbeiten | **DOCUMENTED** |

**Keine unzutreffenden PASS-Angaben.**


---

## 11. Apply-Nachweis (2026-11-06)

| Prüfung | Wert |
|---|---|
| Plan-SHA vor Apply | `2a9e5aa8…` erneut geprüft ✅ |
| State vor Apply | serial 41, 243 Ressourcen |
| Apply | **10 added, 1 changed, 0 destroyed** |
| State nach Apply | serial **42**, 249 Ressourcen |
| Folge-Plan | **0 aktive Änderungen** (273 no-op, 11 berechnete Drift-Einträge) |
| Geschützte Ressourcen | 0 Änderungen |

Live-Zustand:

- Tabelle `ris-dev-dev-consents` **ACTIVE** (`scopeKey`/`entityKey`)
- Lambda-Env: `CONSENTS_TABLE=ris-dev-dev-consents`, `APPLICATION_CONSENT_ENFORCED=false`, `PARTNER_SURFACE_ENABLED=true`
- Vier Consent-Routen auf Kernel- und Edge-API erreichbar (ohne Token jeweils **401**)

---

## 12. Live-E2E über Jobsearch-BFF

Synthetischer Jobsearch-Nutzer (PKCE-Login), BFF lokal mit den produktiven Modulen, `RIS_CONSENT_NOTICE_VERSION=1.0`:

| Schritt | Ergebnis |
|---|---|
| Status initial | **200**, `NOT_GRANTED` |
| Grant | **200**, `GRANTED`, `noticeVersion=1.0` |
| Status danach | **200**, `GRANTED` |
| Withdraw | **200**, `WITHDRAWN` |
| Historie | **200**, Ereignisse `WITHDRAWN`, `GRANTED` |
| Erneute Zustimmung | **200**, `GRANTED` |

Cleanup: 4 Consent-Zeilen gelöscht, Testnutzer gelöscht, Tabelle wieder **0** Einträge, Harness beendet.

**Nicht live getestet:** `403 CONSENT_REQUIRED` beim ApplicationV1-Schreiben, weil `APPLICATION_CONSENT_ENFORCED=false` (Integrationsphase). Der Nachweis existiert lokal (7 Gate-Tests) und wird nach Aktivierung live nachgeholt.

---

## 13. Finale Statusübersicht

| Bereich | Status |
|---|---|
| RIS-Consent-Infrastruktur | **DEPLOYED** |
| RIS-Consent-Endpunkte | **VERIFIED** (401 ohne Token, live erreichbar) |
| Jobsearch-Consent-UI wiederverwendet | **VERIFIED LOCAL** (hinter UI-Flag) |
| Jobsearch-BFF-Anbindung | **VERIFIED** (7 Tests + Live-Flow) |
| Grant/Withdraw/History | **PASS (live, synthetisch)** |
| ApplicationV1-Gate | **PENDING** (`false`) |
| Synthetischer E2E | **PASS (Consent-Flow)**; Gate-403 offen |
| Datenschutz-Folgearbeiten | **DOCUMENTED** |
