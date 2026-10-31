# RIS-PARTNER-PROFILE-R02 — DYNAMODB REPOSITORY

## DynamoDB-Entscheidung

Die bestehende `jobsearches`-Tabelle kann den neuen v1-Vertrag nicht sicher
aufnehmen (unterschiedliche PK-Struktur, Isolation nach Partner/Issuer, Capacity-
Semantik). Daher wurde eine gezielte neue Tabelle `partner-profiles` eingeführt.

## Schema

- Table: `${project}-${env}-partner-profiles`
- PK: `resourceId` (S) — stabile serverseitige ID
- Attribute: userId, tenantId, resourceType, parentId, partnerApplicationId, issuer,
  schemaVersion, version, createdAt, updatedAt
- GSI `gsi-user`: hashKey userId, rangeKey resourceType
- GSI `gsi-parent`: hashKey parentId
- Billing: PAY_PER_REQUEST

## Wiederverwendete RIS-Komponenten

- `jobsearch/partner_profile_contract.py` (R01) — Validierung, keine zweite.
- `jobsearch/repository.py` — Isolation-Muster.
- `agents/ecosystem/api_profiles.py` — Fehlerklassen-Muster.

## Persistente Ressourcentypen

CVDocument, CVSearchProfile, ATSSearchProfile, ManualSearchProfile.
UserProfile und MatchingPreferences sind Vertrags-/eingebettete Typen, keine
eigenen Persistenzressourcen.

## Zugriffsmuster / Isolation

- Get: PK + Identity-Check (userId, tenantId, partnerApplicationId, issuer)
- List by user: GSI gsi-user mit Filter auf tenant/resourceType/partner/issuer
- List by parent: GSI gsi-parent mit Filter
- Update: optimistisches Locking via `version` (ConditionExpression)
- Delete: bedingtes Delete mit Identity + version

## Konkurrenz- und Versionskontrolle

- Create: `attribute_not_exists(resourceId)` + vorherige Capacity-Prüfung
- Update/Delete: ConditionExpression auf version; Konflikt -> PartnerProfileConflictError
- Kapazitätsgrenzen 10/2/5 vor dem Schreiben geprüft

## Tests

- `tests/unit/jobsearch/test_partner_profile_repository.py`: 20/20 PASS
- `tests/unit/jobsearch/test_partner_profile_contract.py`: 35/35 PASS
- Terraform fmt: PASS; validate: PASS (mit vorbestehenden Deprecation-Warnings)

## Abgrenzung

- IMPLEMENTED: Repository-Schicht, Terraform-Tabelle, Tests
- VERIFIED: 55 Unit-Tests PASS, Terraform validate PASS
- NOT DEPLOYED: keine API-Routen, kein AWS Apply
