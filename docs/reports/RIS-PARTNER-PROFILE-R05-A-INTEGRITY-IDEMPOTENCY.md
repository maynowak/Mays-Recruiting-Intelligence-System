# RIS-PARTNER-PROFILE-R05-A — PARENT INTEGRITY & CREATE IDEMPOTENCY

## 1. Git-Baseline

- Branch: `feature/ris-partner-profile-persistence-v1`
- Basis: `18814ad` (R05-P0)
- 39 untracked Dateien unverändert.
- Jobsearch-Referenz: `origin/main@ad9b5ed` (read-only, unverändert).

## 2. P1-5 — Elternintegrität

### Semantik

- Ein `CVDocument` mit vorhandenen `CVSearchProfile`-Kindern wird **nicht**
  gelöscht → **409**.
- Ein `CVSearchProfile` mit vorhandenen `ATSSearchProfile`-Kindern wird
  **nicht** gelöscht → **409**.
- Keine Kaskadenlöschung; keine persistenten Orphans.
- Alle Prüfungen laufen innerhalb des authentifizierten
  Benutzer-/Tenant-/Partner-/Issuer-Kontexts.

### Atomarer Mechanismus

Statt `ListChildren()` vor `Delete` werden die **bestehenden Kapazitätszähler**
als atomare Child-Guards verwendet:

- `capacity#CVSP#<cvId>` zählt die Suchprofile eines CV.
- `capacity#ATS#<searchProfileId>` zählt die ATS-Kinder eines Suchprofils.

Child-Create (Transaktion, je Item genau eine Aktion):

1. `Put` Idempotenznachweis (optional, eigener Key)
2. `Update` Child-Zähler (`count < max`)
3. `ConditionCheck` Elternressource (`attribute_exists` + `userId`/`tenantId`)
4. `ConditionCheck` Lifecycle-Guard (`attribute_not_exists OR state = active`)
5. `Put` Kindressource

Parent-Delete:

- **CVSearchProfile / ManualSearchProfile (ohne S3):** eine Transaktion mit
  `Delete` Ressource + `Update` Elternzähler + `ConditionCheck` Child-Zähler
  (`attribute_not_exists OR count = 0`).
- **CVDocument (mit S3):** zweiphasig:
  - Phase A `reserve_parent_delete`: `Update` Lifecycle-Guard
    (`lifecycle#CVDocument#<cvId>` → `state = deleting`) +
    `ConditionCheck` Elternressource + `ConditionCheck`
    `capacity#CVSP#<cvId> == 0`.
  - Phase B: S3-Delete (nur nach erfolgreicher Phase A).
  - Phase C `finalize_parent_delete`: `Delete` Ressource + `Update` CV-Zähler +
    `Delete` Guard + `ConditionCheck` Child-Zähler.

### Race-Verhalten

DynamoDB serialisiert Transaktionen. Für konkurrierendes Child-Create und
Parent-Delete gilt:

- Gewinnt das Child-Create, steht der Child-Zähler auf 1; der Delete-Reserve
  scheitert an `count = 0` → **409**, S3 bleibt unangetastet.
- Gewinnt der Delete-Reserve, steht der Guard auf `deleting`; das Child-Create
  scheitert am Guard-ConditionCheck → **409**.
- Beide können nie gleichzeitig erfolgreich sein; es entsteht kein Orphan.

Der Guard ist der „äquivalente Sperrmechanismus“ zum DELETING-Zwischenzustand:
- S3-Fehler in Phase B → `release_parent_delete` setzt den Guard auf `active`
  zurück (Metadaten bleiben erhalten, 502).
- Fehler in Phase C → Guard bleibt `deleting`; ein Retry reserviert erneut
  (`state IN (active, deleting)`) und setzt Phase C fort.
- Es wird nie `physicalPurge = true` behauptet.

### S3-Reihenfolge

Die Kindprofil-Sperre ist **vor** jedem S3-Zugriff entschieden. Bei 409 wird S3
nicht berührt. Ein S3-Löschfehler bleibt als `502` mit
`metadataRetained=true` klassifiziert.

## 3. P1-6 — Create-Idempotenz

- Optionaler `Idempotency-Key` (Header, 1–200 Zeichen) im Repository und in den
  bestehenden POST-Handlern (Manual-Profile/CV). Keine neuen Routen.
- Idempotenzschlüssel = `idem#<resourceType>#SHA256(user|tenant|partner|issuer|key)`.
  Die Identität ist Teil des Digests → keine Cross-User-/Tenant-/Partner-/
  Issuer-Kollision. Der Rohschlüssel wird nicht gespeichert.
- Payload-Fingerprint = SHA-256 der kanonisierten Ressource ohne eigene ID,
  `createdAt`, `updatedAt`, `schemaVersion`.
- Eine Transaktion koppelt atomar: Idempotenz-`Put`, Kapazitäts-`Update`,
  Parent-/Guard-`ConditionCheck`, Ressourcen-`Put`.
- Replay (gleicher Key, gleicher Payload) → der ursprüngliche `targetResourceId`
  wird zurückgegeben; es entsteht keine zweite Ressource und keine doppelte
  Kapazitätsbelegung.
- Gleicher Key, anderer Payload → **409** (`Idempotency key reused with a
  different payload`).
- Lebensdauer: **24 h**. Der `Put`-Condition erlaubt nach Ablauf
  (`expiresAt < now`) eine Wiederverwendung. DynamoDB-TTL auf `expiresAt` ist
  nur Cleanup; die Korrektheit liegt im Condition.
- Keine automatische Retry-Logik ohne Schlüssel.

## 4. Legacy-Schutz

- `legacyIncomplete` und `metadata.legacy` bleiben beim Update erhalten (der
  Handler übernimmt `existing.metadata`).
- Ein Update ohne `searchConfig` überschreibt die bestehende (ggf.
  unvollständige) Legacy-Konfiguration nicht; die v1-Write-Regeln gelten nur für
  neue Creates und explizit gelieferte `searchConfig`.
- Es werden keine fehlenden Werte erfunden; unvollständige Legacy-Records
  bleiben unvollständig und werden nicht als vollständig normalisiert
  ausgegeben. Keine AWS-Datenmigration.

## 5. Terraform / IAM / OpenAPI

- `partner_profiles`: TTL auf `expiresAt` (Cleanup der Idempotenznachweise).
- Lambda-IAM für `partner_profiles`: `UpdateItem` und `TransactWriteItems`
  ergänzt (waren für die vorhandenen Transaktionen/Guard-Updates nötig).
- OpenAPI: optionaler `Idempotency-Key`-Header an den beiden bestehenden
  POST-Operationen dokumentiert; keine neuen Routen.
- `terraform fmt -check` (versioniert): PASS; `validate`: PASS
  (vorbestehende Deprecation-Warnings). OpenAPI-Konsistenz: 47/47 PASS.

## 6. Tests

Neu: `tests/test_partner_profile_integrity_idempotency.py` — **16/16 PASS**:

1. CV ohne Kinder löschbar.
2. CV mit CVSearchProfile → 409.
3. Child-Create vs. CV-Delete (10 Iterationen; genau einer gewinnt).
4. Kein Orphan (Invariante Eltern↔Kind).
5. S3 unangetastet bei 409.
6. S3-Löschfehler → 502 + Metadaten + Guard `active` + Retry erfolgreich.
7. Wiederholtes Delete → 404.
8. Delete mit ATS-Kind → 409.
9. Je Transaktion keine doppelte Item-Aktion.
10. Idempotenter Create.
11. Identischer Retry → gleiche ID.
12. Gleicher Key, anderer Payload → 409.
13. Retry nach simuliertem Timeout.
14. Keine doppelte Kapazität.
15. Gleicher Key in anderem Benutzerkontext isoliert.
16. Abgelaufener Key wiederverwendbar; Legacy-Incomplete bleibt erhalten.

R01–R05-A-Regression: **347/347 PASS** (331 bisher + 16 neu).
Der In-Memory-Fake serialisiert Transaktionen per Lock; das belegt die
Transaktionslogik, **nicht** echtes DynamoDB-Concurrency. Echte
DynamoDB-Integration bleibt für **R07** vorgemerkt.

## 7. Verbleibende P1-Findings

| ID | Befund | Status |
|---|---|---|
| P1-5 | Elternintegrität / Delete-vs-Create-Race | **RESOLVED (Logik/Unit)** |
| P1-6 | Create-Idempotenz | **RESOLVED (Logik/Unit)** |
| P1-1 | CVDocument-Naming/Status (`filename`/`name`, `sizeBytes`/`size`, Status-Set) | OPEN |
| P1-2 | CVSearchProfile `description`/`origin`/`searchConfig` (R05-CRUD) | OPEN |
| P1-3 | ATS `criteria`-Shape (R06) | OPEN |

## 8. Klassifikation

- **IMPLEMENTED:** Child-Guard-ConditionChecks, Lifecycle-Guard, zweiphasiger
  CV-Delete, Idempotenz-Transaktion, TTL/IAM, OpenAPI-Header.
- **VERIFIED:** 347/347 Tests; Terraform fmt/validate; OpenAPI 47/47.
- **NOT RUN:** echte DynamoDB-/S3-Integration (R07).
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
- **R05-CRUD-Vorbereitung:** P1-5 und P1-6 sind als Logik/Unit abgeschlossen;
  R05-CVSearchProfile-CRUD kann darauf aufsetzen. P1-2 (CVSearchProfile-Shape)
  bleibt Teil von R05.
