# RIS-PARTNER-PROFILE-R06-G0 — ATS CONTRACT & PARENT SEMANTICS GATE

## 1. RIS-Baseline

- Branch: `feature/ris-partner-profile-persistence-v1`
- HEAD: `ae4eb99` (R05-B)
- Working Tree: tracked clean; 39 untracked Dateien unverändert.
- Keine Produktionsdatei in diesem Gate geändert (nur Tests + Dokumentation).

## 2. Jobsearch-Referenzstand

- `origin/main`: **`0129559`** (`docs: record cache audit commit`).
- Der genannte Stand `c6137b3` existiert; seitdem wurden nur
  Session-Kapazitätsaussagen in `docs/contracts/*` präzisiert (2 CV-Profile,
  5 ATS, Grandfathering) — **keine Änderung der ATS-Datenshape**.
- ATS-relevant gelesen: Data Contract, Repository Contract, JSON Schema,
  Fixtures, `cvSearchConfig.ts`, `contractTypes.ts`, `profileValidation.ts`,
  `sessionRepositories.ts`, `cvProfileStore.ts`, JM-ATS-UNASSIGNED-UX-08,
  JM-ATS-OVERLAY-PARITY-08A, JM-GUEST-CV-E2E-09/09A.
- **Korrektur (R06):** Der frühere Befund, `contractTypes.ts` lasse
  `excludedTerms` aus, war falsch (abgeschnittene Ausgabe). Am Referenzcommit
  `0129559` enthält `ATSCriteriaV1` in `contractTypes.ts` **alle drei** Listen
  inklusive `excludedTerms`. Es besteht **keine** Referenz-Inkonsistenz; keine
  Jobsearch-Änderung nötig.

## 3. ATSSearchProfileV1 — Feldmatrix

| Jobsearch v1 | RIS-Contract (Ist) | Persistenz | Geplante API-Antwort | Klassifikation |
|---|---|---|---|---|
| `schemaVersion: 1` | `schema_version: 1` | `payload.schemaVersion` | `1` | IDENTICAL |
| `atsSearchProfileId` | `ats_profile_id` | `payload.atsProfileId` | `atsSearchProfileId` | LOSSLESS MAPPING (Rename im API-Serializer) |
| `searchProfileId` | `search_profile_id` | `payload.searchProfileId` | `searchProfileId` | IDENTICAL |
| `name` | `name` | `payload.name` | `name` | IDENTICAL |
| `targetRoles: string[]` | `target_roles` | `payload.targetRoles` | `targetRoles` | IDENTICAL |
| `skills: string[]` | `skills` | `payload.skills` | `skills` | IDENTICAL |
| `criteria?` | **fehlt** | — | — | **INCOMPATIBLE (P1-3)** |
| `createdAt/updatedAt/version` | vorhanden | payload/Item | vorhanden | IDENTICAL |
| (kein `cvId` in v1) | `cv_id` (Pflicht) | `payload.cvId` | **nicht ausgeben** | INCOMPATIBLE (Legacy-Feld; aus Parent ableiten) |
| — | `atsKeywords`, `requirements`, `preferredCriteria`, `exclusions`, `location`, `radius`, `workMode` | payload | **nicht ausgeben** | Legacy (nicht v1) |

**Befund:** Das aktuelle RIS-Modell kann die v1-Fixture **nicht** strikt
parsen: `atsSearchProfileId` und `criteria` sind unbekannte Felder; `ATSSearchProfile.to_dict()`
emittiert `atsProfileId` und `cvId`. R06 muss `criteria` modellieren, die
API-Antwort auf `atsSearchProfileId` mappen und `cvId`/Legacy-Felder aus der
v1-Antwort entfernen.

## 4. ATSCriteriaV1 — Soll und Validierung

```typescript
interface ATSCriteriaV1 {
  schemaVersion: 1;
  requiredSkills?: string[];
  preferredSkills?: string[];
  excludedTerms?: string[];
}
```

Verbindliche Regeln für R06:

1. `criteria` darf vollständig fehlen.
2. Wenn vorhanden: `schemaVersion` ist Pflicht und muss Integer `1` sein.
3. Die drei Listen sind optional; leere Arrays sind gültig.
4. Unbekannte Felder werden abgelehnt (`additionalProperties: false`).
5. Score-/Modellfelder (`overallScore`, `atsScore`, `matchScore`,
   `modelExplanation`, `evidence`, `modelResponse`, `prompts`, …) werden
   abgelehnt und nie persistiert.
6. Phrasen bleiben vollständige Strings (kein Whitespace-Split).
7. `criteria` wird nicht mit `MatchingPreferencesV1` vermischt.

Das Fixture `profile.invalid-ats-criteria.json` (mit `overallScore` und
`modelExplanation`) ist der Negativfall.

## 5. Parent-/Owner-Hierarchie

```text
User
└── CVDocument (max 10)
    └── CVSearchProfile (max 2/CV)
        └── ATSSearchProfile (max 5/Suchprofil)
```

Vorhandene R05-A-Mechanismen (wiederverwendbar):

- Child-Create-Transaktion: `Update` des Child-Zählers
  (`capacity#ATS#<searchProfileId>`, `count < 5`) + `ConditionCheck` auf die
  Elternressource (`attribute_exists` + `userId`/`tenantId`) + `ConditionCheck`
  auf den Lifecycle-Guard (`attribute_not_exists OR state = active`) + `Put`.
- Parent-Delete: `ConditionCheck` auf den ATS-Zähler == 0; keine Kaskade.
- Delete-vs-Create: genau eine Transaktion gewinnt; kein Orphan.
- Versionierung: `version` + bedingtes Update/Delete.
- Max. eine Aktion pro Item pro Transaktion.

Die ATS-Create-Transaktion prüft die **direkte** Eltern-CVSearchProfile. Die
Großeltern-Kette (`cvId`) wird über `validate_ats_assignment` (ATS `cv_id` ==
Parent-`cv_id`) und die beim CVSP-Create geprüfte CV-Eigentümerschaft
abgesichert. R06 muss `cv_id` serverseitig aus dem Parent ableiten und darf es
nicht aus dem Client-Body übernehmen.

## 6. 5er-Kapazität

- `CAPACITY_RULES["ATSSearchProfile"] == 5`, Zähler
  `capacity#ATS#<searchProfileId>`, atomar über `TransactWriteItems`.
- Parallele Creates auf dem letzten Platz: genau eine Transaktion gewinnt
  (Unit-/Fake-Nachweis; echte DynamoDB-Integration → R07).

## 7. Session-Unassigned vs. RIS-Persistenz

| Aspekt | Jobsearch-Session | RIS v1 |
|---|---|---|
| Parent bei CVSP-Delete | `searchProfileId = null`, ATS bleibt sichtbar | **nicht erlaubt** |
| Reassignment | `assignUnassigned` im Session-Adapter | **keine API ohne Vertrag** |
| Kaskade | keine | keine |
| CVSP mit ATS-Kindern löschen | Session erlaubt Detach | **409** |
| Persistenz unassigned | — | **abgelehnt** (Parent obligatorisch) |

Der aktuelle RIS-Contract erzwingt bereits einen nicht-leeren
`search_profile_id`; ein persistenter `null`-Parent wird abgelehnt. Ein späterer
Session-to-Remote-Adapter muss vor dem Speichern eines unassigned ATS einen
gültigen Ziel-Parent verlangen. Keine RIS-Reassignment-API in R06.

## 8. ATS-Override-Semantik

`cvSearchConfig.ts` (`buildCvSearchProfile`):

| Feld | Quelle |
|---|---|
| `skills` | ATS-Kind (`ats.skills.join(', ')`) |
| `targetRoles` | ATS-Kind |
| `city`, `radiusKm`, `workModes`, `employmentTypes` | CVSearchProfile (Parent) |

RIS speichert beide Ebenen getrennt und erzeugt im CRUD **keine** kombinierte
Suchkonfiguration. ATS-`skills` bleiben ein Phrase-Array; `targetRoles` bleibt
ein Array (keine Reduktion auf eine Rolle); der Parent bleibt unverändert.

## 9. Vorgeschlagene R06-HTTP-Routen

```text
GET    /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles
POST   /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles
GET    /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/{atsSearchProfileId}
PUT    /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/{atsSearchProfileId}
DELETE /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/{atsSearchProfileId}
```

Die flache Parent-Adressierung ist mit RIS vereinbar: `searchProfileId` ist die
CVSP-ID (global eindeutig), der Pfad kollidiert nicht mit
ManualSearchProfile-IDs, und der CV wird serverseitig über
`CVSearchProfile.cv_id` abgeleitet. Der bestehende Dual-Auth-Kontext bleibt
maßgeblich. Alternativ wäre eine verschachtelte CV-Route möglich, aber nicht
nötig; die flache Form entspricht dem Jobsearch-Repository-Vertrag
(`list(searchProfileId)`).

Statuscodes: 201 Create, 200 Get/List/Update, 204 Delete, 400/422 Validierung,
401/403 Auth, 404 fehlend/fremd, 409 Version/Kapazität/Parent/Idempotenz.

## 10. Wiederverwendbare RIS-Funktionen

- `PartnerProfileRepository.create/get/list_by_parent/update/delete`
- R05-A Parent-Guard, Child-Zähler, Delete-vs-Create-Schutz
- R05-A 24-h-Idempotenz (`Idempotency-Key`)
- R03/R04/R05-B Dual-Auth-Kontext (`_partner_profile_context`)
- `validate_ats_assignment` (Parent-/CV-Kettenprüfung)
- `_decode_cursor`/`_encode_cursor`, `_partner_profile_error`

## 11. Idempotenz und Versionierung

- 24-h-Idempotenz aus R05-A ist wiederverwendbar; der Key wird je
  ResourceType/Identität gebildet, sodass ATS- und CVSP-Keys nicht kollidieren.
- Identischer Retry → gleiche `atsSearchProfileId`; anderer Payload → 409.
- Versionierte Updates/Deletes; stale Version → 409.
- Keine zweite Kapazitäts-/Idempotenzarchitektur.

## 12. Testnachweise

Neu: `tests/test_partner_profile_ats_contract_gate.py` — **20 PASS, 9 PLANNED
(skipped)**.

PASS (Ist-Zustand + vorhandene Mechanik):

- Integer-`schemaVersion`, Pflicht-Parent, unassigned/null-Parent abgelehnt.
- Aktuelles Modell ohne `criteria`, mit `cvId`/`atsProfileId`/Legacy-Feldern.
- Striktes Parsen der v1-Fixture wird abgelehnt (Gap-Nachweis).
- 5er-Kapazität, Parent-Existenz, CV-Kettenprüfung, Parent-Guard,
  Delete-Sperre bei ATS-Kindern, Delete-vs-Create ohne Orphan,
  Cross-User-Isolation.
- ATS-Override-Semantik (Skills/Rollen vom Kind, Rest vom Parent, Parent
  unverändert).

PLANNED (skipped, R06): v1-Fixture-Roundtrip, `criteria` (fehlend/drei Listen/
leer/quoted), Ablehnung unbekannter/Score-/Modellfelder, unbekannte
Schema-Version, v1-Antwort ohne `cvId`.

Regression: **394 passed, 9 skipped** (R01–R06-G0 inkl. Partner-Security und
OpenAPI). Terraform/OpenAPI unverändert.

## 13. Offene P0/P1-Findings

| ID | Befund | Status |
|---|---|---|
| P1-3 | `ATSCriteriaV1`/`criteria` fehlt; `atsSearchProfileId`/`cvId`-API-Mapping fehlt. | **OPEN — R06-Blocker** |
| P1-1 | CVDocument `filename`/`name`, `sizeBytes`/`size`, Status-Set. | OPEN; **keine direkte ATS-Abhängigkeit** (ATS nutzt `cv_id`, nicht Dateiname/Größe/Status) |
| Ref-1 | `contractTypes.ts` enthält `excludedTerms` (R06-Korrektur; früherer Befund war falsch). | **CLOSED — keine Inkonsistenz** |

## 14. Konkreter R06-Implementierungsumfang

1. `ATSCriteria`-Dataclass + `criteria` in `ATSSearchProfile` (optional,
   strikt, `schemaVersion: 1`, drei Listen, keine Score-/Modellfelder).
2. API-Serializer: `atsSearchProfileId` (statt `atsProfileId`), immer
   `targetRoles`/`skills` als Arrays, `criteria` nur wenn vorhanden, **kein**
   `cvId`/Legacy-Felder.
3. Handler: `cv_id` serverseitig aus dem Parent-CVSP ableiten; Parent-/
   Großeltern-Kette prüfen; 5er-Kapazität; Idempotenz; Versionierung.
4. Fünf explizite Terraform-Routen + Human-JWT-Authorizer.
5. OpenAPI: `ATSSearchProfileV1`, `ATSCriteriaV1`, `ATSProfileInput`,
   5 Pfade, `Idempotency-Key` am POST.
6. Delete: ATS hat keine Kinder; CVSP-Delete bleibt bei ATS-Kindern 409.
7. Tests: die 9 PLANNED-Fälle plus CRUD/Security/Concurrency.

## 15. R07-Integrationsbedarf

- Echte DynamoDB-Transaktions-/GSI-Integration (Parent-Guard, 5er-Zähler,
  Delete-vs-Create).
- Live-HTTP-Smoke gegen API Gateway mit Dual-Auth.
- S3/CV-E2E bleibt separat.

## 16. Klassifikation

- **IMPLEMENTED:** R01–R05-B (unverändert); R06-G0-Testmodul.
- **VERIFIED:** 394 passed, 9 skipped; Jobsearch `origin/main` = `0129559`;
  ATS-Fixtures gelesen.
- **SPECIFIED:** ATSCriteriaV1-Soll, Parent-/Owner-Regeln, Unassigned-
  Abgrenzung, Override-Semantik, R06-Routen, R06-Implementierungsumfang.
- **OPEN:** P1-3 (ATS-Criteria/API-Mapping), P1-1 (CV-Naming/Status), Ref-1.
- **NOT RUN:** echte DynamoDB-/S3-Integration (R07); volle `tests/`-Suite
  wegen fehlendem boto3 / präexistenten Windows-/Installer-Fehlern.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
