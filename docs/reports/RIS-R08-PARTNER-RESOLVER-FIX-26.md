# RIS-R08-PARTNER-RESOLVER-FIX-26

## Status

**ROOT CAUSE VERIFIED — RESOLVER FIX IMPLEMENTED — REGRESSIONS PASS —
DEV2 PLAN READY (0/1/0) — NO APPLY**

Keine Cognito-Konfigurationsänderung, keine Terraform-Infrastrukturänderung,
keine `ris-dev`-Änderung, kein Push/Merge.

## A — Root Cause

`resolve_partner_application()` nutzte die GSI `gsi-client` nur als
Reihenfolge-Quelle:

* GSI-Key: `cognitoClientId` (Partition) + `tenantId` (Sort);
* mehrere historische Partner-Records desselben Clients und Tenants erzeugen
  denselben GSI-Key;
* DynamoDB garantiert für diese Treffer **keine** stabile Reihenfolge;
* der alte Code nahm den ersten Nicht-Reservation-Treffer und revalidierte nur
  dessen Basistabelle — ohne Status- oder Reservation-Owner-Prüfung.

Nachweis aus Phase 25:

```text
partner-r08-23 (INACTIVE, alter Client)
partner-r08-25 (ACTIVE, neuer Client)
-> GSI lieferte beide
-> Resolver lieferte partner-r08-23
-> Partnerroute: 403
```

Damit blockierte ein historischer INACTIVE-Record die gültige ACTIVE-Bindung.

## B — Fix

`agents/ecosystem/partner_registry.py`:

1. Die Reservation `CLIENT#<clientId>` ist **autoritativ**, wenn sie existiert.
2. Der Reservation-Owner wird direkt und strongly consistent aus der
   Basistabelle gelesen; GSI-Lag kann ihn nicht mehr verdrängen.
3. Der Owner muss `ACTIVE` sein, dieselbe `cognitoClientId` und — falls die
   Reservation einen `tenantId` trägt — denselben Tenant haben.
4. Ohne Reservation darf genau **ein** ACTIVE-Record existieren. Null oder
   mehrere ACTIVE-Records sind nicht auflösbar.
5. Historische INACTIVE-Records werden ignoriert, nicht gelöscht.
6. Alle Kandidaten werden mit `ConsistentRead=True` gelesen.
7. Jede Ausnahme führt fail-closed zu `None`.

Zusätzlich speichert `create_partner_application()` den `tenantId` jetzt auch
im Reservation-Item. Das ist additiv; ältere Reservationen ohne `tenantId`
bleiben kompatibel.

Der Resolver gibt nur noch ACTIVE-Partner zurück. Bestehende Caller prüfen
weiterhin `status == ACTIVE`.

## C — Regressionstests

Neu bzw. angepasst in `tests/test_partner_registry_atomicity.py`:

| Anforderung | Test |
|---|---|
| Ein ACTIVER Partner | bestehende Resolver-Tests |
| Nur INACTIVE | `test_resolver_none_when_reservation_owner_is_inactive`, Deactivation |
| Mehrere INACTIVE + ein ACTIVER | `test_resolver_prefers_current_owner_over_historical_inactive` |
| Gültige Reservation + Owner | `test_resolver_prefers_current_owner...`, `test_reservation_carries_tenant` |
| Fehlende Reservation | `test_resolver_without_reservation_uses_unique_active` |
| Reservation zeigt auf INACTIVE | `test_resolver_none_when_reservation_owner_is_inactive` |
| Reservation-/Partner-Tenant-Mismatch | `test_resolver_fails_closed_on_reservation_tenant_mismatch` |
| Zwei ACTIVE-Partner | `test_resolver_fails_closed_on_two_active_records` |
| GSI-Lag | `test_resolver_uses_owner_when_gsi_is_still_catching_up` |
| Unbekannter Client | bestehender Test |
| Release + Reuse | `test_resolver_prefers_current_owner...`, Release-Tests |
| Deterministische Reihenfolge | `test_resolver_is_order_independent` |
| Reservation-Client-Mismatch | `test_resolver_fails_closed_on_reservation_client_mismatch` |

Ausgeführt:

```text
Resolver/Auth/Registry/CLI: 112 passed, 7 subtests passed
Credential/HTTP:             81 passed
```

Fremder Issuer wird weiterhin vom API-Gateway-Authorizer und den bestehenden
Auth-Boundary-Tests abgelehnt; der Resolver erhält keinen Issuer und schwächt
diese Grenze nicht ab. Widerrufene Credentials bleiben durch die bestehende
Credential-Verifikation abgelehnt.

## D — Lambda-Paket und DEV2-Plan

Agent-Bundle:

```text
81 Dateien
LOCAL_ZIP_BASE64 = uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=
```

Plan gegen State Serial 29:

```text
Plan-Datei:   C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-26.tfplan
Plan SHA-256: 1AA96AA3951EA6D043D9AA8ACE28F68BF6A8136E8CCBE850083896828D17EDBD
State:        Serial 29
Lineage:      a0bd361d-5cd1-a207-a8c0-e6888f0be082
```

Aktionen:

```text
CREATE  = 0
UPDATE  = 1
DELETE  = 0
REPLACE = 0
CHANGED = module.lambda.aws_lambda_function.agent
```

Code-Hash:

```text
Q0o8VSGDONl44u4q33FRpG/u+4SMJhG6iNtU157hKno=
-> uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=
```

Keine IAM-, PITR-, Cognito-, CloudFront-, DNS-, ACM-, SQS- oder
Orders-Änderung. **Kein Apply.**

## E — Offene Folgearbeit

1. Separater Apply des Plans `1AA96AA…EDBD`.
2. Danach echter Gateway-/JWT-E2E mit `salary.amount = 50000.5` und
   `60000.75`.
3. Release-/Reuse-Test mit dem echten Client.
4. Jobsearch-Handoff um den erfolgreichen Resolver-Reuse-Fall ergänzen.

## Gate-Tabelle

| Prüfung | Ergebnis |
|---|---|
| Resolver Root Cause | **VERIFIED** |
| ACTIVE Partner Resolution | **PASS (lokal)** |
| Historical INACTIVE Handling | **PASS (lokal)** |
| Multi-Tenant Isolation | **PASS (lokal + bestehende Tests)** |
| Regression Tests | **PASS (112 + 81)** |
| Lambda Package | **READY** |
| DEV2 Plan | **READY (0/1/0)** |
| DEV2 Apply | **NOT AUTHORIZED** |
| Jobsearch Handoff | **UPDATED (Deploy noch offen)** |
| Gate B | **NO-GO** |
| Production | **BLOCKED** |
