# RIS-PARTNER-PROFILE-R05-P0 — CONTRACT COMPATIBILITY REPAIR

## 1. Git-Baseline

- Branch: `feature/ris-partner-profile-persistence-v1`
- Basis: `61453f8` (R05-G0)
- Jobsearch-Referenz (read-only): `origin/main@ad9b5ed`
- 39 untracked Dateien unverändert.

## 2. P0-1 — schemaVersion

**Vorher:** `SCHEMA_VERSION = "v1"` (String) in allen RIS-Ressourcen; die API
gab `"schemaVersion": "v1"` zurück. Der Jobsearch-v1-Vertrag verlangt
`schemaVersion: 1` (Integer, `const 1`).

**Nachher:**
- `SCHEMA_VERSION = 1` (Integer).
- `_check_schema_version` akzeptiert kanonisch `1`, liest Legacy `"v1"` und
  normalisiert auf `1`; lehnt `True`, `2`, `"v2"`, `"1"` usw. ab.
- Alle `to_dict()`-Serialisierungen liefern Integer `1`.
- OpenAPI: `schemaVersion` in `ManualSearchProfileV1` und `PartnerCvV1` ist
  jetzt `type: integer, enum: [1]`.
- Keine globale String-Ersetzung; andere RIS-Schemata (z.B. `domain_models.py`)
  wurden nicht angefasst.

## 3. P0-2 — searchConfig

**Vorher:** Es gab kein `searchConfig`. Die R03-Felder (`roles`, `locations`,
`workModes`, `employmentTypes`, `query`, …) lagen in `matchingPreferences`;
`skills` (String) und `radiusKm` (nullable) hatten kein Speicherfeld.

**Nachher:**
- Neues Contract-Objekt `SearchConfiguration` mit exakt den sechs v1-Feldern:
  `skills` (phrase-preserving String), `targetRoles[]`, `city`,
  `radiusKm` (`10|25|50|100|null`), `workModes[]` (`remote|hybrid|onsite`),
  `employmentTypes[]` (`full_time|part_time`, min. 1).
- `ManualSearchProfile.search_config` ist ein eigenes Feld; `to_dict()` liefert
  `searchConfig` und `matchingPreferences` getrennt.
- `MatchingPreferences` ist kanonisch auf die drei v1-Listen reduziert
  (`requiredSkills`, `preferredSkills`, `excludedTerms`); `to_dict()` enthält
  keine Legacy-Felder mehr.
- R03-Handler parst und speichert beide Objekte unabhängig. Ein Update, das nur
  eines der beiden sendet, lässt das andere unverändert.
- Roundtrip: `skills` mit quotierten Phrasen bleibt unverändert; `radiusKm: null`
  bleibt `null`; mehrere Rollen/WorkModes/EmploymentTypes bleiben erhalten.

## 4. Vollständige Feldmatrix (nach Repair)

| Jobsearch v1 | RIS-Contract | Persistenz | API-Antwort | Status |
|---|---|---|---|---|
| `schemaVersion: 1` | `schema_version: 1` | `payload.schemaVersion` | `1` | **IDENTISCH** |
| `cvId` | `cv_id` | `payload.cvId` | `cvId` | IDENTISCH |
| `documentId` | `document_id` | `payload.documentId` | `documentId` | IDENTISCH |
| `filename` | `name` | `payload.name` | `name` | MAPPING REQUIRED (P1-1) |
| `contentType: application/pdf` | `content_type` | `payload.contentType` | `contentType` | MAPPING REQUIRED (P1-1) |
| `sizeBytes` | `size` | `payload.size` | `size` | MAPPING REQUIRED (P1-1) |
| `processingStatus` | `processing_status` | `payload.processingStatus` | `processingStatus` | MAPPING REQUIRED (P1-1) |
| `searchConfig.skills` | `SearchConfiguration.skills` | `payload.searchConfig.skills` | `searchConfig.skills` | **IDENTISCH** |
| `searchConfig.targetRoles` | `target_roles` | `payload.searchConfig.targetRoles` | `searchConfig.targetRoles` | **IDENTISCH** |
| `searchConfig.city` | `city` | `payload.searchConfig.city` | `searchConfig.city` | **IDENTISCH** |
| `searchConfig.radiusKm` | `radius_km` | `payload.searchConfig.radiusKm` | `searchConfig.radiusKm` | **IDENTISCH** |
| `searchConfig.workModes` | `work_modes` | `payload.searchConfig.workModes` | `searchConfig.workModes` | **IDENTISCH** |
| `searchConfig.employmentTypes` | `employment_types` | `payload.searchConfig.employmentTypes` | `searchConfig.employmentTypes` | **IDENTISCH** |
| `matchingPreferences.requiredSkills` | `required_skills` | `payload.matchingPreferences.requiredSkills` | `matchingPreferences.requiredSkills` | **IDENTISCH** |
| `matchingPreferences.preferredSkills` | `preferred_skills` | `...preferredSkills` | `...preferredSkills` | **IDENTISCH** |
| `matchingPreferences.excludedTerms` | `excluded_terms` | `...excludedTerms` | `...excludedTerms` | **IDENTISCH** |
| `manualSearchProfileId` | `manual_profile_id` | `payload.manualProfileId` | `manualSearchProfileId` | **LOSSLESS ALIAS** |
| `name`, `description`, `origin` | gleich | `payload.*` | gleich | IDENTISCH |
| `createdAt`, `updatedAt`, `version` | gleich | payload/Item | gleich | IDENTISCH |
| `CVSearchProfileV1.searchConfig` | noch nicht modelliert | — | — | **OPEN (P1-2, R05)** |
| `ATSSearchProfileV1.criteria` | abweichend | — | — | **OPEN (P1-3, R06)** |

## 5. Legacy-Kompatibilität und Migrationsmatrix

| Legacy | Kanonisch | Regel | Verlustrisiko |
|---|---|---|---|
| `"v1"` | `1` | Lesen normalisiert auf `1`; Schreiben emittiert `1` | keins |
| `matchingPreferences.roles` | `searchConfig.targetRoles` | 1:1 | keins |
| `matchingPreferences.workModes` | `searchConfig.workModes` | 1:1 | keins |
| `matchingPreferences.locations[]` | `searchConfig.city` | genau 1 Eintrag → `city`; mehrere → `city=""`, alle in `metadata.legacy.searchConfig.locations` | gekennzeichnet |
| `matchingPreferences.employmentTypes` | `searchConfig.employmentTypes` | erlaubte Werte übernommen; `contract|temporary|internship` in `metadata.legacy.searchConfig.employmentTypes` | gekennzeichnet |
| fehlendes `skills` | `searchConfig.skills=""` | kein erfundenes Skills-Feld; `legacyIncomplete` | gekennzeichnet |
| fehlendes `radiusKm` | `null` | keine erfundene Zahl | gekennzeichnet |
| `query` | kein v1-Feld | in `metadata.legacy.matchingPreferences.query` | gekennzeichnet |
| `salaryMin`, `remoteOnly`, `sources` | kein v1-Feld | in `metadata.legacy.matchingPreferences.*` | gekennzeichnet |
| IDs/Versionen | unverändert | keine Rekonstruktion | keins |

Legacy-Datensätze bleiben lesbar. Nicht abbildbare Felder werden **nicht**
gelöscht, sondern in `metadata.legacy` konserviert und mit
`metadata.legacyIncomplete = true` markiert. Ein Update erhält diese Metadaten.
Es wurde **keine** AWS-Datenmigration ausgeführt; eine spätere explizite
Migration kann `metadata.legacy` in das kanonische Modell überführen.

## 6. Auswirkungen auf R03/R04

- **R03:** CRUD, Dual-Auth, Owner-/Partner-/Tenant-/Issuer-Isolation,
  Versionierung und Pagination unverändert. Die API-Antwort ist jetzt die
  kanonische v1-Form (`searchConfig` + dreifeldige `matchingPreferences`); der
  `manualSearchProfileId`-Alias bleibt verlustfrei.
- **R04:** CVDocument-API funktioniert unverändert; `schemaVersion` ist jetzt
  Integer `1`. Upload-Ticket, HeadObject-Complete, READY-Regel, Isolation,
  Versionskonflikte und Delete-Marker-Klassifikation sind unverändert getestet.

## 7. Tests

- Neu: `tests/test_partner_profile_v1_repair.py` — **20/20 PASS**
  (Integer-SchemaVersion in Response und Persistenz, Legacy-Read, Legacy-
  Metadaten-Erhalt bei Update, alle sechs searchConfig-Felder persistiert und
  neu geladen, quoted skills, `radiusKm=null`, Mehrfachwerte, Unabhängigkeit
  von `searchConfig`/`matchingPreferences`, CRUD, Alias, Versionskonflikt,
  Cross-User/-Tenant/-Partner/-Issuer, kein Agenten-/Modellaufruf).
- Aktualisiert: `tests/test_partner_profile_contract_reconciliation.py` —
  **27/27 PASS** (P0-Reparatur nachgewiesen; verbleibende P1-Lücken explizit).
- R01–R05-P0-Regression: **331/331 PASS** (96 R01/R02 + 26 R03 + 29 R04 +
  20 R05-P0 + 27 Reconciliation + 75 Partner + 47 OpenAPI + 11 Dokumente).
- OpenAPI-Konsistenz: 47/47 PASS; YAML parsebar (35 Pfade).
- Terraform `fmt -check` (versionierte Dateien): PASS; `validate`: PASS
  (vorbestehende Deprecation-Warnings).

## 8. Noch offene P1-Findings aus R05-G0

| ID | Befund | Status |
|---|---|---|
| P1-1 | CVDocument: `name`/`filename`, `size`/`sizeBytes`, Statuswert-Set, `contentType`-Breite. | **OPEN** |
| P1-2 | CVSearchProfile: `description`, `origin`, `searchConfig` fehlen (R05-CRUD). | **OPEN** |
| P1-3 | ATSSearchProfile: `criteria`-Shape (R06). | **OPEN** |
| P1-4 | Legacy-`MatchingPreferences.employmentTypes` akzeptiert weiterhin die RIS-Superset-Werte (nur Lesepfad); neue v1-`searchConfig`-Writes sind auf `full_time|part_time` begrenzt. | **TEILWEISE BEHOBEN** |
| P1-5 | R04-CV-Delete hat keinen Kind-Guard; vor R05-Freischaltung 409-Guard nötig. | **OPEN** |
| P1-6 | Create-Idempotenz (`Idempotency-Key`) fehlt. | **OPEN** |

## 9. Klassifikation

- **IMPLEMENTED:** `SearchConfiguration`, v1-`MatchingPreferences`, Integer-
  `schemaVersion` mit Legacy-Read, R03-Handler-Anpassung, OpenAPI-Schemas.
- **VERIFIED:** 331/331 Tests; Terraform fmt/validate; OpenAPI-Konsistenz.
- **NOT RUN:** echte AWS-/DynamoDB-/S3-Integration; volle `tests/`-Suite wegen
  fehlendem boto3 / präexistenten Windows-/Installer-Fehlern.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
- **R05-CRUD-Vorbereitung:** P0-1 und P0-2 behoben. R05-CRUD kann auf dem
  v1-Modell aufsetzen; P1-5 (Delete-Guard) und P1-6 (Idempotenz) bleiben
  R05-Vorbedingungen.
