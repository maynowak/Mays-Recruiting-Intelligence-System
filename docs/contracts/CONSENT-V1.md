# Partner Consent V1 — API-Vertrag (Handoff für Mays-Jobsearch)

**Status:** im Code implementiert; Terraform-Wiring für alle Enforcement-Variablen
in diesem Branch ergänzt. **Kein** allgemeiner Rollout, keine neue
Rechtsfreigabe. Deployment-/Aktivierungsstatus ist nicht Teil dieses Dokuments.
**Gilt für:** `mays-jobsearch` und weitere Partner
**Basis:** RIS-Partner-Gateway bzw. Kernel-API, gleiche Lambda

---

## 1. Authentifizierung

Jeder Aufruf benötigt **beides**:

1. `Authorization: Bearer <access_token>` — Access-Token des Partner-Pools (Jobsearch: `ZURSMpD2O`, Client `5hb3…`; `token_use=access`)
2. `X-Api-Credential: <ris_…>` — Partner-Credential, ausschließlich serverseitig im BFF

Zusätzlich serverseitig geprüft: ACTIVE Partner, ACTIVE APIProfile, Tenant-Gleichheit. Identität (`sub`) kommt ausschließlich aus dem Token.

---

## 2. Endpunkte

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/v1/partner/me/consents` | aktueller Status (alle Zwecke oder `?purpose=`) |
| POST | `/v1/partner/me/consents` | Einwilligung erteilen |
| POST | `/v1/partner/me/consents/withdraw` | Einwilligung widerrufen |
| GET | `/v1/partner/me/consents/history` | Ereignishistorie (`?purpose=…&limit=…`) |

Die Consent-Endpunkte selbst sind **nicht** durch die Storage-Gates gesperrt:
Status, Widerruf und Historie bleiben immer erreichbar. Die
`CONSENT_PILOT_ALLOWLIST` beschränkt die *Storage-Schreibpfade*, nicht den
Consent-Dialog.

---

## 3. Zustände

```text
NOT_GRANTED ──grant──► GRANTED ──withdraw──► WITHDRAWN ──grant(REGRANTED)──► GRANTED
```

- `NOT_GRANTED` ist ein virtueller Zustand ohne Datensatz.
- Wiederholtes `grant` bei bereits `GRANTED` mit gleicher `noticeVersion` und
  gleichem Nachweis ist idempotent (kein neues Ereignis).
- `grant` mit **anderem** Text- oder Kategorien-Nachweis bei bestehendem Grant
  → `409 RECONSENT_REQUIRED`; erst widerrufen, dann neu erteilen.
- `withdraw` ohne aktive Einwilligung → `409 NOT_GRANTED`.
- Widerrufe bleiben dauerhaft in der Historie.

---

## 4. Grant

```http
POST /v1/partner/me/consents
Content-Type: application/json

{ "purpose": "application-storage", "noticeVersion": "1.0" }
```

Antwort `200`:

```json
{
  "consent": {
    "schemaVersion": 1,
    "purpose": "application-storage",
    "status": "GRANTED",
    "noticeVersion": "1.0",
    "grantedAt": "2026-11-06T12:00:00+00:00",
    "withdrawnAt": null,
    "version": 1,
    "noticeState": "APPROVED",
    "noticeApproved": true,
    "acceptedForNewGrant": true,
    "specialCategoriesConsent": false,
    "specialCategories": [],
    "externalTextVersion": null,
    "externalTextSha256": null
  }
}
```

### 4.1 Gespeicherter Nachweis (Proof)

| Feld | Typ | Bedeutung |
|---|---|---|
| `specialCategoriesConsent` | boolean | explizites Art.-9-Consent; Default `false` |
| `specialCategories` | string[] | nicht-leere, duplikatfreie Teilmenge der Codes; kanonische Reihenfolge wird gespeichert |
| `externalTextVersion` | string \| null | bekannter Partnertext für **diesen** Purpose; **nie** eine RIS-`noticeVersion` |
| `externalTextSha256` | string \| null | muss exakt dem gepinnten Hash des Texts entsprechen (64 Hex) |

Regeln (fail-closed):

- `specialCategoriesConsent=true` ohne `specialCategories` → `422
  SPECIAL_CATEGORIES_REQUIRED`.
- Kategorien ohne Consent → `422 SPECIAL_CATEGORIES_WITHOUT_CONSENT`.
- Unbekannter/doppelter Code → `422 UNKNOWN_SPECIAL_CATEGORY` /
  `DUPLICATE_SPECIAL_CATEGORY`.
- Art.-9-Consent ohne externen Text → `422
  EXTERNAL_TEXT_REQUIRED_FOR_SPECIAL_CATEGORIES`.
- Historischer oder zweckfremder Text als Art.-9-Nachweis → `422
  EXTERNAL_TEXT_NOT_ART9`.
- Unbekannter Text oder Hash-Mismatch → `422 UNKNOWN_EXTERNAL_TEXT_VERSION` /
  `EXTERNAL_TEXT_HASH_MISMATCH`.

Die Proof-Felder werden **vor** jedem Schreiben validiert und bei Status und
Historie unverändert zurückgegeben. Legacy-Zeilen ohne Proof melden die
fail-closed Defaults (`false`, `[]`, `null`) und werden nie aus dem Notice-Text
abgeleitet.

---

## 5. Withdraw

```http
POST /v1/partner/me/consents/withdraw
{ "purpose": "application-storage" }
```

Antwort `200` mit `status: WITHDRAWN`, `withdrawnAt`, `version+1`. Widerruf ist
unabhängig vom Notice-Lifecycle immer möglich.

---

## 6. Status

```http
GET /v1/partner/me/consents?purpose=cv-storage
```

```json
{
  "items": [ {
    "purpose": "cv-storage", "status": "GRANTED", "noticeVersion": "1.0",
    "grantedAt": "…", "withdrawnAt": null, "version": 1, "schemaVersion": 1,
    "noticeState": "APPROVED", "noticeApproved": true,
    "acceptedForNewGrant": true,
    "specialCategoriesConsent": true,
    "specialCategories": ["health"],
    "externalTextVersion": "cv-storage-consent-2026-11-08-v1",
    "externalTextSha256": "2fe65fd1…"
  } ],
  "catalog": [ … ],
  "externalRefs": [ … ]
}
```

Ohne `purpose` werden **alle** bekannten Zwecke geliefert:
`application-storage`, `cv-storage`, `search-profile-storage`,
`analysis-processing`.

---

## 7. Historie

```http
GET /v1/partner/me/consents/history?purpose=application-storage&limit=50
```

```json
{ "items": [ { "eventId": "…", "purpose": "application-storage", "event": "REGRANTED", "status": "GRANTED", "noticeVersion": "1.0", "occurredAt": "…", "specialCategoriesConsent": false, "specialCategories": [], "externalTextVersion": null, "externalTextSha256": null } ], "nextCursor": false }
```

Ereignisse: `GRANTED`, `WITHDRAWN`, `REGRANTED`. Append-only, neueste zuerst.
`limit` außerhalb 1–100 → `422 INVALID_LIMIT`.

---

## 8. Fehlercodes

| HTTP | Code | Bedeutung |
|---|---|---|
| 401 | `Unauthorized` | Token fehlt/ungültig oder Partner-Credential falsch |
| 403 | `Forbidden` | Partner/Profil/Tenant nicht zulässig |
| 403 | `CONSENT_REQUIRED` | ApplicationV1-Schreibpfad ohne `application-storage`-Grant |
| 403 | `CV_STORAGE_CONSENT_REQUIRED` | CV-Schreibpfad ohne `cv-storage`-Grant |
| 403 | `CV_STORAGE_PILOT_NOT_ALLOWED` | Identität nicht in der CV-Pilot-Allowlist |
| 403 | `SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED` | Suchprofil-Schreibpfad ohne Grant |
| 403 | `SEARCH_PROFILE_STORAGE_PILOT_NOT_ALLOWED` | Identität nicht in der Suchprofil-Pilot-Allowlist |
| 404 | `UNKNOWN_PURPOSE` | Zweck nicht im serverseitigen Katalog |
| 409 | `NOT_GRANTED` | Widerruf ohne aktive Einwilligung |
| 409 | `CONFLICT` | konkurrierender Schreibvorgang |
| 409 | `RECONSENT_REQUIRED` | anderer Nachweis bereits gespeichert |
| 409 | `CONSENT_ALREADY_GRANTED` | andere `noticeVersion` bereits aktiv |
| 422 | `INVALID_NOTICE_VERSION` | Erklärungsversion nicht akzeptiert |
| 422 | `NOTICE_NOT_ACTIVE` | Version bei aktiver State-Enforcement nicht grantbar |
| 422 | `INVALID_LIMIT` | `limit` außerhalb 1–100 |
| 422 | Art.-9-/External-Text-Codes | siehe §4.1 |
| 503 | `Partner surface not activated` | Surface-Rollout noch aus |

---

## 9. Katalog (serverseitig)

| Purpose | Bekannte `noticeVersion` | Lifecycle | Rechtliche Freigabe |
|---|---|---|---|
| `application-storage` | `1.0` | `APPROVED` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` (limited beta pilot) |
| `cv-storage` | `1.0` | `APPROVED` | `JM-CV-STORAGE-V1-BETA-2026-11-08` (limited beta pilot) |
| `search-profile-storage` | `1.0` | `APPROVED` | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` (limited pilot) |
| `analysis-processing` | `1.0` | `DRAFT` | **keine** (`legalApprovalRef` leer) |

Eine frei erfundene Version wird mit `422 INVALID_NOTICE_VERSION` abgewiesen.
Ein bekannter, aber nicht freigegebener Entwurf wird bei aktiver
State-Enforcement mit `422 NOTICE_NOT_ACTIVE` abgewiesen.

Die Antwort von `GET /v1/partner/me/consents` enthält zusätzlich:

```json
{
  "items": [ { "...": "…", "noticeState": "APPROVED", "noticeApproved": true,
               "acceptedForNewGrant": true } ],
  "catalog": [ { "purpose": "application-storage", "noticeVersion": "1.0",
                 "noticeState": "APPROVED", "noticeApproved": true,
                 "acceptedForNewGrant": true,
                 "legalApprovalRef": "JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08",
                 "supersedes": null, "externalRefs": {} } ],
  "externalRefs": [ { "externalRef": "2026-11-04-draft-1",
                      "source": "mays-jobsearch", "noticeState": "DRAFT",
                      "noticeVersion": null },
                    { "externalRef": "application-storage-consent-2026-11-07-v4",
                      "source": "mays-jobsearch", "noticeState": "APPROVED",
                      "noticeVersion": "1.0" } ]
}
```

---

## 9a. Erklärungsversionen — Lifecycle

Eine Versionskennung ist **keine** rechtliche Freigabe.

| State | Bedeutung | Für neue Grants |
|---|---|---|
| `DRAFT` | Text liegt als Entwurf vor, nicht freigegeben | nur bei `CONSENT_NOTICE_STATE_ENFORCED=false` (technisch/synthetisch) |
| `APPROVED` | Von der verantwortlichen Stelle für den begrenzten Pilot freigegeben, nicht allgemein ausgerollt | ja |
| `ACTIVE` | Freigegeben und neuen Benutzern angeboten | ja |
| `SUPERSEDED` | Durch neuere Version ersetzt | nein (bestehende Grants bleiben gültig) |

Regeln:

- `CONSENT_NOTICE_STATE_ENFORCED=false` (Default): bekannte Versionen sind
  technisch grantbar, damit synthetische E2E-Läufe ohne Rechtsfreigabe möglich
  sind. Das ist **keine** Freigabe für echte Verarbeitung.
- `CONSENT_NOTICE_STATE_ENFORCED=true`: nur `APPROVED`/`ACTIVE` sind grantbar;
  `DRAFT` und `SUPERSEDED` liefern `422 NOTICE_NOT_ACTIVE`.
- Ein bestehender Grant behält seine gespeicherte `noticeVersion`. Wird diese
  `SUPERSEDED`, bleibt der Grant gültig; es gibt **keine** automatische
  Rückdatierung und **keine** stille Umdeutung.
- Ein erneuter `grant` mit derselben, inzwischen `SUPERSEDED` Version ist
  idempotent (kein neues Ereignis) und erzeugt keine neue Einwilligung.
- Widerruf bleibt immer möglich, unabhängig vom Lifecycle-State.

### Zuordnung Jobsearch ↔ RIS

| Purpose | Quelle | Kennung | State | Abbildung auf RIS |
|---|---|---|---|---|
| `application-storage` | RIS | `1.0` | `APPROVED` | — |
| `application-storage` | Jobsearch | `application-storage-consent-2026-11-07-v4` | `APPROVED` | `1.0` (limited beta pilot) |
| `application-storage` | Jobsearch | `2026-11-04-draft-1` | `DRAFT` | **keine** (historisch) |
| `cv-storage` | Jobsearch | `cv-storage-consent-2026-11-08-v1` | `APPROVED` | `1.0` (limited beta pilot) |
| `search-profile-storage` | Jobsearch | `search-profile-storage-consent-2026-11-08-v2` | `APPROVED` | `1.0` (limited pilot) |

Unbekannte oder historische Partnerkennungen bleiben serverseitig bekannt,
werden aber **nie** als `noticeVersion` akzeptiert. Das bloße Umbenennen einer
Kennung ist keine Freigabe. Die BFF-Anbindung sendet weiterhin die RIS-Kennung
`noticeVersion: "1.0"` plus die jeweilige Textidentität; das Paar (angezeigter
Text, RIS-`noticeVersion`) muss nachvollziehbar bleiben.

---

## 9b. Enforcement-Variablen und IaC-Vertrag

Alle Gates werden über Umgebungsvariablen gesteuert, die in Terraform
deklariert und an die Lambda-Umgebung verdrahtet sind:

| Terraform-Variable | Lambda-Env | Default | Wirkung |
|---|---|---|---|
| `application_consent_enforced` | `APPLICATION_CONSENT_ENFORCED` | `false` | ApplicationV1-Schreibgate |
| `cv_storage_consent_enforced` | `CV_STORAGE_CONSENT_ENFORCED` | `false` | CV-Schreibgate |
| `search_profile_storage_consent_enforced` | `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` | `false` | Suchprofil-Schreibgate |
| `consent_notice_state_enforced` | `CONSENT_NOTICE_STATE_ENFORCED` | `false` | Nur `APPROVED`/`ACTIVE` grantbar |
| `consent_pilot_allowlist` | `CONSENT_PILOT_ALLOWLIST` | `""` | `<issuer>\|<sub>`-Pilotgrenze |

Verhalten:

- **Variable nicht gesetzt**: Code-Default `false` (bestehende Installation
  bleibt funktionsfähig). Terraform schreibt immer explizit `true`/`false`.
- **Ungültiger Wert** (z. B. `ture`, leer, `1`, `yes`): der Gate ist
  **aktiv** (fail-closed) und der Fehler wird geloggt. Ein Tippfehler kann
  eine Durchsetzung also nie abschalten.
- **Unbekannte/malformed Allowlist-Einträge**: der Runtime-Parser ignoriert sie
  und kann den Scope dadurch nie erweitern. Terraform lehnt malformed Einträge
  bereits im Plan ab, damit ein Tippfehler den Pilotscope nicht still
  verkleinert.
- **Plan-Guards** (`terraform/modules/lambda`): Wenn ein Storage-Gate aktiv ist,
  muss `consent_notice_state_enforced=true` sein. `cv_storage_*` und
  `search_profile_storage_*` verlangen zusätzlich eine nicht-leere Allowlist —
  ein versehentlicher globaler Rollout ist damit kein Nebeneffekt.
- Die Allowlist ist `sensitive` und gehört **nicht** ins Repository. Sie wird
  zur Plan-Zeit aus einer geschützten Datei (0600) übergeben; das Installer-
  Overlay erlaubt sie bewusst nicht.

Diese Defaults und Guards sind **keine** Aktivierungsfreigabe. Jede Aktivierung
bleibt eine separate, dokumentierte Operator-/Privacy-Entscheidung.

---

## 9c. Art. 9 / besondere Kategorien — offener Punkt (cv-storage)

RIS validiert Art.-9-Nachweise technisch (siehe §4.1), erzwingt aber für
`cv-storage` **kein** `specialCategoriesConsent=true`: ein Grant nur mit
`purpose`/`noticeVersion` wird akzeptiert und als
`specialCategoriesConsent=false`, `specialCategories=[]` gespeichert.

Der Jobsearch-BFF verlangt für CV-Daten ein explizites Art.-9-Consent. Daraus
folgt eine **Asymmetrie**: ein RIS-Grant allein belegt keine Art.-9-Freigabe
für Lebenslaufinhalte (Gesundheit, Religion, Gewerkschaft, sexuelle
Orientierung/Sexualleben usw. können in CVs enthalten sein).

**Status: OPEN — Privacy/Legal-Entscheidung erforderlich.** Mögliche Optionen:

1. RIS erzwingt für `cv-storage` (und perspektivisch
   `search-profile-storage`) ein explizites Art.-9-Consent mit
   zweckspezifischem Text (Contract-/Handler-Änderung, neuer Test, neue
   Fehlercodes).
2. Der Partner bleibt die alleinige Art.-9-Grenze; RIS dokumentiert das
   ausdrücklich als Vertrauensgrenze und die BFF-Garantie wird auditiert.

Bis zu einer Entscheidung ändert dieser Branch die Policy **nicht** und
behauptet keine Art.-9-Durchsetzung in RIS.

---

## 10. Consent-Gates für Storage

Bei aktivem Gate prüft RIS vor jedem Schreibzugriff:

| Zweck | Gate | Operationen |
|---|---|---|
| `application-storage` | `APPLICATION_CONSENT_ENFORCED` / Pilot-Allowlist | Create, Patch, Status, History, Anschreiben |
| `cv-storage` | `CV_STORAGE_CONSENT_ENFORCED` / Pilot-Allowlist | CV create, upload, complete, update |
| `search-profile-storage` | `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` / Pilot-Allowlist | manuelle, CV- und ATS-Suchprofil-Create/Update |

Nicht gegatet (Datenschutzrechte bleiben nutzbar): GET, Liste, Detail, Export,
Download und Delete. Ohne `GRANTED` → `403` mit dem jeweiligen Code aus §8.

Die Pilot-Allowlist wirkt additiv: eine gelistete Identität ist auch bei
globalem Flag `false` gegatet; eine nicht gelistete Identität ist bei
gesetzter Allowlist für die CV-/Suchprofil-Schreibpfade gesperrt
(`*_PILOT_NOT_ALLOWED`). Der ApplicationV1-Gate hat keinen
`PILOT_NOT_ALLOWED`-Code; dort gilt die Allowlist nur als zusätzliche
Aktivierung.

---

## 11. Widerruf und bestehende Daten

Ein Widerruf blockiert **neue** Schreibzugriffe. Bereits gespeicherte Daten
bleiben lesbar/exportierbar/löschbar, bis der Benutzer sie löscht oder die
bestehende Erasure-Logik greift. Es wird **keine** automatische physische
Löschung behauptet; Aufbewahrung/Backups bleiben ein separater Nachweis.

---

## 12. Migrationsverhalten für Jobsearch

1. Beim ersten Aufruf `GET /consents` → `NOT_GRANTED` plus `catalog`.
2. Dialog anzeigen, Erklärungstext anzeigen, Zustimmung einholen.
3. `POST /consents` mit `noticeVersion=1.0` und – soweit fachlich erforderlich –
   dem Proof aus §4.1.
4. Erst danach die jeweiligen Schreibzugriffe anbieten.
5. Bei `403` mit `*_CONSENT_REQUIRED` den Dialog erneut anzeigen; bei
   `*_PILOT_NOT_ALLOWED` keine Umgehung versuchen (Identität ist nicht Teil
   des Piloten).
6. `422 NOTICE_NOT_ACTIVE` bedeutet: der Text ist noch Entwurf und die
   Freigabe fehlt. Nicht durch eine andere Kennung ersetzen, sondern eskalieren.
7. `noticeState`/`noticeApproved` aus der Statusantwort nur zur Anzeige
   verwenden, nie clientseitig hochstufen.
8. `404 UNKNOWN_PURPOSE` ist ein Client-/Versionsfehler, kein Grund, einen
   anderen Zweck zu senden.

---

## 13. Aktivierungs-Gates (unverändert verbindlich)

1. RIS-Consent-Infrastruktur erreichbar (Deployment freigegeben und applied).
2. Jobsearch nutzt die Consent-Endpunkte korrekt (Grant/Withdraw/Status/History).
3. Erklärungsversion eindeutig zugeordnet **und** rechtlich freigegeben.
4. Synthetischer Grant-/Withdraw-/Regrant-Test erfolgreich.
5. Wirkungsbereich des gemeinsamen Lambda-Gates geprüft.
6. Jedes Enforcement-Flag (`APPLICATION_CONSENT_ENFORCED`,
   `CV_STORAGE_CONSENT_ENFORCED`,
   `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`,
   `CONSENT_NOTICE_STATE_ENFORCED`) sowie die Pilot-Allowlist werden
   **einzeln** und ausdrücklich freigegeben.
7. Art.-9-Frage aus §9c ist entschieden, wenn CV-Inhalte verarbeitet werden.

Bis dahin bleiben die Flags `false` und die Allowlist leer.
