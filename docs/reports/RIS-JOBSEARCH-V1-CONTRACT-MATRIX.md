# RIS-JOBSEARCH-V1-CONTRACT-MATRIX

**Gate:** R08-JM-G0 — Jobsearch-/RIS-Vertragsabgleich
**Status:** ANALYSIS COMPLETE — no backend behavior changed, no Jobsearch
repository modified.
**Date:** 2026-11-01

## 1. Git-Baseline und Methode

| Prüfung | Ergebnis |
|---|---|
| RIS Branch | `feature/ris-partner-profile-persistence-v1` |
| RIS HEAD | `7d89e9e` |
| RIS Tracked Working Tree | clean |
| RIS Untracked | 39, unverändert |
| Jobsearch Remote `main` | `c787feaf99a604312a2c1f2d28c6e655823856ff` (via `git ls-remote`) |
| Jobsearch lokaler Klon | Branch `feature/arbeit` @ `c7f8eb6`; `origin/main` @ `0129559` |
| Jobsearch Schreibzugriffe | keine |
| AWS-Zugriffe/-Mutation | keine |

Der lokale Jobsearch-Klon war nicht auf `main` und sein `origin/main` war
gegenüber GitHub einen Tag alt. Die Vertragsartefakte wurden deshalb read-only
aus `origin/main` (`0129559`) gelesen. Ein GitHub-Compare
`0129559...c787feaf` meldet 78 geänderte Dateien, **keine** davon unter
`docs/contracts/`; die gelesenen Vertragsdateien sind also auch auf dem
gemeldeten `main`-Stand `c787feaf` gültig.

Methode: Code-Read von RIS-Handler, Contract, Repository, OpenAPI und
Terraform-Routen; read-only Vergleich der Jobsearch-v1-Fixtures mit dem
RIS-Contract über ein temporäres Analyse-Skript. Es wurden keine Dateien in
`mays-jobsearch` angelegt oder geändert.

## 2. Endpoint-Inventar

Jobsearch schlägt `/api/v1/me/...` vor; RIS exponiert Partnerprofil-Routen
unter `/v1/partner/me/...` und UserProfile unter `/me/profile`.

| Jobsearch-Ziel | RIS-Route (Ist) | Auth | Handler | Status |
|---|---|---|---|---|
| `GET /api/v1/me/profile` | `GET /me/profile` | Human-JWT | `_handle_me_profile_get` | vorhanden, Shape abweichend |
| `PATCH /api/v1/me/profile` | `PUT /me/profile` | Human-JWT | `_handle_me_profile_update` | Methode/Version abweichend |
| — | `POST /me/profile` | Human-JWT | `_handle_me_profile_create` | RIS-Extra (Provisionierung) |
| — | `DELETE /me/profile` | Human-JWT | `_handle_me_profile_delete` | RIS-Extra (G5) |
| `GET/POST /api/v1/me/cvs` | `GET/POST /v1/partner/me/cvs` | JWT + `X-Api-Credential` | `_handle_partner_cv_routes` | vorhanden |
| `GET/PATCH/DELETE /api/v1/me/cvs/{cvId}` | `GET/PATCH/DELETE /v1/partner/me/cvs/{cvId}` | JWT + Credential | `_handle_partner_cv_routes` | vorhanden |
| Create-CV mit `documentId` | `POST .../cvs` akzeptiert kein `documentId` | JWT + Credential | `_cv_create` | Lifecycle-Konflikt |
| — | `POST .../cvs/{cvId}/document/upload` | JWT + Credential | `_cv_upload_ticket` | RIS-Extra |
| — | `POST .../cvs/{cvId}/document/complete` | JWT + Credential | `_cv_complete` | RIS-Extra |
| — | `GET .../cvs/{cvId}/document` | JWT + Credential | `_cv_download` | RIS-Extra |
| CVSP-CRUD | `/v1/partner/me/cvs/{cvId}/search-profiles...` | JWT + Credential | `_handle_partner_cv_routes` | vorhanden |
| ATS-CRUD | `/v1/partner/me/search-profiles/{searchProfileId}/ats-profiles...` | JWT + Credential | `_handle_partner_ats_routes` | vorhanden |
| Manual-CRUD | `/v1/partner/me/manual-search-profiles...` | JWT + Credential | `_handle_manual_profile_collection/item` | vorhanden |
| `privacy.inspect/export/receipts/request_status` | — | — | — | **nicht vorhanden (R08-B)** |
| Erasure | `POST /me/erasure` | Human-JWT | `_handle_me_erasure` | G5, nicht partner-/profilvollständig |

Die Routen sind in `docs/API/openapi-platform.yaml` dokumentiert; die
Partnerrouten sind dort ebenfalls enthalten.

## 3. Authentifizierung und Identitätsbindung

- Partnerprofil-Routen verlangen Cognito-**Access-JWT** **und**
  `X-Api-Credential`, dazu Partner-Registry (`apiProfileId`, `tenantId`,
  `status=ACTIVE`) und serverseitige Tenant-Auflösung. Das ist mit dem
  Jobsearch-Ziel „Identität nur aus verifiziertem Kontext" vereinbar.
- `/me/profile` ist **nur JWT-geschützt** und nicht partner-gebunden. Ein
  gemeinsames Jobsearch-BFF müsste daher zwei Auth-Muster bedienen.
- `userId`/`tenantId` werden in allen Profilpfaden serverseitig gesetzt;
  Client-Identitätsfelder werden abgelehnt (`CLIENT_IDENTITY_FORBIDDEN`).
- Parent-Ketten (`cvId → searchProfileId → atsProfileId`) werden serverseitig
  geprüft; Cross-User-/Tenant-/Partner-/Issuer-Zugriffe werden abgewiesen.
- Der `X-Api-Credential` bleibt ein vertrauliches `ris_...`-Secret und darf
  nicht in den Browser. Der Browserpfad muss über ein Jobsearch-BFF bzw. eine
  separate Delegation laufen.

## 4. Ressourcen-Feldmatrix

### 4.1 UserProfileV1

| Jobsearch-Feld | RIS `/me/profile` | Bewertung |
|---|---|---|
| `schemaVersion: 1` | fehlt | **Gap** |
| `userId` | vorhanden | OK |
| `tenantId?` | vorhanden | OK |
| `nickname?`, `firstName?`, `lastName?` | vorhanden | OK |
| `email?` | aus JWT, serverautoritativ | OK |
| `status: active\|disabled\|pending` | `"ACTIVE"` (Großschreibung) | **Gap** |
| `createdAt`, `updatedAt` | vorhanden | OK |
| `version` | fehlt | **Gap** |

RIS liefert das rohe DynamoDB-Item; Statuswerte außer `ACTIVE` existieren im
aktuellen Pfad nicht. Update ist `PUT` ohne Versionsprüfung.

### 4.2 CVDocumentV1

| Jobsearch-Feld | RIS Partner-CV | Bewertung |
|---|---|---|
| `schemaVersion` | vorhanden | OK |
| `cvId` | vorhanden | OK |
| `documentId` (required) | erst nach Upload-Ticket gesetzt; `to_dict` lässt `null` weg | **Gap** |
| `filename` | `name` | **Gap (Mapping)** |
| `contentType: application/pdf` (required) | optional, darf fehlen | **Gap** |
| `sizeBytes` (min. 1) | `size`, initial `0` | **Gap** |
| `processingStatus` | `pending/upload_pending/ready/delete_failed/error` | **Gap** |
| `createdAt`, `updatedAt`, `version` | vorhanden | OK |
| `metadata {pageCount?, language?}` | beliebiges `metadata`, inkl. Legacy | **Gap (Normalisierung)** |

Statuszuordnung ist nicht verlustfrei möglich:

| Jobsearch | RIS | Problem |
|---|---|---|
| `pending` | `pending`, `upload_pending` | RIS-Zwischenzustand hat kein Ziel |
| `ready` | `ready` | OK |
| `failed` | `error` | semantisch nah, Mapping nötig |
| `deleted` | kein Status (Item gelöscht); `delete_failed` bedeutet Fehler | **kein sicheres Mapping** |

### 4.3 CVSearchProfileV1

| Jobsearch-Feld | RIS | Bewertung |
|---|---|---|
| `schemaVersion`, `searchProfileId`, `cvId` | vorhanden | OK |
| `name`, `description`, `origin: cv` | vorhanden | OK |
| `searchConfig` | kanonisch | OK |
| `createdAt`, `updatedAt`, `version` | vorhanden | OK |
| `userId`/`tenantId` | serverseitig, nicht im Response | OK |

### 4.4 ATSSearchProfileV1

| Jobsearch-Feld | RIS | Bewertung |
|---|---|---|
| `atsSearchProfileId` | intern `atsProfileId`, Serializer mappt | OK |
| `searchProfileId`, `name` | vorhanden | OK |
| `targetRoles`, `skills` | vorhanden, case-insensitiv dedupliziert | OK |
| `criteria` (`ATSCriteriaV1`) | exakt drei Listen + `schemaVersion` | OK |
| `version`, Zeitstempel | vorhanden | OK |
| KI-Scores/Prompts | nicht Teil des DTO | OK |

### 4.5 ManualSearchProfileV1

| Jobsearch-Feld | RIS | Bewertung |
|---|---|---|
| `manualSearchProfileId` | intern `manualProfileId`, Serializer mappt | OK |
| `name`, `description`, `origin: manual` | vorhanden | OK |
| `searchConfig`, `matchingPreferences` | kanonisch | OK |
| `version`, Zeitstempel | vorhanden | OK |
| Anzahllimit | offen (Produktentscheidung) | OK, dokumentiert |

### 4.6 SearchConfigurationV1 und MatchingPreferencesV1

Read-only-Fixture-Probe gegen den RIS-Contract:

| Probe | Ergebnis |
|---|---|
| `profile.roundtrip.json` → RIS `SearchConfiguration` → `to_dict()` | **deep equal** |
| Phrase `"Cloud Architecture"` bleibt eine Phrase | PASS |
| `radiusKm: null` bleibt `null` | PASS |
| `workModes: ["remote","hybrid"]` bleibt mehrwertig | PASS |
| `employmentTypes: ["full_time","part_time"]` | PASS |
| `MatchingPreferences`-Roundtrip | **deep equal** |
| Negative ATS-Criteria (`overallScore`, `modelExplanation`) | abgelehnt |
| Unbekanntes Manual-Feld | abgelehnt |

RIS und Jobsearch begrenzen `radiusKm` identisch auf `{10,25,50,100,null}`,
`employmentTypes` auf `minItems: 1` und dieselben Enum-Werte. `skills` ist
beidseitig ein phrase-erhaltender String. **Keine Konvertierung von
`remoteOnly`** ist im Pfad vorhanden.

## 5. Eingabe-Verträge

| Operation | Jobsearch-Input | RIS akzeptiert | Bewertung |
|---|---|---|---|
| Manual Create | `name`, `description?`, `searchConfig`, `matchingPreferences` | identisch | OK |
| Manual Update | Felder + `expectedVersion` | Felder + Body-`version` | Transport-Mapping |
| CVSP Create | `name`, `description?`, `searchConfig` | identisch | OK |
| CVSP Update | Felder + `expectedVersion` | Body-`version` | Transport-Mapping |
| ATS Create | `name`, `targetRoles`, `skills`, `criteria?` | identisch | OK |
| ATS Update | Felder + `expectedVersion` | Body-`version` | Transport-Mapping |
| CV Create | `documentId`, `filename`, `contentType`, `sizeBytes` | nur `name`, `contentType?` | **inkompatibel** |
| CV Update | `filename?` + `expectedVersion` | `name?`, `contentType?`, `version?` | **inkompatibel** |
| UserProfile Patch | `nickname?`, `firstName?`, `lastName?` + Version | `PUT` dieselben Felder, keine Version | **inkompatibel** |
| Delete | `expectedVersion` | Query `?version=` | Transport-Mapping |
| Create-Retry | Idempotency-Key | `Idempotency-Key`/`X-Idempotency-Key` | OK |

## 6. Fehler-, Status- und Envelope-Mapping

Jobsearch `RepositoryErrorCode` gegen RIS-Antworten:

| Jobsearch | RIS | Gap |
|---|---|---|
| `unauthorized` | 401 `{"error":"Unauthorized"}` | Envelope |
| `forbidden` | 403 `{"error":"Forbidden"}` | Envelope |
| `not_found` | 404 `{"error":"Not found"}` | Envelope |
| `validation_error` | 400/422 `{"error":..., "code":...}` | Code-Name/Envelope |
| `conflict` | 409 `{"error":"Conflict"}` / `"Version conflict"` | Envelope |
| `capacity_exceeded` | 409 `{"error":"Conflict"}` (Repository: „Capacity exceeded") | **kein eigener Code** |
| `aborted` | kein Serverfall | Client-Abbruch |
| `unavailable` | 500 / 503 | Envelope |

Jobsearch schlägt `{data, meta}` bzw. `{error:{code,message},meta}` vor; RIS
liefert das Resource-Objekt flach bzw. `{"error": ...}`. Das ist kein
Sicherheitsfehler, aber ein klar zu entscheidender Adapter-/Facade-Punkt.

## 7. Pagination

| Ressource | RIS | Jobsearch `Page<T>` | Gap |
|---|---|---|---|
| Manual | `{items, nextCursor}` | `{items, nextCursor}` | OK |
| CVSearchProfile | `{items, nextCursor}` | `{items, nextCursor}` | OK |
| ATS | `{items, nextCursor}` | `{items, nextCursor}` | OK |
| CV | `{items}` (Limit 50, Cap 10) | `{items, nextCursor}` | `nextCursor` fehlt |

Cursor sind opaque, identitäts-/scope-gebunden und ablaufen nach 15 Minuten;
kein Full-Table-Scan im Lesepfad.

## 8. OpenAPI-/Runtime-Abweichungen

| Punkt | OpenAPI | Runtime | Bewertung |
|---|---|---|---|
| `UserProfile` | `status: [ACTIVE]`, kein `version`/`schemaVersion` | genauso | bewusst, aber nicht Jobsearch-v1 |
| `PartnerCvV1` | `name`, `size`, RIS-Statusenum | genauso | nicht Jobsearch-v1 |
| `POST /me/documents` | `DocumentUploadTicket`: `uploadUrl`, `documentId`, `expiresAt`, `requiredHeaders` | `docId`, `key`, `uploadUrl`, `expiresIn` | **3 Abweichungen** |
| S3-Key im Response | nicht vorgesehen | `key` wird zurückgegeben | **Datensparsamkeitsfinding** |
| Partner-CV-Upload | `PartnerCvUploadTicket` mit `expiresIn` | `expiresIn` | OK |

Der zuletzt genannte `key` im `/me/documents`-Response ist der wichtigste
OpenAPI-/Runtime-Fund: Der Jobsearch-Vertrag verbietet S3-Keys ausdrücklich,
und die RIS-Privacy-Dokumentation ebenfalls.

## 9. Findings

| ID | Priorität | Finding | Ziel-Gate |
|---|---|---|---|
| F-JM-01 | P0 | UserProfile-Response erfüllt `UserProfileV1` nicht: `schemaVersion`/`version` fehlen, `status` ist `ACTIVE` statt lowercase. | G03 |
| F-JM-02 | P0 | UserProfile-Update ist `PUT` ohne optimistische Version; Jobsearch nutzt `PATCH` + `expectedVersion`. | G03 |
| F-JM-03 | P0 | `/me/profile` ist nur JWT-geschützt und nicht partner-/credential-gebunden; kein Partnerprofil-Äquivalent. | G03 |
| F-JM-04 | P0 | CVDocument-Felder `filename`/`sizeBytes` vs `name`/`size`; `contentType`, `documentId` und `sizeBytes >= 1` sind bei RIS nicht garantiert. | G03 |
| F-JM-05 | P0 | CV-Statusenum ist nicht verlustfrei auf `pending/ready/failed/deleted` abbildbar (`upload_pending`, `error`, `delete_failed`). | G03 |
| F-JM-06 | P0 | CV-Lifecycle-Reihenfolge widerspricht dem Jobsearch-Input: Jobsearch erwartet `documentId` beim Create, RIS vergibt ihn erst im Upload-Ticket. | G03 |
| F-JM-07 | P1 | Fehler-Envelope und `capacity_exceeded` sind nicht unterscheidbar; Erfolgs-Envelope `{data,meta}` fehlt. | G03/G11 |
| F-JM-08 | P1 | `GET /v1/partner/me/cvs` liefert kein `nextCursor` (Daten vollständig wegen Cap 10, Shape aber abweichend). | G04 |
| F-JM-09 | P1 | Versions-Transport: RIS Body-`version`/Query-`version`, Jobsearch `expectedVersion`/`If-Match`. | G04/G11 |
| F-JM-10 | P2 | CV-`metadata` ist bei Jobsearch auf `pageCount`/`language` begrenzt; RIS kann beliebige/Legacy-Metadaten emittieren. | G04 |
| F-JM-11 | P1 | Routen-Basis und Envelope (`/api/v1/me` vs `/v1/partner/me`) sind nicht identisch; Adapter vs. RIS-Fassade ist zu entscheiden. | G11 |
| F-JM-12 | P1 | `privacy.inspect/export/receipts/request_status` fehlen als API; das Receipt-Journal ist nur intern vorhanden. | G06 |
| F-JM-13 | P0 | `POST /me/documents` gibt `key` (S3-Objektschlüssel) zurück und weicht bei `docId/documentId` und `expiresIn/expiresAt` von OpenAPI ab. | G03 (Security) |
| F-JM-14 | P2 | Zeitstempel nutzen `+00:00` statt `Z`; beides ist RFC 3339, keine Änderung nötig. | — |
| F-JM-15 | P2 | OpenAPI `UserProfile`/`PartnerCvV1` dokumentiert die abweichende RIS-Form und muss mit G03 synchronisiert werden. | G03 |

Bereits kompatibel und nur noch durch permanente Tests zu sperren:

- `ManualSearchProfileV1`, `CVSearchProfileV1`, `ATSSearchProfileV1` inklusive
  ID-Normalisierung und `version`.
- `SearchConfigurationV1`/`MatchingPreferencesV1` (Roundtrip und Negative).
- Identitäts-/Parent-Isolation und Cursor-Pagination der Partnerrouten.

## 10. Contract-Test-Plan (für G03/G04)

1. Jobsearch-Response-Fixtures in RIS-Normalform (Server-Identität injiziert)
   positiv validieren.
2. Jobsearch-Create/Update-Fixtures gegen die RIS-Handler-Payloads testen.
3. Statusmatrix `pending/upload_pending/ready/error/delete_failed` →
   Jobsearch-Enum als explizite Tabelle testen; kein stilles Mapping.
4. CV-Lifecycle: Create → Upload-Ticket → Complete → `ready`; kein `ready`
   ohne `HeadObject`; `documentId`-Reihenfolge.
5. Fehler-Mapping inklusive `capacity_exceeded` und 503.
6. Pagination inklusive `nextCursor: null` für CV.
7. Cross-User-/Tenant-/Partner-/Issuer- und Parent-Chain-Negativfälle.
8. `/me/documents`-Response darf keinen S3-Key enthalten (F-JM-13).
9. UserProfile-`PATCH`/Version und Statuslowercase.
10. Keine KI-Scores/Prompts/S3-Keys/Secrets in Profil-Responses.

## 11. Abgrenzung und Ergebnis

- Keine RIS-Backend-Änderung in diesem Gate; alle Unterschiede sind als
  eindeutige Implementierungsaufgaben in G03/G04/G06/G11 spezifiziert.
- Keine Jobsearch-Änderung, keine Session-/Redis-Arbeit, keine
  Mays-Orders-Änderung, keine AWS-Mutation.
- Die Matrix ist eine Ist-Aufnahme; `VERIFIED-AWS` wird nicht behauptet.

**Ergebnis:** Der V1-Vertrag ist für Manual-, CVSP- und ATS-Profile sowie für
`SearchConfigurationV1`/`MatchingPreferencesV1` bereits weitgehend
kompatibel. Die P0-Lücken konzentrieren sich auf UserProfile, CVDocument
(Felder, Status, Lifecycle) und den `/me/documents`-Response. Damit ist
R08-P1-1 (Gate 03) der nächste zwingende Schritt; R08-POLICY-01 (Gate 02)
bleibt unabhängig davon Voraussetzung für produktive Journal-Writes.

## 12. Resume Point

- Nächstes Gate: **R08-POLICY-01** (Retention/Rechtsgrundlagen) bzw. parallel
  **R08-P1-1** nach Policy-Freigabe.
- R08-A2, R08-B/C/D, R07-B und Jobsearch-Handoff bleiben nicht gestartet.
