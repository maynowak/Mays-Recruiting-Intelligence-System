# RIS-PARTNER-PROFILE-R05-G0 — CONTRACT RECONCILIATION

## 1. RIS-Git-Baseline

- Repository: `Mays-Recruiting-Intelligence-System`
- Branch: `feature/ris-partner-profile-persistence-v1`
- HEAD: `64972a85d55f3102b351d0fa10a4b0922f614bcb` (R04)
- Working Tree: tracked clean; 39 untracked Dateien unverändert.
- Geprüfte Commits: R01 `761eeb6`, R02 `e43bf53`, R02-R `befbb59`,
  R02-R2 `2e2a72e`, R03 `9de6a14`, R04 `64972a8`.

## 2. Jobsearch-Referenz-HEAD

- Repository: `maynowak/mays-jobsearch`
- `origin/main`: `ad9b5ed333d11163b797b7942f2d1891fb0fce3d` (bestätigt; kein
  Weiterlaufen seit dem letzten geprüften Stand).
- Gelesen ausschließlich read-only via `git show origin/main:...`; keine
  Jobsearch-Datei verändert.
- Relevante Quellen: `JOBMATCHER-PROFILE-DATA-CONTRACT-V1.md`,
  `JOBMATCHER-PROFILE-REPOSITORY-CONTRACT-V1.md`,
  `JOBMATCHER-API-SESSION-BOUNDARY-01.md`,
  `MAYS-RIS-PROFILE-PERSISTENCE-01-HANDOFF.md`,
  `schemas/JOBMATCHER-PROFILE-V1.schema.json`,
  `fixtures/profile-v1/*`, `JM-PROFILE-SESSION-ISOLATION-GATE-06`.

## 3. Feld-Kompatibilitätsmatrix

Legende: **IDENTISCH**, **LOSSLESS ALIAS**, **MAPPING REQUIRED**,
**INCOMPATIBLE**, **NOT VERIFIED**.

### 3.1 CVDocumentV1 → RIS CVDocument (R04)

| Jobsearch v1 | RIS-Contract | Persistenz | API-Antwort | Klassifikation |
|---|---|---|---|---|
| `schemaVersion: 1` | `schema_version: "v1"` | `payload.schemaVersion` | `"v1"` | **INCOMPATIBLE (P0-1)** |
| `cvId` | `cv_id` | `payload.cvId` | `cvId` | IDENTISCH |
| `documentId` | `document_id` | `payload.documentId` | `documentId` | IDENTISCH |
| `filename` | `name` | `payload.name` | `name` | **MAPPING REQUIRED (P1-1)** |
| `contentType: application/pdf` | `content_type` (4 Typen) | `payload.contentType` | `contentType` | **MAPPING REQUIRED (P1-1)** |
| `sizeBytes` (≥1) | `size` (≥0) | `payload.size` | `size` | **MAPPING REQUIRED (P1-1)** |
| `processingStatus: pending/ready/failed/deleted` | `pending/upload_pending/ready/delete_failed/error` | `payload.processingStatus` | `processingStatus` | **INCOMPATIBLE (P1-1)** |
| `metadata.pageCount/language` | `metadata` (untypisiert) | `payload.metadata` | `metadata` | **MAPPING REQUIRED (P1-1)** |
| `createdAt` / `updatedAt` | gleich | `payload.*` | gleich | IDENTISCH |
| `version` | Item-`version` | `version` | `version` | IDENTISCH |

### 3.2 ManualSearchProfileV1 → RIS ManualSearchProfile (R03)

| Jobsearch v1 | RIS-Contract | Persistenz | API-Antwort | Klassifikation |
|---|---|---|---|---|
| `schemaVersion: 1` | `"v1"` | `payload.schemaVersion` | `"v1"` | **INCOMPATIBLE (P0-1)** |
| `manualSearchProfileId` | `manual_profile_id` | `payload.manualProfileId` | `manualSearchProfileId` (Alias) | **LOSSLESS ALIAS** |
| `name` | `name` | `payload.name` | `name` | IDENTISCH |
| `description` | `description` | `payload.description` | `description` | IDENTISCH |
| `origin: manual` | `origin` | `payload.origin` | `origin` | IDENTISCH |
| `searchConfig.skills` | — | — | — | **INCOMPATIBLE (P0-2)** |
| `searchConfig.targetRoles` | `roles` | `payload.matchingPreferences.roles` | `matchingPreferences.roles` | **MAPPING REQUIRED** |
| `searchConfig.city` | `locations[]` | `...locations` | `...locations` | **MAPPING REQUIRED (Typ)** |
| `searchConfig.radiusKm` | — | — | — | **INCOMPATIBLE (P0-2)** |
| `searchConfig.workModes` | `work_modes` | `...workModes` | `...workModes` | IDENTISCH |
| `searchConfig.employmentTypes` | `employment_types` (Superset) | `...employmentTypes` | `...employmentTypes` | **MAPPING REQUIRED (P1-4)** |
| `matchingPreferences.requiredSkills` | `required_skills` | `...requiredSkills` | `...requiredSkills` | IDENTISCH |
| `matchingPreferences.preferredSkills` | `preferred_skills` | `...preferredSkills` | `...preferredSkills` | IDENTISCH |
| `matchingPreferences.excludedTerms` | `excluded_terms` | `...excludedTerms` | `...excludedTerms` | IDENTISCH |
| `createdAt` / `updatedAt` / `version` | gleich | gleich | gleich | IDENTISCH |

### 3.3 CVSearchProfileV1 → RIS CVSearchProfile (R01; R05-Ziel)

| Jobsearch v1 | RIS-Contract | Persistenz | API-Antwort | Klassifikation |
|---|---|---|---|---|
| `schemaVersion: 1` | `"v1"` | `payload.schemaVersion` | `"v1"` | **INCOMPATIBLE (P0-1)** |
| `searchProfileId` | `search_profile_id` | `payload.searchProfileId` | `searchProfileId` | LOSSLESS ALIAS |
| `cvId` | `cv_id` | `payload.cvId` | `cvId` | IDENTISCH |
| `name` | `name` | `payload.name` | `name` | IDENTISCH |
| `description` | — | — | — | **INCOMPATIBLE (P1-2)** |
| `origin: cv` | — | — | — | **INCOMPATIBLE (P1-2)** |
| `searchConfig` | `profile` + `search_configuration` (Dicts) | `payload.*` | Dicts | **INCOMPATIBLE (P0-2/P1-2)** |
| `createdAt` / `updatedAt` / `version` | gleich | gleich | gleich | IDENTISCH |

### 3.4 ATSSearchProfileV1 → RIS ATSSearchProfile (R01; R06-Ziel)

| Jobsearch v1 | RIS-Contract | Persistenz | API-Antwort | Klassifikation |
|---|---|---|---|---|
| `schemaVersion: 1` | `"v1"` | `payload.schemaVersion` | `"v1"` | **INCOMPATIBLE (P0-1)** |
| `atsSearchProfileId` | `ats_profile_id` | `payload.atsProfileId` | `atsProfileId` | LOSSLESS ALIAS |
| `searchProfileId` | `search_profile_id` | `payload.searchProfileId` | `searchProfileId` | IDENTISCH |
| `name` | `name` | `payload.name` | `name` | IDENTISCH |
| `targetRoles` | `target_roles` | `payload.targetRoles` | `targetRoles` | LOSSLESS ALIAS |
| `skills: string[]` | `skills: List[str]` | `payload.skills` | `skills` | IDENTISCH |
| `criteria` | `requirements/preferredCriteria/exclusions/…` | `payload.*` | `*` | **INCOMPATIBLE (P1-3)** |
| `createdAt` / `updatedAt` / `version` | gleich | gleich | gleich | IDENTISCH |

### 3.5 UserProfileV1

| Jobsearch v1 | RIS | Klassifikation |
|---|---|---|
| `userId`, `tenantId`, `email`, `status`, timestamps, version | bestehende `/me/profile`-Verwaltung | **NOT VERIFIED** (R05-nicht-Scope; kein Partner-Contract-DTO) |
| `nickname`, `firstName`, `lastName` | User-Profile-Domain vorhanden | **MAPPING REQUIRED** |

## 4. R03-Alias-Befunde (verifiziert durch Tests)

- `manualSearchProfileId` ↔ `manualProfileId`: **LOSSLESS ALIAS**. Die API
  liefert beide; die Persistenz nutzt `manualProfileId`.
- `searchConfig` ↔ `matchingPreferences`: **NICHT getrennt**. R03 hat die
  Suchfelder in `matchingPreferences` gefaltet. Das ist gegenüber dem
  Jobsearch-v1-Vertrag **nicht verlustfrei**:
  - `searchConfig.skills` (phrase-preserving String) hat kein Zielfeld.
  - `searchConfig.radiusKm` (nullable Zahl) hat kein Zielfeld.
  - `searchConfig.city` wird als Liste `locations` geführt.
  - `searchConfig.targetRoles` wird als `roles` geführt.
  - Die drei `matchingPreferences`-Felder (`requiredSkills`,
    `preferredSkills`, `excludedTerms`) sind dagegen **verlustfrei**.
- Ergebnis: **P0-2 data loss** für manuelle Profile; R05-CRUD wäre mit dem
  heutigen Modell ebenfalls verlustbehaftet.

## 5. CVSearchProfile-v1-Soll (für R05 verbindlich)

```json
{
  "schemaVersion": 1,
  "searchProfileId": "<uuid>",
  "cvId": "<uuid>",
  "name": "Cloud Engineering",
  "description": "optional",
  "origin": "cv",
  "searchConfig": {
    "skills": "AWS, Terraform, \"Cloud Architecture\"",
    "targetRoles": ["Cloud Engineer", "Solutions Architect"],
    "city": "Darmstadt",
    "radiusKm": 50,
    "workModes": ["remote", "hybrid"],
    "employmentTypes": ["full_time"]
  },
  "createdAt": "…",
  "updatedAt": "…",
  "version": 1
}
```

Regeln: `skills` ist ein phrase-erhaltender String (nicht auf Leerzeichen
splitten); `radiusKm` ist `10|25|50|100|null`; `employmentTypes` nur
`full_time|part_time`, `minItems: 1`; `workModes` dürfen leer sein; `city`
ist ein String (leer erlaubt). ATS überschreibt später `skills` und
`targetRoles`; `city`, `radiusKm`, `workModes`, `employmentTypes` kommen
weiterhin aus dem CV-Suchprofil.

## 6. Parent-/Delete-Regeln (SPECIFIED für R05/R06)

- `User → CVDocument → CVSearchProfile → ATSSearchProfile`; manuelle Profile
  bleiben unabhängig.
- Maxima: 10 CVs/User, 2 CVSearchProfiles/CV, 5 ATSSearchProfiles/Suchprofil;
  manuelle Profile **ohne** willkürliche Grenze.
- **CVSearchProfile mit ATS-Kindern:** DELETE → **409 Conflict**, keine
  Kaskade, keine persistenten Orphans.
- **CVDocument mit Suchprofilen:** DELETE → **409 Conflict**, bis eine
  definierte Lifecycle-/Kaskadenregel produktseitig entschieden ist.
- **Delete-vs-Create-Race:** Kind-Create und Eltern-Delete müssen atomar
  gegeneinander geprüft werden (z. B. `TransactWriteItems` mit
  `ConditionCheck` auf Eltern-Existenz/`version` bzw. Child-Count == 0 und
  einem `deleting`-Marker). Read-then-write ist nicht ausreichend.
- **R04-Integritätslücke (P1-5):** Der heutige `PartnerProfileRepository.delete`
  prüft **keine** Kinder. Solange R05 keine CVSearchProfiles erzeugt, gibt es
  keine Live-Orphans; **vor** Freischaltung der Kind-Routen muss der Guard
  ergänzt werden. Das ist eine harte R05-Vorbedingung, keine R04-Änderung in
  diesem Gate.

## 7. Session-/Identity-Abgrenzung

- Jobsearch-Session-Generation schützt den Browser vor späten lokalen Writes
  nach Benutzerwechsel (`ProfileSessionEndedError`).
- RIS darf das **nicht** mit einem serverseitigen Benutzerwechsel verwechseln:
  Jeder RIS-Request bindet die Identität aus dem verifizierten JWT des
  Requests (`sub`, Tenant, Partner, Issuer). Es gibt keinen Session-State,
  der eine autorisierte Server-Operation „abbrechen“ könnte.
- Serverseitige Operationen brauchen **Idempotenz** und **Ownership**,
  unabhängig vom Browser-Sessionzustand. R03/R04 erstellen bei jedem POST eine
  neue UUID; ein Retry erzeugt ein Duplikat. **P1-6:** `Idempotency-Key`
  (oder äquivalent) für Creates ist für R05/R06 vorzusehen.
- CV-Hashes sind **keine** persistente Identität; RIS nutzt serverseitige
  UUIDs. Keine erfundenen persistenten IDs.

## 8. Fixture-Ergebnisse

Synthetische Fixtures aus `origin/main@ad9b5ed` (keine echten Daten), in
`tests/test_partner_profile_contract_reconciliation.py` eingebettet:

| Fixture | Ergebnis |
|---|---|
| `profile.cv-search-profile.json` | `searchConfig` nicht abbildbar (skills/radius fehlen) → **P0-2** |
| `profile.create-cv-search-profile.json` | dito; `radiusKm: null` hat kein Zielfeld |
| `profile.roundtrip.json` | `targetRoles/workModes/employmentTypes` ja; `skills/radiusKm` nein |
| `profile.manual-search-profile.json` | `matchingPreferences` verlustfrei; `searchConfig` nicht |
| `profile.invalid-parent.json` | Parent-Validierung vorhanden (R02), aber v1-Shape fehlt |
| `profile.conflict-stale-version.json` | Version-Konflikt (409) vorhanden (R02/R03) |

## 9. Testnachweise

- Neu: `tests/test_partner_profile_contract_reconciliation.py` — **28/28 PASS**
  (Gap-Nachweise + bestehende Roundtrips + Kapazitäten + keine Agenten-/Modell-
  Kopplung).
- R01–R04-Regression: **312/312 PASS** (inkl. 28 Reconciliation, 273 R01–R04,
  11 Dokumente).
- `git diff --check`: PASS.
- Bekannte Umgebungsfehler (nicht R05-G0-bedingt): volle `tests/`-Suite wegen
  fehlendem `boto3` und präexistenten Windows-/Installer-Defekten unvollständig.

## 10. Konkrete Anforderungen für R05 und R06

**R05 (CVSearchProfile-CRUD):**
1. `SearchConfigurationV1` als eigenes Contract-Objekt einführen
   (`skills` string, `targetRoles[]`, `city`, `radiusKm`, `workModes[]`,
   `employmentTypes[]`) — additiv, keine konkurrierende DTO-Definition.
2. `CVSearchProfile` um `description`, `origin="cv"`, `searchConfig` erweitern.
3. `schemaVersion` auf integer `1` vereinheitlichen **oder** einen
   nachweislich verlustfreien v1-Adapter an der API-Grenze einführen
   (Entscheidung vor R05-Code).
4. CRUD unter `/v1/partner/me/cvs/{cvId}/search-profiles` mit 10/2/5-Grenzen,
   Version, Pagination, Isolationsprüfungen.
5. Delete-Guard: CVSearchProfile mit ATS-Kindern → 409; CVDocument mit
   Suchprofilen → 409; atomare Delete-vs-Create-Prüfung.
6. `Idempotency-Key` für Creates.

**R06 (ATSSearchProfile-CRUD):**
1. `criteria`-Shape (`schemaVersion: 1`, `requiredSkills`, `preferredSkills`,
   `excludedTerms`), keine Requirements/Scores/Modellausgaben persistieren.
2. ATS-Override-Semantik (Skills/Zielrollen) dokumentieren; Standort/Radius/
   Arbeitsmodell/Beschäftigung aus dem Suchprofil.
3. 5er-Grenze, Version, Parent-Chain-Validierung, Delete-Semantik.

## 11. Offene P0/P1-Findings

| ID | Schwere | Befund | Status |
|---|---|---|---|
| P0-1 | P0 | `schemaVersion` ist `"v1"` (String) statt `1` (Integer) in allen RIS-Ressourcen; strikte v1-Validierung schlägt fehl. | **OPEN** |
| P0-2 | P0 | `searchConfig` fehlt; `skills` und `radiusKm` haben kein Speicherfeld; `city`→`locations[]`, `targetRoles`→`roles`. Datenverlust gegenüber v1. | **OPEN** |
| P1-1 | P1 | CVDocument: `name`/`filename`, `size`/`sizeBytes`, Statuswert-Set, `contentType`-Breite weichen ab. | **OPEN** |
| P1-2 | P1 | CVSearchProfile: `description`, `origin`, `searchConfig` fehlen. | **OPEN** |
| P1-3 | P1 | ATSSearchProfile: `criteria` fehlt; abweichende Felder (`requirements`, …). | **OPEN** |
| P1-4 | P1 | `employmentTypes` erlaubt mehr Werte als der v1-Vertrag. | **OPEN** |
| P1-5 | P1 | R04-CV-Delete hat keinen Kind-Guard; latente Orphan-Lücke für R05. | **OPEN (R05-Vorbedingung)** |
| P1-6 | P1 | Create-Idempotenz fehlt; Retry erzeugt Duplikate. | **OPEN** |

## 12. Klassifikation

- **IMPLEMENTED:** R01–R04 (unverändert); neuer Reconciliation-Test.
- **VERIFIED:** 312/312 R01–R05-G0-Tests; Jobsearch-`origin/main` = `ad9b5ed`;
  Matrix und Gap-Nachweise.
- **SPECIFIED:** CVSearchProfile-v1-Soll, Parent-/Delete-Regeln, R05/R06-
  Anforderungen, Session-/Idempotenz-Anforderungen.
- **OPEN:** P0-1, P0-2, P1-1…P1-6.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
- **R05 CRUD: BLOCKED** bis P0-1 und P0-2 entschieden/umgesetzt sind
  (Contract-Entscheidung + additive Modellierung; keine R03-Codeänderung in
  diesem Gate).
