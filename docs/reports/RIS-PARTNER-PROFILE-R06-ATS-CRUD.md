# RIS-PARTNER-PROFILE-R06 — ATS SEARCH PROFILE CRUD

## 1. Git-Stand

- Branch: `feature/ris-partner-profile-persistence-v1`
- Basis: `be2b9e2` (R06-G0)
- 39 untracked Dateien unverändert.
- Jobsearch-Referenz: `origin/main@0129559`. **Korrektur:** `excludedTerms`
  ist in `contractTypes.ts` am Referenzcommit enthalten; der frühere
  R06-G0-Befund war eine abgeschnittene Ausgabe und ist berichtigt. Keine
  Jobsearch-Änderung.

## 2. Kanonisches ATS-v1-Modell

```json
{
  "schemaVersion": 1,
  "atsSearchProfileId": "<server-uuid>",
  "searchProfileId": "<parent-cvsp-id>",
  "name": "DevOps ATS variant",
  "targetRoles": ["DevOps Engineer"],
  "skills": ["Terraform", "Cloud Architecture"],
  "criteria": {
    "schemaVersion": 1,
    "requiredSkills": ["Terraform"],
    "preferredSkills": [],
    "excludedTerms": ["night shift"]
  },
  "createdAt": "…",
  "updatedAt": "…",
  "version": 1
}
```

- `schemaVersion` ist Integer `1`.
- `atsSearchProfileId` ist die serverseitige ID; intern bleibt
  `atsProfileId` als verlustfreier Alias erhalten.
- `searchProfileId` ist Pflicht-Parent; `null` wird abgelehnt.
- `cvId` ist **nicht** Teil des v1-DTOs; es wird serverseitig aus dem Parent
  abgeleitet und intern gespeichert.
- `criteria` ist optional; die API-Antwort enthält es nur, wenn gesetzt.
- Legacy-Felder (`atsKeywords`, `requirements`, `preferredCriteria`,
  `exclusions`, `location`, `radius`, `workMode`) werden nicht in der
  v1-Antwort ausgegeben, bleiben aber intern erhalten.

## 3. ATSCriteriaV1 — Validierung

- `criteria` darf fehlen.
- Wenn vorhanden: `schemaVersion` ist Pflicht und muss Integer `1` sein
  (`"v1"`, `2`, `True` werden abgelehnt).
- `requiredSkills`/`preferredSkills`/`excludedTerms` sind optional; leere
  Arrays sind gültig; Einträge sind nicht-leere Strings; Reihenfolge bleibt,
  case-insensitive Duplikate werden entfernt.
- Unbekannte Felder werden abgelehnt (`additionalProperties: false`).
- Score-/Modellfelder (`overallScore`, `atsScore`, `matchScore`,
  `modelExplanation`, `evidence`, `modelResponse`, `prompts`, …) werden
  abgelehnt und nie persistiert.
- `criteria` ist strikt von `MatchingPreferencesV1` getrennt.

**Update-Semantik:**
- `criteria` fehlt → bestehende Kriterien bleiben unverändert.
- `criteria: null` → Kriterien werden explizit entfernt.
- `criteria: {schemaVersion:1, requiredSkills:[...]}` → die genannte Liste wird
  geändert, nicht genannte Listen bleiben erhalten.
- Explizite leere Liste (`[]`) leert genau diese Liste.

## 4. Legacy-Mapping

| Legacy | Kanonisch | Regel |
|---|---|---|
| `atsProfileId` | `atsSearchProfileId` (API) | Alias; interne ID unverändert |
| `cvId` | — (nicht im v1-DTO) | serverseitig aus Parent-CVSP abgeleitet |
| `requirements` | `criteria.requiredSkills` | verlustfrei; Rohdaten in `metadata.legacy` |
| `preferredCriteria` | `criteria.preferredSkills` | verlustfrei; Rohdaten in `metadata.legacy` |
| `exclusions` | `criteria.excludedTerms` | verlustfrei; Rohdaten in `metadata.legacy` |
| `atsKeywords`, `location`, `radius`, `workMode` | nicht v1 | intern erhalten, nicht ausgeliefert |
| `schemaVersion: "v1"` | `1` | lesend normalisiert |

Legacy-Records bleiben lesbar; `metadata.legacyIncomplete` markiert
unvollständige Migrationen. Keine AWS-Datenmigration.

## 5. Eltern- und Eigentümerisolation

Jede Operation prüft die Kette
`ATS → CVSearchProfile → CVDocument → verifizierter Benutzer`:

- Parent muss ein `CVSearchProfile` sein (ManualSearchProfile → 404).
- Parent und CV müssen zum selben User/Tenant/Partner/Issuer gehören.
- Die URL-`searchProfileId` muss mit `ats.searchProfileId` übereinstimmen.
- Cross-User → 404, Cross-Tenant → 403, Cross-Partner → 403,
  Cross-Issuer → 404.
- Client-seitige Identitätsfelder → 400.
- Fehlende Authentifizierung → 401.

## 6. Fünf API-Routen

| Methode | Pfad | Erfolg |
|---|---|---|
| GET | `/v1/partner/me/search-profiles/{searchProfileId}/ats-profiles` | 200 |
| POST | `/v1/partner/me/search-profiles/{searchProfileId}/ats-profiles` | 201 |
| GET | `…/{atsSearchProfileId}` | 200 |
| PUT | `…/{atsSearchProfileId}` | 200 |
| DELETE | `…/{atsSearchProfileId}` | 204 |

Explizit in Terraform, Human-JWT-Authorizer, kein Wildcard-Proxy.

## 7. Kapazität, Idempotenz, Versionierung, Delete

- Maximal **5** ATS-Kinder je CVSearchProfile; atomar über
  `capacity#ATS#<searchProfileId>` (R05-A).
- Sechstes Create → 409; parallele Creates auf dem letzten Platz → genau ein
  Erfolg.
- 24-h-Idempotenz (R05-A): identischer Retry → gleiche `atsSearchProfileId`;
  anderer Payload → 409; keine doppelte Kapazitätsbelegung.
- Update/Delete versioniert; stale Version → 409.
- Delete dekrementiert den Child-Zähler atomar; Kapazität wird wieder frei.
- Parent-Delete (CVSearchProfile) mit ATS-Kindern → 409; keine Kaskade.
- Delete-vs-Create bleibt atomar; keine Orphans/Counter-Drift.
- Keine Reassignment-API; kein persistenter `null`-Parent.

## 8. Session-Unassigned vs. RIS-v1

Jobsearch hält unzugeordnete ATS-Einträge session-only
(`searchProfileId = null`, `listUnassigned`/`assignUnassigned`). RIS-v1
verlangt immer einen Parent. RIS importiert keine unassigned Session-Daten,
bietet kein Reassignment und ändert das Jobsearch-Session-Verhalten nicht.
Eine spätere Session-to-Remote-Migration muss vor dem ATS-Create einen
gültigen Parent festlegen.

## 9. ATS-Override-Semantik

| Feld | Quelle bei ATS-Suche |
|---|---|
| skills | ATS-Kind |
| targetRoles | ATS-Kind |
| city / radiusKm / workModes / employmentTypes | Parent |

RIS speichert beide Ebenen getrennt; der Parent wird durch ATS-CRUD nicht
verändert; keine kombinierte Suchkonfiguration wird persistiert; keine
Job-Suche/Modellaufrufe.

## 10. Jobsearch-Fixture-Kompatibilität

Die synthetischen Fixtures (`profile.ats-search-profile.json`,
`profile.create-ats-search-profile.json`, `profile.update-ats-search-profile.json`,
`profile.invalid-ats-criteria.json`) sind eingebettet getestet:

- Create-Fixture → 201 mit identischen Client-Feldern inkl. `criteria`.
- Vollständige ATS-Fixture → `ATSSearchProfile.from_dict` (mit injizierter
  Server-Identität) roundtrip-fähig.
- Invalid-Criteria-Fixture (`overallScore`, `modelExplanation`) → abgelehnt.

## 11. Tests und Regression

Neu: `tests/test_partner_ats_profiles_api.py` — **36/36 PASS** (CRUD, v1-Shape,
no `cvId`, criteria absent/three/empty/merge/removal, unknown/score/version
rejection, fixture roundtrip, parent/security, 5-capacity, concurrency,
idempotency, stale version, delete capacity, parent-delete 409, race/no-orphan,
counter drift, legacy record).

R06-G0-Contract-Tests: **alle 9 früheren PLANNED-Fälle sind jetzt echte
Tests** (keine Skips mehr). Die Datei `tests/test_partner_profile_ats_contract_gate.py`
enthält zusätzlich die Criteria-/Legacy-/API-Shape-Tests.

Regression: **437 passed, 0 skipped** (R01–R06 inkl. Partner-Security,
OpenAPI). Keine In-Memory-Fake-Aussage als echte DynamoDB-Integration.

## 12. Terraform / OpenAPI

- 5 explizite Routen in `terraform/modules/api/main.tf`.
- `docs/api/API-STANDARD.md` und `docs/api/openapi-platform.yaml` ergänzt:
  `ATSSearchProfileV1`, `ATSCriteriaV1`, `ATSProfileInput`, 5 Pfade,
  `Idempotency-Key` am POST, Fehlerantworten.
- `terraform fmt -check` (versioniert): PASS; `validate`: PASS
  (vorbestehende Deprecation-Warnings). OpenAPI-Konsistenz: 47/47 PASS.
- Keine neue Tabelle, keine S3-Änderung, kein neues IAM.

## 13. Verbleibende Findings

| ID | Befund | Status |
|---|---|---|
| P1-1 | CVDocument `filename`/`name`, `sizeBytes`/`size`, Status-Set | OPEN; keine ATS-Abhängigkeit (ATS nutzt `cv_id`) |
| P1-3 | ATS `criteria`/`atsSearchProfileId`/`cvId`-API | **RESOLVED (R06)** |
| Ref-1 | `excludedTerms` in `contractTypes.ts` | **CLOSED — war korrekt vorhanden** |

## 14. R07-Integrationsbedarf

- Echte DynamoDB-Transaktionen/GSI (Parent-Guard, 5er-Zähler,
  Delete-vs-Create) und Conditional-Write-Verhalten.
- Live-HTTP-Smoke gegen API Gateway mit Dual-Auth.
- S3/CV-E2E bleibt separat.

## 15. Klassifikation

- **IMPLEMENTED:** ATSCriteriaV1, ATS-v1-API-Shape, 5 CRUD-Routen,
  Parent-/Owner-Kette, 5er-Kapazität, Idempotenz, Versionierung,
  Delete-Schutz, Terraform, OpenAPI.
- **VERIFIED:** 437/437 Tests; Terraform fmt/validate; OpenAPI 47/47.
- **OPEN:** P1-1 (CVDocument-Naming/Status).
- **NOT RUN:** echte DynamoDB-/S3-Integration (R07); volle `tests/`-Suite
  wegen fehlendem boto3 / präexistenten Windows-/Installer-Fehlern.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
