# RIS-APPLICATION-DEV2-APPLY-E2E-25

## Status

**APPLY PASS — SALARY MIT BRUCHWERT LIVE VERIFIED (deployed Lambda) —
ECHTER-CLIENT-GATEWAY-PFAD BLOCKED durch historische Resolver-Kollision —
CLEANUP PASS**

Keine `ris-dev`-Änderung, keine Cognito-Konfigurationsänderung, keine
CloudFront-/DNS-/ACM-/SQS-/PITR-Änderung, kein Push/Merge.

## 1. Pre-Apply und Apply

Vor Apply erneut verifiziert:

```text
Plan SHA-256: 8B16A3F50321952A9BE674DD89DAA9755ADF8363388053D1C5A235905A7FE8C2
State:        Serial 28
Lineage:      a0bd361d-5cd1-a207-a8c0-e6888f0be082
Diff:         CREATE=0, UPDATE=1, DELETE=0, REPLACE=0
Änderung:     module.lambda.aws_lambda_function.agent
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
| `CodeSha256` | `Q0o8VSGDONl44u4q33FRpG/u+4SMJhG6iNtU157hKno=` |
| Lokaler Bundle-Hash | identisch |
| State nach Apply | Serial 29, Lineage unverändert |
| No-Changes-Plan | Exit 0 |
| Lambda-Health | 200 |

## 2. Salary mit Bruchwert — deployed Lambda

Setup über den regulären CLI-Lifecycle:

| Ressource | Kennung |
|---|---|
| APIProfile | `aprof_5230d22190c24c53` |
| Partner | `partner-r08-25-synth` |
| Synthetischer Client | `synthetic-r08-25-e2e-client` |
| Credential | `cred_c7e7d5698b224622` |

Der Test lief am deployten `ris-dev2-dev-agent` mit den Claims, die der
Gateway-Authorizer nach erfolgreicher JWT-Prüfung liefert. Es wurde **kein**
Cognito-Benutzer angelegt.

### Create mit `50000.5`

| Prüfung | Ergebnis |
|---|---:|
| HTTP Create | **201** |
| Response `salary.amount` | `50000.5` |
| DynamoDB Rohwert | `Decimal("50000.5")` |
| Exakter Decimal-Vergleich | **True** |
| Binäres Float-Artefakt | **nein** |

### Patch mit `60000.75`

| Prüfung | Ergebnis |
|---|---:|
| HTTP Patch | **200** |
| Version | **1 → 2** |
| Response `salary.amount` | `60000.75` |
| DynamoDB Rohwert | `Decimal("60000.75")` |
| Exakter Decimal-Vergleich | **True** |
| Detail nach Patch | 200, Version 2 |

### Weitere Operationen

| Test | Ergebnis |
|---|---:|
| List | 200 |
| Detail | 200 |
| Export | 200 |
| Metrics nach Create | 200, `total=1` |
| Delete | 204 |
| List nach Delete | 200, 0 Items |
| Metrics nach Delete | 200, `total=0` |
| Ungültiges Credential | 401 |
| Fremder Tenant | 403 |
| Unbekannter Client | 403 |

Der Salary-Input-Fix ist damit **live auf dem deployten Lambda** verifiziert.

## 3. Registry-Lifecycle live

### Release des historischen Records

```text
partner deactivate partner-r08-23 --release-reservation
-> status INACTIVE, reservationReleased true
-> Reservation CLIENT#21j28... ABSENT
```

### Echter Cognito-Client

Ein neuer Partner `partner-r08-25` mit dem echten Client
`21j28p71vogg0m41tcue0ib3l4` wurde angelegt. Der Resolver lieferte jedoch
weiterhin den historischen `partner-r08-23` (`INACTIVE`) und damit 403.
Ursache: Beide Records teilen `cognitoClientId` und `tenantId` im GSI
`gsi-client`; die GSI-Reihenfolge ist nicht deterministisch, und der Resolver
bevorzugt keinen ACTIVE-/Reservation-Owner-Record.

Deshalb wurde **kein echter Gateway-/JWT-Positivtest mit Bruchwert**
durchgeführt. Der reale Partner und das Profil wurden anschließend widerrufen
bzw. deaktiviert und die Reservation erneut freigegeben.

### Synthetischer Client: Release und Reuse

```text
partner-r08-25-synth (ACTIVE)
-> deactivate --release-reservation
-> Reservation ABSENT
-> partner-r08-25-reuse mit demselben synthetischen Client angelegt
-> CREATE erfolgreich
-> Resolver liefert partner-r08-25-reuse ACTIVE
-> deactivate --release-reservation
-> Reservation ABSENT
```

Damit ist die Release-/Reuse-Semantik für einen synthetischen Client live
bestätigt. Die echte-Client-Auflösung bleibt wegen der historischen
GSI-Doppelung offen.

## 4. Gateway-Negativprüfungen

| Request | Ergebnis |
|---|---:|
| `GET /health` ohne JWT | 401 |
| Metrics ohne Header | 401 |
| Metrics mit malformed Credential | 401 |
| Metrics mit ungültigem Bearer | 401 |

## 5. Cleanup und Residualzustand

| Prüfung | Ergebnis |
|---|---|
| Partner-Records | 4, alle `INACTIVE` |
| Reservations | **0** |
| Applications | **0** |
| Cognito-Benutzer | **0** |
| Credentials | 4, alle `REVOKED` |
| APIProfiles | 6, alle `REVOKED` |
| Secret-Dateien | **0** (gelöscht) |
| Aktive Testberechtigung | keine |
| `ris-dev` | unberührt |

Die historischen Partner-Records bleiben als Audit-Spur erhalten. Es wurden
keine manuellen DynamoDB-Löschungen in diesem Schritt durchgeführt.

## 6. Offener Blocker

Der reale Gateway-/JWT-Positivtest mit `salary.amount = 50000.5` ist blockiert,
weil `resolve_partner_application()` bei mehreren historischen Records mit
demselben `cognitoClientId`/`tenantId` den falschen (INACTIVE) Record wählen
kann.

Erforderlich ist ein separater Resolver-Fix, der:

1. die Reservation als Autorität für den aktuell gebundenen
   `applicationId` nutzt oder
2. nur den eindeutigen ACTIVE-Record zurückgibt und bei Mehrdeutigkeit
   fail-closed bleibt.

Dieser Fix benötigt Code, Tests, einen neuen Terraform-Plan und eine separate
Deploy-Freigabe. Er ist **nicht** Teil dieses Auftrags.

## 7. Gate-Tabelle

| Gate | Ergebnis |
|---|---|
| Lambda-Apply | **PASS** |
| Salary `50000.5` Create | **PASS (deployed Lambda)** |
| Salary `60000.75` Patch | **PASS (deployed Lambda)** |
| ApplicationV1 CRUD/Export/Metrics | **PASS (deployed Lambda)** |
| HTTP-Fehlersemantik | **PASS** |
| Registry-Release | **PASS (live)** |
| Client-Reuse (synthetisch) | **PASS (live)** |
| Echter-Client-Gateway-Positivtest | **BLOCKED (Resolver-Kollision)** |
| Revocation/Cleanup | **PASS** |
| Jobsearch-Handoff | **UPDATED** |
| DEV2 Deploy | **PASS** |
| Production | **BLOCKED** |
| Gate B | **NO-GO** |
