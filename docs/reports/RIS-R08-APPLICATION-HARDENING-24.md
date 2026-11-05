# RIS-R08-APPLICATION-HARDENING-24

## Status

**24A PASS (lokal) — 24B PASS (lokal) — 24C COMPLETE — 24D PLAN READY, NOT APPLIED**

Kein AWS-Apply, kein Lambda-Deployment, keine Cognito-/CloudFront-/DNS-/ACM-/
PITR-Änderung und keine `ris-dev`-Änderung in diesem Auftrag.

## 24A — Salary Decimal Input

Umsetzung in `jobsearch/application_contract.py` und
`jobsearch/application_repository.py`:

* `salary.amount` wird an der Contract-Grenze zu `Decimal` normalisiert;
* Floats werden über `Decimal(str(value))` konvertiert, nie über den binären
  Float-Wert;
* Bool, Strings, NaN, Infinity, negative/Null-Werte und mehr als 38
  signifikante Stellen werden abgelehnt;
* `_json()` ist Decimal-fähig (auch für Cursor-Daten);
* Serialisierungs-`TypeError` wird in Create/Patch nicht mehr als
  `ApplicationConflict`/409 maskiert, sondern als 422 geführt;
* echte Versionskonflikte bleiben 409.

Tests:

```text
122 passed
```

Abgedeckt: `50000`, `50000.5`, `0.1`, Create/Patch-Persistenz, negative und
ungültige Werte, NaN/Infinity, Überpräzision, 422-vs-409-Mapping, stale
Patch → 409.

## 24B — Registry Lifecycle

`agents/ecosystem/partner_registry.py`:

* `deactivate_partner_application()` erhält
  `release_reservation=False` und `dependency_check`;
* der historische Partnerrecord wird **nie** gelöscht;
* ohne `release_reservation` bleibt die Reservation wie bisher erhalten;
* mit `release_reservation=True` ist ein `dependency_check` Pflicht;
* der Check erhält die `apiProfileId` und blockiert bei aktiven Profilen,
  Credentials oder Entitlements;
* die Reservation wird nur bedingt gelöscht, wenn sie exakt diesem
  `applicationId` gehört, der Client passt und der Status `RESERVED` ist;
* bereits fehlende Reservationen sind idempotent erfolgreich;
* fremde Reservationen und Tenant-Mismatches werden vor jedem Write abgelehnt;
* parallele Releases sind getestet.

CLI:

```text
ris-admin partner deactivate <applicationId> --release-reservation
```

Der CLI-Dependency-Check prüft:

1. APIProfile-Status (nicht `ACTIVE`);
2. keine ACTIVE-Credentials für das Profil;
3. keine ACTIVE-Entitlements für das Profil.

Tests: Registry-Atomicity, idempotenter Release, Blockade bei Abhängigkeiten,
fremde Reservation, Tenant-Mismatch, parallele Releases und CLI-Flag: grün.

Aktueller Live-Restzustand (nicht verändert): `partner-r08-23` ist `INACTIVE`,
die Reservation `CLIENT#21j28p71vogg0m41tcue0ib3l4` zeigt auf ihn. Nach einem
freigegebenen Deploy kann sie mit dem neuen CLI-Flag kontrolliert freigegeben
werden. In diesem Auftrag wurde keine Registry-Mutation ausgeführt.

## 24C — Jobsearch Handoff

Erstellt:

`docs/reports/RIS-R08-JOBSEARCH-APPLICATIONV1-E2E-HANDOFF-24.md`

Enthält getestete Endpunkte, Auth-Header, HTTP-Matrix, Versions-/Fehlersemantik,
synthetische Beispiele, Salary-Stand, BFF-Anforderungen und die nicht live
verifizierten Funktionen.

## 24D — Deploy-Readiness

Agent-Bundle neu gebaut:

```text
81 Dateien
LOCAL_ZIP_BASE64 = Q0o8VSGDONl44u4q33FRpG/u+4SMJhG6iNtU157hKno=
```

Plan gegen den aktuellen DEV2-Stand:

```text
Plan-Datei:   C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-24.tfplan
Plan SHA-256: 8B16A3F50321952A9BE674DD89DAA9755ADF8363388053D1C5A235905A7FE8C2
State:        Serial 28, Lineage a0bd361d-5cd1-a207-a8c0-e6888f0be082
```

Maschinell geprüfte Aktionen:

```text
CREATE  = 0
UPDATE  = 1
DELETE  = 0
REPLACE = 0
CHANGED = module.lambda.aws_lambda_function.agent
```

Der Plan enthält ausschließlich den Agent-Lambda-Code-Hash:

```text
bXGTw31W4T1A6TKiUDVr00bYnRKuOUiTlQFES+OC/44=
-> Q0o8VSGDONl44u4q33FRpG/u+4SMJhG6iNtU157hKno=
```

Keine Cognito-, CloudFront-, DNS-, ACM-, PITR-, IAM-, SQS- oder
Orders-Änderung. **Kein Apply ausgeführt.**

## Gate-Tabelle

| Gate | Ergebnis |
|---|---|
| Salary Decimal Input | **PASS (lokal, nicht deployt)** |
| HTTP Error Mapping | **PASS (lokal)** |
| Registry Lifecycle | **PASS (lokal)** |
| Isolation Regression | **PASS** |
| Jobsearch Handoff | **COMPLETE** |
| DEV2 Deploy | **NOT AUTHORIZED** |
| Production | **BLOCKED** |

## Nächster Schritt

Separate Freigabe für den gespeicherten Plan
`8B16A3F50321952A9BE674DD89DAA9755ADF8363388053D1C5A235905A7FE8C2`
einholen. Erst danach Apply, Post-Apply-No-Changes-Prüfung und ein erneuter
DEV2-E2E mit gebrochenem Salary.
