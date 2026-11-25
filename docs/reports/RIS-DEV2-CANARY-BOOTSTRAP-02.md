# RIS-DEV2-CANARY-BOOTSTRAP-02

**Datum:** 2026-11-25
**Branch / Baseline:** `feature/ris-analysis-integration-07` / `c994cd5b67c48415f393424f842ef262f86c18f5`
**MO-Pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Modus:** Read-only Analyse + Freigabepaket; **kein AWS-Write, kein Apply, kein State-Write, kein Main-Merge**

## Ergebnis

**BLOCKED** — der positive Canary ist mit den vorhandenen autorisierten
Provisionierungswegen **nicht ausführbar**. Drei unabhängige Blocker:

| # | Blocker | Beleg (read-only) |
| --- | --- | --- |
| B1 | Keine Cognito-Testidentität | `ris-dev2-dev-users` (`eu-central-1_OYN9QiHc5`): 0 User; ebenso `ris-dev2-mays-orders-users` und `ris-agent-dev-users`: 0. Die 10 bestehenden Orders sind an den Issuer von `OYN9…` gebunden, der Besitzer existiert nicht mehr. |
| B2 | Kein ACTIVE-API-Profil und keine Partner-/Issuer-Bindung | 4/4 Profile `REVOKED`; das Profil-Schema kennt `partnerApplicationId`/`issuer` nicht (create ignoriert, update lehnt unbekannte Felder ab, live: `None`). `resolve_context` liest genau diese Felder → Dispatch-Kontext hat **leere** Partner-/Issuer-Werte. |
| B3 | Kein Katalog-/Offer-/Entitlement-Pfad für `analysis-agent` | Katalog: `ats-agent`, `reference_agent`, `jobsearch-agent`; **kein** `analysis-agent`. Offers: 0. `analysis-agent`-Entitlements: 0. `_validate_agents` verweigert unbekannte Agenten → Offer/Grant unmöglich. |

Damit ist Punkt 4 des Auftrags („`ANALYSIS_SYNTHETIC_MODE=true` mit exakt
diesem Kontext“) nicht erfüllbar: Es gibt keine Sub, keine ACTIVE-Profil-ID und
keine nicht-leeren Partner-/Issuer-Werte. Ein Plan mit Platzhaltern ist
ausdrücklich unzulässig; deshalb wurde **kein neuer Synthetic-Plan** erzeugt.
P1 (`bac9af1c…`, Mode off) bleibt der sichere Kandidat; P2 (`7ecb0da6…`) darf
nicht angewendet werden.

## 1. Geprüfte autorisierte Wege

| Weg | Zweck | Grenze |
| --- | --- | --- |
| `tools/ris_admin apiprofile create/activate` | Profil anlegen/aktivieren | Owner/Tenant kommen aus der Authorization-Datei bzw. `--target-owner`; **keine** Partner-/Issuer-Felder |
| `tools/ris_admin offer create/grant` | Offer + Entitlement | Agenten müssen im Katalog existieren; Tenant kommt aus der Authorization-Datei |
| `POST /v1/apiprofiles`, `POST /v1/offers/{id}/grant` | HTTP-Adminpfad (Gruppe `admins`) | gleiche Domain-Grenzen; keine direkten DynamoDB-Schreibskripte |
| `agents/ecosystem/api_profiles.create_profile` | Domain-Create | nur `name`, `description`, `target_owner`; `partnerApplicationId`/`issuer` nicht vorgesehen |
| `lambda/dispatch_ingress.resolve_context` | Vertrauenswürdiger Kontext | `partner_application_id = profile.get("partnerApplicationId","")`, `issuer = profile.get("issuer","")` |

Kein direkter DynamoDB-Seed wurde vorgeschlagen oder ausgeführt.

## 2. Warum die Kette bricht

1. **Order-Create** braucht ein gültiges Cognito-JWT (Owner-Bindung) → ohne
   User nicht möglich.
2. **`AGENT_ORDER_REJECTED`** ohne ACTIVE-Profil und `analysis-agent`-
   Entitlement; das Entitlement kann nur über ein Offer entstehen, das
   `analysis-agent` im Katalog voraussetzt.
3. **Dispatch-Kontext** trägt `tenantId`/`ownerUserId` aus dem Profil, aber
   `partnerApplicationId`/`issuer` wären leer.
4. **Synthetic-Verifier** verlangt alle vier Felder **nicht-leer** und exakt
   gleich → mit leeren Partner-/Issuer-Werten ist eine Autorisierung
   ausgeschlossen (fail-closed, korrekt).

Das ist dieselbe offene Gate-C-Lücke (`apiProfileRef`-Owner-/Partner-Bindung),
die bereits dokumentiert ist — hier wird sie im Live-Pfad konkret.

## 3. Bootstrap-Paket (ausführbar erst nach gesonderten Freigaben)

### Phase A — Produktänderungen (Code/Terraform, separater Auftrag)

| Schritt | Änderung | Wirkung |
| --- | --- | --- |
| A1 | `analysis-agent` in den Terraform-Katalog-Seed aufnehmen (Agent-ID, Status ACTIVE, Capability `analysis.run`, Runtime `python3.14`) | 1 neues `aws_dynamodb_table_item`; Offer/Grant wird möglich |
| A2 | Autoritative, admin-only Bindung von `partnerApplicationId` und `issuer` an das API-Profil (validiert, server-derived) und Verwendung in `resolve_context` | schließt die leere Partner-/Issuer-Lücke; erfordert API-Vertrag + Tests |
| A3 | Grant-Scope festlegen (laut `API-STANDARD` user-wide) | bestimmt, ob `apiProfileId` in der Entitlement-Zeile steht |

Ohne A1 und A2 bleibt der positive Canary dauerhaft unmöglich; A2 ist kein
Datenproblem, sondern eine Produkt-/Vertragslücke.

### Phase B — AWS-Provisionierung (separate Write-Freigabe)

1. **Cognito-User** im Pool `eu-central-1_OYN9QiHc5` (Issuer des Orders-Readers)
   anlegen, `custom:tenant_id = tenant-ris-canary-01`, bestätigen.
2. **API-Profil** über `ris_admin apiprofile create --target-owner <sub>`
   (Admin-Mapping) anlegen, dann `activate`; Profil-ID erfassen.
3. **Offer** `analysis-agent` anlegen und **grant** an `<sub>`/Tenant mit
   kurzem Fenster; Entitlement-ID erfassen.
4. Erfasste Werte: `sub`, `tenant`, `partnerApplicationId`, `issuer`,
   `apiProfileId`, `entitlementId`.

Beispielbefehle (nicht ausgeführt; Authorization-Datei erforderlich):

```text
ris_admin apiprofile create --name ris-canary-01 --target-owner <sub> \
  --authorization-file <file>
ris_admin apiprofile activate --apiProfileId <aprof_…> --reason canary \
  --authorization-file <file>
ris_admin offer create --name ris-canary-analysis --agent-ids analysis-agent \
  --authorization-file <file>
ris_admin offer grant --offerId <offer_…> --user-id <sub> \
  --valid-from <ISO> --valid-until <ISO> --reason canary \
  --authorization-file <file>
```

### Phase C — Terraform + Canary (nach A/B)

1. Var-Datei mit den **erfassten** Werten füllen (keine Platzhalter), Ablauf
   kurz vor dem Testfenster.
2. Neuen Plan erzeugen, SHA-256 + 0/8/0-Diff prüfen, freigeben, anwenden.
3. Canary: Order → Dispatch → WorkItem `RUNNING` → Analysis → ORDER_RESULT →
   Owner-GET (fremder Owner 404) → Negativfälle → Cleanup.
4. Rückweg: Mode `false`, neuer Plan, Freigabe, Apply, Env verifizieren.

## 4. Berechtigungsumfang der Provisionierung

| Operation | IAM-Aktionen (Minimum) | Ziel |
| --- | --- | --- |
| Cognito-User | `cognito-idp:AdminCreateUser`, `AdminSetUserPassword`, `AdminUpdateUserAttributes`, `AdminGetUser`, `AdminDeleteUser` | Pool `eu-central-1_OYN9QiHc5` |
| Profil | `dynamodb:GetItem`, `PutItem`, `UpdateItem`, `Query` | `ris-dev2-dev-api-profiles` |
| Offer/Grant | `dynamodb:GetItem`, `PutItem`, `UpdateItem`, `Query`, `DeleteItem` | `ris-dev2-dev-offers`, `ris-dev2-dev-entitlements` |
| Katalogprüfung | `dynamodb:GetItem`, `Query` | `ris-dev2-dev-agent-catalog` |

Keine SQS-, Lambda-, Secrets-, Cognito-Konfigurations- oder
CloudFront-Änderung. Kein direkter Tabellen-Seed.

## 5. Cleanup

1. Entitlement über `offer withdraw` entfernen (oder per Domain-Delete).
2. Offer auf `INACTIVE`.
3. Profil auf `REVOKED`.
4. Cognito-User löschen (`AdminDeleteUser`).
5. Synthetische Order/WorkItems nach bestehendem Verfahren bereinigen.
6. Synthetic-Modus deaktivieren (Terraform-Rückplan, neue Freigabe).

## 6. Tests

Übernommen, unverändert gültig (keine Laufzeitänderung in diesem Schritt):

| Lauf | Ergebnis |
| --- | --- |
| MO-Lambda-Suite `db4f9e7` | **240 OK** |
| RIS-Cross-Repo (`MO_ORDERS_SRC`), keine Skips | **61 passed** |
| Parser-/Analysis-Agent-Set | **109 passed** |
| Synthetic-Konfigurationsgrenzen (`test_analysis_runtime_terraform`, `test_analysis_synthetic_profile`) | **38 passed** |

Neue Provisionierungsgrenzen sind hier nur dokumentiert; Tests dafür gehören zu
Phase A (Katalog-/Profilbindung), nicht zu diesem Read-only-Gate.

## 7. Entscheidung

**BLOCKED.** Konkrete Gründe: B1 (keine Identität), B2 (keine Partner-/Issuer-
Bindung im Profil), B3 (kein Katalog-/Offer-Pfad für `analysis-agent`).
B2 und B3 sind Produkt-/Vertragslücken, keine fehlenden Daten. Ein
mode=true-Plan mit erfundenen Werten wäre irreführend und wurde nicht erzeugt.

Sobald A1/A2 freigegeben und umgesetzt sowie B1–B3 provisioniert sind, ist das
Paket in Phase C ohne weitere Architekturentscheidung ausführbar.

## 8. Nicht ausgeführt

Kein AWS-Write, kein Apply, kein State-Write, kein neuer Terraform-Plan, kein
Main-Merge. P1 bleibt der sichere Kandidat; P2 ist gesperrt.
