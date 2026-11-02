# RIS-PARTNER-PROFILE-R01 — CONTRACT FOUNDATION

## Git-Ausgangsstand

- Branch: `feature/ris-partner-profile-persistence-v1`
- Base: `main` @ `c49eb2b37ab3d629eeee224084045a9659c59705`
- MO-Pin unverändert: `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d`

## Wiederverwendbare RIS-Komponenten

- `jobsearch/domain_models.py`: WorkMode / EmploymentType Enums (wiederverwendet, nicht dupliziert).
- `jobsearch/repository.py`: Tenant/User-Isolation-Muster (referenziert für spätere Persistenz, nicht verändert).
- `agents/partner_schema.py`, `agents/ecosystem/api_profiles.py`: Fehlerklassen- und Lifecycle-Muster (referenziert).
- `tests/unit/jobsearch/`: bestehende Testkonventionen.

## Implementierte Contract-Schicht

- Neue Datei: `jobsearch/partner_profile_contract.py`
- Schema-Version: `v1`
- Ressourcentypen: UserProfile, CVDocument, CVSearchProfile, ATSSearchProfile, ManualSearchProfile, MatchingPreferences
- Dataclasses mit `to_dict`/`from_dict` (strict unknown-field rejection), `validate()`
- `parse_resource()` Dispatcher
- `build_from_client_payload()` mit server-autoritativer Identity-Injektion und `reject_client_identity()`
- Hierarchie-Validatoren: `validate_ats_assignment`, `validate_parent_link`
- Kapazitäts-Validatoren: max 10 CVs/User, max 2 Suchprofile/CV, max 5 ATS/Suchprofil
- Fehlerklasse `ProfileContractError` mit Codes (MISSING_FIELD, UNKNOWN_FIELD, INVALID_SCHEMA_VERSION, INVALID_RESOURCE_TYPE, CLIENT_IDENTITY_FORBIDDEN, CAPACITY_EXCEEDED, INVALID_HIERARCHY, FORBIDDEN_CONTENT, INVALID_SEARCH_CONFIG, INVALID_FIELD)

## Datenmodell- und Hierarchie-Abgleich

- Hierarchie umgesetzt: User -> CV -> CVSearchProfile -> ATSSearchProfile
- Manuelle Suchprofile unabhängig vom CV
- ATS-Kriterien (ATSSearchProfile) und manuelle MatchingPreferences getrennt
- Suchkonfiguration behält Mehrfachwerte (Listen) ohne Verlust
- Identitätsfelder (userId, tenantId) nur serverseitig
- Keine Browser-File-Objekte oder Original-CV-Text in Profil-JSON

## Offene Punkte für R02+

- DynamoDB-Tabellen und Repository-Adapter
- API-Routen (CRUD)
- S3 für CV-Originaldateien
- Manual-Profile-Kapazitätsgrenze (Produktvertrag offen)
- OpenAPI-Erweiterung

## Testergebnisse

- Neue Tests: `tests/unit/jobsearch/test_partner_profile_contract.py` — 35/35 PASS (unittest, lokal)
- Bestehende Jobsearch-Tests nutzen pytest (nicht in dieser Umgebung installiert); Import der neuen Schicht fehlerfrei.

## Abgrenzung

- IMPLEMENTED: Contract-/Validierungsschicht, Tests, Report
- VERIFIED: 35 Unit-Tests PASS
- NOT DEPLOYED: keine API-Routen, keine DynamoDB-Tabellen, keine AWS-Ressourcen
