# RIS-R08-RESOLVER-DEV2-GATEWAY-E2E-27

## Status

**APPLY PASS — REAL GATEWAY/JWT/PARTNER E2E PASS — FRACTIONAL SALARY LIVE
VERIFIED — RESOLVER/REUSE LIVE VERIFIED — CLEANUP PASS**

Keine `ris-dev`-Änderung, keine Cognito-Konfigurationsänderung, keine
CloudFront-/DNS-/ACM-/PITR-/SQS-/Orders-/Jobsearch-Änderung, kein Push/Merge.

## 1. Apply

Vor Apply erneut geprüft:

```text
Plan SHA-256: 1AA96AA3951EA6D043D9AA8ACE28F68BF6A8136E8CCBE850083896828D17EDBD
State:        Serial 29
Lineage:      a0bd361d-5cd1-a207-a8c0-e6888f0be082
Diff:         CREATE=0, UPDATE=1, DELETE=0, REPLACE=0
Änderung:     module.lambda.aws_lambda_function.agent
Bundle:       uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=
```

Apply:

```text
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

Nachprüfung:

| Prüfung | Ergebnis |
|---|---|
| Lambda `State` | `Active` |
| `LastUpdateStatus` | `Successful` |
| `CodeSha256` | `uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=` |
| State nach Apply | Serial 30, Lineage unverändert |
| No-Changes-Plan | Exit 0 |
| Lambda-Health | 200 |

## 2. Real Gateway/JWT/Partner-E2E

Provisioniert über den bestehenden CLI-Lifecycle:

| Ressource | Kennung |
|---|---|
| APIProfile | `aprof_06cd4d210f694679` |
| Partner | `partner-r08-27` |
| Credential | `cred_c7f6ff63405f4235` |
| Client | `21j28p71vogg0m41tcue0ib3l4` |
| Tenant | `ris-dev2-e2e-20261105` |

Genau ein temporärer synthetischer Cognito-Benutzer wurde im bestehenden Pool
angelegt, per `USER_PASSWORD_AUTH` angemeldet und nach dem Test gelöscht.
Der Access-JWT hatte `token_use=access` und die korrekte `client_id`; das
Access-Token enthielt keinen `custom:tenant_id`-Claim — der Tenant wurde
serverseitig aus Credential und Registry aufgelöst.

### HTTP-Matrix (echtes API Gateway)

| Test | Ergebnis |
|---|---:|
| Metrics vor Create | **200** |
| Create mit `salary.amount=50000.5` | **201** |
| List | **200** |
| Detail | **200** |
| Patch mit `salary.amount=60000.75` | **200** |
| Version nach Patch | **1 → 2** |
| Detail nach Patch | **200**, Version 2 |
| Export | **200** |
| Metrics nach Create | **200**, `total=1`, `drafts=1` |
| Delete | **204** |
| List nach Delete | **200**, 0 Items |
| Metrics nach Delete | **200**, `total=0` |
| Ungültiger Partner-Key | **401** |
| Widerrufenes Credential + gültiger JWT | **403** |

### Decimal-Persistenz

| Prüfung | Ergebnis |
|---|---|
| Create-Response | `50000.5` |
| DynamoDB Rohwert | `Decimal("50000.5")` |
| Exakter Vergleich | **True** |
| Patch-Response | `60000.75` |
| DynamoDB nach Patch | `Decimal("60000.75")` |
| Exakter Vergleich | **True** |

Kein binäres Float-Artefakt, keine 422/409-Fehlklassifikation.

## 3. Isolation

Am deployten Lambda mit gültigem Credential und Authorizer-äquivalenten
Claims:

| Test | Ergebnis |
|---|---:|
| Gültiger Tenant + Client | 200 |
| Fremder Tenant | 403 |
| Unbekannter Client | 403 |
| Malformed Credential | 401 |

Reservation mit falschem Owner/Tenant sowie zwei widersprüchliche ACTIVE-Records
sind durch die Resolver-Regressionstests fail-closed abgedeckt.

## 4. Resolver und historische Records

Vor dem Test existierten drei historische INACTIVE-Partner für denselben
realen Client (`partner-r08-23`, `partner-r08-25`, `partner-r08-27` nach
Cleanup). Der neue Resolver lieferte dennoch deterministisch den aktuellen
ACTIVE-Partner.

Nach dem Release:

```text
partner-r08-27 -> INACTIVE, reservationReleased=true
Reservation ABSENT
```

Anschließend wurde derselbe reale Client erneut gebunden:

```text
partner-r08-27-reuse (ACTIVE)
Resolver -> partner-r08-27-reuse (ACTIVE)
```

Damit ist die Wiederverwendung desselben Clients trotz historischer
INACTIVE-Records live bestätigt.

## 5. Cleanup

| Prüfung | Ergebnis |
|---|---|
| Partner-Records | 6, alle `INACTIVE` |
| Reservations | **0** |
| Applications | **0** |
| Cognito-Benutzer | **0** |
| Credentials | 6, alle `REVOKED` |
| APIProfiles | 8, alle `REVOKED` |
| Secret-Dateien | **0** |
| Aktive Testberechtigung | keine |
| `ris-dev` | unberührt |

Historische Record-Namen: `partner-r08-20`, `partner-r08-22`,
`partner-r08-23`, `partner-r08-25`, `partner-r08-25-reuse`,
`partner-r08-25-synth`, `partner-r08-27`, `partner-r08-27-reuse`.
Sie bleiben ausschließlich als Audit-Spur erhalten; es wurden keine
pauschalen Registry- oder DynamoDB-Löschungen durchgeführt.

## 6. Gate-Tabelle

| Prüfung | Ergebnis |
|---|---|
| Lambda-Apply | **PASS** |
| Echter Gateway + JWT + Partner-Key | **PASS** |
| Metrics | **PASS (200)** |
| Create `50000.5` | **PASS (201, exakt Decimal)** |
| List / Detail | **PASS (200)** |
| Patch `60000.75` | **PASS (200, Version 2, exakt Decimal)** |
| Export | **PASS (200)** |
| Delete | **PASS (204)** |
| Metrics nach Create/Delete | **PASS (1/0)** |
| Ungültiger Key | **PASS (401)** |
| Widerrufenes Credential | **PASS (403)** |
| Fremder Tenant / unbekannter Client | **PASS (403, Lambda-Grenze)** |
| Historische INACTIVE-Records | **PASS (ignoriert)** |
| Release + Real-Client-Reuse | **PASS (live)** |
| Cleanup | **PASS** |
| Jobsearch-Handoff | **UPDATED** |
| Gate B | **NO-GO (separate Gesamtabnahme)** |
| Production | **BLOCKED** |
