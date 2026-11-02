# RIS-PARTNER-PROFILE-R03 — MANUAL CRUD API

## Git-Ausgangsstand

- Branch: `feature/ris-partner-profile-persistence-v1`
- Basis: `2e2a72e` (R02-R2)
- 39 untracked Dateien unverändert.

## Implementierte Endpunkte

| Methode | Pfad | Erfolg |
|---|---|---|
| GET | `/v1/partner/me/manual-search-profiles` | 200 (paginiert) |
| POST | `/v1/partner/me/manual-search-profiles` | 201 |
| GET | `/v1/partner/me/manual-search-profiles/{profileId}` | 200 |
| PUT | `/v1/partner/me/manual-search-profiles/{profileId}` | 200 |
| DELETE | `/v1/partner/me/manual-search-profiles/{profileId}` | 204 |

Die Handler delegieren ausnahmslos an `jobsearch.partner_profile_repository.PartnerProfileRepository`
(R02/R02-R2). Es gibt keine zweite DynamoDB-Schicht und keine parallele
Contract-Validierung.

## Request-/Response-Beispiele (synthetisch)

POST-Body:

```json
{
  "name": "Senior Backend",
  "description": "Manuell erstellt",
  "matchingPreferences": {
    "requiredSkills": ["python", "aws"],
    "preferredSkills": ["terraform"],
    "excludedTerms": ["internship"],
    "roles": ["Backend", "Platform"],
    "workModes": ["remote", "hybrid"],
    "employmentTypes": ["full_time"],
    "locations": ["Berlin"]
  }
}
```

201-Antwort (gekürzt):

```json
{
  "schemaVersion": "v1",
  "manualSearchProfileId": "8f...",
  "manualProfileId": "8f...",
  "name": "Senior Backend",
  "description": "Manuell erstellt",
  "origin": "manual",
  "matchingPreferences": { "requiredSkills": ["python", "aws"], "...": "..." },
  "version": 1
}
```

## Partner-/Benutzerautorisierung

Reuses the existing dual-auth boundary (no new login flow):

1. Cognito access JWT (gateway `authorization_type = JWT`).
2. Opaque RIS credential in `X-Api-Credential` (`resolve_credential_profile`).
3. ACTIVE partner application registry binding (client_id → apiProfileId/tenantId).
4. Server-side tenant resolution (L03); a contradicting claim → 403.
5. `userId` = JWT `sub`, `tenantId` = resolved tenant, `partnerApplicationId` =
   registry `applicationId`, `issuer` = JWT `iss`.

**Minimal storage scope:** authenticated user + ACTIVE credential/profile +
ACTIVE partner application. Agent entitlements are deliberately **not** reused
as a storage permission. Storing/loading/deleting never enqueues work and never
calls a model.

Manipulated `userId`/`tenantId`/owner fields in the body are rejected
(`CLIENT_IDENTITY_FORBIDDEN`, 400) and never become authority.

## Fehlercodes

| Status | Bedeutung |
|---|---|
| 400 | Ungültiges JSON / clientseitige Identity-Felder / ungültiger Cursor |
| 401 | Fehlende oder ungültige Authentifizierung |
| 403 | Partner-/Tenant-/Credential-Grenze verweigert |
| 404 | Ressource nicht vorhanden oder nicht zugänglich |
| 409 | Versionskonflikt (optimistisches Locking) |
| 422 | Contract-Validierung fehlgeschlagen |
| 500/503 | Interner Fehler / Store nicht erreichbar (ohne interne Details) |

## Contract-Abgleich (Dokumentierte Abweichungen)

- R01 persistiert `manualProfileId`; die R03-API liefert zusätzlich
  `manualSearchProfileId` als Alias. Es gibt **keine** zweite DTO-Definition.
- R03 nennt ein `searchConfig`. Der R01-Vertrag führt die Suchparameter
  (`roles`, `workModes`, `employmentTypes`, `locations`, `salaryMin`,
  `remoteOnly`, `sources`, `query`) bereits innerhalb von
  `matchingPreferences`. Es wurde kein konkurrierendes `searchConfig`-Objekt
  eingeführt; die Felder bleiben im einen R01-Objekt.
- `requiredSkills`, `preferredSkills`, `excludedTerms` sowie `description` und
  `origin` wurden **additiv** in den R01-Vertrag aufgenommen (abwärtskompatibel;
  R01-Tests unverändert grün).

## Wiederverwendete R02-Komponenten

- `PartnerProfileRepository.create/get/list_by_user/update/delete`
- Optimistisches Locking über `version` (409)
- Bedingtes Delete mit Identity + Version
- Pagination über `ExclusiveStartKey` (opaker Cursor)
- User-/Tenant-/Partner-/Issuer-Isolation

## Terraform / OpenAPI

- `terraform/modules/api/main.tf`: 5 explizite Routen, JWT-Authorizer,
  bestehende Lambda-Proxy-Integration. Kein Wildcard-Proxy, keine Default-Route.
- `terraform/modules/lambda`: `PARTNER_PROFILE_TABLE` Env-Variable + IAM-Policy
  (`PutItem/GetItem/Query/DeleteItem` auf Tabelle + Indizes).
- `terraform/main.tf`: Verdrahtung der `partner_profiles`-Tabelle.
- `docs/api/openapi-platform.yaml`: 5 Operationen + `ManualSearchProfileV1`,
  `ManualSearchProfileInput`, `MatchingPreferencesV1`.
- `docs/api/API-STANDARD.md`: Routen-Tabelle ergänzt.
- Terraform `fmt -check` (nur versionierte Dateien): PASS; `validate`: PASS
  (vorbestehende Deprecation-Warnings). Die untracked `ris-dev2.tfvars` blieb
  unangetastet.

## Testergebnisse

- Neue API-/Security-Tests: `tests/test_partner_manual_profiles_api.py` — 26/26 PASS.
- R01-Contract: 35/35 PASS.
- R02/R02-R2-Repository: 33/33 PASS.
- Partner-Security/Registry: 75/75 PASS.
- OpenAPI-Konsistenz (`test_p20_api_contract_consistency`,
  `test_platform_openapi_contract`): 47/47 PASS.
- R03-relevante Gesamtmenge: **216/216 PASS**.

## Abgrenzung

- **IMPLEMENTED:** 5 HTTP-Endpunkte, Handler, Contract-Erweiterung, Terraform-Routen,
  Lambda-Env/IAM, OpenAPI, Tests, Report.
- **VERIFIED:** 216/216 R03-relevante Tests PASS; Terraform fmt/validate PASS;
  OpenAPI-Konsistenz PASS.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Apply/Destroy, kein Push/PR/Merge.
- **NOT RUN:** volle `tests/`-Suite ist in dieser Umgebung nicht vollständig
  lauffähig (fehlendes boto3 für 10 Collection-Module; 154 präexistente Fehler
  in installer/state_mirror/timestamp/Windows-Pfaden; ein Windows-Pfadtrenner-
  Fehler in `test_partner_terraform_wiring`). Diese sind **nicht** R03-bedingt.
  Eine echte DynamoDB-Transaktions-/GSI-Integrationsprüfung bleibt für **R07**
  vorgemerkt.

## Offene Punkte für CV-/ATS-Routen

- `CVDocument`, `CVSearchProfile`, `ATSSearchProfile` sind bewusst **nicht**
  über HTTP freigeschaltet (R03-Scope).
- CV-Datei/Originaltext bleiben außerhalb von DynamoDB (S3, späterer Gate).
- Echte DynamoDB-Integration (Transaktionen, GSI-Eventual-Consistency) → R07.
