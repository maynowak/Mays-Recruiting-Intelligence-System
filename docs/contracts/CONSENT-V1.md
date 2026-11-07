# Partner Consent V1 — API-Vertrag (Handoff für Mays-Jobsearch)

**Status:** implementiert, lokal verifiziert, **nicht deployt**
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
| `application-storage` | `1.0` | `DRAFT` | keine (`legalApprovalRef = null`) |

Eine frei erfundene Version wird mit `422 INVALID_NOTICE_VERSION` abgewiesen.
Ein bekannter, aber nicht freigegebener Entwurf wird bei aktiver
State-Enforcement mit `422 NOTICE_NOT_ACTIVE` abgewiesen.

Die Antwort von `GET /v1/partner/me/consents` enthält zusätzlich:

```json
{
  "items": [ { "...": "…", "noticeState": "DRAFT", "noticeApproved": false,
               "acceptedForNewGrant": true } ],
  "catalog": [ { "purpose": "application-storage", "noticeVersion": "1.0",
                 "noticeState": "DRAFT", "noticeApproved": false,
                 "acceptedForNewGrant": true, "legalApprovalRef": null,
                 "supersedes": null, "externalRefs": {} } ],
  "externalRefs": [ { "externalRef": "2026-11-04-draft-1",
                      "source": "mays-jobsearch", "noticeState": "DRAFT",
                      "noticeVersion": null } ]
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
| RIS | `application-storage` / `1.0` | `DRAFT` | — |
| Jobsearch | `STORAGE_CONSENT_TEXT_VERSION = 2026-11-04-draft-1` | `DRAFT` | **keine** (nicht äquivalent) |
| Jobsearch | `STORAGE_CONSENT_PRIVACY_NOTICE_VERSION = 2026-11-04-draft-1` | `DRAFT` | **keine** |

`2026-11-04-draft-1` ist serverseitig bekannt, wird aber **nie** als
`noticeVersion` akzeptiert. Eine Gleichsetzung mit `1.0` entsteht erst durch
eine dokumentierte, rechtlich freigegebene Zuordnung; das bloße Umbenennen
einer Kennung ist keine Freigabe.

Die BFF-Anbindung sendet deshalb weiterhin `noticeVersion: "1.0"` (die
RIS-Kennung), zeigt aber den Jobsearch-Text an und protokolliert die
angezeigte Textkennung (`2026-11-04-draft-1`) im eigenen Audit-Trail. Das Paar
(angezeigter Text, RIS-`noticeVersion`) muss nachvollziehbar bleiben.

---

## 9b. Aktivierungs-Gates (unverändert verbindlich)

1. RIS-Consent-Infrastruktur erreichbar (Deployment freigegeben und applied).
2. Jobsearch nutzt die Consent-Endpunkte korrekt (Grant/Withdraw/Status/History).
3. Erklärungsversion eindeutig zugeordnet **und** rechtlich freigegeben.
4. Synthetischer Grant-/Withdraw-/Regrant-Test erfolgreich.
5. Wirkungsbereich des gemeinsamen Lambda-Gates geprüft.
6. `APPLICATION_CONSENT_ENFORCED=true` gesondert freigegeben.

Bis dahin bleibt `APPLICATION_CONSENT_ENFORCED=false`.


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
