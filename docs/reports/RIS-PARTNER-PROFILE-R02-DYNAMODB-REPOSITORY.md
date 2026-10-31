# RIS-PARTNER-PROFILE-R02 â€” DYNAMODB REPOSITORY

## DynamoDB-Entscheidung

Die bestehende `jobsearches`-Tabelle kann den neuen v1-Vertrag nicht sicher
aufnehmen (unterschiedliche PK-Struktur, Isolation nach Partner/Issuer, Capacity-
Semantik). Daher wurde eine gezielte neue Tabelle `partner-profiles` eingefÃ¼hrt.

## Schema

- Table: `${project}-${env}-partner-profiles`
- PK: `resourceId` (S) â€” stabile serverseitige ID
- Attribute: userId, tenantId, resourceType, parentId, partnerApplicationId, issuer,
  schemaVersion, version, createdAt, updatedAt
- GSI `gsi-user`: hashKey userId, rangeKey resourceType
- GSI `gsi-parent`: hashKey parentId
- Billing: PAY_PER_REQUEST

## Wiederverwendete RIS-Komponenten

- `jobsearch/partner_profile_contract.py` (R01) â€” Validierung, keine zweite.
- `jobsearch/repository.py` â€” Isolation-Muster.
- `agents/ecosystem/api_profiles.py` â€” Fehlerklassen-Muster.

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

- Create: `attribute_not_exists(resourceId)` + vorherige Capacity-PrÃ¼fung
- Update/Delete: ConditionExpression auf version; Konflikt -> PartnerProfileConflictError
- KapazitÃ¤tsgrenzen 10/2/5 vor dem Schreiben geprÃ¼ft

## Tests

- `tests/unit/jobsearch/test_partner_profile_repository.py`: 20/20 PASS
- `tests/unit/jobsearch/test_partner_profile_contract.py`: 35/35 PASS
- Terraform fmt: PASS; validate: PASS (mit vorbestehenden Deprecation-Warnings)

## Abgrenzung

- IMPLEMENTED: Repository-Schicht, Terraform-Tabelle, Tests
- VERIFIED: 55 Unit-Tests PASS, Terraform validate PASS
- NOT DEPLOYED: keine API-Routen, kein AWS Apply

---

## R02-R — Concurrency & Isolation Gate (Nachtrag)

### Gefundene Race Condition (vor R02-R)

Die R02-Implementierung prüfte die Kapazität mit einer Query/Count und schrieb
danach per `put_item`. Zwischen Zählen und Schreiben konnten zwei parallele
Creates denselben letzten freien Platz belegen (TOCTOU). Zusätzlich waren
`ExpressionAttributeValues` in `list_by_user`/`list_by_parent` nicht
DynamoDB-serialisiert (`{"S": ...}`), was gegen echtes DynamoDB fehlgeschlagen
wäre.

### Gewählte atomare Kapazitätssemantik

Jede begrenzte Dimension hat ein Zähler-Item (`capacity#CV#<userId>`,
`capacity#CVSP#<cvId>`, `capacity#ATS#<searchProfileId>`). Ein Create läuft
als `TransactWriteItems` mit drei Aktionen:

1. `ConditionCheck` auf dem Zähler: `count < max`
2. `Put` der Ressource: `attribute_not_exists(resourceId)`
3. `Update` des Zählers: `SET count = count + 1`

Delete läuft analog als `TransactWriteItems` (`Delete` + `count - 1` mit
`count > 0`). Eine abgebrochene Transaktion hinterlässt keinen Teilzustand,
also keine Kapazitätsdrift und keine doppelt freigegebenen Plätze.

### Isolations- und Pagination-Ergebnisse

- User-, Tenant-, Partner- und Issuer-Isolation werden bei Get/List/Update/Delete
  geprüft; fremde Datensätze werden nicht zurückgegeben.
- `gsi-user` und `gsi-parent` werden für gezielte Queries genutzt; kein
  Table-Scan. Kapazitätszähler werden aus Listings gefiltert
  (`resourceType <> CapacityCounter`).
- Pagination über `ExclusiveStartKey` liefert keine verlorenen oder fremden
  Ressourcen.

### Testnachweise

- `tests/unit/jobsearch/test_partner_profile_repository.py`: 28/28 PASS
  (inkl. zwei konkurrierende Creates auf dem letzten CV-/Suchprofil-/ATS-Platz,
  Delete+Recreate ohne Drift, fehlgeschlagene Transaktion ohne Kapazitätsänderung,
  Cross-User/Tenant/Partner/Issuer, Pagination, Versionskonflikte).
- `tests/unit/jobsearch/test_partner_profile_contract.py`: 35/35 PASS.
- Bestehende Partner-Regression: 75/75 PASS.
- Terraform `fmt -check`: PASS.

### Offene Integrationsprüfung (R07)

Die Concurrency-Tests bilden die Transaktionssemantik mit einem seriellen
In-Memory-Fake ab; sie beweisen die Logik, aber nicht das reale
DynamoDB-Transaktionsverhalten (GSI-Eventual-Consistency, echte
`TransactionCanceledException`-Payloads). Eine Integrationsprüfung gegen eine
echte DynamoDB-Tabelle ist für R07 vorgemerkt. Dieser Nachweis ist daher
**kein vollständiger Concurrency-PASS**, sondern ein Logik-/Unit-PASS.
