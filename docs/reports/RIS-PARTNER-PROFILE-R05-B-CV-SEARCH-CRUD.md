# RIS-PARTNER-PROFILE-R05-B — CV SEARCH PROFILE CRUD

## 1. Git-Baseline und Jobsearch-Referenz

- RIS Branch: `feature/ris-partner-profile-persistence-v1`
- Basis: `a665b5a` (R05-A)
- 39 untracked Dateien unverändert.
- Jobsearch `origin/main` wurde erneut abgeglichen: **`a47a957`**
  (vorher `ad9b5ed`). Die Commits dazwischen betreffen ausschließlich
  UI/Session/Guest-CV (`src/`, `docs/reports/`, `tests/`); das Verzeichnis
  `docs/contracts/` ist **unverändert**. Die v1-Vertragsbasis bleibt
  `ad9b5ed`-äquivalent. Zusatz: `profileValidation.ts` ergänzt den Code
  `capacity_exceeded`; `repositoryTypes.ts` ergänzt session-only unassigned
  ATS-Einträge (relevant für R06, nicht für R05-B).

## 2. API-Routen

| Methode | Pfad | Erfolg |
|---|---|---|
| GET | `/v1/partner/me/cvs/{cvId}/search-profiles` | 200 |
| POST | `/v1/partner/me/cvs/{cvId}/search-profiles` | 201 |
| GET | `/v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}` | 200 |
| PUT | `/v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}` | 200 |
| DELETE | `/v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}` | 204 |

Alle Routen sind explizit in Terraform, nutzen den bestehenden Human-JWT-
Authorizer und die bestehende Lambda-Proxy-Integration. Kein Wildcard-Proxy.

## 3. CVSearchProfileV1

```json
{
  "schemaVersion": 1,
  "searchProfileId": "<server-uuid>",
  "cvId": "<parent-uuid>",
  "name": "Cloud Engineering",
  "description": "optional",
  "origin": "cv",
  "searchConfig": {
    "skills": "AWS, Terraform, \"Cloud Architecture\"",
    "targetRoles": ["Cloud Engineer"],
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

- `schemaVersion` ist Integer `1`; `origin` ist `cv`.
- `cvId` ist die unveränderliche Parent-Verknüpfung; `searchProfileId` ist die
  serverseitige Ressourcen-ID.
- `searchConfig` nutzt das R05-P0-`SearchConfiguration`-Objekt (sechs Felder,
  phrase-preserving `skills`, nullable `radiusKm`). Keine Vermischung mit
  `matchingPreferences`.
- Legacy-R01-`profile`/`searchConfiguration` werden beim Lesen in
  `searchConfig` überführt und in `metadata.legacy` konserviert.

## 4. Authentifizierung und Parent-Isolation

- Bestehende Dual-Auth unverändert: Cognito-JWT + `X-Api-Credential` +
  Partner-Registry + L03-Tenant-Auflösung.
- `userId`/`tenantId`/`partnerApplicationId`/`issuer` werden serverseitig
  abgeleitet; manipulierte Body-Felder → 400.
- Collection-Operationen prüfen zuerst die Parent-CV-Eigentümerschaft
  (fehlend/fremd → 404).
- Item-Operationen prüfen zusätzlich `cvId == profile.cv_id`; ein falscher
  Parent in der URL → 404 (kein Cross-Parent-Zugriff).
- Cross-User → 404, Cross-Tenant → 403, Cross-Partner → 403, Cross-Issuer →
  404.

## 5. Kapazität, Idempotenz, Versionierung

- Maximal **2** Suchprofile je CV; atomar über den bestehenden
  `capacity#CVSP#<cvId>`-Zähler (R02/R05-A). Drittes Create → 409.
- Create nutzt die R05-A-Idempotenz (24 h, identitätsgebundener Digest,
  Payload-Hash). Identischer Retry → dieselbe `searchProfileId`; gleicher Key
  mit anderem Payload → 409; keine doppelte Kapazitätsbelegung.
- Update/Delete nutzen `version`; stale Version → 409. IDs, Parent und
  Identität sind unveränderlich.
- Parent-Lifecycle: Ein Create gegen eine CV im `deleting`-Guard → 409.

## 6. Delete-Semantik

- `DELETE` prüft `version` (optional) und den ATS-Child-Zähler.
- Vorhandene ATS-Kinder → **409**, keine Kaskade.
- Atomarer Delete-vs-Child-Create-Schutz über den bestehenden
  `capacity#ATS#<searchProfileId>`-Zähler und den R05-A-Parent-Guard.
- Keine Orphans, keine Counter-Drift; 204 bei Erfolg.

## 7. Terraform / OpenAPI

- 5 neue explizite Routen in `terraform/modules/api/main.tf`.
- `docs/api/API-STANDARD.md` und `docs/api/openapi-platform.yaml` ergänzt:
  `CVSearchProfileV1`, `CVSearchProfileInput`; Pfade mit
  `x-infrastructure-governance: terraform-managed`, `Idempotency-Key` am POST.
- Keine neue DynamoDB-Tabelle, keine S3-Änderung, kein neues IAM (die
  `partner_profiles`-Policy deckt die Tabelle ab).
- `terraform fmt -check` (versioniert): PASS; `validate`: PASS
  (vorbestehende Deprecation-Warnings). OpenAPI-Konsistenz: 47/47 PASS.

## 8. Tests

Neu: `tests/test_partner_cv_search_profiles_api.py` — **27/27 PASS**:

- Create/Get/List/Update/Delete; Delete → 404.
- v1-Shape (Integer `1`, `origin=cv`, Parent `cvId`).
- Vollständiger `searchConfig`-Roundtrip, quoted Skills, Mehrfachwerte,
  `radiusKm=null`, City, ungültige Config/Name, Pagination.
- Cross-User/-Tenant/-Partner/-Issuer, gefälschte Identity, fehlender/fremder
  Parent, falsche Parent-ID.
- Kapazität 2/CV, parallele Creates auf dem letzten Platz.
- Idempotenter Retry, gleicher Key mit anderem Payload, keine doppelte
  Kapazität.
- Stale Update/Delete, ATS-Kind → 409, Delete-vs-ATS-Create ohne Orphan,
  Parent `deleting` → 409, Legacy-Incomplete-Schutz.
- Kein Agenten-/Modellaufruf.

R01–R05-B-Regression: **374/374 PASS** (347 bisher + 27 neu).
Der In-Memory-Fake serialisiert Transaktionen per Lock; das belegt die
Transaktionslogik, **nicht** echtes DynamoDB-Concurrency (R07).

## 9. Verbleibende P1 / Abhängigkeiten

| ID | Befund | Status |
|---|---|---|
| P1-1 | CVDocument-Naming/Status (`filename`/`name`, `sizeBytes`/`size`, Status-Set) | OPEN |
| P1-2 | CVSearchProfile `description`/`origin`/`searchConfig` | **RESOLVED (R05-B)** |
| P1-3 | ATS `criteria`-Shape | OPEN (R06) |

**R06-Abhängigkeiten:** ATS-CRUD benötigt `criteria` (nur
requiredSkills/preferredSkills/excludedTerms), die 5er-Grenze je Suchprofil,
die ATS-Override-Semantik (Skills/Zielrollen) und die unassigned-ATS-Session-
Semantik aus dem neuen Jobsearch-Stand `a47a957` (nur als Produktkontext,
keine RIS-Persistenz von Session-Einträgen).

**R07:** echte DynamoDB-Transaktions-/GSI-Integration und S3-E2E bleiben
vorgemerkt.

## 10. Klassifikation

- **IMPLEMENTED:** 5 CRUD-Routen, CVSearchProfile-v1-Vertrag, Parent-/Owner-
  Isolation, 2/CV-Kapazität, 24-h-Idempotenz, Versionierung, ATS-Child-Guard,
  Terraform-Routen, OpenAPI.
- **VERIFIED:** 374/374 Tests; Terraform fmt/validate; OpenAPI 47/47.
- **NOT RUN:** echte DynamoDB-/S3-Integration (R07); volle `tests/`-Suite
  wegen fehlendem boto3 / präexistenten Windows-/Installer-Fehlern.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
