# Partner Consent V1 — API-Vertrag (Handoff für Mays-Jobsearch)

**Status:** implementiert, lokal verifiziert, **nicht deployt**;
Notice `application-storage/1.0` `APPROVED` für den begrenzten Beta-Pilot
(`JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`), kein allgemeiner Rollout
**Gilt für:** `mays-jobsearch` und weitere Partner
**Basis:** RIS-Partner-Gateway (`c7e9pdwe78`) bzw. Kernel-API, gleiche Lambda

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

---

## 3. Zustände

```text
NOT_GRANTED ──grant──► GRANTED ──withdraw──► WITHDRAWN ──grant(REGRANTED)──► GRANTED
```

- `NOT_GRANTED` ist ein virtueller Zustand ohne Datensatz.
- Wiederholtes `grant` bei bereits `GRANTED` mit gleicher `noticeVersion` ist idempotent (kein neues Ereignis).
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
    "version": 1
  }
}
```

---

## 5. Withdraw

```http
POST /v1/partner/me/consents/withdraw
{ "purpose": "application-storage" }
```

Antwort `200` mit `status: WITHDRAWN`, `withdrawnAt`, `version+1`.

---

## 6. Status

```http
GET /v1/partner/me/consents?purpose=application-storage
```

```json
{ "items": [ { "purpose": "application-storage", "status": "GRANTED", "noticeVersion": "1.0", "grantedAt": "…", "withdrawnAt": null, "version": 1, "schemaVersion": 1 } ] }
```

Ohne `purpose` werden alle bekannten Zwecke geliefert (aktuell nur `application-storage`).

---

## 7. Historie

```http
GET /v1/partner/me/consents/history?purpose=application-storage&limit=50
```

```json
{ "items": [ { "eventId": "…", "purpose": "application-storage", "event": "REGRANTED", "status": "GRANTED", "noticeVersion": "1.0", "occurredAt": "…" } ], "nextCursor": false }
```

Ereignisse: `GRANTED`, `WITHDRAWN`, `REGRANTED`. Append-only, neueste zuerst.

---

## 8. Fehlercodes

| HTTP | Code | Bedeutung |
|---|---|---|
| 401 | `Unauthorized` | Token fehlt/ungültig oder Partner-Credential falsch |
| 403 | `Forbidden` | Partner/Profil/Tenant nicht zulässig |
| 404 | `UNKNOWN_PURPOSE` | Zweck nicht im Katalog |
| 409 | `NOT_GRANTED` | Widerruf ohne aktive Einwilligung |
| 409 | `CONFLICT` | konkurrierender Schreibvorgang |
| 422 | `INVALID_NOTICE_VERSION` | Erklärungsversion nicht akzeptiert |
| 422 | `INVALID_LIMIT` | `limit` außerhalb 1–100 |
| 503 | `Partner surface not activated` | Surface-Rollout noch aus |

---

## 9. Katalog (serverseitig)

| Purpose | Bekannte `noticeVersion` | Lifecycle-State | Rechtliche Freigabe |
|---|---|---|---|
| `application-storage` | `1.0` | `APPROVED` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` (limited beta pilot, 2026-11-08) |

Die Freigabe gilt **nur** für den begrenzten ApplicationV1-Beta-Pilot, nicht für
einen allgemeinen Rollout. Eine frei erfundene Version wird mit
`422 INVALID_NOTICE_VERSION` abgewiesen. Ein bekannter, aber nicht freigegebener
Entwurf wird bei aktiver State-Enforcement mit `422 NOTICE_NOT_ACTIVE`
abgewiesen.

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
  "externalRefs": [ { "externalRef": "application-storage-consent-2026-11-07-v4",
                      "source": "mays-jobsearch", "noticeState": "APPROVED",
                      "noticeVersion": "1.0" } ]
}
```

---

## 9a. Erklärungsversionen — Lifecycle (JM-RIS-CONSENT-RECONCILIATION-01)

Eine Versionskennung ist **keine** rechtliche Freigabe.

| State | Bedeutung | Für neue Grants |
|---|---|---|
| `DRAFT` | Text liegt als Entwurf vor, nicht freigegeben | nur bei `CONSENT_NOTICE_STATE_ENFORCED=false` (technisch/synthetisch) |
| `APPROVED` | Von der verantwortlichen Stelle freigegeben, noch nicht ausgerollt | ja |
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

| Quelle | Kennung | State | Abbildung auf RIS |
|---|---|---|---|
| RIS | `application-storage` / `1.0` | `APPROVED` (`JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`) | — |
| Jobsearch | `application-storage-consent-2026-11-07-v4` (SHA-256 `8722aed9…43c7`) | `APPROVED` (limited beta pilot) | **`1.0`** |
| Jobsearch | `STORAGE_CONSENT_TEXT_VERSION = 2026-11-04-draft-1` | `DRAFT` | **keine** (nicht äquivalent) |
| Jobsearch | Jobsearch v1/v2/v3 Texte | `DRAFT`, superseded | **keine** |

Der Betreiber hat die v4-Textfassung am 2026-11-08 für den begrenzten
ApplicationV1-Beta-Pilot freigegeben (Referenz
`JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`, Betreiberin May's Job Matcher).
Diese Freigabe umfasst **keinen** allgemeinen Rollout. `2026-11-04-draft-1` und
die historischen v1–v3-Texte bleiben bekannt, aber **nie** als `noticeVersion`
akzeptiert; das bloße Umbenennen einer Kennung ist keine Freigabe.

Die BFF-Anbindung sendet `noticeVersion: "1.0"` (die RIS-Kennung) und
protokolliert zusätzlich die angezeigte Textkennung
(`application-storage-consent-2026-11-07-v4`) samt SHA-256 im Consent-Proof.
Das Paar (angezeigter Text, RIS-`noticeVersion`) bleibt nachvollziehbar.

Art. 9: Nur v4 ist Art.-9-fähig. Ein `specialCategoriesConsent=true` verlangt
Version `application-storage-consent-2026-11-07-v4` und den exakten Hash
`8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7`; sonst
`422 EXTERNAL_TEXT_REQUIRED_FOR_SPECIAL_CATEGORIES` bzw.
`422 EXTERNAL_TEXT_NOT_ART9`.

---

## 9b. Aktivierungs-Gates (unverändert verbindlich)

1. RIS-Consent-Infrastruktur erreichbar (Deployment freigegeben und applied).
2. Jobsearch nutzt die Consent-Endpunkte korrekt (Grant/Withdraw/Status/History).
3. Erklärungsversion eindeutig zugeordnet **und** rechtlich freigegeben.
4. Synthetischer Grant-/Withdraw-/Regrant-Test erfolgreich.
5. Wirkungsbereich des gemeinsamen Lambda-Gates geprüft.
6. `APPLICATION_CONSENT_ENFORCED=true` gesondert freigegeben.

Gate 3 ist für den **begrenzten Beta-Pilot** durch
`JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` erfüllt. Gates 1, 4, 5 und 6
bleiben deployment-/pilot-spezifisch und sind nicht durch diese Freigabe
abgedeckt. `APPLICATION_CONSENT_ENFORCED` bleibt `false`, bis der Pilot separat
freigegeben und deployed ist.


---

## 10. Consent-Gate für ApplicationV1

Bei `APPLICATION_CONSENT_ENFORCED=true` prüft RIS vor jedem Schreibzugriff:

| Operation | Gate |
|---|---|
| Create | ja |
| Patch / Status / History / Anschreiben | ja |
| GET, Liste, Detail, Export, Delete | **nein** (Datenschutzrechte bleiben nutzbar) |

Ohne `GRANTED` → `403 CONSENT_REQUIRED`.

**Rollout:** Default ist `false`, damit bestehende Installationen weiterlaufen. Jobsearch muss zuerst den Consent-Dialog ausliefern; danach wird das Flag zentral aktiviert.

---

## 11. Widerruf und bestehende Daten

Ein Widerruf blockiert **neue** Schreibzugriffe. Bereits gespeicherte Bewerbungen bleiben lesbar/exportierbar/löschbar, bis der Benutzer sie löscht oder die bestehende Erasure-Logik greift. Es wird **keine** automatische physische Löschung behauptet.

---

## 12. Migrationsverhalten für Jobsearch

1. Beim ersten Aufruf `GET /consents` → `NOT_GRANTED` plus `catalog`.
2. Dialog anzeigen, Erklärungstext anzeigen, Zustimmung einholen.
3. `POST /consents` mit `noticeVersion=1.0`.
4. Erst danach ApplicationV1-Schreibzugriffe anbieten.
5. Bei `403 CONSENT_REQUIRED` den Dialog erneut anzeigen.
6. `422 NOTICE_NOT_ACTIVE` bedeutet: der Text ist noch Entwurf und die
   Freigabe fehlt. Nicht durch eine andere Kennung ersetzen, sondern eskalieren.
7. `noticeState`/`noticeApproved` aus der Statusantwort nur zur Anzeige
   verwenden, nie clientseitig hochstufen.
